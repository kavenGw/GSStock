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
| 产出形态 | 新建一份 buffett 深度档（`conviction_date` = 今天）+ `git rm` 该股**所有历史 buffett 档**（只删 buffett 档；comps/theme/quarterly 一律保留），目录只留最新一份 |
| 证据深度 | **全量联网验证** + 实时行情锚 |
| 估值框架 | **场景加权**：结构性重估(bull) / 基准(base) / 空头(bear)，概率由证据强度定 |
| 分析框架 | 先调用 `buffett` skill 取框架，再动笔 |
| A+H 口径 | A+H 双重上市标的**取 A/H 两地中估值更低（安全边际更大）一侧**作跟踪主体，**不强行 A 股**；H 股通常折价更优。frontmatter `stock_code` + valuations `market`/`currency`/每股内在价值按选定口径写，币种统一见 playbook §3、H 口径市值自洽校验见 `.claude/rules/data-fetch-conventions.md` 港股节 |
| 语言 | 中文 |

**只有这些情况才回头问用户**（歧义门）：
- 标的跨两个一级 sector 且收入权重接近，归属不明（按主业权重判，见 `.claude/rules/docs-conventions.md`）
- 用户明确要的是 comps 横评或 theme 专题，而非个股 buffett 档
- 旧档结论与近期已有底稿（comps/theme/quarterly）出现冗列冲突，不确定以谁为准

## 总编排：3 阶段 subagent + 合并审查

为什么拆 subagent：联网采证、长文撰写、lint 收尾是三种不同的认知活；分开派能让每棒上下文干净，
也满足"撰写与审查分属不同上下文、不在同一上下文自审"（见 CLAUDE.md）。**串行**，不要并行派实现者。

### 先做（控制者本人）
1. 用 Glob 找该股已有底稿：`docs/stock-analytics/**/*<股票名>*.md`（buffett / comps / quarterly / theme）。
   挑出最新 buffett 档 + 最相关 comps 作为基线，传给后续 subagent。
2. 确认股票代码、市场（A/US/HK）、sector/subsector 归属。
3. **列待删旧档清单**：从上面 Glob 结果筛出该股所有历史 buffett 档（`*buffett*.md`）。删前**先 Read 一眼
   确认确属同股旧 buffett 档**（判据：档名含目标股票名 **且** frontmatter `stock_code` 与目标一致；CLAUDE.md
   铁律：删除前看目标。不满足判据、或内容与预期严重不符，停下 surface 给用户，不照删）。把确认后的待删清单传给 Phase C。
4. **选 sector-lens**：按 subsector 从 `references/sector-lenses.md` 挑命中的 lens 节（**可叠加**：主 lens
   如 PCB/存储 + **两个横切 lens（AI、成长）默认对每只股跑识别**）。把命中节的【必查清单】【撰写落点】摘出，分别注入 Phase A / Phase B 提示。

### Phase A — 联网采证（派 1 个 subagent，opus）
产出 `.omc/artifacts/<股票名>-<日期>-evidence.md`（gitignore，不入库）。要点：
- WebSearch/WebFetch 逐条验证核心多空论点（供给侧/需求/涨价/政策/财报），英文+中文交叉验证。
- 实时行情直连腾讯 HTTP（比走 service 快且无副作用）：`qt.gtimg.cn/q=sh<code>`（A股 sh/sz 前缀），
  GBK 解码、`~` 分隔，字段 `[1]=name [3]=price [39]=PE_TTM [45]=市值(亿) [46]=PB`。脚本跑完即删。
- **证据分级**：【硬】=公司公告/财报/官方 EOL；【软】=媒体/分析师推测；【缺】=未找到。找不到就写"未找到公开证据"，**绝不编造数字或来源**，每个关键数字挂一个真实 URL + 日期。
- **注入命中 lens 的【必查清单】**（来自 `references/sector-lenses.md` 命中节）：要求逐条联网核实，
  查不到就明写"未找到公开证据"，不许跳过。
- 详细采证清单与字段见 `references/playbook.md`。

### Phase B — 撰写（派 1 个 subagent，opus）
先 `Skill buffett` 取框架，读 evidence.md + 基线底稿，按 13 节结构写正文 + frontmatter，跑 frontmatter lint，提交。
**只跑 `lint_docs_frontmatter.py`，不跑 refs**（对称留给 Phase C）。13 节模板、frontmatter 字段、场景加权
估值机制、AI 维度标签法、质量红线全部在 `references/playbook.md`，撰写 subagent 必须先读它。
**注入命中 lens 的【撰写落点】**（来自 `references/sector-lenses.md` 命中节）：要求对应节按落点深化，
命中 lens 的每个必查项都要在正文有回应（查无证据也要写明）。

### 合并审查（派 1 个 read-only subagent，sonnet；异常升 opus）
一个 sonnet 只读 subagent，单 prompt 内**先规格、后质量**两段顺序输出（顺序不可反）：
1. **规格符合性**：13 节齐全？frontmatter 合规（含 `valuation` 块与正文 §0/§9/§3 数字一致）？三情景概率 Σ=100%
   且期望值算术对？AI 维度都打了标？供给侧双面写了吗？数字可追溯无造数？无范围外夹带？命中 lens 的必查项是否
   在正文均有回应（查无证据也写明）？**命中成长 lens 时**：扩产达产 / 客户增长预期（分层兑证）/ 跑道长度是否
   均有回应？bull 是否被增长证据包门控？→ 输出 SPEC-COMPLIANT 或问题清单。
