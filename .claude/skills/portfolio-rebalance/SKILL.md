---
name: portfolio-rebalance
description: 日常再平衡分析。读最新持仓 + 已固化的目标权重，算 target/current 差额，输出 BUY/SELL/HOLD 操作建议（100 股倍数）+ 主题偏离 + 关键事件。支持 --dry-run 不写库。
---

# Portfolio Rebalance — 日常再平衡

## 何时使用

- 每日盘后想知道是否要调仓
- 看到大事件想立刻知道影响
- 持仓刚更新（OCR 上传后）

**首次配置 / 主题大调用 `/portfolio-init`，本 skill 假设 StockWeight 已就绪。**

## 参数

- 默认：写库 + 输出 markdown
- `--dry-run`：只输出 markdown，不写 PositionPlan

## 工作流

### 第 0 步：检查前置条件 + 读取配置

1. 检查 StockWeight：
   ```sql
   SELECT COUNT(*) FROM stock_weights WHERE selected = 1;
   ```
   如果 = 0 → 报错并提示 "StockWeight 为空，请先运行 `/portfolio-init`"。

2. 读共享配置 `.claude/skills/portfolio-init/config.yaml` 取 `rules`

3. 读本地配置 `.claude/skills/portfolio-init/local-config.yaml`：
   - **如果文件不存在** → 立即报错并停止执行，输出：
     ```
     ⚠️ 本地配置缺失。请先复制模板：
        cp .claude/skills/portfolio-init/local-config.yaml.example .claude/skills/portfolio-init/local-config.yaml
     再编辑 local-config.yaml 填写 portfolio.output_dir（HTML 报告输出绝对路径，建议在 git 工程外）
     然后重跑 /portfolio-rebalance
     ```
   - **如果 `portfolio.output_dir` 为空** → 报错提示填写后重试
   - 不存在则 `mkdir -p`，后续第 8 步使用

### 第 1 步：读基础数据

```sql
-- 目标总市值
SELECT target_value FROM rebalance_config LIMIT 1;

-- 已固化的目标权重
SELECT stock_code, weight FROM stock_weights WHERE selected = 1;

-- 最新持仓快照
SELECT stock_code, stock_name, quantity, total_amount, current_price
FROM positions
WHERE date = (SELECT MAX(date) FROM positions);
```

### 第 2 步：取实时价

```python
# ⚠️ 环境变量必须在 import app 之前设置，否则调度器仍会启动 17 个任务 + OCR + LLM
import os
os.environ['SCHEDULER_ENABLED'] = '0'
from app import create_app
app = create_app()
with app.app_context():
    from app.services.unified_stock_data import UnifiedStockDataService
    svc = UnifiedStockDataService()
    # 重点池所有股票 + 当前持仓中不在重点池的股票（用于"建议清仓"提示）
    all_codes = list(set(weight_codes + position_codes))
    prices = svc.get_realtime_prices(all_codes)
```

实时价失败的股票：用 cache 价（`UnifiedStockCache` 表的 cache_type='price' 最新一行）+ 标 ⚠️。

### 第 3 步：算 diff

对每只重点池股票：
1. `current_value` = quantity × 实时价（不在持仓表中则为 0）
2. `target_value_stock` = `target_value × weight`
3. `diff` = `target_value_stock - current_value`
4. 操作判定：
   - `abs(diff) < rebalance_threshold_value`（默认 ¥2,000）→ `operation = 'hold'`，shares=0
   - `diff > rebalance_threshold_value` → `operation = 'buy'`，`shares = floor(diff / 现价 / 100) × 100`
   - `diff < -rebalance_threshold_value` → `operation = 'sell'`，`shares = ceil(abs(diff) / 现价 / 100) × 100`，但不能超过当前持有数

对持仓表中存在但**不在重点池**的股票：
- 标记为"建议清仓"（如美国50 ETF 残值）
- 不计入主题统计，但在输出 markdown 中单独列出

### 第 4 步：算主题偏离

按主题分组重点池（参考 `portfolio-init` SKILL.md §第 4 步 嵌入的主题归属表 + config.yaml.themes）：
- 主题目标 = `target_value × theme.weight`
- 主题当前 = sum(主题内每只股的 current_value)
- 主题缺口 = 主题目标 - 主题当前
- 偏离比 = 主题缺口 / target_value
- abs(偏离比) > `theme_drift_threshold`（默认 5%）→ 标红 ⚠️

### 第 5 步：扫近期事件

1. **docs/analysis/ 近 7 天文档**

用 Glob 工具扫 `docs/analysis/**/*.md`，按文件名前缀（`YYYY-MM-DD-`）解析日期，筛出今日往前 7 天内的文档。例如今日是 2026-05-09，则保留文件名以 `2026-05-02` ~ `2026-05-09` 开头的。

读取每个文档头部 200 字，提取关键词：
- "业绩说明会"、"新增产能"、"涨价"、"投产"、"中标"、"财报联动"
- 形成「未来 1-2 周关注事件」清单（5-10 条）

2. **news_item 近 3 天，命中目标池**

```sql
SELECT n.title, n.link, n.published_at
FROM news_item n
JOIN identified_company ic ON ic.news_id = n.id
WHERE ic.stock_code IN (重点池 codes)
  AND n.published_at >= datetime('now', '-3 days')
ORDER BY n.published_at DESC
LIMIT 20;
```

