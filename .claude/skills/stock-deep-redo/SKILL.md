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

采证/撰写/收尾是三种不同认知活，分开派上下文干净，满足撰写≠审查上下文铁律（见 CLAUDE.md）。
**阶段严格串行**（A 全落盘经控制者亲验 → B → 审查 → C，不流水线重叠）；**唯一并行点是 Phase A 内部 A1/A2/A3**。

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
6. **建 artifacts 目录**：`mkdir -p .omc/artifacts`（闸门脚本要求该目录存在，否则报 exit 2）。

**建档前避坑门（强制，先于 Phase A）**：采证第一步先查 `docs/stock-analytics/avoidance-list.yaml`——命中目标 `stock_code` 则按 `.claude/rules/docs-conventions.md`「建档前避坑列表验证」做原因验证：用最新单季季报 + akshare 重取 `key_metrics_snapshot` 对应指标，逐条对照 `avoid_reason` 判仍成立/被推翻。**理由仍成立即中断建档**（口头说明后停手，不派 Phase A/B/C）；**被推翻**（基本面真实反转）才放行，且建档完成后从 avoidance-list.yaml 移除该条并 commit。

### Phase A — 联网采证（3 路并行，均 opus）

**做什么**：A1 数据锚 / A2 论点验证 / A3 lens 专项，三路各写各的 evidence 片段与 report，
**不派合并 agent**。文件名统一 `.omc/artifacts/<股票名>-<日期>-<后缀>`。

| Agent | 负责 | evidence 片段 | 汇报文件（见 playbook §9.0）|
|---|---|---|---|
| **A1 数据锚** | 实时行情双源交叉 + 市值自洽校验、最新财报、逐月交付/出货、可比公司估值表 | `-evidence-A1-数据锚.md` | `-phaseA1-report.md` |
| **A2 论点验证** | 核心多空论点逐条联网核实（最重的一块，决定整轮墙钟）| `-evidence-A2-论点.md` | `-phaseA2-report.md` |
| **A3 lens 专项** | 命中 lens 的【必查清单】逐条核实（AI / 成长 / 板块 lens）| `-evidence-A3-lens.md` | `-phaseA3-report.md` |

**必内联**（控制者摘原文进 prompt，不给路径让它自读，铁律见 playbook §9.1）：
- 三路深度上限各一条（A1 跑完必查清单即收 / A2 每论点取到能定性即止 / A3 逐条回应即可）
- 「A1 是所有硬数字唯一权威源」+ A2/A3 以定性表述为主、冲突以 A1 为准 [L15]
- 命中 lens 的【必查清单】原文（进 A3）
- 控制者的前置观察**一律写成「我的推断是 X，请核实 X 是否成立」，且三路都给** [L5]
- 证据分级（硬/软/缺）+ 不造数 + §9.0 汇报文件协议

**放行闸门**：

```bash
python scripts/deep_redo_gate.py <股票名> <日期> --phase A --quiet-min 3
```

exit 0 **且**所有在途校准项已收到「已闭合」回复 → 才派 Phase B [L1][L2]。
exit 1 → 输出会指明哪一路缺什么/仍在写，不许提前放行。需要等待时按 `[L7]` 的探测模板包一层
（超时分支也要发信号，否则分不清 crashloop 与"还没好"）。

**预估**：按「最慢路 + 1~2 轮校准」，**不是三路取最大**——十三轮里跨路校准出现四次，是常态 [L4]。
A+H / 多业务线 / 多 lens 命中往上取。

**"相对旧档变化清单"不由三路写**（需全局视野）→ 移交 Phase B。

- 详细采证清单与字段见 `references/playbook.md`。

### Phase B — 撰写（1 个 subagent，opus）

**做什么**：**不拆**——「§6 论点 → §9 估值 → §10 评级」链式推导，拆多写手最容易断链。先 `Skill buffett`
取框架，读三份 evidence + 旧档，按 13 节结构写正文+frontmatter，跑 `lint_docs_frontmatter.py`（**不跑
refs**，留 Phase C；**不 git add/commit**）。13 节模板/字段/场景加权估值/AI 标签法在 `references/playbook.md`，
必读。独有两项交办：写"相对旧档变化清单"（逐条列旧档口径 vs 最新事实+变化方向）；标注三路数字冲突
（A1 权威，冲突取 A1 并正文显式标注，不静默取一个）。

**必内联**（不许给路径让它自读）：
- 命中 lens 的【撰写落点】【双面必答】【监控指标模板】原文——对应节按落点深化，命中 lens 的每个
  必查项都要在正文有回应（查无证据也要写明）
- 兄弟档口径要点 3-5 行（不给兄弟档全文）
- A1 片段里的关键事实锚（实时市值/PB/PS/股本/汇率）+ 任何需纠正的旧档错误假设
- **8 条质量红线原文**（本文件「质量红线」节，不在 playbook 里，须控制者内联）

