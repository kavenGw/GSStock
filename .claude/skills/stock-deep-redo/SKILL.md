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

## 总编排：3 阶段 subagent（A 三路并行）+ 合并审查

为什么拆 subagent：联网采证、长文撰写、lint 收尾是三种不同的认知活；分开派能让每棒上下文干净，
也满足"撰写与审查分属不同上下文、不在同一上下文自审"（见 CLAUDE.md）。
**阶段之间严格串行**（Phase A 全部落盘并经控制者亲验 → Phase B → 审查 → Phase C，不做流水线重叠）；
**唯一的并行点是 Phase A 内部的 A1/A2/A3 三路**，除此之外不并行派实现者。

### 先做（控制者本人）
1. 用 Glob 找该股已有底稿：`docs/stock-analytics/**/*<股票名>*.md`（buffett / comps / quarterly / theme）。
   挑出最新 buffett 档 + 最相关 comps 作为基线，传给后续 subagent。
2. 确认股票代码、市场（A/US/HK）、sector/subsector 归属。
3. **列待删旧档清单**：从上面 Glob 结果筛出该股所有历史 buffett 档（`*buffett*.md`）。删前**先 Read 一眼
   确认确属同股旧 buffett 档**（判据：档名含目标股票名 **且** frontmatter `stock_code` 与目标一致；CLAUDE.md
   铁律：删除前看目标。不满足判据、或内容与预期严重不符，停下 surface 给用户，不照删）。把确认后的待删清单传给 Phase C。
4. **选 sector-lens 并把命中节原文摘出**：按 subsector 从 `references/sector-lenses.md` 挑命中的 lens 节
   （**可叠加**：主 lens 如 PCB/存储 + **两个横切 lens（AI、成长）默认对每只股跑识别**）。
   **控制者必须把命中节的【必查清单】原文内联进 A3 提示、【撰写落点】【双面必答】【监控指标模板】原文内联进
   Phase B 提示——不许只报 lens 名字让 subagent 自己去读整份 sector-lenses.md**（261 行里命中的通常只有
   约 70 行，让它自读是纯浪费，且它可能挑错节）。铁律与理由见 `references/playbook.md` §9.1。
5. **备兄弟档口径摘要**：若同板块有近期兄弟档可参照，控制者**读一遍并提炼成 3-5 行口径要点**
   （如"兄弟档用 TTM 营收作分母 / bull 封顶 20% / 买点取 30% 折价"）备用于 Phase B 提示。
   **不把兄弟档全文塞给写手、也不让它自己去读全文**（实测兄弟档 791 行，真正有用的就那几条）。

**建档前避坑门（强制，先于 Phase A）**：采证第一步先查 `docs/stock-analytics/avoidance-list.yaml`——命中目标 `stock_code` 则按 `.claude/rules/docs-conventions.md`「建档前避坑列表验证」做原因验证：用最新单季季报 + akshare 重取 `key_metrics_snapshot` 对应指标，逐条对照 `avoid_reason` 判仍成立/被推翻。**理由仍成立即中断建档**（口头说明后停手，不派 Phase A/B/C）；**被推翻**（基本面真实反转）才放行，且建档完成后从 avoidance-list.yaml 移除该条并 commit。

### Phase A — 联网采证（派 **3 个并行** subagent，均 opus）

**并行，不串行**——六大采证块之间无依赖，单 agent 顺序跑完实测 ~7min，拆三路 ~4min。
三个 agent 各写各的 evidence 片段，**不派合并 agent**（合并会把省下的时间又串回去），Phase B 同时读三份。

| Agent | 负责 | evidence 片段（`.omc/artifacts/<股票名>-<日期>…`） | 汇报文件（见 playbook §9.0）|
|---|---|---|---|
| **A1 数据锚** | 实时行情双源交叉 + 市值自洽校验、最新财报、逐月交付/出货、可比公司估值表 | `-evidence-A1-数据锚.md` | `-phaseA1-report.md` |
| **A2 论点验证** | 核心多空论点逐条联网核实（最重的一块，决定整轮墙钟）| `-evidence-A2-论点.md` | `-phaseA2-report.md` |
| **A3 lens 专项** | 命中 lens 的【必查清单】逐条核实（AI / 成长 / 板块 lens）| `-evidence-A3-lens.md` | `-phaseA3-report.md` |

（片段与汇报均落 `.omc/artifacts/`，文件名统一 `<股票名>-<日期>-<后缀>`，已 gitignore、不入库。）

**A1 是所有行情/财务硬数字的唯一权威源**（铁律）：A2/A3 涉及数字时以定性表述为主，
与 A1 冲突一律以 A1 为准；要求 Phase B 发现冲突时在正文显式标注，不得静默取一个。

