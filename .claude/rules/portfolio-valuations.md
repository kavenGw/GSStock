# Portfolio / Valuations skill 行为与 A+H 口径

> **何时读**：跑 /portfolio-init 或 /portfolio-rebalance、改 RebalanceConfig/StockWeight/PositionPlan、改 /valuations 页或 valuations.yaml、裁定 A+H 双重上市口径
> **不必读**：文档写作/frontmatter/lint（见 docs-conventions.md）

## 持仓再平衡报告输出

- 入口：`/portfolio-init`（首次配置 / 主题大调）+ `/portfolio-rebalance`（日常算 diff，支持 `--dry-run`）
- HTML 报告输出目录走本地配置 `.claude/skills/portfolio-init/local-config.yaml` 的 `portfolio.output_dir`（已 gitignore；模板 `local-config.yaml.example`）
- 报告文件名：`{output_dir}/portfolio-init-{YYYY-MM-DD}.html`（按日覆盖）/ `{output_dir}/portfolio-rebalance-{YYYY-MM-DD-HHMM}.html`（按时分留历史）
- 共享 HTML 模板（git 跟踪）：`.claude/skills/portfolio-init/report-template.html`
- 写库表：`RebalanceConfig.target_value` / `StockWeight` / `PositionPlan`（PositionPlan 无 unique，写前先 `DELETE FROM position_plans`）
- `StockWeight.weight` 存原始 float，不要 `round(_, 4-6)`。rebalance 的 shares 计算同时加 `floor(diff/price/100 + 1e-6)*100` / `ceil(.../100 - 1e-6)*100` 吸收 FP roundtrip 噪声

## docs/stock-analytics/ 是 portfolio skill 的隐式选股池

- 用 Glob `docs/stock-analytics/sectors/**/*.md` + `docs/stock-analytics/cross-sector/**/*.md` 提取候选标的
- 评级 / 主题 / 选股理由从 frontmatter 读
- 同股多 doc 时按 `conviction_date` desc 取首条作为权威评级，其余进 `related_docs`
- 季报点评（`quarterly/`）不进选股池，只作为同期事件清单源（见 portfolio-rebalance SKILL）

## 估值汇总页（/valuations，即"价值洼地"）

路由 `app/routes/valuations.py`，数据源 `docs/stock-analytics/valuations.yaml`（与 frontmatter 分离的独立聚合文件，不被 docs linter 约束）。

分组规则（`group_by_sector`）：行的 DB 分类命中白名单 `CARVE_OUT_CATEGORIES`（如 `{'啤酒'}`）→ 抬成独立顶级组覆盖 sector；否则按 `sector`→`SECTOR_LABELS`。

**新增一个主题/二级板块分组**：① 在 `CARVE_OUT_CATEGORIES` 加分类名 ② 在分类管理（`StockCategory`，stock_code 唯一约束=一股一类）把目标股设为该分类。模板零改动（数据驱动）。

分类数据是用户数据非 seed（seed 铁律"不覆盖已存在归属"，而改挂分类恰需覆盖）；建/改分类走分类管理 UI 或一次性 DB 写入。

**A+H 双重上市标的取较低估值口径（铁律）**：A+H 股做 buffett 档 / 写 valuations.yaml 时，**取 A 股与 H 股两地中估值更低（安全边际更大）一侧作跟踪主体，不强行用 A 股口径**——H 股通常较 A 股折价，AH 折价是安全边际放大器（实测天岳 A 股口径安全边际 -18.7%，切 H 股 02631 因折价 -38.7% 反转为 +32.7%）。frontmatter `stock_code` 与 valuations 条目（`market`/`currency`/每股内在价值）按选定口径写；同股切换口径时 valuations 按 `stock_code` 覆盖旧条目（688234→02631）。H 口径市值自洽校验见 `data-fetch-conventions.md` 港股节，币种折算（RMB→HKD ×1.08）+ 安全边际两口径对照见 stock-deep-redo playbook §3。

**A+H 标的在 valuations.yaml 里可能只存 H 股口径代码**：承上铁律——A+H 股若选 H 口径跟踪，valuations 条目的 `stock_code` 就是港股形态（如洛阳钼业实际为 `'03993'` 而非 A 股 `'603993'`，瑞浦兰钧为 `'00666.HK'`）。按 A 股代码索引 valuations 条目的回填/聚合脚本必须预期此形态：用「剥 `.HK` + 去前导零」归一化双向匹配，或直接以 valuations 里的实际 code 为准；勿用 A 股代码硬等值匹配，否则 A+H 标的静默漏命中。

**ADR + 港股双重主要上市 ≠ A+H（fungible 无折价，切口径不带安全边际红利）**：中概股「美股 ADR + 港股」双重/二次上市（如腾讯音乐 TME↔1698.HK、理想 LI↔2015.HK、阿里/京东/网易等），两地份额 **fungible 可互转**，经套利无持续折价（实测 TME -0.7%、LI +0.4%，仅套利噪声）——**与 A+H（A 股 H 股分别注册、不可互转、有持续折价）本质不同**。给这类标的「切港股口径」时**绝不能套用上一条 A+H 的"切 H 折价放大安全边际"逻辑**：切口径只是币种/锚定统一，安全边际的任何变化只来自股价波动 + 正常化利润重估，不存在凭空折价红利。frontmatter `stock_code`/valuations 按所选口径（HKD）写，正文须明写 fungible 无折价以防自欺。判别：A 股代码（6 位）+ H 股代码并存 = A+H 非互转；美股字母 ticker + 港股代码并存 = ADR+HK 多为 fungible（仍以实测两地市值/价差自洽校验为准）。ADS:普通股比例（TME/LI 均 2:1）影响每股口径换算，市值跨地一致。
