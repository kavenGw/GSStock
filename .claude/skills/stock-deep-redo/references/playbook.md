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
sector: semiconductor        # 11 项一级枚举之一，见 docs-and-portfolio.md
subsector: storage           # 二级自由起名
conviction_date: 2026-05-31  # YYYY-MM-DD（会被 yaml 解析成 date 对象）
themes:
- memory
- 供给侧
rating: watch                # 枚举仅 {core, config, watch, exclude}
watch_reason: ...            # rating=watch 必填；rating=exclude 必填 exclude_reason
thesis: 一句话投资论点
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

## 4. AI 维度标签法 → 见 sector-lenses.md「AI」节

AI 视角已统一到 `references/sector-lenses.md` 的 **AI（横切）** 节，避免两处维护。要点：逐维度写，
**每维度结尾打 `【真敏感】` 或 `【蹭概念】` + 一句理由**；区分**产品层 vs 业绩层**；
未兑现的概念不许进 §9 估值的 owner earnings 基础。命中 AI lens 时撰写 subagent 读该节的【撰写落点】。
**成长横切 lens 同理**：命中时读 sector-lenses.md「成长 / 扩产 / 客户增长」节的【必查清单】【撰写落点】，
其【撰写落点】§9 的「成长持续性证据包」对应本文件 §3 的 bull 门控铁律。

## 5. 联网采证清单

evidence.md 建议结构：核心论点逐家拆解（退出/扩产/政策的范围+时间表+动机+来源日期+硬软分级）、
报价/需求数据（带来源口径，注明机构间分歧）、标的最新动向（季报/路线图）、概念维度线索（标【实证/概念】）、
实时行情锚。纪律：英文+中文交叉验证；区分公司官方 vs 媒体 vs 分析师；找不到写"未找到公开证据"；
每个关键数字挂真实 URL + 日期；绝不编造。研究取数坑（新浪 IR PDF 无法解析等）见 `.claude/rules/data-fetch-conventions.md`。

## 6. 数据获取

**实时行情直连腾讯 HTTP**（一次性脚本，比走 create_app/service 快 5x+ 且无副作用）：
```python
import urllib.request
raw = urllib.request.urlopen('http://qt.gtimg.cn/q=sh603986', timeout=10).read().decode('gbk')
f = raw.split('"')[1].split('~')
print(f[1], f[3], f[39], f[45], f[46])  # name, price, PE_TTM, 市值(亿), PB
```
A股前缀：6 开头 `sh`、0/3 开头 `sz`。脚本跑完即删，不入库（`scripts/_xxx.py` 一次性脚本约定见 dev-conventions.md）。
若直连失败再用 `UnifiedStockDataService.get_realtime_prices([code], force_refresh=True)` 兜底。

**港股/美股行情**：腾讯 `q=hk01810` 港股字段索引**异于 A 股**（勿照搬 [39]PE/[45]市值/[46]PB，详见 `.claude/rules/data-architecture.md` 腾讯HTTP节）。
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

Phase C 必须将新档的估值数据同步到 `docs/stock-analytics/valuations.yaml`，供 `/valuations` 页面实时安全边际计算。

### 提取规则

从新档 §0（结论摘要）或 §9（估值）提取 **bear / base / bull 每股内在价值**：

1. **A 股**：正文中 `X.XX 元/股` 或 `每股 X.XX 元` 格式
2. **港股/美股**：正文中 `X.XX 港元/股` / `X.XX 美元/股`，或从 `内在价值 XXX 亿 / 股本 Y 亿股` 反推每股
3. **无法估值**：正文明确写"无法可靠估算"→ bear/base/bull 均填 `null`

从新档 §3（盈利能力）或 §11（风险/监控）提取 **dividend_yield（分红率）**：

1. **有明确分红率**：正文中 `分红率 X.X%` / `股息率 X.X%` / `dividend yield X.X%` → 填数值（如 `3.5`）
2. **无分红 / 未提及**：填 `null`（成长股 / 亏损股通常无分红）
3. **消费/传统股必填**：sector 为 `consumer` / `materials` / `energy` / `industrial` / `financial` 的标的，分红率是重要收益来源，Phase A 采证时须联网查最新年度分红（东财/同花顺/公司公告），Phase B 撰写时在 §3 或 §11 明确写出

### YAML 条目格式

```yaml
- stock_code: '000878'        # 字符串引号，防 YAML int 化丢前导 0
  stock_name: 云南铜业
  market: A                   # A / US / HK
  currency: CNY               # CNY / USD / HKD（与每股估值币种一致）
  sector: materials           # 一级 sector
  rating: watch               # core / config / watch / exclude
  bear: 6.50                  # 每股内在价值（原币），无法估算填 null
  base: 7.78
  bull: 8.87
  dividend_yield: 2.8         # 分红率（%），无分红填 null
  conviction_date: '2026-06-02'  # 字符串引号
  source_doc: sectors/materials/nonferrous/2026-06-02-云南铜业-buffett分析.md
  note: 可选备注（如"每股由市值反推股本，不确定性偏高"）
```

