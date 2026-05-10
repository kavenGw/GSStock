---
name: portfolio-init
description: 首次配置或主题权重大调时调用。从 docs/analysis/ 已分析的股票池中筛选 15-25 只重点池，按主题权重分配目标仓位（100 股倍数），写入 RebalanceConfig 和 StockWeight 表。
---

# Portfolio Init — 首次持仓配置

## 何时使用

- 第一次跑配置（StockWeight 表为空 / 全部 selected=False）
- 主题权重大调（修改了 config.yaml）
- 季报集中发布后需要重新筛重点池

**日常再平衡不要用本 skill，用 `/portfolio-rebalance`。**

## 工作流

### 第 0 步：读取配置（共享 + 本地）

1. 读共享配置 `.claude/skills/portfolio-init/config.yaml`，提取 themes / rules

2. 读本地配置 `.claude/skills/portfolio-init/local-config.yaml`：
   - **如果文件不存在** → 立即报错并停止执行，输出：
     ```
     ⚠️ 本地配置缺失。请按以下步骤创建：

     1. 复制模板：
        cp .claude/skills/portfolio-init/local-config.yaml.example .claude/skills/portfolio-init/local-config.yaml

     2. 编辑 local-config.yaml，把 portfolio.output_dir 填写为 HTML 报告输出目录的绝对路径
        （强烈建议在 git 工程外，如 D:\Git\GSStockHold 或 ~/portfolio）

     3. 重新运行 /portfolio-init
     ```
   - **如果文件存在但 `portfolio.output_dir` 为空** → 报错并提示填写后重试

3. 校验 / 准备 `output_dir`：
   - 不存在则自动 `mkdir -p`（Windows 可用 Python `pathlib.Path(p).mkdir(parents=True, exist_ok=True)`）
   - 后续第 9 步生成 HTML 时使用此路径

### 第 1 步：确认总资产

1. 查 `data/private.db` 的 `rebalance_config` 表
2. 如果 `target_value` > 0，问用户："当前 RebalanceConfig.target_value=¥X，是否更新？"
3. 如果为 0 或用户确认更新，问用户："请确认目标总资产（账户实际总资产）"
4. 写入：`UPDATE rebalance_config SET target_value=?, updated_at=NOW()` 或 INSERT 一行

### 第 2 步：读最新持仓快照（多账户合并）

```sql
SELECT date, stock_code, stock_name, quantity, total_amount, current_price
FROM positions
WHERE date = (SELECT MAX(date) FROM positions)
ORDER BY total_amount DESC;
```

输出汇总：总市值 / 持仓股数 / 现金估算（target_value - 持仓市值）。

### 第 3 步：建立候选池

用 Glob 工具 `docs/analysis/**/*.md` 取所有文件名，按正则提取股票名：
- `*-buffett分析.md` → 提取主体名
- `*-NNQN季报点评.md` → 提取主体名
- `*-<主题>专题.md` → 提取主体名

去重得到候选池（约 50 只）。

对每只候选股票，按下面顺序找 stock_code：

1. **查 `data/stock.db` 的 `stock` 表**：
```sql
SELECT stock_code, stock_name FROM stock WHERE stock_name = ?;
```
找到 → 直接用。

2. 表里没有 → **查 `docs/analysis/` 对应文档**：
   - 用 Glob 找 `docs/analysis/**/*<股票名>*.md` 或 `docs/analysis/**/*<别名>*.md`
   - Read 文档前 30 行，找形如 `(601138)` / `代码：601138` / `## 601138 工业富联` 的标注

3. 文档里没有 → **查 `app/config/supply_chain.py`**：
   - Grep 搜股票名，找形如 `'601138': {'name': '工业富联', ...}` 的条目
   - dict key 即 stock_code

4. 三处都找不到 → **标记为"代码缺失"**，列在最终输出的"排除池"里说明（不入 StockWeight）