2. **分析质量**：内在一致性、概率可辩护性、供给侧双面是否走过场、"贵"是否被诚实消化、AI 是否蹭概念拔高、
   增长是否被诚实证据化、bull 赋权是否与增长证据强度匹配、slop 检查、buffett 框架贴合度、监控指标是否带阈值可执行。
   → APPROVED / APPROVED-WITH-NITS / CHANGES-REQUESTED。

**纪律保持**：审查员是独立 subagent（非撰写者自审），撰写≠审查上下文铁律不变。
**异常升级**：sonnet 给出 `CHANGES-REQUESTED`，或规格段发现 Critical 问题 → 控制者**追派 1 个 opus 只读审查员
复核该结论**，再据复核让撰写 subagent 修；同一审查上下文复审直到过。Minor nits 可修后控制者直接核验。

### Phase C — 收尾（派 1 个 subagent，sonnet 足够）
- **删除旧档**：对"先做"传来的待删清单逐个 `git rm`（该股历史 buffett 档）。
- **反向链改指**：扫所有 `symmetric: true` 指向被删档的反向条目（别的 comps/theme/quarterly 的
  related_docs）→ 改指到新档，或删除该条目（防 refs lint 悬空报错）。
- 给指向新档的外部文档（comps/theme/quarterly）补反向 related_docs 条目（symmetric: true 的那些）。
- `python scripts/lint_docs_refs.py --rewrite-blocks` 重生顶部块（别手编 `<!-- BEGIN/END related_docs -->`）。
- `lint_docs_frontmatter.py` + `lint_docs_refs.py` **都要 exit 0**；`--check-orphans` 确认新档非孤儿。
- **同步 valuations.yaml**：估值数字已由 Phase B 写进 buffett 档 frontmatter 的 `valuation` 块，
  此处只需运行 `PYTHONIOENCODING=utf-8 rtk python scripts/sync_valuations.py --stock-code <code>`
  确定性 upsert（无需 LLM 再从正文提取）。详见 `references/playbook.md` §8。
- **质地星级覆写（仅当与 rating 背离）**：估值页质地列默认按 rating 现算星级（core5/config4/watch3/exclude2）。**仅当**业务质地与该默认背离时——典型即红线 #4 的对偶：护城河顶级的好公司仅因太贵被评 `watch`/`config`——在 valuations.yaml 该条目手工加 `quality: N`（1-5），sync 已保留不冲掉。一致则留空。详见 `references/playbook.md` §8「quality 质地星级」。
- **矿产/商品标的加 `commodity` 字段**：若标的属铜/锂等矿产板块（受某商品期货价格驱动），在 frontmatter 与 valuations.yaml 条目**同步**写：
  - `commodity`: `copper` | `lithium`（枚举见 `scripts/_docs_schema.py:COMMODITIES`；非矿产标的不写）
  - `commodity_impact`: `positive`（上游资源/矿/锂盐——商品涨价利好，卖方如紫金/赣锋）| `negative`（下游加工/电池/消费——商品涨价是成本，买方如铜冠铜箔/亿纬锂能）| `neutral`（中游冶炼厂——低自给率，铜价 pass-through、利润由 TC/RC 加工费驱动，如云南铜业/铜陵有色/江西铜业）
  - 判据来自产业链位置（与 `.claude/rules/docs-conventions.md`「电池厂是锂买方，锂价涨=成本压力」一致）；本字段驱动 `/minerals` 矿产看板的板块归属与影响徽章。
  - 枚举权威源：`scripts/_docs_schema.py` 的 `COMMODITIES`/`COMMODITY_IMPACTS`（含 neutral）。
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
7. **替换=物理删除旧档**：新档落定后该股历史 buffett 档必须 `git rm`，且所有指向旧档的 symmetric 反向链
   改指到新档——目录里同股只留最新一份，refs lint 无悬空引用。
8. **看增长但不被增长拔高**：成长/扩产标的必查扩产达产 + 客户增长预期（分层：具名优先 → 终端兑底，逐条标【硬/软/缺】）；bull
   情景的概率/倍数由「成长持续性证据包」门控（扩产达产确定性 + 客户 capex 能见度 + TAM 跑道），证据全软则
   概率封顶；同时高增长不许稀释"贵"——这是红线 3（拒绝周期顶定价）的对偶，既防高估也防系统性低估真成长。

## 参考文件

- `references/playbook.md` — 13 节模板、frontmatter 字段集 + rating 枚举、场景加权估值机制、采证清单、qt.gtimg.cn 字段、lint 命令、各 subagent 派发提示骨架。**撰写/审查 subagent 必读。**
- `references/sector-lenses.md` — 可扩展板块视角注册表（AI/PCB/存储…），每 subsector 一节五段式调查清单。**命中 lens 的撰写/审查 subagent 必读对应节。**
- 项目既有 rules（按需指给 subagent）：`.claude/rules/docs-conventions.md`（目录/frontmatter/lint/related_docs）、
  `.claude/rules/data-fetch-conventions.md`（akshare/实时价/qt.gtimg.cn 字段坑）、`.claude/rules/stock-data-cache.md`（缓存）、
  `.claude/rules/dev-environment.md`（Windows 编码/heredoc/create_app 副作用）。