**放行闸门**：

```bash
python scripts/deep_redo_gate.py <股票名> <日期> --phase B --doc <新档路径>
```

占位检查对应"主体 + 填锚"抗中断设计——主体先落盘，中断只损失填空那一小段 [L14]；财报盘后披露 +
次日盘前采证时，市值分母整段留 `【待锚】`、开盘后补锚再过闸 [L10]。

**预估**：墙钟由**成稿长度**驱动、不由标的复杂度驱动，且不可并行（拆写手会断"论点→估值→评级"链）；
首建档无需读旧档+写变化清单，省 3-5min。约 **17-30min**（十三轮实测，见 `references/lessons.md`「附录：
分棒耗时明细」）。

### 合并审查（1 个 read-only subagent，sonnet；异常升 opus）

**做什么**：单 prompt 内**先规格、后质量**两段顺序输出（顺序不可反）：①规格符合性——13 节齐全？frontmatter
合规（`valuation` 块与正文 §0/§9/§3 一致）？概率 Σ=100% 且期望值算术对？AI 维度都打标？供给侧双面？数字
可追溯无造数？lens 必查项均有回应？→ SPEC-COMPLIANT 或问题清单。②分析质量——一致性、概率可辩护性、"贵"
是否诚实消化、增长是否诚实证据化、bull 赋权是否匹配增长证据强度、slop 检查、框架贴合度、监控指标可执行
→ APPROVED / APPROVED-WITH-NITS / CHANGES-REQUESTED。独立 subagent（非自审），撰写≠审查铁律不变。
**异常升级**：CHANGES-REQUESTED 或规格段发现 Critical → 追派 opus 只读审查员复核，同一上下文复审直到过；
Minor nits 可修后控制者直接核验。

**必内联**：
- 反向对称与 refs lint 归 Phase C、尚未运行，**不必判为缺陷**，但可指出哪些兄弟档 note 数字已被新档推翻
- 镜像同步类检查写成「**所有含数字的 frontmatter 字段**（valuation 块 + watch_reason/exclude_reason +
  thesis）都要与正文 §0/§9 逐个比对」，**别只点名 valuation**

**放行闸门**：

```bash
python scripts/deep_redo_gate.py <股票名> <日期> --phase review
```

两段正文都要写进文件；审查 subagent 是"只回 idle 不给正文"的重灾区，控制者一律读文件，不追要。

**预估**：约 4-10min；触发复核另计一轮。

### Phase C — 收尾（1 个 subagent，sonnet 足够）

**做什么**（动作清单，原样保留）：
- **删除旧档**：对"先做"传来的待删清单逐个 `git rm`（该股历史 buffett 档）。
- **反向链改指**：扫所有 `symmetric: true` 指向被删档的反向条目（comps/theme/quarterly 的 related_docs）
  → 改指到新档，或删除该条目（防 refs lint 悬空报错）。
- 给指向新档的外部文档补反向 related_docs 条目（symmetric: true 的那些）。
- `python scripts/lint_docs_refs.py --rewrite-blocks` 重生顶部块（别手编 BEGIN/END related_docs）。
- `lint_docs_frontmatter.py` + `lint_docs_refs.py` **都要 exit 0**；`--check-orphans` 确认新档非孤儿。
- **同步 valuations.yaml**：`PYTHONIOENCODING=utf-8 rtk python scripts/sync_valuations.py --stock-code <code>`
  确定性 upsert（估值数字已在 Phase B 写进 frontmatter `valuation` 块）。详见 playbook §8。
- **质地星级覆写（仅当与 rating 背离）**：默认按 rating 现算星级；仅当业务质地背离（如护城河顶级仅因太贵
  评 watch/config）时手工加 `quality: N`（1-5）。
- **矿产/商品标的加 `commodity` 字段**：frontmatter 与 valuations.yaml 同步写 `commodity`（`copper`/`lithium`，
  见 `scripts/_docs_schema.py:COMMODITIES`）+ `commodity_impact`（`positive`/`negative`/`neutral`，判据见产业链位置）。
- 确认一次性采证脚本已删；三份 evidence + 六份 report 均未被 git add（`.omc/artifacts/` 已 gitignore，仍要确认）。
- **提交终稿**：`git rm -q --ignore-unmatch <待删旧档...> && git add <新档> <被改档> valuations.yaml &&
  git commit -F .git/MSG-<股票名>-<日期>.txt`——删增必须与 commit **同一条命令链**（并行 session 抢 index）；
  message 文件名带任务专属后缀（勿用固定 `.git/MSG.txt`，后写者会覆盖）；提交后 `git show --stat HEAD` 确认
  只含本任务文件；`git show HEAD:docs/stock-analytics/valuations.yaml` 复核本股条目落库（sync 自报不可信）。

**必内联**：无——清单本身已足够具体，直接摘给 subagent。

