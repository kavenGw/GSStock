---
doc_type: buffett-section
stock_code: '02513'
stock_name: 智谱
section: sources
---

# 智谱 — §12 数据来源 & 局限

> 采证日 2026-09-01（HKT 上午，港股未开盘）｜行情锚 2026-08-31 收盘。
> 证据分级：【硬】公司公告/财报/交易所披露/官方声明｜【软-高】多源交叉的媒体转述公告口径｜【软】单源或二手转述｜【缺】未找到公开证据。

---

## 12.0 本档最大方法论局限（必读，与 [index.md](index.md) 口径声明重复写出）

**港交所披露易（hkexnews）1H2026 中期业绩公告 PDF 原文，经以下七条路径全部未取到：**

| # | 路径 | 结果 |
|---|---|---|
| 1 | `www1.hkexnews.hk/search/titlesearch.xhtml`（中/英，stockId=-1，title=智譜，日期 20260830–20260901） | 返回「沒有找到訊息 / 共有 0 紀錄」（JS 驱动页，服务端渲染无结果） |
| 2 | `www1.hkexnews.hk/search/titleSearchServlet.do` 直连 | 返回 100 条中无 02513 |
| 3 | `www1.hkexnews.hk/listedco/listconews/sehk/2026/0831/` 目录列举 | HTTP 404 |
| 4 | `stockn.xueqiu.com/02513/*.pdf` 镜像 | 仅命中 20260414 / 20260602 两份旧件，无 0831 |
| 5 | `xueqiu.com/S/02513` 公告列表（控制者） | WAF 加密返回，不可解析 |
| 6 | hkexnews 标题搜索 / 0831 日期索引（控制者独立重试） | 同 1、3，无结果 |
| 7 | euroland CDN（控制者） | 未命中 |

> ### ⚠️ **因此：本档全部 1H2026 财务数字均为多源交叉的【软-高】证据，无页码、无审计原文。**
> 每个数字至少两源交叉且内部算术自洽（见 12.2 交叉验证闭环），但**证据级别不是【硬】**。控制者若需【硬】级引用，须由人工从披露易取 PDF 后回填。**这是本档最大的方法论局限，直接影响 [valuation.md](valuation.md) 全部三档的可靠性等级——本档的确定性等级因此被定为"低"。**

### 级别 1【缺】清单（影响裁决，必须由人工从披露易 PDF 回填）

| # | 缺失项 | 影响的判断 |
|---|---|---|
| 1 | **1H2026 中期业绩公告 / 中期报告 PDF 原文与页码** | 全部财务数字降级为【软-高】 |
| 2 | **2026-06-30 现金及现金等价物具体金额** | pro-forma 现金 269 亿 CNY 只能给区间中枢；[valuation.md §9.5](valuation.md) 现金地板检验的起点 |
| 3 | **2026-06-30 净资产 / 权益总额 / pro-forma 权益** | PB 无法计算（叠加优先股列金融负债失真，本档一律禁用 PB / Altman Z） |
| 4 | **合同负债 / 在手订单** | **旧档触发器 2b 的第二半句直接依赖此项**；亦是"API 是否为真订阅"的唯一会计证据（[§6.1](thesis.md)）；bull 门控要素 (b) 判"弱"的直接原因 |
| 5 | **1H2026 前五大客户集中度与单一最大客户占比** | 收入质量。可比历史：FY2024 前五大 45.5%、单一最大客户 19.0% |
| 6 | **关联交易附注**（美团/腾讯/蚂蚁/清华系是否为客户或供应商） | 无法排除关联收入；"9 家头部互联网公司深度集成 GLM"这条多头论据因此不能作数 |
| 7 | **审计师身份与中期审阅意见类型** | 中期业绩通常未经审计仅经审计委员会审阅，但未取得原文确认。任何非标意见 → 立即重估 |
| 8 | **Coding Plan 付费开发者数** | **旧档触发器 3 附条款（一级警报）因此无法裁决**。替代指标（MaaS 用户 740 万、付费日活 +603%）**不得冒充**该项 |
| 9 | **本地化部署分部毛利率（1H2026 与 1H2025）** | 无法精确拆分 mix 效应与单位成本效应的各自贡献 |

### 级别 2【缺】清单（影响完整性，不改变裁决方向）

1H2026 销售及营销费用与行政开支明细（销售成本 7.02 亿为倒算非披露）｜1H2026 一次性项 1.07 亿的逐项拆分（股份支付/汇兑/政府补助各多少）｜**1GW 数据中心投资总额、时间表、资金结构、选址、芯片供应商名单**｜中科加禾精确对价、北京红钻科技收购对价｜**2026-08 下旬南向资金逐日净流向**（触发器 1 的监测数据）｜当前自由流通盘精确比例｜美国实体清单 2026-08 后状态｜1H2026 平均回款天数（旧档 112 天）｜Claw Plan 订阅数｜MiniMax 总股本与精确收盘价（其市值为媒体口径，未做自洽校验）｜**Artificial Analysis 官网原始榜单快照**（技术排名全部为二手转述）｜2026-08-01 后新增具名大客户公告｜A 股 IPO 是否已向上交所递交/获受理｜沙利文 2026 版中国大模型 TAM｜Anthropic/OpenAI 2026-08 一级估值｜金山办公与美股 AI 可比的同口径 PS。

