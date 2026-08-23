---
name: buffett-doc-spec
description: >-
  Use when writing or reviewing a buffett 深度分析档 under docs/stock-analytics（stock-research 模式 1/2 的
  Phase B 写手与合并审查员必须加载）——需要 frontmatter 字段集/rating 枚举、13 节文档结构、场景加权估值铁律、
  valuation 块字段、8 条质量红线时。不含采证与收尾流程（见 stock-research / stock-doc-finalize）。
---

# buffett 深度档规格（buffett-doc-spec）

一份 buffett 档要同时满足：机器可校验的 frontmatter（lint）、固定 13 节骨架、场景加权估值算术自洽、
8 条质量红线。撰写前先 `Skill buffett` 取分析框架，再按本规格落笔；审查按本规格逐项核对。

## 1. frontmatter

必填（`scripts/_docs_schema.py:REQUIRED_FIELDS_BY_TYPE`）：
`doc_type, stock_code, stock_name, sector, subsector, themes, rating, conviction_date, thesis`

```yaml
---
doc_type: buffett
stock_code: '603986'        # 必须字符串引号，防 YAML int 化丢前导 0
stock_name: 兆易创新
sector: semiconductor        # 11 项一级枚举之一，见 .claude/rules/docs-conventions.md
subsector: storage           # 二级自由起名
conviction_date: 2026-05-31  # YYYY-MM-DD
themes:
- memory
- 供给侧
rating: watch                # 枚举仅 {core, config, watch, exclude}
watch_reason: ...            # rating=watch 必填；rating=exclude 必填 exclude_reason
thesis: 一句话投资论点
valuation:                   # Phase B 写入，Phase C 用 sync_valuations.py 同步到 valuations.yaml
  bear: 6.50                 # 每股内在价值（原币），无法估算填 null
  base: 7.78
  bull: 8.87
  currency: CNY              # CNY / USD / HKD，与每股估值币种一致；缺省按市场推断
  dividend_yield: 2.8        # 分红率（%），无分红填 null
commodity: copper            # 可选，仅矿产/商品标的；枚举见 scripts/_docs_schema.py:COMMODITIES
commodity_impact: positive   # positive=上游资源（涨价利好）/ negative=下游买方（涨价是成本）/ neutral=中游冶炼（加工费驱动）
related_docs:
- path: <相对路径>            # 按所在目录算：storage 档→comps ../../../comps/<file>.md；comps→storage ../sectors/semiconductor/storage/<file>.md；同目录直接文件名
  note: ...
  symmetric: true            # true 要求被链档补反向条目（Phase C 做）；不想补就 false
---
# <标题>

<!-- BEGIN related_docs (auto-generated from frontmatter, do not edit) -->
<!-- END related_docs -->
```

文件落点：`sectors/<sector>/<subsector>/<股票名>/`（稳定路径，重做原地覆盖，历史靠 git）：

| 文件 | doc_type | 内容 | 体量 |
|------|----------|------|------|
| index.md | buffett（上述完整 frontmatter） | §0 + §10 + §11 | ≤12KB |
| business.md | buffett-section / section: business | §1-§5 | — |
| thesis.md | buffett-section / section: thesis | §6-§8 | — |
| valuation.md | buffett-section / section: valuation | §9 + 相对旧档变化清单 | — |
| sources.md | buffett-section / section: sources | §12 | — |
| events.md | buffett-events | 只含 frontmatter related_docs（stock-research 模式 3 回写）+ h1；**重做时不覆盖**，不存在才新建 `related_docs: []` | — |

section 档 frontmatter 仅 `doc_type / stock_code / stock_name / section` 四字段，禁止 rating/valuation/related_docs/themes
（lint 强校验）。index.md 的 `related_docs` 只放结构性引用（comps/quarterly/cross-sector/兄弟 buffett 档），事件 theme
一律在 events.md。跨文件引用用相对链接 `[§9](valuation.md)`，不复制正文；每个 section 文件以 `# <股票名> — <节范围>` 开头。
存量平铺档 `YYYY-MM-DD-<股票名>-buffett分析.md` 是 2026-08-23 前的旧形态，**不再新建**；消费者双模识别。
`quality`（质地星级）**不进 frontmatter**，是 valuations.yaml 条目专属字段，Phase C 按需写。

