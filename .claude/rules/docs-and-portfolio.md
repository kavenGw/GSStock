# 文档目录与 portfolio skill

> **何时读**：写 docs/analysis 或 docs/financial-analysis 新文档、修改文档 frontmatter、调用 /portfolio-init 或 /portfolio-rebalance、调整 RebalanceConfig / StockWeight / PositionPlan
> **不必读**：纯代码改动 / 通知 / 数据获取

## 文档目录约定

- `docs/plans/` — 设计与实施计划，格式 `YYYY-MM-DD-<topic>-design.md`
- `docs/analysis/` — 个股 buffett 风格深度分析，格式 `YYYY-MM-DD-<股票名>-buffett分析.md`
- `docs/analysis/<NNqN>/` — 季报点评归档，格式 `YYYY-MM-DD-<股票名>-NNQN季报点评.md`（如 `docs/analysis/26q1/`）
- `docs/analysis/<NNqN>/` 同时收纳同期专题分析（产能/事件驱动/技术路线深度），命名 `YYYY-MM-DD-<股票名>-<主题>专题.md`，与季报点评互加 `> 配套专题` / `> 关联文档` 反向链接
- **`docs/analysis/` 同时是 portfolio skill 的隐式选股池索引** — 用 Glob `docs/analysis/**/*.md` + 解析 `YYYY-MM-DD-<股票名>-<类型>.md` 文件名提取候选标的，无需独立索引表
- `docs/financial-analysis/` — 多股横向对比 / comps / 估值，格式 `YYYY-MM-DD-<主题>-<细分>.md`
- `docs/financial-analysis/<NNqN>/` — 该季度 comps / 横向对比归档，命名同上
- **跨目录引用惯例**：季报点评 / buffett 分析头部常见 `> 配套 comps：[..](../financial-analysis/...)` 相对链接互引；调整目录结构前先 `Grep "\.\./financial-analysis"` 和 `Grep "\.\./analysis"` 找出所有引用并同步修复，否则静默断链
- **新建分析前先翻历史档案**：写新 buffett / 季报 / comps 文档前先 `Glob "docs/**/*<股票名>*"` 和 `Glob "docs/**/*<代码>*"`（含 ticker 与中文名两路），把已有专题 / 季报点评 / 联动分析全部纳入正文头部 `>` 反向引用 + §0 执行摘要复用其监控指标，避免重复测算或忽略已兑现/已失效的预设触发条件
- **`docs/analysis/**/*.md` frontmatter 约定**（portfolio-init/rebalance v2 数据源）：YAML 头必填 `stock_code`（**字符串引号必填**，否则 YAML 解析为 int 丢前导 0：`'000021'` → `21` 全链路失败）/ `stock_name` / `themes`（数组，themes[0] 为计仓主题）/ `rating`（core/config/watch/exclude）/ `conviction_date`（YYYY-MM-DD）/ `thesis`（1-2 句）；rating=watch 加 `watch_reason`，rating=exclude 加 `exclude_reason`。枚举见 `.claude/skills/portfolio-init/config.yaml` 的 `metadata_schema`。同股多 doc 时 skill 按 conviction_date desc 取首条作为权威评级，其余进 `related_docs`

## 持仓再平衡报告输出

- 入口：`/portfolio-init`（首次配置 / 主题大调）+ `/portfolio-rebalance`（日常算 diff，支持 `--dry-run`）
- HTML 报告输出目录走本地配置 `.claude/skills/portfolio-init/local-config.yaml` 的 `portfolio.output_dir`（**已 gitignore**；模板：同目录 `local-config.yaml.example`）。skill 启动时缺该文件会立即报错并打印创建步骤
- 报告文件名：`{output_dir}/portfolio-init-{YYYY-MM-DD}.html`（按日覆盖）/ `{output_dir}/portfolio-rebalance-{YYYY-MM-DD-HHMM}.html`（按时分留历史）。强烈建议 output_dir 设在 git 工程外
- 共享 HTML 模板（git 跟踪）：`.claude/skills/portfolio-init/report-template.html`，rebalance skill 复用
- 写库表：`RebalanceConfig.target_value` / `StockWeight` / `PositionPlan`（PositionPlan 无 unique，写前先 `DELETE FROM position_plans`）
- `StockWeight.weight` 存原始 float（schema 写 NUMERIC(5,2) 但 SQLite 不强制），不要 `round(_, 4-6)`，否则 `target_mv = TARGET × weight` 经 floor 计算会少买一手。rebalance 的 shares 计算同时加 `floor(diff/price/100 + 1e-6)*100` / `ceil(.../100 - 1e-6)*100` 吸收 FP roundtrip 噪声