找到 stock_code 后，如果 `stock` 表里没有，幂等 INSERT（不走 app/seeds/，那是 create_app 启动钩子；这里直接 SQL 即可）：

```sql
INSERT OR IGNORE INTO stock (stock_code, stock_name, created_at, updated_at)
VALUES (?, ?, datetime('now'), datetime('now'));
```

### 第 4 步：按主题分组

把候选池每只股归入 5 大主题之一，参考下表（同名标的只归一类，不重复计入）：

| 主题 | 包含的标的 |
|------|------|
| AI 算力 | 工业富联、光迅科技、光库科技、源杰科技、阳光电源 |
| CPU+封测+PCB | 通富微电、长电科技、华天科技、盛合晶微、胜宏科技、沪电股份、生益科技、南亚新材、金安国纪、宏和科技、彤程新材 |
| 存储涨价 | 北京君正、江波龙、兆易创新、聚辰股份、普冉股份、深科技、太极实业、雅克科技、南大光电、复旦微电、希荻微、国芯科技 |
| 世界杯 | 安踏、舒华、金陵体育、中体产业、粤传媒、共创草坪、青岛啤酒、燕京啤酒、重庆啤酒、鸿博股份 |
| 黄金防御 | 紫金矿业、洛阳钼业、中金黄金 |

**主题外标的**（→ **排除**，不入 StockWeight）：万华化学、巨化股份、昊华化学、药明康德、东吴证券、赛腾股份、西部材料、石英股份、立讯精密 等。

**跨链复用规则**：生益科技在产业链图谱里同时被 AI 链和 CPU 链引用，本表固定归 CPU+封测+PCB；遇到表外的歧义标的，按"主营业务所属链"归一类，不在多主题双计。

### 第 5 步：评级（4 档）

读取每只股票最新的 buffett 分析文档 + 最新季报点评（如果有），按以下标准评：

| 评级 | 标准 |
|------|------|
| **核心** | buffett 分析结论为"买入"/"强烈推荐" + 季报兑现/超预期 + 当前估值在合理或低估区间 |
| **配置** | 主题贴合 + 质地良 + 估值合理；或 buffett 评级良 但季报中性 |
| **观察** | 主题贴合但估值偏高 / 季报低于预期 / buffett 结论为观望 |
| **排除** | 质地差 / 估值已透支 / 主题外 / buffett 结论为回避 |

读文档时关注：
- buffett 文档末尾的"投资建议"或"操作建议"
- 季报点评末尾的"评级"或"调整后预期"
- 专题文档（涨价 / 业绩说明会）的核心结论

### 第 6 步：算目标仓位（B-动态规则）

对每个主题：
1. 主题市值 = `target_value × theme.weight`
2. 主题内核心股占 60-80%，配置股填剩余
3. **单股市值上限 = 主题市值 × `single_stock_max_pct_of_theme`**（即主题权重的 50%）
4. 取实时价：调用 `UnifiedStockDataService.get_realtime_prices(codes)`
5. 目标股数 = floor(单股目标市值 / 现价 / 100) × 100
6. 如果目标股数 = 0，标"目标过小，建议提高总市值或调整权重"

实时价获取代码示例：

```python
# ⚠️ 环境变量必须在 import app 之前设置，否则调度器仍会启动 17 个任务 + OCR + LLM
import os
os.environ['SCHEDULER_ENABLED'] = '0'
from app import create_app
app = create_app()
with app.app_context():
    from app.services.unified_stock_data import UnifiedStockDataService
    svc = UnifiedStockDataService()
    prices = svc.get_realtime_prices(['603986', '600183', '601899', '600600'])
    for code, info in prices.items():
        print(code, info.get('name'), info.get('price'))
```

### 第 7 步：写库

1. 清空旧权重（仅核心+配置+观察的 selected 标志，保留排除股不入库）：

```sql
DELETE FROM stock_weights;
```

