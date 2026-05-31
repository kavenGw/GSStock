# stock-deep-redo Playbook（撰写 / 审查 subagent 必读）

目录：
1. [frontmatter 字段集 + rating 枚举](#1-frontmatter)
2. [13 节文档结构](#2-13-节文档结构)
3. [场景加权估值机制](#3-场景加权估值机制)
4. [AI 维度标签法 → sector-lenses](#4-ai-维度标签法--见-sector-lensesmd-ai-节)
5. [联网采证清单](#5-联网采证清单)
6. [数据获取：实时行情 + 坑](#6-数据获取)
7. [lint 与 related_docs 对称](#7-lint-与-related_docs-对称)
8. [各阶段 subagent 派发提示骨架](#8-subagent-派发提示骨架)

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
- **§2 市场规模**（各业务线 TAM/SAM/SOM）
- **§3 盈利能力**（最新季报兑现 + 毛利率·ROIC 周期分析 + 涨价/需求弹性精算）
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

## 4. AI 维度标签法 → 见 sector-lenses.md「AI」节

AI 视角已统一到 `references/sector-lenses.md` 的 **AI（横切）** 节，避免两处维护。要点：逐维度写，
**每维度结尾打 `【真敏感】` 或 `【蹭概念】` + 一句理由**；区分**产品层 vs 业绩层**；
未兑现的概念不许进 §9 估值的 owner earnings 基础。命中 AI lens 时撰写 subagent 读该节的【撰写落点】。

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

## 8. subagent 派发提示骨架

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
跑 `--rewrite-blocks` + 双 lint exit 0 + `--check-orphans` 确认新档非孤儿；确认采证脚本已删、evidence.md 未 add；
提交终稿；汇报双 lint 退出码 + SHA + 状态。