**三路共同纪律**：
- WebSearch/WebFetch 英文+中文交叉验证；区分公司官方 vs 媒体 vs 分析师。
- **证据分级**：【硬】=公司公告/财报/官方 EOL；【软】=媒体/分析师推测；【缺】=未找到。找不到就写"未找到公开证据"，**绝不编造数字或来源**，每个关键数字挂一个真实 URL + 日期。

**A1 专属**：实时行情直连腾讯 HTTP（比走 service 快且无副作用）。**A 股与港股字段索引不同，不可照搬**：
- A 股 `qt.gtimg.cn/q=sh<code>`（6 开头 sh、0/3 开头 sz），GBK 解码、`~` 分隔，`[1]=name [3]=price [39]=PE_TTM [45]=市值(亿) [46]=PB`
- **港股 `q=hk<code>` 索引异于 A 股**，勿套用上面的 39/45/46——先把整串字段 dump 出来自行辨认，
  并用 **市值 = 现价 × 总股本** 自洽校验兜底（详见 `.claude/rules/data-fetch-conventions.md` 腾讯HTTP节）
- 港股/美股市值、PE、PB、52 周区间**必须交叉验证 2 源**（stockanalysis.com / Yahoo / 富途），市值口径常分歧
- 脚本跑完即删，控制者会亲验

**"相对旧档变化清单"不由 A1/A2/A3 写**——它需要全局视野，任何单路都写不了，**移交 Phase B**
（Phase B 本就要读全部三份 evidence + 旧档，天然有全局视野，不增加串行时间）。

**三路深度上限（收敛条件，控制者派发时必须写进 prompt）**：并行只在工作量本身可切分时才省墙钟；
若每路都把调查深度扩张到填满自己的时间，并行只会放大总工作量、墙钟由最慢一路决定——**2026-08-09
紫金实跑已实测到这个失败模式：A1 单路就跑到 12.8min，超过基线整个单 agent 顺序跑完的 7min**。
每路都要有明确的收敛条件：
- **A1**：把「必查清单」跑完即收，**不主动扩展到清单外的指标**；双源交叉只做清单里点名的那几个数字，
  不逐个数字都找两源。
- **A2**：每个论点**取到能定性即止**（证据 + 反驳点 + 硬软分级），不追求穷尽所有信源；单个论点找不到
  就标【缺】继续下一个，**不为一条论点反复深挖**。
- **A3**：**逐条回应 lens 必查清单即可**，查不到写「未找到公开证据」立即进入下一条，不做清单外的延伸调查。

**控制者的责任**：派发前明确告诉每一路「你的边界到哪为止」；**发现某一路的产出明显超出其边界
（如 A1 自行补了大量清单外分析），要在收尾复盘里记下来**，因为这就是墙钟失控的来源。

**例外**：标的为 **A+H / ADR+港股双重上市**，或需要跨市场口径校验时，A1 的工作量天然翻倍，
**允许其超出常规边界**，但控制者要预期到墙钟会拉长，不要按单市场标的的时间预估。

**汇合闸门（强制）**：三路**全部**写完 evidence 片段与 report 后，控制者逐份 `Read` 亲验（片段真实落盘、
A1 的采证脚本真删、数字有 URL 与日期）——**通过后才派 Phase B**。不许 A1 一落盘就开写（旧档过时事实会被
写进正文洗不掉），也不许跳过任一路的亲验。

- 详细采证清单与字段见 `references/playbook.md`。

### Phase B — 撰写（派 1 个 subagent，opus）

**不拆**——13 节长文的价值很大程度在「§6 论点 → §9 估值 → §10 评级」的链式推导，拆多写手最容易断链。

先 `Skill buffett` 取框架，读 **Phase A 的三份 evidence 片段（A1 数据锚 / A2 论点 / A3 lens）** + 旧档，
按 13 节结构写正文 + frontmatter，跑 frontmatter lint。
**只跑 `lint_docs_frontmatter.py`，不跑 refs**（对称留给 Phase C）；**不 git add/commit**（提交由 Phase C 统一做）。
13 节模板、frontmatter 字段、场景加权估值机制、AI 维度标签法在 `references/playbook.md`，撰写 subagent 必须先读它；
**8 条质量红线不在 playbook，由控制者从本文件「质量红线」节原文内联进 Phase B 提示**（同 §9.1 内联铁律）。

**控制者必须内联进提示的**（见 `references/playbook.md` §9.1，不许给路径让它自读）：
- 命中 lens 的【撰写落点】【双面必答】【监控指标模板】原文 —— 要求对应节按落点深化，
  命中 lens 的每个必查项都要在正文有回应（查无证据也要写明）
- 兄弟档口径要点 3-5 行 —— 不给兄弟档全文
- A1 片段里的关键事实锚（实时市值/PB/PS/股本/汇率）+ 任何需纠正的旧档错误假设

