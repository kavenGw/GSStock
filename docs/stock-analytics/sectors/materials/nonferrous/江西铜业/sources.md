---
doc_type: buffett-section
stock_code: '00358'
stock_name: 江西铜业
section: sources
---
# 江西铜业 — §12 数据来源 & 局限

## 12.1 一级证据（硬）

- **[江西铜业股份有限公司 2026 年半年度报告（2026-08-25 披露，216 页 PDF 全文本地解析）](http://dataclouds.cninfo.com.cn/shgonggao/hsomarket/2026/20260825/4e31066641744255b5fa407c1ee4f60c.PDF)** —— 本档所有标【硬·中报】的数字来源：财务三表（P6/P13/P15）、非经常性损益表（P7–P8）、经营情况讨论与铜价/TC/RC 行业描述（P10–P12）、产量与资源量（P13–P14）、重大科目变动与境外资产（P17–P18）、利润分配预案（第六节）、长期股权投资与合联营权益附注（P173–174）、分部与地理附注（P203–204）、以公允价值计量项目（P9）。
- **A 股行情（2026-09-04 收盘）**：腾讯 `qt.gtimg.cn/q=sh600362` —— 45.86 CNY，已经 `scripts/quote_guard.py` 双通过，价 × 股本自洽偏差 0.00%。
- **H 股行情/估值（双源交叉，2026-09-04）**：腾讯 `q=hk00358` + [stockanalysis.com/quote/hkg/0358](https://stockanalysis.com/quote/hkg/0358/) —— 36.580 HKD，52 周区间 23.58–53.75 HKD；PE-TTM 本方重算 9.36 vs stockanalysis 9.44（差 1.0% ✓）。
- **汇率**：CNY/HKD = **1.1686**（2026-09-04，freecurrencyrates / investing 口径）。
- **多期财务序列**：akshare `stock_financial_abstract_ths`（同花顺口径），2026-09-06 取数。
- **LME / COMEX 期货序列**：akshare `futures_foreign_hist`（`CAD` = LME 三个月期铜、`HG` = COMEX 铜），10 年窗口 2016-09-06 起，2026-09-06 取数。**口径自证**：该序列 2026H1 均价 $13,130.8/吨，与中报 P11 公司自述"LME 铜（三个月）均价 13,137 美元/吨"差 **0.05%** → `CAD` 确为 LME 3M 口径，序列可信。
- **SolGold 收购（多源）**：[证券时报](https://www.stcn.com/article/detail/3660184.html) / 第一财经 / Lexology（安杰世泽），2026-03；[江西铜业并购"全球最具潜力的未开发铜矿"获批（新浪财经 2026-03-03）](https://finance.sina.com.cn/jjxw/2026-03-03/doc-inhpspmp4120374.shtml)。
- **业绩预告与中报转述**：[上半年净赚 86 亿超预告上限（财联社 2026-08-25）](https://www.cls.cn/detail/2465174)；[2026 年半年度业绩预告（同花顺 2026-07-08）](https://news.10jqka.com.cn/20260708/c678048429.shtml)；[Q1 营收 1,391.24 亿 / 归母 28.18 亿（经观 2026-05-02）](http://www.eeo.com.cn/2026/0502/860809.shtml)。
- **铜箔分拆**：[拟筹划分拆江铜铜箔至港交所（同花顺 2026-05-01）](https://m.10jqka.com.cn/20260501/c676435067.shtml)；[正式公告拟分拆（新浪财经 2026-07-16）](https://finance.sina.com.cn/roll/2026-07-16/doc-inihzfcz8217296.shtml)。
- **分红对照**：[2025 中期股息每 10 股 4.3824 港元（腾讯新闻 2025-10-28）](https://news.qq.com/rain/a/20251028A06EMO00)；[2025 末期股息每 10 股 6 元、2026-07-17 派发（新浪财经 2026-06-08）](https://finance.sina.com.cn/stock/hkstock/ggscyd/2026-06-08/doc-iniasmvu7220829.shtml)。

## 12.2 二级 / 第三方证据（软）

- **估值分位**：akshare `stock_zh_valuation_baidu`（百度股市通口径，n=366 周频点位，近 5 年自 2021-09-06），2026-09-06 —— A 股 PB 1.810 处 **88.0 分位**、PE-TTM 13.70 处 68.9 分位。
- **铜现价**：[tradingeconomics.com/commodity/copper](https://tradingeconomics.com/commodity/copper)（2026-09-04，COMEX $6.60/lb）；mining.com / benchmarkminerals（8–9 月纪录价）。
- **TC/RC**：SMM 进口铜精矿指数 −159.37 美元/干吨（2026-07-31），[同花顺/新浪转载券商周报 2026-08-03](https://finance.sina.com.cn/wm/2026-08-03/doc-inikzuym5973479.shtml)；[铜价飙涨背后的"冰与火"：0 加工费与 CSPT 减产 10%（财联社 2025-12-29）](https://www.cls.cn/detail/2242970)。
- **Cobre Panama / FQM**：[First Quantum adds 1,000 jobs as Cobre Panama restart nears (MINING.COM)](https://www.mining.com/first-quantum-adds-1000-jobs-as-cobre-panama-restart-nears/)；[Cobre Panamá partial restart results in a US$44mn quarterly loss (BNamericas)](https://www.bnamericas.com/en/features/first-quantums-cobre-panama-restart-posts-us44mn-quarterly-loss)；[FQM Q2 2026 (Investing.com)](https://ca.investing.com/news/company-news/first-quantum-q2-2026-slides-copper-output-rises-panama-restarts-93CH-4760704)。
- **ICSG 平衡表**：[ICSG forecasts copper market surplus in 2026 and 2027 (IndexBox)](https://www.indexbox.io/blog/icsg-forecasts-copper-market-surplus-in-2026-and-2027/)；[Global refined copper market to swing to surplus in 2026 (Mining Weekly, 2026-04-23)](https://www.miningweekly.com/article/global-refined-copper-market-to-swing-to-surplus-in-2026-group-says-2026-04-23)；月度实际值 [ICSG July surplus (Yieh)](https://www.yieh.com/en/News/icsg-global-refined-copper-market-oversupply-in-jul//83718)。
- **机构价格预测（分歧极大，必须并列）**：GS 2026-04-06/07 下调 2026 均价至 **$12,650/t**、过剩上调至 49 万吨（[Sahm Capital 转路透](https://www.sahmcapital.com/news/content/update-1-goldman-sachs-cuts-2026-copper-price-outlook-sees-larger-market-surplus-2026-04-07)）；花旗 2026-08-07 看 3 个月 **$14,500/t**、年底 **$15,000/t**（[新浪财经](https://finance.sina.com.cn/stock/hkstock/marketalerts/2026-08-07/doc-inimnent3221698.shtml)）。
- **再生铜 / 铝代铜**：[ICSG forecasts secondary copper output boost (Recycling Today)](https://www.recyclingtoday.com/news/copper-icsg-recycling-output-refining-supply-demand-2026-2027/)；[2026 年中国再生铜行业产量、需求规模分析（智研咨询）](https://www.chyxx.com/industry/1254395.html)；[铜价高位震荡 "以铝节铜"应用提速（新华网 2026-02-05）](https://www.news.cn/fortune/20260205/f1f230c5c75f4fd880ba0bd6d209e47f/c.html)；[中小型充电站"铝代铜"潮（新浪财经 2026-01-30）](https://finance.sina.com.cn/jjxw/2026-01-30/doc-inhkakfp0625523.shtml)。
- **AI 用铜量级**：[Copper: the perfect squeeze (Kpler, 2026-07-17)](https://www.kpler.com/blog/copper-the-perfect-squeeze)。
- **厄瓜多尔重谈背景**：[Cascabel/Mirador renegotiation — power self-generation (Ecuador Brief)](https://www.ecuadorbrief.com/articles/cascabel-mirador-renegotiation-mining-power-self-generation-2026)；[江西铜业收购 SolGold：拿下 Cascabel 控制权（Keno Consulting）](https://kenoconsulting.mx/zh/2026/02/jiangxi-copper-solgold-cascabel-ecuador/)。
- **LME 铜库存**：296,625 吨（注册仓单 130,775 / 注销仓单 165,850，注销占比 55.9%），2026-07-17，akshare `macro_euro_lme_stock`。

## 12.3 三路 evidence 冲突处理（以 A1 为准并显式标注）

| # | 冲突项 | A2 / A3 口径 | **A1 裁定（本档采用）** | 处理 |
|---|---|---|---|---|
| 1 | **汇率 CNY/HKD** | A3 用 **1.16412**（与洛钼档同源） | **1.1686**（2026-09-04） | 采 A1，**全档派生数一律按 1.1686 重算**。受影响并已改正的：H 股静态股息率 A3 的 3.18% → 本档 **3.20%**；前瞻股息率 A3 的 1.91% → 本档 **1.92%**；三档每股 HKD 由 13.41/26.89/38.80 → **13.46/26.99/38.95**，期望内在价值 24.55 → **24.65 HKD**，H 股安全边际 −32.9% → **−32.6%**；FQM 敏感性上限 29.36 → **29.46 HKD**、−19.7% → **−19.5%**。**不受影响的**：A 股口径（IV **21.09 CNY** / 安全边际 **−54.0%**）与三档 CNY 阶梯（11.52/23.10/33.33）由「EPS × 倍数」直接得出、不经汇率，故与 A3 数值一致纯属同源而非沿用作废汇率 |
| 2 | **COMEX 对 LME 的口径差** | A2 称约 **15%** | **同日（2026-09-04）COMEX $14,699/t vs LME 3M $14,371.5/t = 溢价 +2.28%** | 采 A1。A2 是把 COMEX 的一个时点高点与另一时点的 LME 价相比，属口径错配；**A2 据此做的任何调整已撤回** |
| 3 | **FQM 权益价值** | A2 估"权益市值约 350 亿元 ≈ A 股市值 22%" | **半年报单列的公开报价公允价值 285.56 亿元**（占 A 股市值 18.0%） | 采 A1。A2 偏高约 23% |
| 4 | **FQM 会计处理** | A2 存疑（权益法 vs FVOCI）、称"未按公允价值进净资产" | **权益法核算（联营企业）**，账面 143.01 亿**已进净资产**，**市价部分 142.55 亿未进** | 采 A1。**PB 被系统性低估的幅度是 142.55 亿（净资产的 16.3%），不是 285 亿或 350 亿** |
| 5 | **2026H1 OCF** | A2 标【缺】（PDF 未能解析） | **58.14 亿元（5,814,230,993 元），+102.49%** | 采 A1，A2 缺口已补 |
| 6 | **铜价弹性跨主体比较** | A3 称"江铜扣非 1.89x vs 洛钼 2.2x，只差约 15%" | 两者**口径不同**：洛钼 2.2x 是归母口径，江铜 1.89x 是扣非口径（江铜归母口径实为 **2.74x**） | **禁止任何基于跨口径相减/相除的精确比较数**；本档分别列出两个口径并只保留定性结论 |
| 7 | **"自产铜精矿 +37.36%"** | A2 提示是口径变更 | **证实**：自有矿 10.00 万吨、年化 20 万吨零增长，增量来自 FQM 权益并表口径变更 | 采 A1，本档按境内自给率 **7.9%** 写 |
| 8 | **CSPT 减产落空** | A2 称"说好减产 10%、实际增产 6.1%" | **未独立采证【软·A2 单源】**；且与中报"5–6 月集中检修"是两个时间窗、可并存 | **本档不下"减产落空"结论**；能下的唯一结论是"6–8 月产量数据未取到【缺】，减产是否落实无法裁决" |
| 9 | **兄弟档 comps 定性** | comps 档称江铜"矿端护城河板块最强" | **7.9% 自给率证伪** | 本档按 7.9% 写；comps 档更正交 Phase C |

## 12.4 已知局限与信息真空（明写，不编数）

1. **【本轮最大真空】Cascabel 厄瓜多尔重谈最终条款**：2026-05-29 厄方要求重谈（100% 自发电、保护区范围、合同期限）后的结果，半年报**零披露、零减值计提**。未找到公开证据说明重谈已了结或恶化。**勘探成本已 138.55 亿且商誉仅 38.69 万元、无缓冲，减值将直冲该科目。"零披露"不等于"安全"。**
2. **分部 / 分产品毛利表不存在**：A 股半年报不强制披露，216 页全文无此表。**本档严禁虚构**，业务结构改用产量结构 + 采购定价机制 + TC/RC 三条硬证据间接支撑。
3. **H 股 PB 近 5 年精确分位【缺】**：东财 H 股历史行情接口两次 `RemoteDisconnected`、百度 H 股估值接口返回非 JSON，未取到序列，**不编数**。仅给方向性推断（AH 折价区间稳定 → H 股 PB 分位应与 A 股 88.0 分位同向、大概率仍在 80% 以上）。
4. **冶炼板块单独盈亏未披露**：故风险 2 触发器的后半段（"自有矿 + FQM 权益利润是否足以覆盖冶炼亏损"）**无法裁决**。
5. **2026-09 现货 TC/RC 点位【缺】**：SMM / Mysteel 需订阅，只能引 2026H1 最低 −124.45 美元/吨（硬）与 2026-07-31 的 −159.37 美元/干吨（软）。
6. **HVLP-3 / 铜箔业务收入、毛利、客户名【缺】**：中报未拆分 → **不进 base 正常化利润**。
7. **Cascabel 投产年份口径冲突**：媒体口径 **2028** vs 旧档/theme 口径 **2031**，中报未披露 →【缺】。本档不给 Cascabel 任何近端利润，两口径均不影响结论。
8. **铜箔分拆股东会（2026-08-07）表决结果与递表进展【缺】**。
9. **2026 年回购公告【缺】** → 股东回报仅计分红。
10. **粗铜/粗杂铜采购占比【缺】** → "原料替代阀"论只能定性。
11. **AI 数据中心用铜对江铜营收/利润的可归因证据【缺】**：中报只给了"AI 产业链相关铜材需求向好、铜箔开工率维持高位"的定性归因，无任何一手量化数字。
12. **厄瓜多尔"100% 自发电"要求对 Cascabel 资本开支与 NPV 的量化测算【缺】**。
13. **口径提示**：腾讯 H 股"总市值 1,266.67 亿 HKD" = H 股价 × **全部 A+H 股本**，非 H 股流通市值；stockanalysis 报 161.35B HKD 是 A/H 分价混合口径。两者均已自洽，不冲突，本档统一用前者。
14. **2026 全年 ROE 外推（约 17.3%）为外推非事实**，须待年报确认；估值仍按穿越周期 ROE 8–9% 取倍数。

---

**本文档为投资研究记录，基于公开信息与个人判断，不构成投资建议。** 铜为强周期商品，标的盈利与估值均对铜价高度敏感，历史数据不代表未来表现。