2. 批量 INSERT 重点池（核心 + 配置）+ 观察池：

```sql
-- SQLite 用 1/0 表示 boolean；用 SQLAlchemy ORM 时直接传 True/False 即可
INSERT INTO stock_weights (stock_code, weight, selected, updated_at)
VALUES (?, ?, ?, datetime('now'));
```

- 核心 / 配置：`selected=True`，`weight` = 该股目标市值 / target_value
- 观察：`selected=False`，`weight` = 0

3. 排除池不入库

### 第 8 步：输出 markdown

按以下结构输出（直接打印到对话，不写文件）：

```markdown
## 持仓首次配置（YYYY-MM-DD）

### 总资产
目标总市值 ¥X | 当前持仓 ¥X | 可用现金 ¥X

### 重点池（共 N 只）

#### AI 算力（目标 30% / ¥X）
| 代码 | 名称 | 评级 | 目标权重 | 目标市值 | 目标股数 | 现价 |
|------|------|------|---------|---------|---------|------|
| 601138 | 工业富联 | 核心 | 12% | ¥52,000 | 1700 | 30.50 |
| ... | ... | ... | ... | ... | ... | ... |

[CPU+封测+PCB / 存储涨价 / 世界杯 / 黄金防御 同样格式]

### 选取理由（每只一行）
- 601138 工业富联（核心）：AI 服务器代工龙头，2026Q1 营收+45%，buffett 分析估值合理
- ... 

### 观察池（共 N 只，不实际配仓）
- ... （列举每只 + 一行原因）

### 排除池（共 N 只）
- 万华化学：主题外（化工）
- ... 

### 下一步
运行 `/portfolio-rebalance` 生成首次建仓操作清单。
```

### 第 9 步：生成 HTML 报告（私密信息，写到 git 工程外）

把第 8 步的 markdown 内容渲染为 HTML，写到 `{output_dir}/portfolio-init-{YYYY-MM-DD}.html`（按日覆盖）。`output_dir` 来自第 0 步读到的 `local-config.yaml` 的 `portfolio.output_dir`。

**步骤**：

1. Read 模板 `.claude/skills/portfolio-init/report-template.html`
2. 把 markdown 转 HTML（保留表格 / 列表 / 标题层级；评级用 `<span class="tag tag-core/config/watch/exclude">` 高亮）
3. 替换占位符：
   - `{TITLE}` → `持仓首次配置 - YYYY-MM-DD`
   - `{CONTENT}` → 渲染好的 HTML body
   - `{TIMESTAMP}` → `YYYY-MM-DD HH:MM`
   - `{KIND}` → `init`
4. Write 到 `{output_dir}/portfolio-init-{YYYY-MM-DD}.html`（**绝不要写到 git 工程内**！）
5. 输出末尾追加："📄 HTML 报告：file:///{output_dir 转 URL 形式}/portfolio-init-YYYY-MM-DD.html"

**HTML 渲染要点**：
- 主题归属表用 `<table>`，每只股的"评级"列用 `<span class="tag tag-core">核心</span>` 等彩色 tag
- 重点池/观察池/排除池分别用 `<h2>` 大节
- 选取理由用 `<ul>` 列表
- 输出文件路径不要在 git 工程内（D:\Git\stock\），必须写 `D:\Git\GSStockHold\`

## 异常处理

| 场景 | 处理 |
|------|------|
| `rebalance_config` 表不存在 | 报错提示先启动 app 让迁移跑 |
| `docs/analysis/` 全空 | 报错提示先做股票分析 |
| 实时价部分获取失败 | 用最近 cache 价并在表格价格列加 ⚠️ 注释 |
| 主题归属冲突的股票（罕见） | 默认按 spec §4.3 表，遇到不在表里的标的直接归"排除" |
| docs 提到但 Stock 表无 stock_code | 查 `app/config/supply_chain.py` 或文档头补全后 INSERT |
