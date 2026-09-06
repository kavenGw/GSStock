# 模式 1 · 个股深度分析（原 stock-deep-redo）

把一只股票的投资结论"重新承做一遍"：最新事实（联网验证）+ 实时估值，套 buffett 框架，场景加权给出
**能经得起反驳**的新评级，落档到 `docs/stock-analytics/`。价值在**纪律**而非篇幅：联网核实、证据分硬软、
强论点双面、拒绝周期顶定价、诚实面对"贵"、撰写≠审查上下文。

本文件只做**编排**（谁、何时、闸门）。配套：`dispatch.md`（每个 subagent 的**变量清单**，派发前必读对应节；
固定协议在 `.claude/agents/sr-*.md`）、`references/lenses/`（由 sr-a3-lens / sr-writer / sr-reviewer **自读**，控制者不内联）、
`lessons.md`（案例溯源，**不通读**，`grep -n "^## L19"` 翻单条）、`timing-baseline.md`（轮数与耗时统计的**唯一真源**）。
写手/审查员自加载 `buffett-doc-spec`。

## 何时用 / 何时不用

**用**：单只个股深度分析或重估，尤其有新变量（涨价周期、供给侧出清、AI、政策、重大财报/并购）需刷新或推翻旧结论。
**不用**：已有文件夹档 + 附带财报 → 模式 2（`mode-earnings.md`）；板块批量 → `analyze-category`；再平衡 → `portfolio-rebalance`；清仓 → `liquidation-strategy`；只要个实时价 → 直接查。

## 默认参数（开工时一句话说明即可）

| 维度 | 默认 |
|------|------|
| 产出形态 | 写 `sectors/<sector>/<subsector>/<股票名>/` 七文件（规格见 `buffett-doc-spec`，`conviction_date`=今天）。只有平铺历史档 → 新建文件夹 + Phase C `git rm` 全部平铺 buffett 档（旧档事件 theme 迁进 `events.md` 而非新建空档 [L17]）；已是文件夹 → 原地覆盖 6 文件（含 `related.md`）、`events.md` 不动；存量 index.md 的 `related_docs` 迁进 `related.md`。comps、机理/结构性专题、他股主体的行业 theme 一律保留；该股「期间数据本体」档按步骤 4b 判 |
| 证据深度 | 全量联网验证 + 实时行情锚 |
| 估值框架 | 场景加权 bull/base/bear，概率由证据强度定 |
| A+H 口径 | 取估值更低一侧作跟踪主体（H 通常折价更优）；`stock_code`/`currency`/每股价值随选定口径；市值自洽校验见 `.claude/rules/data-fetch-conventions.md` 港股节 |
| 语言 | 中文 |

**歧义门（只有这些才回头问）**：跨两个一级 sector 且收入权重接近（按主业权重判，见 `.claude/rules/docs-conventions.md`）；用户要的其实是 comps/theme；旧档结论与近期 comps/theme/quarterly 底稿冲突不知以谁为准。

## 编排：先做 → A(三路并行) → B → 审查 → C，阶段严格串行

### 先做（控制者本人）

1. Glob `docs/stock-analytics/**/*<股票名>*` 找底稿，挑最新 buffett 档 + 最相关 comps 作基线。已有 `<股票名>/events.md` → 读其 related_docs，theme `date` > 旧 index `conviction_date` 的条目即「未消化事件」，摘 note/impact/magnitude 备内联给 A2（dispatch.md §1）。
2. 确认代码、市场（A/US/HK）、sector/subsector。前置观察取行情：验时戳与成交量非集合竞价时段 [L24]；`quote_guard` 代码带市场前缀（`sh603618`）[L36]；收盘后用当日收盘价作锚走 `--allow-preopen`，此时**必然**附带「竞价参考价」警告，属窗口边界，看成交量与价×股本偏差判真伪、别退回盘中价 [L43]。
3. **避坑门**：查 `docs/stock-analytics/avoidance-list.yaml`，命中则按 `.claude/rules/docs-conventions.md`「建档前避坑列表验证」重验；理由仍成立即中断；被推翻才放行，建档后从列表移除并 commit。
4. **列待删旧档清单**（合并成一份传给 Phase C）：
   - **4a 平铺 buffett 旧档**：只筛平铺 `*buffett*.md`（文件夹档不删），**逐个 Read 确认**股票名与 `stock_code` 一致；不符即停下 surface。
   - **4b 期间数据本体档**（跨 `quarterly/` `themes/` `cross-sector/` 全扫，**不限 doc_type**）：判据一句——**信息本体是不是某一期数据、或基于该期数据的直接推演** [L48]。命中形态：季报/中报/年报点评、预告/快报/指引、财报联动专题、行情验证/异动复盘、单期事项落地（定增说明书发行完成后、减持计划实施完毕后）。主体判定 `stock_code` **OR** `stock_name` 并集（A+H 双代码、证券简称变更都会让单键合法失配）；**`related_codes` 挂多只不构成保留理由**（判「谁是分析对象」）；覆盖期 ≤ 新档（`h1`≡`q2`、`a`≡`q4`，无 `period` 按 `date`）。**始终保留**：comps（跨股资产）、机理/结构性专题（核心假设被证伪也不自动删，结论写进新档）、主体非本股的行业/政策 theme。
   - **删前铁律**：① 承接——未被新档**正文**覆盖的结论先内联进 `events.md` 正文再删（related_docs note 随条目消失）；② 改指——全仓 grep 档名**含正文行内链接**（refs lint 只查 frontmatter）[L48]，改指新档并补对称条目，**不许 `symmetric: false` 省事** [L41]。
   - **确认闸**：4b 清单**surface 给用户、确认后才传 C**（删除不可逆；4a 走自动流程）。边界拿不准时列「性质 / 是否被本期取代 / 被谁引用」表让用户划线。
