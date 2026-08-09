# stock-deep-redo Playbook（撰写 / 审查 subagent 必读）

目录：
1. [frontmatter 字段集 + rating 枚举](#1-frontmatter)
2. [13 节文档结构](#2-13-节文档结构)
3. [场景加权估值机制](#3-场景加权估值机制)
4. [AI 维度标签法 → sector-lenses](#4-ai-维度标签法--见-sector-lensesmd-ai-节)
5. [联网采证清单](#5-联网采证清单)
6. [数据获取：实时行情 + 坑](#6-数据获取)
7. [lint 与 related_docs 对称](#7-lint-与-related_docs-对称)
8. [valuations.yaml 同步](#8-valuationsyaml-同步)
9. [各阶段 subagent 派发提示骨架](#9-subagent-派发提示骨架)

---

## 1. frontmatter

buffett 档必填字段（`scripts/_docs_schema.py:REQUIRED_FIELDS_BY_TYPE`）：
`doc_type, stock_code, stock_name, sector, subsector, themes, rating, conviction_date, thesis`

```yaml
---
doc_type: buffett
stock_code: '603986'        # 必须字符串引号，防 YAML int 化丢前导 0
stock_name: 兆易创新
sector: semiconductor        # 11 项一级枚举之一，见 docs-conventions.md
subsector: storage           # 二级自由起名
conviction_date: 2026-05-31  # YYYY-MM-DD（会被 yaml 解析成 date 对象）
themes:
- memory
- 供给侧
rating: watch                # 枚举仅 {core, config, watch, exclude}
watch_reason: ...            # rating=watch 必填；rating=exclude 必填 exclude_reason
thesis: 一句话投资论点
valuation:                   # 可选；Phase B 写入，Phase C 用 sync_valuations.py 同步到 valuations.yaml
  bear: 6.50                 # 每股内在价值（原币），无法估算填 null
  base: 7.78
  bull: 8.87
  currency: CNY              # CNY / USD / HKD，与每股估值币种一致
  dividend_yield: 2.8        # 分红率（%），无分红填 null
commodity: copper            # 可选，仅矿产/商品标的；枚举 copper|lithium（见 scripts/_docs_schema.py:COMMODITIES）
commodity_impact: positive   # 可选，仅矿产/商品标的；positive=上游资源/矿/锂盐（商品涨价利好）/ negative=下游买方/电池/消费（商品涨价是成本）/ neutral=中游冶炼（TC/RC 加工费驱动，铜价 pass-through）；同步写 valuations.yaml，供 /minerals 看板使用
related_docs:
- path: <相对路径>
  note: ...
  symmetric: true            # true 要求被链档补反向条目；不想补就 false
---
# <标题>

<!-- BEGIN related_docs (auto-generated from frontmatter, do not edit) -->
<!-- END related_docs -->
```

相对路径示例（务必按所在目录算）：
- storage 档（`sectors/semiconductor/storage/`）→ comps：`../../../comps/<file>.md`
- comps（`comps/`）→ storage 档：`../sectors/semiconductor/storage/<file>.md`
- 同目录互链：直接文件名

文件命名：`sectors/<sector>/<subsector>/YYYY-MM-DD-<股票名>-buffett分析.md`

## 2. 13 节文档结构

- **§0 结论摘要**（倒金字塔：新评级 + 期望内在价值 + 三情景概率各一句）
- **§1 能力圈 & 本次重审触发**（为何现在重做：哪些新变量；对比旧档结论）
- **§2 市场规模**（各业务线 TAM/SAM/SOM + 跑道长度：标的当前渗透率/份额距天花板多远）
- **§3 盈利能力**（最新季报兑现 + 毛利率·ROIC 周期分析 + 涨价/需求弹性精算 + 增长拆量价与增长质量：高增长是否伴随毛利改善）
- **§4 全球竞争力**（全球份额、细分龙头识别、vs 国际龙头差距）
- **§5 核心优势 / 护城河**（类型 + 强度 + 趋势；重评旧档判断）
- **§6 核心新论点**（如供给侧结构变化：逐家拆解 + 受益侧传导 + 周期性 vs 结构性二分判定 + 反驳点）
- **§7 AI / 概念潜力**（分维度，每维度打标签，见 §4 → sector-lenses.md「AI」节）
- **§8 周期定位**（当前是周期顶 还是 结构性新台阶？正反信号对冲）
- **§9 估值（场景加权）**（见 §3）
- **§10 评级决策**（期望内在价值 vs 实时市值 → 评级 + 买点/卖点阈值；说明相对旧档是否翻转）
- **§11 关键风险 Top 3-5 + 监控指标/卖出触发器**（带硬阈值；复盘旧档触发器现状）
- **§12 数据来源 & 局限**（逐条列联网来源含日期 + 已知局限 + "不构成投资建议"）

节的命名/侧重可随标的调整，但 §6（核心新论点）+ §9（估值）+ §10（评级）是骨干，不可省。

## 3. 场景加权估值机制

三情景，各定**正常化 owner earnings 口径** + **合理倍数** + **概率**：

| 情景 | 逻辑 | 正常化利润 | 倍数 | 概率 |
|------|------|-----------|------|------|
| 结构性重估 bull | 新论点不可逆 → 高毛利可持续 → 护城河升级 | 上修（仍低于周期顶） | 上修 | 证据强度定 |
| 基准 base | 仅一轮常规周期，穿越周期归一化 | 周期均值 | 商品档 10-12x | |
| 空头 bear | 旧逻辑（商品陷阱/配额收缩）依旧 | 周期底 | 低 | |

铁律：
- **正常化利润绝不取财报顶部年化**；三档都应低于顶部年化，体现穿越周期。
- 概率不能拍脑袋——每档挂一句赋权理由，引 §6/§8 的证据。
- 期望内在价值 = Σ(情景内在价值 × 概率)，Σ概率 = 100%（自检算术）。
- 安全边际 = (期望内在价值 − 实时市值) / 实时市值。必要时对最乐观 bull 单独再算一次安全边际做压力测试。
- 实时市值用 Phase A 采证的真实值，不用估。
- **重要联营/合营 → SOTP 拆分**：标的持有贡献可观投资收益的联营/合营企业（如亿纬持思摩尔 30.26%）时，该权益作独立资产单独估值（按其市值×持股或贡献利润给低倍数），且主业正常化 owner earnings 必须剔除联营投资收益 + 一次性项目；期望内在价值 = 主业场景加权 + 联营 SOTP。
- **跨币种标的（港股/美股）币种统一**：市值币种 ≠ 财报币种时（如港股市值计 HKD、财报利润计 RMB，接口 PE 为混合口径），
  场景加权前先把正常化利润按当期汇率折算到市值币种（如 RMB→HKD ~×1.08），三档与期望内在价值、安全边际全程同一币种，
  并在 §9 注明汇率假设。否则 Σ(内在价值×概率) 与市值不同币种，安全边际算错。
- **bull 情景增长证据包门控**（命中成长横切 lens 时必算）：bull 的概率与倍数上修必须由「成长持续性
  证据包」三要素支撑——(a) **扩产达产确定性**（产线已开工 / 设备到位 / 达产路线清晰=硬；仅规划=软）、
  (b) **客户 capex / 出货能见度**（具名客户公开 guidance=硬；终端市场总量=中；卖方一致预期=软）、
  (c) **TAM 跑道**（渗透率低、空间大）。三项里硬证据越少，bull 概率越要封顶（如三项全软 → bull 概率
  ≤ 20%）。这是「拒绝周期顶定价」的**对偶约束**：既不许用周期顶利润定价（防高估），也不许在缺乏增长
  证据时给 bull 高权重（防被叙事拔高）。**反过来**：三项全硬的结构性成长股，base 情景也可适度脱离纯
  周期均值（用穿越周期的成长中枢），避免系统性低估真成长。
- **倍数被迫破框架 = 该档每股价值本身没有支撑，回查隐含 ROE 而非抬倍数**：若某档（多为 bull）要给到
  buffett 倍数框架之外（周期性/衰退型 <8×、窄护城河 8-12×）才凑得出"像样"的每股内在价值，**不要抬倍数**——
  先算该档的**隐含 ROE = 该档正常化 owner earnings ÷ 当期净资产**，与标的风险等级对应的股权成本比（高杠杆/
  Altman Z 低/无股息的标的 ≥12%）。隐含 ROE 低于股权成本 → 残值收益模型给出的公允 PB 就在 1× 附近，
  原先那个"像样"的数字本就无严谨路径支撑。**修法是按各档隐含 ROE 把整条 PB 阶梯重排**（保持 bear<base<bull
  单调），而不是把超框架倍数写进 §9.3 官方加权表；超框架倍数一律降格进 §10 压力测试并逐行标「❌破框架」。
  症状识别：把 bull 降回框架内倍数后出现 **bull < base**（利润法失效而资产法仍在托底），即是此坑——
  说明该股的利润法整体失效，三档都应改以资产法为主锚、利润法作验证。

## 4. AI 维度标签法 → 见 sector-lenses.md「AI」节

AI 视角已统一到 `references/sector-lenses.md` 的 **AI（横切）** 节，避免两处维护。要点：逐维度写，
**每维度结尾打 `【真敏感】` 或 `【蹭概念】` + 一句理由**；区分**产品层 vs 业绩层**；
未兑现的概念不许进 §9 估值的 owner earnings 基础。命中 AI lens 时，该节的【撰写落点】**由控制者原文内联进 Phase B 提示**（§9.1 铁律，写手不自读 sector-lenses.md）。
**成长横切 lens 同理**：【必查清单】内联进 A3 采证提示、【撰写落点】内联进 Phase B 提示；
其【撰写落点】§9 的「成长持续性证据包」对应本文件 §3 的 bull 门控铁律。

## 5. 联网采证清单

三份 evidence 片段的建议结构（Phase A 三路各写各的，见 §9）：**A1 数据锚**=实时行情锚 + 最新财报 + 逐月交付 +
可比公司估值表；**A2 论点**=核心论点逐家拆解（退出/扩产/政策的范围+时间表+动机+来源日期+硬软分级）+
报价/需求数据（带来源口径，注明机构间分歧）+ 标的最新动向（季报/路线图）；**A3 lens**=命中 lens 必查清单逐条 +
概念维度线索（标【实证/概念】）。纪律（三路通用）：英文+中文交叉验证；区分公司官方 vs 媒体 vs 分析师；
找不到写"未找到公开证据"；每个关键数字挂真实 URL + 日期；绝不编造。研究取数坑（新浪 IR PDF 无法解析等）
见 `.claude/rules/data-fetch-conventions.md`。

## 6. 数据获取

**实时行情直连腾讯 HTTP**（一次性脚本，比走 create_app/service 快 5x+ 且无副作用）：
```python
import urllib.request
raw = urllib.request.urlopen('http://qt.gtimg.cn/q=sh603986', timeout=10).read().decode('gbk')
f = raw.split('"')[1].split('~')
print(f[1], f[3], f[39], f[45], f[46])  # name, price, PE_TTM, 市值(亿), PB
```
A股前缀：6 开头 `sh`、0/3 开头 `sz`。脚本跑完即删，不入库（`scripts/_xxx.py` 一次性脚本约定见 dev-environment.md）。
若直连失败再用 `UnifiedStockDataService.get_realtime_prices([code], force_refresh=True)` 兜底。

**港股/美股行情**：腾讯 `q=hk01810` 港股字段索引**异于 A 股**（勿照搬 [39]PE/[45]市值/[46]PB，详见 `.claude/rules/data-fetch-conventions.md` 腾讯HTTP节）。
港股/美股市值、PE(TTM)、PB、52 周区间优先用 WebFetch `stockanalysis.com/quote/hkg|nasdaq/<code>/statistics/` 或 Yahoo，**交叉验证 2 源**（市值口径常分歧）。
亏损标的 PE(TTM)=N/A，估值锚改看 PS / PB / Forward PE。**市值=现价×总股本自洽校验**是兜底（曾靠此兜住港股字段索引误读）。

**多年财务时序**：`ak.stock_financial_abstract_ths(symbol, indicator="按年度")`（全市场稳定）。
**PE/PB 5 年分位**：`ak.stock_zh_valuation_baidu(symbol, indicator=..., period="近5年")`。
**主营构成定 sector**：`ak.stock_zygc_em(symbol='SZ300757')`。akshare 限流/失效坑见 data-fetch-conventions.md。

**Windows**：`PYTHONIOENCODING=utf-8`；写中文文件显式 `encoding='utf-8'`；别用 heredoc，用 Write→脚本→python 跑；
管道可能吞 stdout，验证脚本改写文件再 Read。

## 7. lint 与 related_docs 对称

```bash
python scripts/lint_docs_frontmatter.py            # frontmatter 校验
python scripts/lint_docs_refs.py                   # related_docs 路径 + 反向对称
python scripts/lint_docs_refs.py --rewrite-blocks  # 重生所有文档顶部 markdown 块
```
退出码 0 = 全过。`symmetric: true` 的 related_docs 条目要求被链文档有反向条目，否则 refs lint 报错——
Phase C 给被链档补反向条目后跑 `--rewrite-blocks` 再跑两支 lint 确认 exit 0。

## 8. valuations.yaml 同步

估值数字由 **Phase B 撰写时写进 buffett 档 frontmatter 的 `valuation` 块**（见 §1 模板），
Phase C 用确定性脚本 upsert 到 `docs/stock-analytics/valuations.yaml`，**不再用 LLM 从正文提取**。

### frontmatter valuation 块字段

| 字段 | 含义 | 缺省 |
|------|------|------|
| `bear`/`base`/`bull` | 三情景每股内在价值（原币） | 无法估值填 `null` |
| `currency` | `CNY`/`USD`/`HKD`，与每股估值币种一致 | 缺省时脚本按市场推断 |
| `dividend_yield` | 分红率（%） | 无分红填 `null` |

撰写纪律：
- 三档每股内在价值与正文 §0/§9 一致；分红率与 §3/§11 一致（规格审查核对镜像同步）。
- **消费/材料/能源/工业/金融**标的分红率是重要收益来源，Phase A 须联网查最新年度分红（东财/同花顺/公司公告），Phase B 在 §3/§11 写出并填入 `valuation.dividend_yield`。
- **港股/美股**每股估值用对应币种（HKD/USD）；A+H 选定口径由 frontmatter `stock_code` 本身体现，`currency` 随之。

### 同步操作（Phase C）

```bash
PYTHONIOENCODING=utf-8 rtk python scripts/sync_valuations.py --stock-code <code>
```

脚本扫 `*buffett*.md` 的 frontmatter，flatten `valuation` 块为扁平条目（`market` 按 `stock_code` 推断），
按 `stock_code` upsert valuations.yaml（已存在→更新、不存在→追加），**不删除未匹配的存量条目**。
无参数则全量扫描 upsert。详见 `scripts/sync_valuations.py`。

### quality 质地星级（valuations.yaml 专属字段，按需覆写）

估值页 `/valuations`「质地」列：★1-5 星，**抛开当前价格谈公司本身好坏**（与 bear/base/bull 的价格维度正交）。

- **不在 frontmatter**，是 valuations.yaml 条目的可选整数字段（1-5）。**多数标的不必写**：渲染层缺省按 `rating` 现算（`core`→5 / `config`→4 / `watch`→3 / `exclude`→2，未知→3）。
- **何时显式写（覆写默认）**：当**业务质地与 rating 隐含星级背离**时——典型即红线 #4「诚实面对贵」的对偶面：一家护城河顶级的好公司**仅因当前太贵**被你评 `watch`/`config`，rating 现算只给 3/4 星，会把"好公司"误显示成"一般"。此时在该条目显式写 `quality: 5`，让质地列把「好公司」与「便宜」分开。反向亦然：平庸生意因超跌进 `config`（现算 4 星）但质地实差 → 写 `quality: 2`。**★1 星保留给"质地很差"**。
- **怎么写**：先跑 `sync_valuations.py` 建/更新条目，再在 valuations.yaml 该条目手工加一行 `quality: N`（1-5）。`sync_valuations.upsert` 已把 `quality` 列入保留名单（同 `note`），后续任何 re-sync **不会冲掉**手写值。
- **怎么不写**：质地与 rating 隐含星级一致时（绝大多数情形）留空即可，靠现算，避免 167 条 yaml 噪音。

## 9. subagent 派发提示骨架

每个 subagent 都要给**完整自包含上下文**（别让它读本计划/SKILL，直接喂它需要的）。骨架：

### 9.0 汇报文件协议（所有 subagent 通用，硬约定）

**问题**：实测多数 subagent 完成后只发 idle 通知、不回传汇报正文，控制者须逐个 `SendMessage` 追要，
每次一个完整往返（实测一轮吃掉约 5 分钟）。在 prompt 里写"最终回复必须包含完整正文"**已被证明无效**
（审查 subagent 收到该指令后仍先回 idle）——靠措辞加压治不了，必须改机制。

**约定**：每个 subagent 的派发 prompt 末尾**必须**包含以下要求，一字不可省：

> 汇报**必须**用 Write 写到 `.omc/artifacts/<股票名>-<日期>-<阶段标识>-report.md`，写完才结束。
> 文件头两行固定为耗时戳（开工时与收工时各跑一次 `date "+%Y-%m-%d %H:%M:%S"` 取值）：
> ```
> start: YYYY-MM-DD HH:MM:SS
> end: YYYY-MM-DD HH:MM:SS
> ```
> 其后是汇报正文。消息回传是可选冗余通道，不是交付方式。

**阶段标识固定六种**：`phaseA1` / `phaseA2` / `phaseA3` / `phaseB` / `review` / `phaseC`。
**异常轮次**：追派的 opus 复核审查员写 `review-2`（标识仍归入审查段），Phase B 返修/续跑写 `phaseB-2`；
耗时账里并入对应段落并注明轮次，例：`审查 5.5 + 复核 2.0`。基本六标识不变。

**控制者侧**：不等消息、不追要报告，subagent 结束后直接 `Read` 对应文件。收尾时把六个 start/end
汇总成一行耗时账报给用户（这是"提速是否真的发生"的唯一可证伪依据）。

**为什么顺带加固了可信度**：subagent 的口头汇报本就不可信（已有教训：Phase A 曾自报"一次性脚本已删"
而实际未删）。落成文件后，控制者的亲验对象从"它说了什么"变成"它写了什么 + 我自己查到什么"。

### 9.1 内联铁律：控制者摘原文，不给路径让 subagent 自读

**问题**：让 subagent 自己去读整份参考文件，既费它的墙钟（读+导航往返），又有挑错节的风险。
实测一轮里写手自读了 6 份材料，其中两份是纯浪费：兄弟档 791 行（真正有用的仅 3-5 条口径）、
sector-lenses.md 261 行（命中的仅约 70 行）。

**铁律**：以下内容**由控制者摘成原文内联进 prompt**，**不许给文件路径让 subagent 自读**——

| 内容 | 内联到 | 不许的做法 |
|---|---|---|
| 命中 lens 的【必查清单】 | A3 采证提示 | ❌ "命中 AI + 成长 lens，去读 sector-lenses.md" |
| 命中 lens 的【撰写落点】【双面必答】【监控指标模板】 | Phase B 提示 | ❌ 同上 |
| 兄弟档口径要点（3-5 行） | Phase B 提示 | ❌ "参考兄弟档 xxx.md 的质量水位" |
| 命中 lens 的【必查清单】【双面必答】 | 合并审查提示 | ❌ "去 sector-lenses.md 对照命中节" |

**仍由 subagent 自读的**（必要，压不掉）：evidence 片段（事实源）、旧档（翻转对照）、
本 playbook（规格）、`Skill buffett`（框架）。

**这条不是新约定，是把既有约定的漏洞堵上**：SKILL.md「先做」本就写着"把命中节摘出注入"，
但措辞允许控制者只报 lens 名字了事——实测控制者确实这么偷懒过。现措辞不留"指路"这个选项。

**Phase A 采证（3 个并行，均 opus）**：三份 prompt 都要交代标的+代码+市场+今天日期+知识截止须联网、
证据分级+不造数、§9.0 汇报文件协议（标识分别 `phaseA1`/`phaseA2`/`phaseA3`）。各自差异：

- **A1 数据锚**：给 qt.gtimg.cn 取数脚本（见 §6）**并强调港股字段索引异于 A 股、须 dump 全串自辨 +
  市值=现价×总股本自洽校验 + 双源交叉**；要它产出 `-evidence-A1-数据锚.md`（行情锚 / 最新财报 /
  逐月交付 / 可比公司估值表）；明告它**是本轮所有硬数字的唯一权威源**，另两路会让位于它。
- **A2 论点验证**：给旧档核心论点清单 + 本次重审触发的新变量；要它逐条联网核实、每条给
  证据（硬/软/缺）+ URL + 日期 + **反驳点**，产出 `-evidence-A2-论点.md`；
  **明告它数字以 A1 为准、自己以定性表述为主**。
- **A3 lens 专项**：**把命中 lens 的【必查清单】原文内联进 prompt**（不是给文件路径让它自己去读，
  见 §9.1），要求逐条核实、查不到明写"未找到公开证据"不许跳过，产出 `-evidence-A3-lens.md`。

**不派合并 agent**（合并把省下的时间串回去）；**"相对旧档变化清单"移交 Phase B**（需全局视野）。

**Phase B 撰写（1 个 opus，不拆）**：要求先 `Skill buffett`；给**三份 evidence 片段路径**（A1/A2/A3）+ 旧档路径；
给 frontmatter 模板（§1）+ 13 节结构（§2）+ 场景加权机制（§3）+ **8 条**质量红线（由控制者从 SKILL.md「质量红线」节**原文内联**，不给路径）；
**按 §9.1 内联铁律直接贴入**命中 lens 的【撰写落点】【双面必答】【监控指标模板】原文 + 兄弟档口径要点 3-5 行
（**不给 sector-lenses.md / 兄弟档的路径让它自读**）；给关键事实锚（A1 的市值/PB/PS/股本/汇率 + 硬软分级 +
需纠正的旧档错误假设）；交办两项独有活——**写"相对旧档变化清单"**、**标注 A2/A3 与 A1 的数字冲突**；
要求只跑 frontmatter lint、**不 git add/commit**；汇报按 §9.0 写文件（标识 `phaseB`），内容含评级 +
期望内在价值 + 安全边际 + 最脆弱论点自评。

**合并审查**（read-only，sonnet）：给交付物路径 + `references/playbook.md` 路径 + 三份 evidence 片段路径 +
**控制者内联的 8 条质量红线与命中 lens 必查清单原文**；要求单 prompt 内先规格后质量两段输出——
规格段给逐项核对清单（13 节/frontmatter 含 valuation 块与正文一致/Σ概率=100% 且期望值算术/AI 标签/供给侧双面/
数字可追溯/无范围外夹带）输出 SPEC-COMPLIANT 或问题清单；质量段给质量维度（内在一致/概率可辩护/双面性/"贵"诚实度/
AI 不拔高/增长证据化/slop/buffett 贴合/监控可执行）输出 APPROVED / APPROVED-WITH-NITS / CHANGES-REQUESTED + 2-3 条做得好的点。
控制者收到 CHANGES-REQUESTED 或 Critical 规格问题时追派 1 个 opus 只读审查员复核该结论再放行修复。
APPROVED-WITH-NITS 的 Minor 可修后控制者直接核验。
**汇报按 §9.0 写文件（标识 `review`），两段正文全文写进文件**——审查是"只回 idle"的重灾区。

**Phase C 收尾**：先 `git status` 查遗留改动；**`git rm` 控制者传来的待删旧 buffett 档清单**；
**把所有 symmetric 指向被删档的反向链改指到新档或删条目**；给要补反向条目的被链档路径 + 反向 YAML；
跑 `--rewrite-blocks` + 双 lint exit 0 + `--check-orphans` 确认新档非孤儿；
**同步 valuations.yaml**（见 §8）：运行 `sync_valuations.py --stock-code <code>` 确定性 upsert（估值数字已在 frontmatter `valuation` 块）；确认采证脚本已删、三份 evidence 片段与六份 report 均未被 git add；
提交终稿；汇报按 §9.0 写文件（标识 `phaseC`），内容含双 lint 退出码 + valuations 同步状态 + SHA +
`git show --stat HEAD` 文件清单 + 遗留检查结论（三份 evidence 片段与六份 report 均未被 add）。

**派发坑：长文撰写 subagent 的 stream idle timeout**：Phase B（opus 写 300+ 行）可能中途报
`Stream idle timeout - partial response received`、文件 0 落盘（多发生在它还在读基线/取框架阶段）。
**恢复用 `SendMessage` 按返回的 `agentId` 续跑**（transcript 上下文保留），指令它"立即一次性 Write
完整篇、勿再读文件/联网检索、勿分段试探"，下一棒即完整落盘——**别重派新 subagent**（丢上下文 + 重复采证）。
续跑前先 `ls`/行数确认文件确实未生成，避免误判。

**派发坑：subagent 的"善后已完成"自报不可信，控制者必须亲验**：Phase A 采证 subagent 常声称
"一次性脚本已删""evidence 已落盘"甚至把自己写的 evidence.md 叙述成"orchestrator 预置的更完整版本"
（来源混淆）。实测脚本可能仍在 `scripts/_xxx.py`、需控制者手删。铁律：Phase A 返回后控制者**一律亲验**——
`ls scripts/ | grep <采证脚本名>` 确认真删、逐个 `Read` 三份 evidence 片段（A1/A2/A3）确认均真实落盘且内容/来源可靠，
再放行 Phase B，不信 subagent 的总结措辞。