筛 5-10 条最相关的，附在事件清单。

### 第 6 步：写库（除非 --dry-run）

```sql
-- PositionPlan 无 unique 约束，先清空再 INSERT
DELETE FROM position_plans;

INSERT INTO position_plans (stock_code, stock_name, target_value, current_value,
                             diff, operation, shares, weight, updated_at)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'));
```

每只重点池股票一行（含 hold）。**不改 StockWeight。**

### 第 7 步：输出 markdown

```markdown
## 持仓再平衡建议（YYYY-MM-DD HH:MM）

### 总览
总资产 ¥X | 持仓市值 ¥X (X.X%) | 可用现金 ¥X (X.X%)
偏离阈值：单股 ±¥2,000，主题 ±5%

### 主题偏离
| 主题 | 目标权重 | 目标市值 | 当前市值 | 缺口 | 偏离 |
|------|---------|---------|---------|------|------|
| AI 算力 | 30% | ¥X | ¥X | ±¥X | ⚠️ -8.2% |
| CPU+封测+PCB | 30% | ... | ... | ... | ... |
| 存储涨价 | 15% | ... | ... | ... | ... |
| 世界杯 | 15% | ... | ... | ... | ... |
| 黄金防御 | 10% | ... | ... | ... | ... |

### 个股操作清单

#### 🟢 BUY（共 N 笔，合计 ¥X）
| 代码 | 名称 | 主题 | 现价 | 目标股数 | 当前股数 | **建议买** | 占用资金 |
|------|------|------|------|---------|---------|----------|---------|
| 601138 | 工业富联 | AI 算力 | 30.50 | 1700 | 0 | **+1700** | ¥51,850 |
| ...

理由：
- 601138 工业富联：AI 服务器代工龙头，buffett 估值合理 + 26Q1 营收+45%

#### 🔴 SELL（共 N 笔，合计 ¥X）
| 代码 | 名称 | 主题 | 现价 | 目标股数 | 当前股数 | **建议卖** | 释放资金 |
|------|------|------|------|---------|---------|----------|---------|
| ...

#### ⚪ HOLD（共 N 只）
紫金矿业 1000 股 ¥34,800（防御 8.0% / 目标 10%，缺口 ¥3,560 < 阈值）
...

#### ⚠️ 重点池外建议清仓
- 美国50 ETF（513850）：当前 1700 股 ¥2,890，已亏 -88%，建议清仓释放资金

### 未来 1-2 周关注事件
- 2026-05-15 通富微电业绩说明会（来自 docs/analysis/26q1/2026-05-09-长电科技-26Q1业绩说明会专题.md）
- 2026-05-12 AMD 财报盘后（关联通富微电 / 海光信息）
- ... 

### Web UI
访问 http://127.0.0.1:5000/position-plan 查看完整方案
```

### 第 8 步：生成 HTML 报告（私密信息，写到 git 工程外）

把第 7 步的 markdown 内容渲染为 HTML，写到 `{output_dir}/portfolio-rebalance-{YYYY-MM-DD-HHMM}.html`（按时分，可看历史）。`output_dir` 来自第 0 步读到的 `local-config.yaml`。

**步骤**：

1. Read 模板 `.claude/skills/portfolio-init/report-template.html`（共享模板，由 init skill 维护）
2. 把 markdown 转 HTML（保留表格 / 列表 / 标题层级）
3. 替换占位符：
   - `{TITLE}` → `持仓再平衡建议 - YYYY-MM-DD HH:MM`
   - `{CONTENT}` → 渲染好的 HTML body
   - `{TIMESTAMP}` → `YYYY-MM-DD HH:MM`
   - `{KIND}` → `rebalance`
4. Write 到 `{output_dir}/portfolio-rebalance-{YYYY-MM-DD-HHMM}.html`（**绝不要写到 git 工程内**！）
5. 输出末尾追加："📄 HTML 报告：file:///{output_dir 转 URL 形式}/portfolio-rebalance-YYYY-MM-DD-HHMM.html"

**HTML 渲染要点**：
- 主题偏离表：`abs(偏离比) > 5%` 行用 `<tr class="theme-row-warn">` 或在偏离列用 `<span class="warn">`
- BUY 个股清单：表格内"建议买"列用 `<span class="buy">+1700</span>`
- SELL 个股清单：表格内"建议卖"列用 `<span class="sell">-N</span>`
- HOLD 列表用 `<ul>` + `<span class="hold">` 灰色
- 重点池外清仓提示用 `<div class="warn-box">`
- 数字加千分位（如 ¥51,850），百分比含正负号
- 输出文件路径不要在 git 工程内（D:\Git\stock\），必须写 `D:\Git\GSStockHold\`

## 异常处理

| 场景 | 处理 |
|------|------|
| `stock_weights` 全空 | 报错提示先 `/portfolio-init` |
| Position 表为空 | 视作纯现金，输出全建仓计划 |
| 实时价个别失败 | 用 UnifiedStockCache 最近行 + ⚠️ 标记 |
| 持仓表中股票不在重点池 | 单独列"重点池外建议清仓"，不计主题 |
| sell shares 超过 current quantity | shares = current quantity（清仓），diff 标"超配 + 清仓"|
| docs/analysis 近 7 天无新增 | 事件清单可空，输出"近 7 天无新分析" |