5. **lens 命中**：按 subsector 对照 `references/lenses/` 映射表，命中文件名写进写手与审查员派发（横切 `x-*.md` 由 agent 默认全加载）。不摘原文。
6. **兄弟档口径摘要**：同板块近期兄弟档提炼 3-5 行（TTM 分母 / bull 封顶 / 买点折价等）。
7. `mkdir -p .omc/artifacts`。

### Phase A — 联网采证（A1 数据锚 / A2 论点 / A3 lens，并行，均 opus）→ dispatch.md §1

闸门 `python scripts/deep_redo_gate.py <股票名> <日期> --phase A`：exit 0 **且**在途校准项全部收到「已闭合」才派 B。
预估「最慢路 + 1~2 轮校准」[L4]；派发前粗数必查条数（上限管"查多深"管不住"有多少条"），A+H / 多业务线 / 多 lens 往上取。

| 时机 | 判据 | 出处 |
|---|---|---|
| 闸门 exit 1 | 先分形式失败 / 内容失败；形式失败亲验内容后放行，**不代写 end 戳** | [L52] |
| 结论层标题带编号前缀 | 按 `^##.*结论层$` 匹配，不算缺项 | [L28] |
| 判该路是否收工 | 看 evidence `end:` 戳/mtime，不看 report 是否存在；校准消息在途 ≠ 已闭合 | [L1][L2] |
| 需要等待 | 用 [L7] 探测模板包一层，超时分支也发信号；成功条件**调用闸门**，别手写 `grep -q "^end:"` | [L7][L44] |
| 探测点报 TIMEOUT | 先 `ls` 全部产物 + `ListAgents`，分辨死在交付前 / 后 | [L22] |
| 某路报「前提变化」 | 先 grep 另两路 evidence，已自发命中就不派校准轮 | [L16] |
| 控制者接棒补过收口 | exit 0 只证形态完整；该路仍可能二次收工推翻硬数字，下游引用前复核或标「待二次确认」 | [L46] |
| 二次补证与写手已落盘冲突 | 先 grep 对账；财报口径（分部 / 附注 / 管理层讨论）默认并存，禁用「全错」「作废」整体否定词 | [L56] |
| 三路未齐 | 任一路强断言只记「待另两路复核」不进裁定；早到的一路给**终局性建议**时加严不放宽 | [L29][L45] |
| 裁定含跨主体比较派生量 | 自算算式并显式标口径（营收 / 归母 / 扣非） | [L40] |
| 裁定含量化拆分 | 先用该量关键词 grep 三路**明细层**全文，结论层不够 | [L42] |

### Phase B — 撰写（1 个 opus，不拆）→ dispatch.md §2

闸门 `python scripts/deep_redo_gate.py <股票名> <日期> --phase B --doc <新档文件夹>`（7 文件齐全 + 占位，对应「主体 + 填锚」抗中断设计 [L14][L10]）。
预估 17-30min，由成稿长度驱动，不可并行。派发单写死落盘顺序 **valuation → thesis → business → sources → related → events → index**（index 是汇总、先写必回改）。

| 时机 | 判据 | 出处 |
|---|---|---|
| 要求写手达成某规格 | 先全仓统计该规格实际执行状况；subagent 拿证据顶回时先亲验其证据 | [L26] |
| 财报盘后披露、次日建档 | 等开盘取锚，等待窗口排成同一写手三段式（非价格段 → §9 非价格 → 填锚），别用作废锚写完再回填 | [L34] |
| 盘中开工且写手早于收盘完稿 | 写手用盘中锚起稿 + `valuation.md` 标「盘中」并列回填清单，收口由控制者做 | — |

### 合并审查（1 个 read-only sonnet；异常升 opus）→ dispatch.md §3

闸门 `python scripts/deep_redo_gate.py <股票名> <日期> --phase review`，两段正文都在文件里、控制者读文件不追要。预估 4-10min，复核另计。