**写手职责边界**：写完只跑 `python scripts/lint_docs_frontmatter.py`（6 文件齐全 + 占位由 gate `--doc <文件夹>` 校验）；**不跑 refs lint、不 git add/commit、不删旧档、
不改兄弟档**（这些归 Phase C 的 `stock-doc-finalize`）。

撰写纪律：三档每股内在价值与正文 §0/§9 一致；分红率与 §3/§11 一致；**所有含数字的 frontmatter 字段**
（valuation 块 + watch_reason/exclude_reason + thesis）都须与正文镜像一致——审查逐个比对，不只查 valuation。
消费/材料/能源/工业/金融标的分红率是重要收益来源，§3/§11 须写出并填入 `dividend_yield`。
港股/美股每股估值用对应币种；A+H 选定口径由 `stock_code` 本身体现，`currency` 随之。

## 2. 13 节文档结构

- **§0 结论摘要** → index.md（倒金字塔：新评级 + 期望内在价值 + 三情景概率各一句）
- **§1 能力圈 & 本次重审触发** → business.md（为何现在重做：哪些新变量；对比旧档结论）
- **§2 市场规模** → business.md（各业务线 TAM/SAM/SOM + 跑道：当前渗透率/份额距天花板多远）
- **§3 盈利能力** → business.md（最新季报兑现 + 毛利率·ROIC 周期分析 + 涨价/需求弹性精算 + 增长拆量价与增长质量）
- **§4 全球竞争力** → business.md（全球份额、细分龙头识别、vs 国际龙头差距）
- **§5 核心优势 / 护城河** → business.md（类型 + 强度 + 趋势；重评旧档判断）
- **§6 核心新论点** → thesis.md（逐家拆解 + 受益侧传导 + 周期性 vs 结构性二分判定 + 反驳点）
- **§7 AI / 概念潜力** → thesis.md（分维度，每维度结尾打 `【真敏感】`/`【蹭概念】` + 一句理由；区分产品层 vs 业绩层；
  未兑现概念不许进 §9 的 owner earnings 基础）
- **§8 周期定位** → thesis.md（周期顶还是结构性新台阶？正反信号对冲）
- **§9 估值（场景加权）** → valuation.md（见 §3 机制）
- **§10 评级决策** → index.md（期望内在价值 vs 实时市值 → 评级 + 买点/卖点阈值；相对旧档是否翻转）
- **§11 关键风险 Top 3-5 + 监控指标/卖出触发器** → index.md（带硬阈值；复盘旧档触发器现状）
- **§12 数据来源 & 局限** → sources.md（逐条列联网来源含日期 + 已知局限 + "不构成投资建议"）

节名/侧重可随标的调整，但 §6 + §9 + §10 是骨干，不可省。重做档另须写"相对旧档变化清单"
（逐条列旧档口径 vs 最新事实 + 变化方向，落 valuation.md 末尾）。

## 3. 场景加权估值机制

三情景各定**正常化 owner earnings 口径** + **合理倍数** + **概率**：

| 情景 | 逻辑 | 正常化利润 | 倍数 |
|------|------|-----------|------|
| 结构性重估 bull | 新论点不可逆 → 高毛利可持续 → 护城河升级 | 上修（仍低于周期顶） | 上修 |
| 基准 base | 仅一轮常规周期，穿越周期归一化 | 周期均值 | 商品档 10-12x |
| 空头 bear | 旧逻辑（商品陷阱/配额收缩）依旧 | 周期底 | 低 |

铁律：
- **正常化利润绝不取财报顶部年化**；三档都应低于顶部年化。
- 概率每档挂一句赋权理由，引 §6/§8 证据；期望内在价值 = Σ(情景 × 概率)，Σ概率 = 100%（自检算术）。
- 安全边际 = (期望内在价值 − 实时市值) / 实时市值；实时市值用 Phase A 采证真实值。必要时对 bull 单独压力测试。
- **重要联营/合营 → SOTP 拆分**：该权益单独估值（市值×持股或贡献利润给低倍数），主业 owner earnings 剔除
  联营投资收益 + 一次性项目；期望内在价值 = 主业场景加权 + 联营 SOTP。