**Phase B 独有的两项交办**：
- **写"相对旧档变化清单"**（Phase A 三路都写不了，需全局视野）：逐条列旧档口径 vs 最新事实 + 变化方向。
- **标注三路 evidence 的数字冲突**：A1 是唯一权威源，若 A2/A3 与之打架，取 A1 并在正文显式标注，不得静默取一个。

汇报按 `references/playbook.md` §9.0 写文件，标识 `phaseB`。

### 合并审查（派 1 个 read-only subagent，sonnet；异常升 opus）
一个 sonnet 只读 subagent，单 prompt 内**先规格、后质量**两段顺序输出（顺序不可反）：
1. **规格符合性**：13 节齐全？frontmatter 合规（含 `valuation` 块与正文 §0/§9/§3 数字一致）？三情景概率 Σ=100%
   且期望值算术对？AI 维度都打了标？供给侧双面写了吗？数字可追溯无造数？无范围外夹带？命中 lens 的必查项是否
   在正文均有回应（查无证据也写明）？**命中成长 lens 时**：扩产达产 / 客户增长预期（分层兑证）/ 跑道长度是否
   均有回应？bull 是否被增长证据包门控？→ 输出 SPEC-COMPLIANT 或问题清单。
2. **分析质量**：内在一致性、概率可辩护性、供给侧双面是否走过场、"贵"是否被诚实消化、AI 是否蹭概念拔高、
   增长是否被诚实证据化、bull 赋权是否与增长证据强度匹配、slop 检查、buffett 框架贴合度、监控指标是否带阈值可执行。
   → APPROVED / APPROVED-WITH-NITS / CHANGES-REQUESTED。

**汇报**：按 `references/playbook.md` §9.0 写文件，标识 `review`——**两段正文都要写进文件**。
审查 subagent 是"只回 idle 不给正文"的重灾区（实测 prompt 明写"最终回复必须包含完整两段"仍先回 idle），
控制者一律读文件，不追要。

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
- 确认一次性采证脚本已删；**三份 evidence 片段（A1/A2/A3）与六份 report 文件均未被 git add**
  （都在 `.omc/artifacts/`，已 gitignore，但仍要确认）。
- **提交终稿**：`git rm -q --ignore-unmatch <待删旧档...> && git add <新档> <被改兄弟档/被链档> valuations.yaml && git commit -F .git/MSG.txt`
  —— 删除与新增**必须与 `git commit` 在同一条命令链**（并行 session 会抢 index，早前单独跑的 `git rm` 可能已被撤出暂存区）；
  提交后 `git show --stat HEAD` 确认只含本任务文件、未裹挟他人在写档；
  并 `git show HEAD:docs/stock-analytics/valuations.yaml` 复核本股条目真的落库（sync 的"已同步"自报不可信，
  他方 session 的工作区旧版本可能覆盖本次结果，需重跑 sync 补正）。
- 汇报按 `references/playbook.md` §9.0 写文件，标识 `phaseC`。

### 收尾（控制者本人）

**先算耗时账**：**以控制者自己记录的派发/收回时刻为准**（每一棒派发时打点、收到回复时打点），
六份 report 文件的 `start`/`end` 头（`phaseA1`/`phaseA2`/`phaseA3`/`phaseB`/`review`/`phaseC`）仅作
交叉参考——自报时间戳已被证伪不可信（2026-08-09 紫金实跑中审查 subagent 产出 19KB 完整报告却自报
耗时仅 1.4 分钟，明显是收工时补记）。发现自报值与控制者记录相差超过 2 倍，要在耗时账里注明该棒
自报失真。汇总成一行报给用户，格式例：`A1 x / A2 y / A3 z（并行取最大）+ B + 审查 + C ≈ 合计`。
**这是"提速是否真的发生"的唯一可证伪依据**，不许省。

**已有基线（四轮实测，如实记录）**：

| 轮次 | 标的 / 口径 | Phase A 形态 | 返修 | 合计 |
|---|---|---|---|---|
| 2026-08-08 | 零跑（港股单市场、重做档）| 单 agent | 0 | **~40min** |
| 2026-08-09 | 紫金（A+H 双市场、重做档）| 三路**无深度上限** | 1 Critical | **47.0min** |
| 2026-08-09 | 寒武纪（A 股单市场、**首建档**）| 三路**+深度上限** | 1 Major | **32.3min** |
| 2026-08-13 | 瑞联新材（A 股单市场、**首建档**）| 三路**+深度上限** | 1 Minor | **48.3min** |

分棒（瑞联）：A 10.5（A1 8.6 / A2 9.1 / A3 10.5，取最大）+ B 19.8 + 审查 6.5 + 返修 5.1 + C 2.8。

