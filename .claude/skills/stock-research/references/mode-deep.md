
# 模式 1 · 个股深度分析（原 stock-deep-redo）

把一只股票的投资结论"重新承做一遍"：最新事实（联网验证）+ 实时估值，套 buffett 框架，场景加权给出一个
**能经得起反驳**的新评级，落档到 `docs/stock-analytics/`。价值在**纪律**而非篇幅：联网核实、证据分硬软、
强论点双面、拒绝周期顶定价、诚实面对"贵"、撰写≠审查上下文。

本文件只做**编排**（谁、何时、闸门）。三份配套：
- `dispatch.md` — 每个 subagent 的派发内容（必内联项 / prompt 骨架 / 派发坑）。**派发前必读对应节。**
- `sector-lenses.md` — 板块视角注册表；控制者读并摘原文内联，subagent 不自读。
- `lessons.md` — 十三轮实测教训 L1–L15 + 耗时附录；按 `[Ln]` 编号翻，不通读。

subagent 自行加载的规格 skill：`buffett-doc-spec`（写手/审查员：frontmatter/13 节/估值机制/8 条红线）、
`finalize.md`（Phase C：删旧档/反向链/lint/valuations 同步/提交协议）。

## 何时用 / 何时不用

**用**：单只个股深度分析或重估，尤其有新变量（涨价周期、供给侧出清、AI、政策、重大财报/并购）需刷新或推翻旧结论。
**不用**：已有文件夹档 + 附带财报 → 模式 2（`mode-earnings.md`）；板块批量 → `analyze-category`；再平衡 → `portfolio-rebalance`；
清仓 → `liquidation-strategy`；只要个实时价 → 直接查。

## 默认参数（开工时一句话说明即可）

| 维度 | 默认 |
|------|------|
| 产出形态 | 写 `sectors/<sector>/<subsector>/<股票名>/` 七文件（规格见 `buffett-doc-spec`，`conviction_date`=今天）。该股只有平铺历史档 → 新建文件夹 + Phase C `git rm` 全部平铺 buffett 档（一次性迁移，旧档事件 theme 须迁进 `events.md` 而非新建空档 [L17]）；已是文件夹 → 原地覆盖 6 文件（含 `related.md`）、`events.md` 不动；存量文件夹档 index.md 里的 `related_docs` 本轮迁进 `related.md` 并从 index.md 删除。comps/theme/quarterly 一律保留 |
| 证据深度 | 全量联网验证 + 实时行情锚 |
| 估值框架 | 场景加权 bull/base/bear，概率由证据强度定 |
| A+H 口径 | 取 A/H 中估值更低一侧作跟踪主体（H 通常折价更优）；`stock_code`/`currency`/每股价值随选定口径；市值自洽校验见 `.claude/rules/data-fetch-conventions.md` 港股节 |
| 语言 | 中文 |

**歧义门（只有这些才回头问）**：跨两个一级 sector 且收入权重接近（按主业权重判，见 `.claude/rules/docs-conventions.md`）；用户要的其实是 comps/theme；旧档结论与近期
comps/theme/quarterly 底稿冲突不知以谁为准。

## 编排：先做 → A(三路并行) → B → 审查 → C，阶段严格串行

### 先做（控制者本人）

1. Glob `docs/stock-analytics/**/*<股票名>*` 找底稿（平铺档或 `<股票名>/index.md`），挑最新 buffett 档 + 最相关 comps 作基线。
   已有 `<股票名>/events.md` → 读其 related_docs，theme `date` > 旧 index `conviction_date` 的条目即「未消化事件」，
   摘 note/impact/magnitude 备内联给 A2（dispatch.md §1）。
2. 确认代码、市场（A/US/HK）、sector/subsector。控制者自取行情做前置观察时，须验时戳与成交量非集合竞价时段 [L24]。
3. **避坑门**：查 `docs/stock-analytics/avoidance-list.yaml`，命中则按 `.claude/rules/docs-conventions.md`
   「建档前避坑列表验证」重验；理由仍成立即中断建档；被推翻才放行，建档后从列表移除并 commit。
4. **列待删旧档清单**：只筛平铺 `*buffett*.md`（文件夹档不删），**逐个 Read 确认**档名含目标股票名且 `stock_code`
   一致；不符则停下 surface 给用户。目标已是文件夹 → 清单为空。
5. **选 lens**：按 subsector 从 `sector-lenses.md` 挑命中节（主 lens + AI/成长两个横切默认都跑识别），把命中节
   原文摘出备内联（dispatch.md §0.2）。
6. **兄弟档口径摘要**：同板块近期兄弟档读一遍提炼 3-5 行（TTM 分母 / bull 封顶 / 买点折价等），不给全文。
7. `mkdir -p .omc/artifacts`（闸门脚本要求存在）。

