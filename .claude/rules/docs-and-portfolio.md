# 文档目录与 portfolio skill

> **何时读**：写 docs/stock-analytics/ 新文档、修改文档 frontmatter、调用 /portfolio-init 或 /portfolio-rebalance、调整 RebalanceConfig / StockWeight / PositionPlan、跑 lint_docs_frontmatter / lint_docs_refs
> **不必读**：纯代码改动 / 通知 / 数据获取

## 文档目录约定（docs/stock-analytics/）

- `sectors/<sector>/<subsector>/YYYY-MM-DD-<股票名>-buffett分析.md` — 个股 buffett 风格深度分析（按主业务归属）
- `cross-sector/YYYY-MM-DD-<主题>.md` — 多股专题 / 多股 buffett 对比（如 AMD-Intel、立讯-歌尔、工业富联-甲骨文）
- `themes/YYYY-MM-DD-<主题>.md` — 事件驱动主题（世界杯炒作 / CCL 涨价 / 磷化铟板块）
- `quarterly/<NNqN>/YYYY-MM-DD-<股票>-<类型>.md` — 季报点评 + 同期专题（时间归档，跨板块横看）
- `comps/YYYY-MM-DD-<横向主题>-comps.md` — 估值/财务横向对比
- `comps/quarterly/<NNqN>/...` — 季度 comps

**一级 sector 枚举**（11 项，linter 强校验）：
`semiconductor` / `electronics` / `consumer` / `materials` / `energy` / `healthcare` / `media` / `financial` / `industrial` / `ai-application` / `other`

二级 subsector 自由起名。详细 schema + lint 用法见 `docs/stock-analytics/README.md` 与 `scripts/_docs_schema.py`。

**跨板块标的 sector 归属准则**：标的横跨两个一级板块时（如罗博特科 51% 半导体 + 48% 光伏、工业富联 PCB+服务器），按**收入第一权重**归类，次要业务在 thesis / themes 中说明。仅在两业务旗鼓相当且核心叙事来自次要业务时，例外放 `cross-sector/`。判断主业权重用 `ak.stock_zygc_em(symbol='SZ<code>')` 取最新报告期的"按产品分类"切片。

**锂电/储能成品制造归 `energy`/`battery`，不归 `materials`**：电芯/电池系统/动力/储能/消费电池制造（如亿纬锂能）属 energy；`materials` 仅放上游锂盐/正负极/隔膜/电解液（如赣锋锂业=materials/lithium）。中游电池厂 vs 上游锂资源成本传导方向相反（电池厂是锂买方，锂价涨=成本压力）。采证 subagent 易误判电池厂为 materials/industrial，控制者需纠。

## Frontmatter 约定（5 类 doc_type）

所有文档必须有 YAML frontmatter，按 `scripts/_docs_schema.py:REQUIRED_FIELDS_BY_TYPE` 字段集补齐。

**强制规则**：
- `stock_code` / `stock_codes` 必须字符串引号（防 YAML int 化丢前导 0）—— `'000021'` 而非 `000021`
- `rating=watch` → 必填 `watch_reason`；`rating=exclude` → 必填 `exclude_reason`
- `conviction_date` / `date` 必须 `YYYY-MM-DD` 格式
- `period` 必须与所在 `quarterly/<NNqN>/` 目录名一致

**`conviction_date` YAML 解析为 `datetime.date` 不是 str** — `yaml.safe_load` 把 `conviction_date: 2026-05-09` 转 `datetime.date` 对象。与字符串做 `>` 比较会抛 `TypeError`。聚合多 doc 取最新时必须 `str(fm.get('conviction_date') or '')` 先转字符串。

## 跨文档引用：frontmatter.related_docs 唯一源

```yaml
related_docs:
  - path: ../../quarterly/26q1/2026-04-29-兆易-26Q1季报点评.md
    note: 26Q1 实证点评
    symmetric: true  # 默认 true，要求反向对称
```

h1 之后的 `<!-- BEGIN related_docs -->` / `<!-- END related_docs -->` 块由脚本生成，**不要手编**。

## Lint 脚本（手动 run）

```bash
python scripts/lint_docs_frontmatter.py          # 校验所有 frontmatter
python scripts/lint_docs_refs.py                 # 校验 related_docs 路径 + 反向对称
python scripts/lint_docs_refs.py --rewrite-blocks  # 重生所有文档顶部 markdown 块
python scripts/lint_docs_refs.py --check-orphans   # 列孤儿文档
```

退出码 0 = 全过；非 0 = 列违例清单。新写或迁移文档后跑 lint 自检。

**Lint 坑（Windows + 并发）**：
- `--check-orphans` 会因 print 含中文（如「铜」）的孤儿路径撞 cp950 抛 `UnicodeEncodeError` 返回 exit 1，**而 orphan 判定逻辑其实已跑完**——加 `PYTHONIOENCODING=utf-8` 才得真实 exit 0，别误判为 lint 失败。
- `--rewrite-blocks` 会重生**所有** block 与 frontmatter 失步的文档（含并行 session 未提交的在写档），易产生跨任务连带 diff。跑完**只精确 `git add` 本任务的档**，**勿 `git add -A`**，避免裹挟他人半成品。
- 但"精确 add"仍有盲区：refs `symmetric: true` **强制**你 touch 兄弟档补反向条目才过 lint，若该兄弟档正被并行 session 改（带未提交分析改动），`git add <兄弟档>` 会连其未提交改动一并裹挟进你的 commit。add 前先 `git diff <兄弟档>`：若有 `related_docs` 块以外的改动即对方在写，归其自行提交（其后续 commit 会干净收尾、非破坏性，但勿误判为本任务产物）。**对偶情形**：并行 session 同跑 stock-deep-redo 于同板块兄弟股、共享同一 comps 时，指向你新档的反向条目可能已被对方抢先写入并 committed——补反向链前先 `grep <新档名> <兄弟档>`，已在则跳过（勿重复追加），以 `refs lint exit 0` 为真闸而非"必须由我添加"。

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
