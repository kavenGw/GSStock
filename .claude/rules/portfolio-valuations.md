---
paths:
  - "app/routes/valuations.py"
  - "docs/stock-analytics/**"
  - ".claude/skills/portfolio-init/**"
  - ".claude/skills/portfolio-rebalance/**"
---
# Portfolio / Valuations 与 A+H 口径

> **何时读**：跑 /portfolio-init 或 /portfolio-rebalance、改 RebalanceConfig/StockWeight/PositionPlan、改 /valuations 页或 valuations.yaml、裁定 A+H 口径

## 再平衡报告

- 入口 `/portfolio-init`（首次/主题大调）、`/portfolio-rebalance`（日常 diff，支持 `--dry-run`）。
- HTML 输出目录读 `.claude/skills/portfolio-init/local-config.yaml` 的 `portfolio.output_dir`（gitignore，模板 `.example`）；文件名 `portfolio-init-{YYYY-MM-DD}.html`（按日覆盖）/ `portfolio-rebalance-{YYYY-MM-DD-HHMM}.html`；模板 `.claude/skills/portfolio-init/report-template.html`。
- 写库 `RebalanceConfig.target_value` / `StockWeight` / `PositionPlan`（无 unique，写前 `DELETE FROM position_plans`）。`StockWeight.weight` 存原始 float 不 round；shares 用 `floor(diff/price/100 + 1e-6)*100` / `ceil(... - 1e-6)*100` 吸收 FP 噪声。
- **选股池**：Glob `docs/stock-analytics/sectors/**/*.md` + `cross-sector/**/*.md`，评级/主题从 frontmatter 读；同股多 doc 按 `conviction_date` desc 取首条；`quarterly/` 不进池、只作事件清单。

## /valuations 页（价值洼地）

路由 `app/routes/valuations.py`，数据源 `docs/stock-analytics/valuations.yaml`（独立聚合文件，不受 docs linter 约束）。分组 `group_by_sector`：
- DB 分类命中 `CARVE_OUT_CATEGORIES`（如 `{'啤酒'}`）→ 抬成独立顶级组。新增主题分组：加分类名 + 在分类管理把目标股设为该分类，模板零改动。
- `sector=='materials'` 且 `subsector ∈ PROMOTE_MATERIALS_SUBSECTORS`（nonferrous/lithium/copper-foil）→ 扁平顶级板块（`flat=True`），其余归 `materials-other`。按 subsector（source_doc 路径派生）驱动，零数据改动。
- 分类是用户数据非 seed（seed 不覆盖已有归属），改分类走 UI 或一次性 DB 写入。

## A+H 口径铁律

- **A+H 取估值更低一侧作跟踪主体**：H 股折价是安全边际放大器，不强行用 A 股口径。frontmatter `stock_code` 与 valuations 条目（`market`/`currency`/每股内在价值）按选定口径写；切口径时 valuations 按 `stock_code` 覆盖旧条目。H 口径市值自洽校验见 data-fetch-conventions.md，币种折算（RMB→HKD ×1.08）与两口径安全边际对照见 `buffett-doc-spec` §3。
- **valuations.yaml 里 A+H 股可能只存 H 代码**（`'03993'` / `'00666.HK'`）：按 A 股代码索引的脚本须「剥 `.HK` + 去前导零」双向归一匹配，勿硬等值。
- **ADR + 港股双重上市 ≠ A+H**：两地份额 fungible 可互转、无持续折价，切港股口径只是币种/锚定统一，**不带折价红利**，正文须明写 fungible。判别：6 位 A 股码 + H 码并存 = A+H；字母 ticker + 港股码并存 = 多为 fungible（仍以两地市值实测自洽为准）。ADS:普通股比例影响每股换算，市值跨地一致。