- **跨币种标的币种统一**：市值币种 ≠ 财报币种时（港股 HKD 市值 / RMB 利润），场景加权前先按当期汇率把正常化
  利润折到市值币种，三档/期望值/安全边际全程同币种，§9 注明汇率假设。
- **bull 增长证据包门控**（命中成长 lens 必算）：bull 概率与倍数上修须由 (a) 扩产达产确定性、(b) 客户 capex/
  出货能见度、(c) TAM 跑道 三要素支撑，逐项标【硬/软/缺】；硬证据越少 bull 概率越要封顶（三项全软 → ≤20%）。
  反之三项全硬的结构性成长股，base 可适度脱离纯周期均值（用穿越周期的成长中枢）。
- **倍数被迫破框架 = 该档每股价值本身没有支撑，回查隐含 ROE 而非抬倍数**：某档要给到 buffett 倍数框架之外
  （周期/衰退型 <8×、窄护城河 8-12×）才凑得出"像样"的数字时，先算该档隐含 ROE = 正常化 owner earnings ÷
  当期净资产，与风险对应的股权成本比（高杠杆/Altman Z 低/无股息 ≥12%）。隐含 ROE 低于股权成本 → 公允 PB
  在 1× 附近。修法是按各档隐含 ROE 重排整条 PB 阶梯（保持 bear<base<bull），超框架倍数一律降格进 §10 压力
  测试并逐行标「❌破框架」。症状：bull 降回框架内倍数后出现 bull < base → 利润法整体失效，三档改以资产法为
  主锚、利润法作验证（轻资产软件股不适用，见 memory `rim-ironlaw-not-for-asset-light-software`）。

## 4. 质量红线（审查重点）

1. **联网而非凭记忆**：知识截止之后的供需/报价/业绩进展一律实时核实；硬软证据措辞区分（"官方 EOL" vs "据媒体"）。
2. **供给侧/任何强论点必须双面**：最强反驳点前置写出（如"大厂退出是否可逆"），不写单边多头叙事。
3. **拒绝用周期顶利润定价**：正常化利润取穿越周期均值，绝不把财报顶部年化当常态。
4. **诚实面对"贵"**：PB/PE/市值高就老实算安全边际，必要时对最乐观情景压力测试；不用"护城河上修"稀释"价格太贵"。
5. **AI/概念维度分"产品 vs 业绩"**：有产品能力 ≠ 有业绩贡献；未兑现概念不许偷渡进估值；每维度打【真敏感】/【蹭概念】。
6. **数字可追溯**：每个关键数字能回指 evidence 片段（A1/A2/A3）或基线底稿；无裸断言、无造数。
   三路数字冲突以 A1 为准并在正文显式标注，不静默取一个。
7. **替换=物理删除旧档**：新档落定后该股历史 buffett 档 `git rm`，symmetric 反向链改指新档（Phase C 执行，
   写手/审查员不做）。
8. **看增长但不被增长拔高**：扩产达产 + 客户增长预期（具名客户优先 → 终端市场兑底）逐条标【硬/软/缺】；bull 由证据包门控；高增长不许稀释"贵"
   ——红线 3 的对偶，既防高估也防系统性低估真成长。

## 5. 审查输出格式（合并审查员）

单 prompt 内**先规格、后质量**两段，顺序不可反：
1. **规格符合性**：13 节齐全？frontmatter 合规且含数字字段与正文镜像？Σ概率=100% 且期望值算术对？AI 维度
   都打标？供给侧双面？数字可追溯？命中 lens 必查项均有回应（查无证据也要写明）？无范围外夹带？
   → `SPEC-COMPLIANT` 或问题清单（标 Critical/Minor）。
2. **分析质量**：内在一致、概率可辩护、"贵"是否诚实消化、增长是否诚实证据化、bull 赋权匹配证据强度、
   slop、buffett 框架贴合、监控指标可执行 → `APPROVED` / `APPROVED-WITH-NITS` / `CHANGES-REQUESTED` + 2-3 条做得好的点。

反向对称与 refs lint 归 Phase C 尚未运行，**不判为缺陷**；可指出哪些兄弟档 note 数字已被新档推翻。