**放行闸门**：无独立命令；`lint_docs_frontmatter.py` / `lint_docs_refs.py` 双 exit 0 即为完成判据。

**预估**：约 3-10min，取决于反向链改指条数。

### 跨日重启 / 中断恢复（控制者本人）

- 会话中断会杀掉全部 subagent；别把"到点再做"的任务交给 subagent，能亲自接棒就别等 [L6]。
- 跨日重启第一件事：**复核基本面基线是否仍成立**（期间是否落了财报——落了就不是刷新锚而是实质返修）。
- 刷新价格锚后，**grep 字面量只能覆盖一次引用**；派生数（反推/隐含/对照当前市值/前瞻 PE 等句式）不含
  旧锚字面量，grep 扫不到，必须逐句手算 [L8]：`python scripts/deep_redo_anchor_audit.py <新档路径> --old <旧价> --new <新价>`（只列清单不算数，逐句手算仍是人的活）。
- 亲验用**精确锚点**（tail 看真尾部 + 关键词计数 + 文件 mtime + report 的 `end:`），别用会误命中的模糊 grep [L13]。
- Phase B 若被中断，续跑不必重派完整写手：给一个"只填占位、不重写任何已有内容"的收口棒即可 [L14]。

### 收尾（控制者本人）

**耗时账**：以控制者自记的派发/收回时刻为准（自报时间戳不可信 [L3]），report 的 `start`/`end` 仅作
交叉参考，相差超 2 倍要注明该棒自报失真。汇总一行报给用户：`A1 x / A2 y / A3 z（取最大）+ B + 审查 + C ≈ 合计`。

十三轮实测基线（标的/形态/返修/合计）见 `references/lessons.md` 附录「十三轮合计」表；分棒明细同附录备查。

**读法**：
- 三路并行只在配深度上限时才省墙钟（无上限 12.8min 慢于单 agent 的 7min，加上限 6.0min）。
- **上限管住"每条查多深"，管不住"有多少条要查"**——派发前先粗数必查条数，别套用上一轮墙钟。
- Phase B 墙钟由**成稿长度**驱动、不由标的复杂度驱动，且不可并行（拆写手会断"论点→估值→评级"链）。
- 首建档比重做档少两块活（B 无需读旧档+写变化清单、C 无需删旧档+反向链改指），粗估 3-5min。
- **按 40-60min 预估**：十三轮中位数 56.6min、区间 32.3-86min。下限只在「单市场+首建档+无跨路校准+
  无附件型缺口」齐备时出现；A+H 标的两轮都在中位数之上 [L9][L11][L12]。

`git log --oneline` + `git status` 确认 commit 链干净、双 lint 全绿，向用户汇报核心结论（评级是否翻转、
期望内在价值、安全边际）。默认在 `main` 直接提交；**不主动 push**，等用户要。

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

## 维护规则（防止本文件长回编年体）

新一轮跑完有教训时：
1. **只在 `references/lessons.md` 追加 `Ln`**（编号顺延，永不复用、不重排），三段式写全。
2. 在本文件对应的闸门/预估处加一个 `[Ln]` 引用，**不写叙事**。
3. 基线表**只加一行**（合计列）；分棒明细写进 lessons.md 附录。
4. 若该教训能机械化，优先落成 `scripts/deep_redo_*.py` 的一个检查项，再在闸门段引用它——
   **措辞管不住的判据要变成命令**（L1/L7/L8 三条就是这么来的）。

本文件的目标是 **≤260 行**。超了先问一句：是不是又把某一轮的教训叙事写回正文了？是就搬去
lessons.md；不是（确属新增的操作步骤）就照实加，并在这里更新数字。

## 参考文件

- `references/playbook.md` — 13 节模板、frontmatter 字段集 + rating 枚举、场景加权估值机制、采证清单、qt.gtimg.cn 字段、lint 命令、各 subagent 派发提示骨架。**撰写/审查 subagent 必读。**
- `references/sector-lenses.md` — 可扩展板块视角注册表（AI/PCB/存储…），每 subsector 一节五段式调查清单。
  **由控制者读并摘原文内联进 A3 / Phase B / 审查提示，subagent 不自读**（§9.1 内联铁律）。
- `references/lessons.md` — 十三轮实测教训案例库（L1–L15）+ 分棒耗时明细附录。
  **控制者按需按编号翻，不必通读；subagent 一律不读**（它们拿到的是控制者内联的具体指令）。
- 项目既有 rules（按需指给 subagent）：`.claude/rules/docs-conventions.md`（目录/frontmatter/lint/related_docs）、
  `.claude/rules/data-fetch-conventions.md`（akshare/实时价/qt.gtimg.cn 字段坑）、`.claude/rules/stock-data-cache.md`（缓存）、
  `.claude/rules/dev-environment.md`（Windows 编码/heredoc/create_app 副作用）。