**读法**：
- **三路并行只在配深度上限时才省墙钟**——无上限时 Phase A 12.8min（慢于单 agent 的 7min），
  加上限后 6.0min（快于单 agent）。上限是杠杆二成立的前提，不是可选项。
- **但深度上限不保证 Phase A 快**：瑞联同样配了上限，Phase A 仍跑到 10.5min（vs 寒武纪 6.0min）。
  差别在**标的的采证面**——瑞联四条业务线（OLED/液晶/医药 CDMO/电子材料）+ 67.6% 海外收入 +
  三个横切 lens 全部命中，清单本身就比寒武纪长。**上限管住的是"每条查多深"，管不住"有多少条要查"**。
  派发前先粗数必查条数，条数多就按上限往高预估，别套用上一轮的墙钟。
- **Phase B 的墙钟由成稿长度驱动，不由标的复杂度驱动**：瑞联 19.8min 出 746 行（返修后 826 行），
  寒武纪同期约 12min。**长文是最大的单项开销**，且不可并行（拆写手会断"论点→估值→评级"的链）。
- **首建档比重做档少两块活**（Phase B 无需读旧档+写变化清单、Phase C 无需删旧档+反向链改指），
  粗估 3-5min。
- **派发时按 35-50min 预估**（多业务线 / 多 lens 命中 / A+H / 多轮返修往上取），**别按理论值许诺**——
  spec 原定的 29min 四轮实测无一达到，四轮中位数约 43min。
- **自报时间戳继续被证伪（第二次）**：本轮审查 subagent 自报 `end: 10:48:30`，但其完成消息在控制者
  10:44:42 打点前就已送达。**耗时账一律以控制者侧派发/收回记录为准**（playbook §9.0 已有此约定）。

`git log --oneline` + `git status` 确认 commit 链干净、双 lint 全绿，向用户汇报核心结论（评级是否翻转、
期望内在价值、安全边际）。工作流默认在 `main` 直接提交（本仓库 docs 一贯如此）；**不主动 push**，等用户要。

## 质量红线（这套流程的灵魂，审查重点查这些）

1. **联网而非凭记忆**：知识截止之后的供需/报价/业绩进展一律实时核实；硬软证据措辞要区分（"官方 EOL" vs "据媒体"）。
2. **供给侧/任何强论点必须双面**：把最强的反驳点前置写出来（如"大厂退出是否可逆"），不能写成单边多头叙事。
3. **拒绝用周期顶利润定价**：周期股正常化利润取穿越周期的均值，绝不把财报顶部年化当常态——这是周期股 buffett 分析最常翻车处。
4. **诚实面对"贵"**：PB/PE/市值高就老实算安全边际，必要时对最乐观情景也做压力测试；不要用"护城河上修"稀释"价格太贵"。
5. **AI/概念维度分"产品 vs 业绩"**：有产品能力不等于有业绩贡献；未兑现的概念不许偷渡进估值。每个 AI 维度打【真敏感】/【蹭概念】+理由。
6. **数字可追溯**：正文每个关键数字能回指三份 evidence 片段（A1/A2/A3）之一或基线底稿；无裸断言、无造数。
7. **替换=物理删除旧档**：新档落定后该股历史 buffett 档必须 `git rm`，且所有指向旧档的 symmetric 反向链
   改指到新档——目录里同股只留最新一份，refs lint 无悬空引用。
8. **看增长但不被增长拔高**：成长/扩产标的必查扩产达产 + 客户增长预期（分层：具名优先 → 终端兑底，逐条标【硬/软/缺】）；bull
   情景的概率/倍数由「成长持续性证据包」门控（扩产达产确定性 + 客户 capex 能见度 + TAM 跑道），证据全软则
   概率封顶；同时高增长不许稀释"贵"——这是红线 3（拒绝周期顶定价）的对偶，既防高估也防系统性低估真成长。

## 参考文件

- `references/playbook.md` — 13 节模板、frontmatter 字段集 + rating 枚举、场景加权估值机制、采证清单、qt.gtimg.cn 字段、lint 命令、各 subagent 派发提示骨架。**撰写/审查 subagent 必读。**
- `references/sector-lenses.md` — 可扩展板块视角注册表（AI/PCB/存储…），每 subsector 一节五段式调查清单。
  **由控制者读并摘原文内联进 A3 / Phase B / 审查提示，subagent 不自读**（§9.1 内联铁律）。
- 项目既有 rules（按需指给 subagent）：`.claude/rules/docs-conventions.md`（目录/frontmatter/lint/related_docs）、
  `.claude/rules/data-fetch-conventions.md`（akshare/实时价/qt.gtimg.cn 字段坑）、`.claude/rules/stock-data-cache.md`（缓存）、
  `.claude/rules/dev-environment.md`（Windows 编码/heredoc/create_app 副作用）。
