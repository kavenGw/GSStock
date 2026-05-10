# Portfolio Shortlist — 持仓精选 ≤ 10 设计

> 日期：2026-05-10
> 触发：`portfolio-init-2026-05-10.html` 重点池 23 行入库过散，决定按"评级 + 文档证据 + 技术形态"全局排序压缩到 ≤ 10 只
> 涉及：新建一次性脚本 + skill 流程；不改 `config.yaml` themes 权重，不动观察池/排除池机制

## 0 背景

当前 `/portfolio-init` 输出 23 只重点池入库（4 只触顶 0 股 + 19 只可买），分 5 主题：
- AI 算力 3 只 / CPU+封测+PCB 7 只 / 存储涨价 4 只 / 世界杯 6 只 / 黄金防御 3 只

问题：
- 单只目标市值最低仅 ¥2.7k（占总仓 0.6%），操作摩擦大
- CPU+PCB 单主题 7 只、世界杯 6 只主题内分散
- 主题分配机械，没有结合每只股的 docs 投资逻辑、估值、催化、技术形态实际证据

目标：基于 `docs/analysis/` 文档证据 + 实时技术形态全局排序，取 Top 10 入重点池，其余降 watch。

## 1 评估维度（6 项）

| # | 维度 | 数据源 | 是否缓存 |
|---|---|---|---|
| ① | 投资逻辑强度 | docs 正文「核心逻辑/护城河」段 | MD5 缓存 |
| ② | 估值合理性 | docs「估值/PE 分位/目标价」段 | MD5 缓存 |
| ③ | 催化剂时点 | docs「催化/触发条件/事件锚」段 | MD5 缓存 |
| ④ | 主题关联紧密度 | frontmatter `themes` + 正文论述 | MD5 缓存 |
| ⑤ | 已兑现/已失效 | 跨 docs 反向引用（季报点评 vs 早期 buffett） | MD5 缓存 |
| ⑥ | 技术形态 | `UnifiedStockDataService.get_trend_data(days=30)` + MA5/MA20/支撑阻力/量比/TD 九转 | 不缓存（每日重算） |

## 2 MD5 缓存机制

**路径**：`.claude/skills/portfolio-init/.cache/shortlist/<stock_code>.json`（加入 `.gitignore`）

**结构**：
```json
{
  "stock_code": "601138",
  "stock_name": "工业富联",
  "docs": [
    {
      "path": "docs/analysis/2026-05-09-工业富联-甲骨文-走势相关性专题.md",
      "md5": "abc123...",
      "extracted_at": "2026-05-10T16:00:00"
    }
  ],
  "summary": {
    "logic": "AI 算力曲线传导，与 ORCL 走势相关性 465 配对交易日验证",
    "valuation": "PE 28x，相对 AI 算力同业偏中性",
    "catalyst": "26Q2 财报 + 北美 hyperscaler 资本开支兑现",
    "theme_fit": "ai_compute 主题核心，关联紧密",
    "realized_or_invalidated": "5/9 专题已识别相关性，预设触发条件未失效"
  },
  "rating": "core",
  "version": 1
}
```

**流程**：
1. `Glob "docs/analysis/**/*<股票名>*"` 和 `Glob "docs/analysis/**/*<代码>*"` 收齐该股全部 docs
2. 对每个 doc 算 `md5(file_content)`
3. 全部 doc 的 md5 与缓存一致 → 直接用 `summary` 跳过提取
4. 任一 md5 变化 / 新增 doc / 缓存不存在 → 重读全部 docs 重新提取 5 段摘要 → 写缓存

**缓存版本**：顶层 `version` 字段；schema 变更 bump version 触发全量重算。

## 3 打分公式（0-100 分）

| 维度 | 分值范围 | 计分逻辑 |
|---|---|---|
| 评级基分 | core=50 / config=25 / watch=0 | 直接按 frontmatter `rating` |
| 投资逻辑 | 0-15 | 主线龙头/独家逻辑 12-15；二线跟随 6-10；纯主题 0-5 |
| 估值合理 | 0-10 | PE 分位 < 50% 8-10；50-70% 4-7；> 70% 0-3 |
| 催化清晰 | 0-10 | 6 个月内有明确事件锚 8-10；3-6 月 4-7；模糊/无 0-3 |
| 技术形态 | 0-10 | 站 MA20 + 量正常 + 支撑稳 8-10；震荡 4-7；破位/量缩 0-3 |
| 已兑现/已失效 | -20 ~ +5 | 已失效 -20 ~ -10；未失效中性 0；新催化加成 +3 ~ +5 |

**硬约束**（不满足直接出局，降 watch）：
- 100 股市值 > 该股所属主题 `single_stock_max_pct_of_theme=0.50` × 主题预算
  - 例：AI 算力 30% × ¥433,765 × 50% = ¥65,065 上限；> ¥65,065/100 = ¥650.65/股 100 股触顶
- frontmatter `rating ∈ {watch, exclude}` → 不参与排序

**取 Top 10**，平票按：rating > 文档新鲜度（最新 conviction_date desc） > 名称字典序。

### 3.1 入选后主题内权重分配

打分仅用于决定 Top 10 入选名单；入选后每只股在所属主题内的 `StockWeight.weight` 按"打分归一化"分配：