> **两个"未找到"须特别标注为真实缺口，不得当作"无风险"处理**：① 1GW 数据中心的投资总额与资金结构；② A 股 IPO 的递交/受理进度。**"未找到公开证据"不是"没有进展"的等价物。**

---

## 12.1 行情与股本（【硬】，交易所口径）

| 项 | 值 | 来源 |
|---|---|---|
| 收盘价 / 时戳 | **1,195.000 HKD** / 2026-08-31 16:08:50 HKT | 腾讯行情 `q=hk02513` 字段 [3]/[30] |
| 涨跌 | **+9.63%**；当日高/低 1,195.000 / 1,038.000 | [32]/[33]/[34] |
| 成交量 / 成交额 | 11,083,749 股 / 127.55 亿 HKD | [36]/[37] |
| **总股本** | **465,623,090 股** | [69] |
| **总市值** | **5,564.196 亿 HKD** | [45] |
| 已上市 H 股（**不是自由流通盘**） | 241,094,605 股（51.78%） | [70] |
| 52 周高 / 低 | 2,980.000 / 116.100 HKD | [48]/[49] |
| PE-TTM | −106.97（亏损，**N/A**） | [57] |
| 股息率 | 0.00% | [47] |

**quote_guard 校验（CLI，exit 0 通过）**：`1,195.000 × 465,623,090 = 556,419,592,550 HKD`，与 [45] 完全一致，**价×股本偏差 0.00%** ✅。流通市值交叉验 `1,195.000 × 241,094,605 = 2,881.081 亿` 与 [44] 一致 ✅。
> 守卫的"竞价参考价"警告为**误报**：16:08:50 落在港股 16:00–16:10 收市竞价时段（CAS），是当日**收盘定盘价**而非开盘集合竞价参考价，成交量/额远超零成交阈值，价格自洽。**本档明确标注为「2026-08-31 收盘价」，非盘中价、非 9-01 价。**

**汇率**：HKD/CNY = **0.8572**、USD/CNY = **6.7439**（xe.com / Investing.com，2026-09-01 取数）【软】——非官方中间价，仅用于口径换算，误差 <1% 不影响裁决方向。**旧档 0.865 / 6.79 已作废。**

---

## 12.2 1H2026 中期业绩（【软-高】，多源交叉，无页码）

**来源（每个数字至少两源交叉）**：
- IT之家〈智谱 2026 年上半年归母亏损 20.71 亿元，同比亏损收窄 12.1%〉 https://www.ithome.com/0/996/626.htm （2026-08-31）
- 星島頭條〈智谱中期经调整多蚀12% 收入劲增4倍 每投入1元算力对应收入升14倍〉 https://www.stheadline.com/zh-hans/stock-market/3610186/ （2026-08-31）
- 禁闻网转路透〈MiniMax、智谱发布中期业绩〉 https://www.bannedbook.org/bnews/itnews/20260831/2354586.html （2026-08-31）
- 5oops〈上半年收入增长近 400%，API 收入占比近九成〉 https://5oops.com/258051.html （2026-08-31）
- 路透 / CNBC 英文口径：H1 revenue RMB 953.9m = US$141.96m, +400%；net loss RMB 2.0bn
- 财中社 https://m.caizhongshe.cn/article-8575014945158064915.html ；钛媒体 https://www.tmtpost.com/8039657.html （现金与 capex）
- DoNews〈智谱正在穿越大模型最危险的那段路〉 https://www.donews.com/article/detail/8114/94715.html （招股书 1H2025 经调整口径）
- 我的驱动〈单位 token 推理成本较年初下降 80%〉 https://news.mydrivers.com/1/1147/1147681.htm ；36氪 https://www.36kr.com/p/3956946155355267

**交叉验证闭环（三条独立路径互证，是本档接受【软-高】的依据）**：
1. **1H2025 经调整亏损**：DoNews 引招股书披露「净亏损 17.51 亿」，与从 YoY 反推的 19.64 ÷ 1.121 = **17.52 亿**吻合到 0.01 亿。
2. **1H2025 IFRS 亏损**：20.71 ÷ (1 − 0.121) = **23.56 亿**，与旧档记录的 −23.58 亿差 0.02 亿（四舍五入）。
3. **毛利率自洽**：26.4% + 23.6pct = **50.0%** ✅；**研发自洽**：21.31 ÷ 1.336 = **15.95 亿** ✅；**收入自洽**：9.539 ÷ 1.909 = 4.997 → **+399.7%** ✅。