### Phase A — 联网采证（A1 数据锚 / A2 论点 / A3 lens，并行，均 opus）→ dispatch.md §1

闸门：`python scripts/deep_redo_gate.py <股票名> <日期> --phase A --quiet-min 3`，exit 0 **且**所有在途校准项
已收到「已闭合」回复才派 B [L1][L2]。需等待时按 [L7] 探测模板包一层（超时分支也要发信号）；探测点报 TIMEOUT 后先 `ls` 全部产物 + `ListAgents` 看状态，分辨 agent 是死在交付前还是交付后 [L22]。
预估按「最慢路 + 1~2 轮校准」[L4]；派发前先粗数必查条数，上限管"查多深"管不住"有多少条"；A+H / 多业务线 / 多 lens 命中往上取。
某一路报「前提变化」时先 grep 另两路 evidence 确认是否已自发命中，命中就别派校准轮 [L16]。

### Phase B — 撰写（1 个 opus，不拆）→ dispatch.md §2

闸门：`python scripts/deep_redo_gate.py <股票名> <日期> --phase B --doc <新档文件夹>`（要求写手达成某条规格前先全仓统计其实际执行状况；subagent 拿证据顶回指令时先亲验它的证据 [L26]）（查 7 文件齐全 + 占位，对应
"主体 + 填锚"抗中断设计 [L14][L10]）。预估 17-30min，由成稿长度驱动，不可并行（拆写手断"论点→估值→评级"链）。

### 合并审查（1 个 read-only sonnet；异常升 opus）→ dispatch.md §3

闸门：`python scripts/deep_redo_gate.py <股票名> <日期> --phase review`。两段正文都要在文件里，控制者读文件不追要。
审查报的「两路 evidence 数字冲突」先核是不是同一张表的不同列，再决定改数还是补口径说明 [L19]。
返修单只下"结构/格式/补解释"指令；**凡引入新事实或因果论断的，先经一路验证或写成「请核实 X 是否成立」，不得直接写成「请补写 X」** [L21]。
预估 4-10min，复核另计。

### Phase C — 收尾（1 个 sonnet）→ dispatch.md §4

闸门：`lint_docs_frontmatter.py` / `lint_docs_refs.py` 双 exit 0 + `git show HEAD:docs/stock-analytics/valuations.yaml`
复核本股条目。预估 3-10min。

## 跨日重启 / 中断恢复（控制者本人）

- 会话中断杀掉全部 subagent；"到点再做"别交给 subagent，能亲自接棒就别等 [L6]。账号会话额度耗尽会同时杀掉全部在途 subagent 且重派必然同样失败，别等重置 [L22]。
- 跨日第一件事：复核基本面基线是否仍成立（期间落了财报就是实质返修，不是刷新锚）[L9]。
- 刷新价格锚后派生数 grep 扫不到，必须逐句手算 [L8]：`python scripts/deep_redo_anchor_audit.py <新档文件夹> --old <旧价> --new <新价>`
  只列清单不算数。
- 亲验用精确锚点（tail + 关键词计数 + mtime + report `end:`），别用模糊 grep [L13]；且必须等 agent 结束后再验，对关键结论整节读、不靠关键词抽样（写盘中的产物会给出过渡态）[L23]。
- Phase B 中断续跑给"只补缺的文件 / 只填占位、不重写已有内容"的收口棒，不重派完整写手 [L14]。

## 收尾（控制者本人）

耗时账以控制者自记派发/收回时刻为准 [L3]，一行报给用户：`A1 x / A2 y / A3 z（取最大）+ B + 审查 + C ≈ 合计`。
**按 40-60min 预估**（十三轮中位数 56.6min、区间 32.3-86min；A+H 标的在中位数之上 [L9][L11][L12]；首建档
少读旧档/写变化清单/删旧档/反向链约 3-5min）。基线明细见 `lessons.md` 附录。

`git log --oneline` + `git status` 确认 commit 链干净、双 lint 全绿，向用户汇报评级是否翻转、期望内在价值、安全边际。
默认在 `main` 直接提交；**不主动 push**。

## 维护规则

新一轮有教训时（模式 1/2 共用）：只在 `lessons.md` 追加 `Ln`（三段式写全；编号永不复用/重排）→ 本文件对应闸门处加 `[Ln]` 引用不写叙事 →
基线表只加一行 → 能机械化的优先落成 `scripts/deep_redo_*.py` 检查项再在闸门引用（L1/L7/L8 就是这么来的）。
派发内容变化改 `dispatch.md`；文档规格变化改 `buffett-doc-spec`；收尾动作变化改 `finalize.md`。
本文件目标 **≤130 行**；路由判据归 `../SKILL.md`，本文件不写"何时触发"。
