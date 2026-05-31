---
name: stock-deep-redo
description: >-
  个股 buffett 深度重做分析（re-underwrite）全流程编排：全量联网验证供需事实 → 实时行情锚定 →
  场景加权估值 → 写入 docs/stock-analytics 的 buffett 分析档 → frontmatter/lint/related_docs 对称收尾。
  当用户要求对某只股票做深度分析、重做/重估/重新承做、用新事实（供给侧变化、涨价、AI、政策、财报、并购）
  刷新或推翻旧结论、或产出/更新某股的 buffett 深度分析文档时，务必使用本 skill——即使用户没说
  "buffett""重做""re-underwrite"也要触发。典型触发语："深度分析 XX""重做 XX 的分析""XX 还能不能买"
  "用最新存储涨价重估 XX""考虑 AI/供给侧重新看 XX"。不要用于：板块批量分析（用 analyze-category）、
  纯季报点评（quarterly 流程）、持仓再平衡（portfolio-rebalance）、清仓策略（liquidation-strategy）。
---

# 个股 buffett 深度重做分析（stock-deep-redo）

把一只股票的投资结论"重新承做一遍"：拿当下最新事实（联网验证）+ 实时估值，套 buffett 框架，
用场景加权给出一个**能经得起反驳**的新评级，并落档到 `docs/stock-analytics/`。

这个 skill 的价值不在"写得长"，而在**纪律**：联网核实而非凭记忆、证据分硬软、供给侧论点必须双面、
拒绝用周期顶利润定价、诚实面对"贵"、撰写与审查分属不同上下文。下面每一步都为这些纪律服务。

## 何时用 / 何时不用

**用**：对单只个股做深度分析或重估，尤其是有新变量（涨价周期、供给侧出清、AI、政策红利、重大财报/并购）
需要刷新甚至推翻旧结论时。

**不用**：板块批量 → `analyze-category`；季报点评 → quarterly 流程；再平衡 → `portfolio-rebalance`；
清仓 → `liquidation-strategy`；只要个实时价 → 直接查不必起 skill。

## 默认参数（烘进流程，不必每次问）

除非检测到歧义，按这些默认直接做，开工时一句话说明用了什么默认即可：

| 维度 | 默认 |
|------|------|
| 产出形态 | 新建一份 buffett 深度档（`conviction_date` = 今天），supersede 旧档（旧档保留，related_docs 互链） |
| 证据深度 | **全量联网验证** + 实时行情锚 |
| 估值框架 | **场景加权**：结构性重估(bull) / 基准(base) / 空头(bear)，概率由证据强度定 |
| 分析框架 | 先调用 `buffett` skill 取框架，再动笔 |
| 语言 | 中文 |

**只有这些情况才回头问用户**（歧义门）：
- 标的跨两个一级 sector 且收入权重接近，归属不明（按主业权重判，见 `.claude/rules/docs-and-portfolio.md`）
- 用户明确要的是 comps 横评或 theme 专题，而非个股 buffett 档
- 旧档结论与近期已有底稿（comps/theme/quarterly）出现冗列冲突，不确定以谁为准

## 总编排：3 阶段 subagent + 两段式审查

为什么拆 subagent：联网采证、长文撰写、lint 收尾是三种不同的认知活；分开派能让每棒上下文干净，
也满足"撰写与审查分属不同上下文、不在同一上下文自审"（见 CLAUDE.md）。**串行**，不要并行派实现者。

### 先做（控制者本人）
1. 用 Glob 找该股已有底稿：`docs/stock-analytics/**/*<股票名>*.md`（buffett / comps / quarterly / theme）。
   挑出最新 buffett 档 + 最相关 comps 作为基线，传给后续 subagent。
2. 确认股票代码、市场（A/US/HK）、sector/subsector 归属。

### Phase A — 联网采证（派 1 个 subagent，opus）
产出 `.omc/artifacts/<股票名>-<日期>-evidence.md`（gitignore，不入库）。要点：
- WebSearch/WebFetch 逐条验证核心多空论点（供给侧/需求/涨价/政策/财报），英文+中文交叉验证。
- 实时行情直连腾讯 HTTP（比走 service 快且无副作用）：`qt.gtimg.cn/q=sh<code>`（A股 sh/sz 前缀），
  GBK 解码、`~` 分隔，字段 `[1]=name [3]=price [39]=PE_TTM [45]=市值(亿) [46]=PB`。脚本跑完即删。