---

## 12.3 论点面与 lens 采证来源

**技术排名（全部【软】，AA 官网原始榜单未直接取到）**：知乎〈GLM-5.3 在 AA 14 模型对比中综合第 5，Agentic 第 2〉 https://zhuanlan.zhihu.com/p/2074917712191547315 ｜知乎问答 https://www.zhihu.com/question/2073339278076142673 ｜潮起网〈智谱 VS DeepSeek〉 https://www.ichaoqi.com/guandian/2026/0817/85440.html ｜网易（DeepSeek V4-Pro 53 分） https://www.163.com/dy/article/L4I2SJ1N0518EIBL.html ｜新浪财经（GLM-5.3 发布） https://finance.sina.com.cn/tech/roll/2026-08-14/doc-ininhhrr2869922.shtml ｜腾讯新闻（三模型能力分域横评） https://view.inews.qq.com/a/20260815A060H600 ｜AIDeepThink（GLM-5.3 API 定价持平） https://aideepthink.cn/news/20260820-glm53-api

**定价权与提价（【硬/公司公告】+【软】）**：21经济网（张鹏业绩会原话「涨价 83% 调用量 +400%」「算力供给约束和瓶颈」） https://www.21jingji.com/article/20260401/herald/7f61c12ec2c31a516281317359ad5cb3.html ｜财联社（Coding Plan 改版） https://m.cls.cn/detail/2287878 ｜网易科技 https://www.163.com/tech/article/L369B15G00097U7T.html ｜腾讯云社区 https://cloud.tencent.com/developer/article/2718987

**ARR 口径（本档首要风险的证据链）**：36氪独家（US$1bn，**自标 RRR 口径、可能高估、未经官方确认**） https://36kr.com/p/3898662052693894 ｜新浪科技 https://finance.sina.com.cn/tech/digi/2026-07-17/doc-iniianxe7365712.shtml ｜钛媒体（公司自述 ARR 约 17 亿 CNY，2026-03） https://www.tmtpost.com/7947142.html
> **否定性断言（A2 已说明查证范围）**：**中报未官方确认 US$1bn ARR** —— 查了中报全部媒体转述稿与业绩会报道，无一篇引用公司确认该数字。

**1GW 与收购（【软】，公司口头宣布，未见港交所自愿性公告编号）**：新浪财经 https://finance.sina.com.cn/tech/roll/2026-07-21/doc-iniiqefh4852306.shtml ｜ https://finance.sina.com.cn/stock/t/2026-07-21/doc-iniippik9405621.shtml ｜腾讯新闻 https://news.qq.com/rain/a/20260721A03ZGE00 ｜新京报 https://m.bjnews.com.cn/detail/1784598635129318.html ｜观点网 https://www.guandian.cn/article/20260721/575158.html ｜虎嗅 https://www.huxiu.com/article/4876982.html
> **新浪 2026-07-23 深度稿明写：记者就算力占比采访智谱「截至发稿未收到回复」** https://finance.sina.com.cn/roll/2026-07-23/doc-iniivihw4519486.shtml

**融资与股权（【硬-公司公告/监管披露】经媒体转述）**：每日经济新闻（A 股方案 2%–8%、拟募 150 亿） https://www.nbd.com.cn/articles/2026-06-01/4414544.html ｜新浪财经 https://finance.sina.com.cn/wm/2026-06-02/doc-inhzynrx1787322.shtml ｜新浪财经（辅导 11 天验收） https://finance.sina.com.cn/wm/2026-06-17/doc-inictnup3789670.shtml ｜财联社（7/8 基石解禁） https://www.cls.cn/detail/2420039 ｜新浪港股 https://finance.sina.cn/hkstock/gggd/2026-07-08/detail-inihaawe8264782.d.html

**价格发现与行情事件（【软】）**：21经济网（7/30 单日 −16.55%） https://m.21jingji.com/article/20260730/herald/7e98f1090bdfdc3a53512d67bb5049d9.html ｜新浪财经（8/14 卖空创纪录、8/18 −13.3%） https://finance.sina.com.cn/roll/2026-08-18/doc-inintpin8659729.shtml ｜新浪快讯（8/18 单日 −17% 破 1,000 HKD） https://wap.cj.sina.cn/pc/7x24/5045130 ｜新浪财经（MSCI 纳入） https://finance.sina.com.cn/jjxw/2026-08-13/doc-ininctaw3387785.shtml ｜财联社（纳入恒科当日反跌） https://m.cls.cn/detail/2396848