- 设主题 T 入选 N 只，得分分别 `s_1 ... s_N`
- 单股 weight = `s_i / sum(s_1..s_N)`，再乘主题权重得最终目标市值占比
- 触发"单股上限 50%"截顶后，溢出部分按比例回流给同主题其他入选股
- 若回流后仍有溢出（如主题内只有 1 只入选且触顶）→ 多余预算转该主题 cash buffer，HTML 报告标注

## 4 主题权重处理

**不动 `config.yaml` themes 权重**（30/30/15/15/10 保留）。

入选 10 只在主题间分布按打分自然形成，可能不均。

**主题 0 入选告警**：
- HTML 报告顶部标红 `⚠️ 主题 X 当前 0 只入选`
- 给两个选项让用户决策：
  - (a) 把该主题权重按比例分摊到其他入选主题（生成新 `themes_override` 写入 `RebalanceConfig.metadata` JSON 字段，不改 config.yaml）
  - (b) 保留该主题权重为 0，对应预算转 cash buffer
- **不自动选**，等用户在 HTML 报告里勾选后再写库

## 5 技术形态计算细则

调用 `UnifiedStockDataService.get_trend_data(stock_codes=[code], days=30)` 拿 30 日 OHLC，本地算：

| 指标 | 计算 | 用途 |
|---|---|---|
| MA5 / MA20 | rolling close | 当前价 vs MA20 → 站上/破位 |
| 30d 高/低 | max(high) / min(low) | 当前距高/低 % → 强弱位置 |
| 支撑/阻力 | 最近 30d 至少 2 次反弹/回压点 | 与现价 % 距离 |
| 量比 | 最近 5d 均量 / 30d 均量 | > 1.2 放量 / < 0.8 缩量 |
| TD 九转 | `app/services/td_sequential_service.py` 已有实现 | 买/卖 setup 信号 |

输出每只股一个 `technical_summary` dict，注入打分维度 ⑥。

## 6 实现路径

### 6.1 新建脚本

`scripts/_portfolio_shortlist.py`（一次性脚本，跑完不入库 git，逻辑通过本 spec 留痕）：

1. 读 `data/private.db` 当前 RebalanceConfig + 持仓
2. Glob `docs/analysis/**/*.md` 解析 frontmatter，按 `rating ∈ {core, config}` 收候选池
3. 对每只候选：
   - 收齐相关 docs → md5 缓存层 → 拿 5 段 summary
   - 调 `UnifiedStockDataService.get_trend_data` 算 6 项技术形态指标
   - 按打分公式算总分
4. 应用硬约束（100 股触顶 → 出局）
5. 全局排序取 Top 10
6. 主题分布检查 → 0 入选主题标红
7. 渲染 HTML 报告 + markdown 评估报告
8. 输出 `RebalanceConfig` / `StockWeight` patch JSON（**不直接写库**）

### 6.2 输出物

| 文件 | 路径 | 用途 |
|---|---|---|
| spec | `docs/superpowers/specs/2026-05-10-portfolio-shortlist-design.md` | 留痕，commit |
| HTML 报告 | `D:\Git\GSStockHold\portfolio-shortlist-2026-05-10.html` | 用户审 |
| markdown 摘要 | `D:\Git\GSStockHold\portfolio-shortlist-2026-05-10.md` | 用户审（与 HTML 内容等价，便于复制） |
| patch JSON | `.omc/artifacts/portfolio-shortlist-patch-2026-05-10.json` | 用户确认后由 rebalance skill 落库 |
| 缓存 | `.claude/skills/portfolio-init/.cache/shortlist/*.json` | 跨次运行加速（gitignore） |

### 6.3 不改的部分

- `config.yaml` themes 权重不改
- frontmatter rating 不擅自改（仅在 patch JSON 里建议变更，由用户审完批准）
- 观察池 / 排除池逻辑不动
- `single_stock_max_pct_of_theme=0.50` 单股上限规则保留

## 7 风险与边界

- **docs 提取摘要的可靠性**：5 段摘要由我（Claude）人工读 docs 提取，不调 LLM 自动化。一致性靠 spec 的"评估维度"定义保证。
- **技术形态时效**：`get_trend_data` 在交易时段 30 分钟缓存，收盘后 8 小时；脚本跑前可 `force_refresh=True` 一次确保最新
- **缓存失效漏检**：md5 检查只看 file content，docs 间反向引用（如季报点评 → buffett）的级联变化由"任一 md5 变化即重算该股全部 docs"覆盖
- **主题 0 入选场景**：本次 5 主题里"黄金防御"权重最低（10%），评级 core 仅 1 只（紫金矿业），如打分不进前 10 则触发该场景；仍按"报告标红 + 等审" 处理，不强保

## 8 验收标准

- [ ] `.claude/skills/portfolio-init/.cache/shortlist/` 缓存文件按 stock_code 生成，第二次跑命中率 100%
- [ ] HTML 报告每只候选股显示 6 维度打分 + 总分 + 决定（保留/降 watch/触顶出局）
- [ ] 入选 ≤ 10 只
- [ ] 主题 0 入选时报告顶部标红 + 两个决策选项可勾选
- [ ] patch JSON 包含 `(stock_code, current_rating, suggested_rating, reason)` 列表，未自动写库
- [ ] 一次性脚本跑完后 `rm scripts/_portfolio_shortlist.py`，缓存保留