- **证据分级**：【硬】=公司公告/财报/官方 EOL；【软】=媒体/分析师推测；【缺】=未找到。找不到就写"未找到公开证据"，**绝不编造数字或来源**，每个关键数字挂一个真实 URL + 日期。
- 详细采证清单与字段见 `references/playbook.md`。

### Phase B — 撰写（派 1 个 subagent，opus）
先 `Skill buffett` 取框架，读 evidence.md + 基线底稿，按 13 节结构写正文 + frontmatter，跑 frontmatter lint，提交。
**只跑 `lint_docs_frontmatter.py`，不跑 refs**（对称留给 Phase C）。13 节模板、frontmatter 字段、场景加权
估值机制、AI 四维度标签法、质量红线全部在 `references/playbook.md`，撰写 subagent 必须先读它。

### 两段式审查（每段派 1 个 read-only subagent，opus）
顺序不能反——**先规格、后质量**：
1. **规格符合性**：13 节齐全？frontmatter 合规？三情景概率 Σ=100% 且期望值算术对？AI 四维度都打了标？
   供给侧双面写了吗？数字可追溯无造数？无范围外夹带？→ 输出 SPEC-COMPLIANT 或问题清单。
2. **分析质量**：内在一致性、概率可辩护性、供给侧双面是否走过场、"贵"是否被诚实消化、AI 是否蹭概念拔高、
   slop 检查、buffett 框架贴合度、监控指标是否带阈值可执行。→ APPROVED / APPROVED-WITH-NITS / CHANGES-REQUESTED。
有 Critical/Important 问题 → 让撰写 subagent 修 → 同一审查员复审，直到过。Minor nits 可修后控制者直接核验。

### Phase C — 收尾（派 1 个 subagent，sonnet 足够）
- 给被链的旧档/comps 补反向 related_docs 条目（symmetric: true 的那些）。
- `python scripts/lint_docs_refs.py --rewrite-blocks` 重生顶部块（别手编 `<!-- BEGIN/END related_docs -->`）。
- `lint_docs_frontmatter.py` + `lint_docs_refs.py` **都要 exit 0**。
- 确认一次性采证脚本已删、evidence.md 未被 add。
- 提交终稿。

### 收尾（控制者本人）
`git log --oneline` + `git status` 确认 commit 链干净、双 lint 全绿，向用户汇报核心结论（评级是否翻转、
期望内在价值、安全边际）。工作流默认在 `main` 直接提交（本仓库 docs 一贯如此）；**不主动 push**，等用户要。

## 质量红线（这套流程的灵魂，审查重点查这些）

1. **联网而非凭记忆**：知识截止之后的供需/报价/业绩进展一律实时核实；硬软证据措辞要区分（"官方 EOL" vs "据媒体"）。
2. **供给侧/任何强论点必须双面**：把最强的反驳点前置写出来（如"大厂退出是否可逆"），不能写成单边多头叙事。
3. **拒绝用周期顶利润定价**：周期股正常化利润取穿越周期的均值，绝不把财报顶部年化当常态——这是周期股 buffett 分析最常翻车处。
4. **诚实面对"贵"**：PB/PE/市值高就老实算安全边际，必要时对最乐观情景也做压力测试；不要用"护城河上修"稀释"价格太贵"。
5. **AI/概念维度分"产品 vs 业绩"**：有产品能力不等于有业绩贡献；未兑现的概念不许偷渡进估值。每个 AI 维度打【真敏感】/【蹭概念】+理由。
6. **数字可追溯**：正文每个关键数字能回指 evidence.md 或基线底稿；无裸断言、无造数。

## 参考文件

- `references/playbook.md` — 13 节模板、frontmatter 字段集 + rating 枚举、场景加权估值机制、AI 四维度标签法、采证清单、qt.gtimg.cn 字段、lint 命令、各 subagent 派发提示骨架。**撰写/审查 subagent 必读。**
- 项目既有 rules（按需指给 subagent）：`.claude/rules/docs-and-portfolio.md`（目录/frontmatter/lint/related_docs）、
  `.claude/rules/data-fetch-conventions.md`（akshare/实时价坑）、`.claude/rules/data-architecture.md`（qt.gtimg.cn/缓存）、
  `.claude/rules/dev-conventions.md`（Windows 编码/heredoc/create_app 副作用）。