**同业对照（【软】，MiniMax 与商汤市值均为媒体口径，未做市值自洽校验）**：虎嗅〈MiniMax 市值五个月蒸发 76%〉 https://www.huxiu.com/article/4886381.html ｜凤凰科技 https://tech.ifeng.com/c/8vuMOxzFIOc ｜第一财经 https://www.yicai.com/news/103066133.html ｜澎湃 https://m.thepaper.cn/newsDetail_forward_33953750 ｜财新（MiniMax 纳港股通） https://companies.caixin.com/m/2026-08-06/102471722.html ｜新浪财经（商汤首次中期盈利） https://finance.sina.com.cn/stock/hkstock/hkstocknews/2026-08-26/doc-iniprums2335532.shtml ｜虎嗅 https://www.huxiu.com/article/4883708.html

**TAM（全部【软】）**：IDC 官网博客〈从基模到应用·全面智能体化〉（大模型公有云 2025 = 79.4 亿、AI 应用公有云 137.3 亿、AI IaaS 2029 近 1,500 亿）｜艾媒咨询（AI 大模型 2026E = 738.57 亿） https://www.iimedia.cn/c1094/110207.html ｜IDC（中国 AI 总投资 2029） https://my.idc.com/getdoc.jsp?containerId=prCHC53829925

**实体清单**：Federal Register（2025-01-16 加入实体清单，EAR §744.11）【硬】 https://www.federalregister.gov/documents/2025/01/16/2025-00704/addition-of-entities-to-and-revision-of-entry-on-the-entity-list ｜natlawreview（法律分析）【软】 https://natlawreview.com/article/choosing-between-us-and-chinese-ai-models-export-control-risks-both-sides

**份额侧反驳**：钛媒体（MiniMax 月调用 6.9 万亿 vs 智谱 2.7 万亿；2026 年三次提价路径） https://www.tmtpost.com/7947142.html ｜财联社（中国开源模型占 OpenRouter 流量 >45%） https://m.cls.cn/detail/2293160 ｜echohaoran（GLM-5.3-Flash 破 OpenRouter 纪录） https://blog.echohaoran.top/posts/2026-08-31-zhipu-glm53-flash/

---

## 12.4 本档明确排除的来源与口径

| 排除项 | 理由 |
|---|---|
| **stockanalysis / Yahoo 的市值与 PS** | 股本滚动滞后失真（兄弟档 [MiniMax](../MiniMax/index.md) 确立的 TTM 分母铁律） |
| **stockanalysis 的 PB 与 Altman Z（−5.89）** | IPO 前优先股列金融负债导致权益 −81.11 亿，任何 PB / Z 值失真 |
| **腾讯行情 [50] 字段** | **不是 PB**（该字段读数 2.55，含义未在数据源文档中定义；当日振幅 14.40% 是 [43] 字段，勿混淆）。[58]=20.93 才是 PB，但同样禁用 |
| **媒体「现金可维持约 1.9 年」** | 用 2025 末 22.59 亿余额、未计 IPO 与配售，**严重低估续航** |
| **「H1 占全年 26.4%」季节性外推** | 产生该季节性的本地化年底验收业务已退场（占比 13.5%），**参数作废** |
| **ARR 作 PS 分母（44.2x / 35.4x）** | 与入账收入裂口 6.5–8.7x，与同业 IFRS 分母不同质，混用会把 PS 压低 7–8 倍 |
| **摩根大通目标价（2,400 → 1,600 → 1,800 HKD，两个月三改）** | **不具锚定价值，本档不引用** |
| **旧档 Anthropic 20.5x 一级估值** | 2026-08 未能刷新，本档不作锚（若他处引用须标注为 2026-08-01 旧值） |
| **旧汇率 0.865 / 6.79 及其全部派生数** | 已作废，全档复扫归零 |
| **旧档 PS 549x（FY2025 分母）** | 口径已被 PS(TTM 含 1H2026) = 320.7x 取代 |

---

## 12.5 三路采证的数字冲突处置

**纪律：三路数字冲突一律以 A1 为准，并在正文显式标注，不静默取一个。** 逐条冲突清单与处置结果见 [valuation.md 末「相对旧档变化清单」E 节](valuation.md)，其中最重要的两条：
- **A2 写「前十大客户日均调用量 +98 **倍**」，A1 为 +98%** → **取 A1**。A2 的"倍"为转述笔误，量级差 100 倍，采用会严重夸大客户深度。
- **ARR 裂口：A1 测 6.5–8.2x、A3 测 7–8.7x** → 按裁定**取并集 6.5–8.7x 并注明两路测算**。

---

## 12.6 免责声明

本文档为个人投资研究记录，基于公开信息与自行推算，**不构成投资建议**。1H2026 全部财务数字为媒体转述的公告口径【软-高】，未经审计原文核对；三档内在价值为情景假设下的推算结果，实际结果可能显著不同。任何据此做出的投资决策，风险自负。