### 同步操作

1. **读取现有 valuations.yaml**（用 `yaml.safe_load`）
2. **按 `stock_code` 查找**：已存在 → 更新该条目；不存在 → 追加到末尾
3. **保持列表结构**：不要改变其他条目的顺序
4. **写回时用 `yaml.dump(..., allow_unicode=True, sort_keys=False)`** 保持中文可读 + 键顺序

### 特殊情况

- **港股代码格式**：`valuations.yaml` 中部分港股用 `03690`（5 位纯数字），部分用 `09992.HK`（带后缀）。
  新条目按 frontmatter `stock_code` 原样写入；若与已有条目 `stock_code` 不一致但实为同股，**以新档为准覆盖**。
- **市值口径→每股**：若正文只给市值内在价值（如 `~643 亿港元`）未给每股，需用 `市值 / 股本` 反推；
  股本从实时行情或正文推算（如 `市值 711 亿 / 现价 12.76 = 55.7 亿股`）。此时 `note` 字段标注
  `每股由市值/股价推算股本，不确定性偏高`。

## 9. subagent 派发提示骨架

每个 subagent 都要给**完整自包含上下文**（别让它读本计划/SKILL，直接喂它需要的）。骨架：

**Phase A 采证**：交代标的+代码+市场+今天日期+知识截止须联网；给 evidence.md 结构（见 §5）；
给 qt.gtimg.cn 取数脚本（见 §6）；强调证据分级+不造数；要求汇报证据强度 + 实时行情 + 状态。

**Phase B 撰写**：要求先 `Skill buffett`；给 evidence.md 路径 + 基线底稿路径；给 frontmatter 模板（§1）+
13 节结构（§2）+ 场景加权机制（§3）+ 命中 lens 的【撰写落点】（sector-lenses.md）+ 7 条质量红线（SKILL.md）；
给关键事实锚（实时市值/PE/PB + 证据硬软分级 + 任何需纠正的错误假设）；要求只跑 frontmatter lint 后提交；汇报评级+期望内在价值+安全边际+SHA+状态。

**规格审查**（read-only）：给交付物+spec/playbook+evidence 路径；给逐项核对清单（13 节/frontmatter/Σ概率=100%
且期望值算术/AI 标签/供给侧双面/数字可追溯/无范围外夹带）；要求输出 SPEC-COMPLIANT 或分类问题清单（缺失/夹带/造数）。

**质量审查**（read-only）：给交付物+evidence 路径；给质量维度（内在一致/概率可辩护/双面性/"贵"诚实度/AI 不拔高/
slop/buffett 贴合/监控可执行）；要求总判定 + 按严重度列问题 + 2-3 条做得好的点。

**Phase C 收尾**：先 `git status` 查遗留改动；**`git rm` 控制者传来的待删旧 buffett 档清单**；
**把所有 symmetric 指向被删档的反向链改指到新档或删条目**；给要补反向条目的被链档路径 + 反向 YAML；
跑 `--rewrite-blocks` + 双 lint exit 0 + `--check-orphans` 确认新档非孤儿；
**同步 valuations.yaml**（见 §8）：从新档提取 bear/base/bull 每股内在价值 + dividend_yield 分红率，upsert 到
`docs/stock-analytics/valuations.yaml`；确认采证脚本已删、evidence.md 未 add；
提交终稿；汇报双 lint 退出码 + valuations 同步状态 + SHA + 状态。

**派发坑：长文撰写 subagent 的 stream idle timeout**：Phase B（opus 写 300+ 行）可能中途报
`Stream idle timeout - partial response received`、文件 0 落盘（多发生在它还在读基线/取框架阶段）。
**恢复用 `SendMessage` 按返回的 `agentId` 续跑**（transcript 上下文保留），指令它"立即一次性 Write
完整篇、勿再读文件/联网检索、勿分段试探"，下一棒即完整落盘——**别重派新 subagent**（丢上下文 + 重复采证）。
续跑前先 `ls`/行数确认文件确实未生成，避免误判。

**派发坑：subagent 的"善后已完成"自报不可信，控制者必须亲验**：Phase A 采证 subagent 常声称
"一次性脚本已删""evidence 已落盘"甚至把自己写的 evidence.md 叙述成"orchestrator 预置的更完整版本"
（来源混淆）。实测脚本可能仍在 `scripts/_xxx.py`、需控制者手删。铁律：Phase A 返回后控制者**一律亲验**——
`ls scripts/ | grep <采证脚本名>` 确认真删、`Read` evidence.md 确认真实落盘且内容/来源可靠，
再放行 Phase B，不信 subagent 的总结措辞。