| 时机 | 判据 | 出处 |
|---|---|---|
| 本轮中途下过修正单 | 派审查前逐条 grep 亲验落地 + 七文件 mtime 收敛；审查员是快照读者，过渡态会成片假 Critical | [L53][L23] |
| 审查报「全仓 0 命中」类否定断言 | 自跑 grep 复核；返修单按亲验结果收窄并注明「勿按审查原话全面返工」 | [L33] |
| 审查报两路数字冲突 | 先核是否同一张表不同列 / 同一算法不同期间 | [L19] |
| 某路用反解判另一路口径对错 | 用量纲不同的独立路径回算同一数再采信 | [L70] |
| 返修单同时含「改口径」与「订正派生数」 | 后者不得照抄审查值（按旧参数算的），写明按新参数重算 | [L63] |
| 返修单引入新事实 / 因果论断 | 先经一路验证或写成「请核实 X 是否成立」，不得写「请补写 X」 | [L21] |

### Phase C — 收尾（1 个 sonnet）→ dispatch.md §4

闸门：双 lint exit 0 + `git show HEAD:docs/stock-analytics/valuations.yaml` 自读本股条目 + `grep -c "symmetric: false" <新档>/events.md <新档>/related.md` 为零。预估 3-10min。

| 时机 | 判据 | 出处 |
|---|---|---|
| 派发单 | 显式列「本 session 已改未提交的 docs 文件」；亲验必看 `git status` 按 diff 认领，C 的归属自报不可信 | [L51] |
| 清理一次性脚本 | 正向白名单只删自己建的；`_a1_*`/`_a3_*` 是各轮共用前缀，先验 mtime 归属 | [L30] |
| valuations `note` | 旧口径常以**方法论措辞**而非数字残留，自读自判 | [L67] |
| lint 绿 | `symmetric: false` 可被被检查方关掉，绿灯只证「没有开着的违规」 | [L41] |
| C idle 而产出缺席 | 交付物是 commit / lint / valuations 本身，自己验完补记录，别重派 | [L35] |

## 跨日重启 / 中断恢复（控制者本人）

| 时机 | 判据 | 出处 |
|---|---|---|
| 会话中断 / 额度耗尽 | 全部在途 subagent 被杀，重派必同样失败；「到点再做」别交给 subagent，能亲自接棒就别等 | [L6][L22] |
| 跨日第一件事 | 复核基本面基线是否仍成立，期间落了财报即实质返修 | [L9] |
| 刷新价格锚 | 派生数 grep 扫不到，逐句手算（`python scripts/deep_redo_anchor_audit.py <档> --old <旧价> --new <新价>` 只列清单）；双锚并存时加换算表、只修读作「当前」的措辞，不逐句替换 | [L8][L32] |
| 脚本化回填 | 句级批次排在 token 级之后，覆盖全角 / 半角乘号 | [L47] |
| 作废口径参数 | 按它算过的每个派生数全仓 grep 复扫至归零，跨档比较两端都重述到新口径；按量纲分货币组 / 实物组各扫一遍，覆盖 `related.md`/`sources.md` | [L55][L69] |
| 亲验产出 | tail + 关键词计数 + mtime + 六份产出的 `end:` 戳；等 agent 结束后整节读 | [L13][L23] |
| Phase B 中断续跑 | 先 `ls -la` + `tail` 验落盘：主体已落盘派「只补缺 / 只填占位」收口棒，零落盘重派完整写手；failed 消息里的进度自述是意图快照 | [L14][L64] |

## 收尾（控制者本人）

耗时以控制者自记派发/收回时刻为准 [L3]，一行报给用户：`A1 x / A2 y / A3 z（取最大）+ B + 审查 + C ≈ 合计`。
**按 50-75min 预估**（净耗时口径；中位数 / 四分位 / 区间只看 `timing-baseline.md`，本文件不复制数字）。首建档比重做少 3-5min；
A+H 与撞财报日在中位数之上 [L9][L11][L12]；超 90min 全部由外部中断或 A 路二次返工造成，预估时问「今天会不会撞额度 / 撞财报 / 撞盘中」。
**收尾必须往 `timing-baseline.md` 加一行并重算其统计表**，预估区间变动时同步回本节。

`git log --oneline` + `git status` 确认 commit 链干净、双 lint 全绿，汇报评级是否翻转、期望内在价值、安全边际。默认 `main` 直接提交，**不主动 push**。

## 维护规则

- 新教训先过 `lessons.md` 的**新增门槛**（能机械化 / 首次新形态才开新号；同族复发只在旧条追加「复发」行、本文件不加字）。开新号时：`lessons.md` 追加 `Ln` + 索引行 → 本文件对应表加**一行**（判据 ≤ 40 字，不写叙事）→ `timing-baseline.md` 加一行并重算 → 能机械化的落成 `scripts/deep_redo_*.py` / `quote_guard.py` / `.claude/agents/sr-*.md`，落成后把 lessons 条目压成「规则 / 机制 / 一句案例」。
- 派发内容改 `dispatch.md`；文档规格改 `buffett-doc-spec`；收尾动作改 `finalize.md` **与** `.claude/agents/sr-finalize.md`（同源两份）。
- 本文件目标 **≤120 行**；路由判据归 `../SKILL.md`，本文件不写"何时触发"。
