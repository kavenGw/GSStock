---
doc_type: buffett-section
stock_code: '09992.HK'
stock_name: 泡泡玛特
section: sources
---
# 泡泡玛特 — §12 数据来源 & 局限

> 采证日 **2026-09-13**（周六，港股休市）；行情锚 **2026-09-11（周五）收盘**。
> 三路采证底稿：`.omc/artifacts/泡泡玛特-2026-09-13-A1.md`（数据锚，含附录 A 跨路校准）、`-A2.md`（论点）、`-A3.md`（lens）、`-控制者裁定.md`。

---

## 12.1 方法学诚实声明（最重要，先读）

> ### ⚠️ 证据等级须分两层：**H1'25 对照数字是一手原文，H1'26 数字是多源转述**
>
> - **hkexnews 检索接口在 6 组参数组合 + Cookie 会话下一律返回 `recordCnt=0`**；港交所权益披露门户 `di.hkex.com.hk` 返回 1,132 字节框架页。
> - **控制者已于 2026-09-13 亲自到 `di.hkex.com.hk` 前端人工复核，门户返回「page temporarily unavailable」，复核失败。**
>   因此**段永平 5.55% 无法取得原始披露页，维持【硬-转述】等级**（依据：三源以上媒体对同一份 DI 申报表的转述，比例 / 股数 / 日期 / 原因栏措辞互相一致，并通过股数自洽校验）。
> - **A1 二次收工已成功下载并解析港交所 2025 年中期業績公告 PDF 原文（40 页）**——H1'25 的政府补助、汇兑、存货、现金三项拆分、分部与渠道数据**均为一手原文**，
>   本档大量「同期可比」口径（存货 22.74 亿、政府补助 0.378 亿、跌价 0.043 亿、资产负债率 32.4%、海外 55.93 亿、海外线上占比 45.8%、海外分部经营利润率 44.2%）**皆源于此**。
> - **但 A1 为定位文件编号而扫描 hkexnews 编号空间，触发 IP 限流、整站对本机 403**，故 **2026 中期業績公告原文、股份购回月报表、段永平权益披露原始表单三项维持【缺-检索失败】**。
>   **这是检索受限，不是「文件不存在」**——尤其「新授权下零回购」**不得作为结论**。
> - 因此：**H1'26 的中报数字全部为多源转述互证，本档不谎称核过 H1'26 原表。**
> - 本档采用的处理：所有中报与 DI 字段均取自**三源以上财经媒体对同一份披露的转述**，且通过**股数自洽**（段永平 1.02 亿 − 2,793.3 万 = 7,406.7 万 ÷ 13.3178 亿 = 5.562% ✅）
>   与**市值自洽**（153.000 × 1,331,779,203 = 2,037.62 亿 HKD，偏差 0.00% ✅）两道交叉校验，故标为【硬-转述】。
> - **本档明确不谎称核过原表。** 若需在段永平持股或回购执行上下更强断言，**建议人工到 hkexnews / DI 门户前端复核一次**。

---

## 12.2 已知局限与【缺】项清单（逐条，不编造）

| # | 缺失项 | 影响 |
|---|---|---|
| **1** | **2026H1 经营活动现金流量净额** | **不是「找不到」，是「尚未披露」。** 香港中期業績公告结构上不含现金流量表（2025 年同类文件 40 页全文「現金流量」出现 0 次，自述编制依据为「初步中期業績公告的適用披露規定」）；现金流量表只在完整《中期報告》里，按上市规则须于期末后 3 个月内刊发 → **最迟 2026-09-30 公开**。**本档列为一级触发器**，见 [index.md §0](index.md) 与 [valuation.md §9.7.1](valuation.md) |
| ~~2~~ | ~~2026H1 政府补助金额~~ | **已结案、移出缺项**：H1'25 原文 **0.378 亿 = 归母的 0.83%**，1% 以内调整，**不设不确定区间** |
| ~~3~~ | ~~2026H1 存货跌价准备当期计提绝对额~~ | **降级为噪音、移出关键缺项**：H1'25 原文基数仅 **0.043 亿**，即便 +430% 也只约 0.23 亿 = 归母的 0.45%。**风险在资产负债表（61.02 亿存货、同期 +168.4%）不在利润表**；bear 的 30% 减值是**前瞻性假设**，不是对已披露计提的外推 |
| 4 | 2026H1 资本开支 | 随现金流量表一并于 **9/30 前**公开。年度代理：FY2025 capex **9.85 亿**、占营收仅 **2.7%**（轻资产实证）、FCF 98.80 亿 |
| ~~5~~ | ~~「净现金 141.64 亿」的构成拆分~~ | **已结案：名称错、数字对。** 141.6 亿 = 广义现金资源（现金 124.42 + 定期 15.20 + 受限约 2.0）；**真·净现金 102.44 亿**（扣 37.28 亿总债务，主要为 IFRS 16 租赁负债）；银行借款为零、无资产抵押。另：**资产负债率 32.4% → 24.9%，改善 7.5pct** |
| 6 | MOLLY −33.6%（旧档口径） | 本轮无公开复核源，**本档不再引用** |
| ~~7~~ | ~~FY2025 ROE~~ | **已结案、移出缺项**：FY2025 **76.2%**（平均净资产口径）/ 期末 56.4%；**TTM 70.2%**；**H1'26 年化 43.9%**。PB 自算 7.53x |
| 8 | 2026-08-21 至 09-13 的**港交所公告全集** | **A1 扫描 hkexnews 编号空间触发 IP 限流、整站 403**，未能穷尽；「该区间无新公告」为方法受限下的推断而非确证。**同一限制适用于新授权回购——「未检索到任何《股份购回报告表》」≠「零执行」，本档一律记【缺-检索失败】，且不得据此写任何估值下界** |
| 8b | 段永平 DI 原始披露页 | **控制者 2026-09-13 亲自前端复核失败**（`di.hkex.com.hk` 返回 page temporarily unavailable）。5.55% 维持【硬-转述】，不升级为【硬-原表】 |
| 9 | **同口径可比公司估值表** | A1 未完成（52TOYS、TOP TOY、卡游、万代、Funko、Takara Tomy 的同日 PE-TTM / PB / 市值均未双源取到）。**[valuation.md §9.6](valuation.md) 的同业表来自不同日期不同数据源，已标注该限制，不可用于精确分位计算** |
| 10 | MEGA / 衍生品分品类收入 | 品类拆分不完整 |
| 11 | 乐园 / 影视 / 游戏 / POP BAKERY / popop 的**单独收入与利润口径** | 门控 (c) 无法解除的直接原因；索尼影业 LABUBU 电影无定档、无投资额、无分成条款 |
| 12 | 1H2025 同口径会员复购率 | 51.6% 无法做严格同比 |
| 13 | 销量 / ASP 量价拆分 | 中报无量价表，增长无法拆量价 |
| 14 | 分部 ROIC（美洲口径） | **升级为【硬-原文依据】的结构性不可验证，不是尽调缺失**：公司**只有「中国业务」「海外业务」两个可呈报分部，根本没有美洲分部**；且原文明载「由於主要經營決策者並不使用分部資產及分部負債資料…故並無向主要經營決策者單獨提供此資料」。**不得断言美洲开店为正或负 ROIC。** 替代硬指标：**H1'25 海外分部经营利润率 44.2%**（中国 48.9%），H1'26 同口径未取到 → 中期报告后一级复核项 |
| 15 | 单店 capex 与回收期、乐园 capex 金额 | 重资产稀释风险只能设阈值监控，无法定量 |
| 16 | 业绩后**完整**卖方一致预期与目标价全表 | 仅有点状：汇丰 136.5 / 美银 153 / 杰富瑞 146 / 大摩 214 |
| 17 | 08-22 至 09-11 逐日主力资金流 | **港股无官方逐日资金流披露，本档全程禁止引用逐日序列**；仅 08-21 单日净流入 6.39 亿 HKD 为【软】单点 |
| 18 | 公司是否有**章程层面**的分红承诺 | 媒体「把上一财年赚的钱全部分回股东」为标题化表述，**不得写成章程承诺** |

---

## 12.3 本档显式作废 / 禁用的数字（红线 6 执行）

| 作废项 | 正确口径 |
|---|---|
| PE-TTM **14.41** | 那是**静态 PE**；PE-TTM = 13.17（自算）/ 13.37（腾讯）/ 13.33（stockanalysis） |
| 「美洲单店产出 **−35%**」 | **无源，禁止引用**；只写方向：门店 +34% 远超线下收入增幅，单店产出必然显著下滑 |
| 逐日主力资金流序列 | **禁止引用**（港股无官方口径） |
| 「**净现金** 141.64 亿」这个**叫法** | 数字对、名称错：141.6 亿是**广义现金资源**；**真·净现金 102.44 亿** |
| 存货对照「年末 54.73 → 61.02 = **+11.5%**」 | **全档禁用**（跨季节、把问题缩小一个数量级）。同期口径为 **H1'25 22.74 → 61.02 亿 = +168.4%** |
| 新授权回购「**零执行**」 | **不得作为结论写**——港交所检索本轮受限（IP 限流、整站 403），只能写【缺-检索失败】 |
| 派付率 **52%~75%** | **25.0%**（股息口径）/ 36.7%（股息+回购）。原值系「分子全年股息 ÷ 分母半年利润」跨期错配 |
| 段永平 **7.65%** | **5.55%**（2026-08-05 港交所权益披露），持仓市值 113.32 亿 HKD（非 153 亿） |
| 中途一度采用的 **−11.6%** | **撤回。正确值 −11.1%**（原文 H1'25 55.93 → H1'26 49.72 亿 = −11.10%），**旧档是对的** |
| 存货对照基数 **123 天** | **83 天**（2025H1 同期口径），123 天是年末数、跨季节 |
| A3 三档股价 69.9 / 108.8 / 160.4 | **作废**，见 [valuation.md §9.3](valuation.md) 重算的 74.61 / 105.99 / 171.17 |

---

## 12.4 联网证据源（含 URL 与日期）

### 行情与汇率（硬源）
1. 腾讯行情 `https://qt.gtimg.cn/q=hk09992`（2026-09-13 取，行情戳 2026-09-11 16:09:02）——价 / 量 / 股本 / 市值 / PE / PB / 股息率 / 52 周
2. 腾讯日 K `https://web.ifzq.gtimg.cn/appstock/app/hkfqkline/get?param=hk09992,day,2026-08-10,2026-09-13,40,qfq`（2026-09-13）——完整价格路径
3. stockanalysis.com POP MART https://stockanalysis.com/quote/hkg/9992/ （2026-09-13）——收盘 / 市值 / PE / 52 周 / TTM
4. stockanalysis.com 半年财务 https://stockanalysis.com/quote/hkg/9992/financials/?p=quarterly （2026-09-13）——分期营收 / 毛利 / 归母 / EPS
5. frankfurter.dev ECB https://api.frankfurter.dev/v1/latest?base=CNY&symbols=HKD （2026-09-11 = 1.1690）
6. 新浪即期汇率 `fx_scnyhkd`（2026-09-12 = 1.16899）

### 2026 中期业绩（2026-08-20 披露，均为转述）
7. PR Newswire《Pop Mart Reports First Half 2026 Financial Results, Announces Future Stock Buyback Plan》 http://www.prnewswire.com/news-releases/pop-mart-reports-first-half-2026-financial-results-announces-future-stock-buyback-plan-302856357.html
8. 中国基金报《泡泡玛特发布2026年半年报》 https://www.chnfund.com/article/AR9b83e8d8-4a1d-cc72-0536-3a2330d8c813
9. 经济参考报（新华社）《泡泡玛特上半年营收171.7亿元 大额股份回购计划未来将落地》 http://jjckb.xinhuanet.com/20260820/c344aeb9bf554770a327433bbf87a948/c.html
10. 东方财富《图解财报：泡泡玛特中报盈利50.38亿人民币，同比增加10.14%》 https://finance.eastmoney.com/a/202608203847789622.html
11. 36氪《半年净赚50亿，泡泡玛特却被市场"判不及格"》 https://www.36kr.com/p/3947795568727688 ——分地区 / 分 IP / 汇兑 7.2 亿 / 会员 / 现金 124.4 亿
12. 华盛通《王宁：20%年增长目标可能无法完成！拟回购最多50亿元，海外开店"质量大于数量"》 https://www.hstong.com/news/detail/26082021403342769 ——**线上/线下拆分关键源**
13. 每日经济新闻《王宁称：今年销售不是主要目标》 https://www.nbd.com.cn/articles/2026-08-20/4548384.html
14. 中国企业报道《泡泡玛特2026上半年营收171.7亿元 新锐IP爆发》 https://www.cenr.com.cn/cyjj/fz/2026/08/21/232535.html ——门店 676 / 机器人 2,827 / 区域分布
15. 澎湃《泡泡玛特中期业绩》 https://m.thepaper.cn/newsDetail_forward_33822767 ——线上渠道拆分、王宁「单店效率回落」
16. 东方财富《泡泡玛特将在未来6个月内启动20—50亿人民币的股份回购计划》 https://finance.eastmoney.com/a/202608203847940420.html
17. 同花顺《最高50亿元！泡泡玛特，拟大手笔回购》 https://news.10jqka.com.cn/20260820/c679146063.shtml

### 历史对账与存货同期口径
18. 21经济网《泡泡玛特2025年营收371.2亿元，LABUBU成百亿IP》 https://www.21jingji.com/article/20260325/herald/6229eb4dbcb491339ed0ed85aa06f33d.html
19. 网易《泡泡玛特2025年净利润暴涨308.8%，段永平买入》 https://www.163.com/dy/article/KSTT19V70511U82T.html ——FY2025 归母 127.76 亿
20. 数英《泡泡玛特半年报出炉，数据后的重要信息点》 https://www.digitaling.com/articles/1396310.html ——**2025H1 存货周转 83 天（对照基数关键源）**
21. 华尔街见闻《泡泡玛特2025年净利润同比暴增293%，2026年增速预期仅20%》 https://wallstreetcn.com/articles/3768334

### 价格路径与卖方
22. 21世纪经济报道《中期业绩不及预期，泡泡玛特盘中跌超8%》 https://m.21jingji.com/article/20260821/herald/be78423e515b89a2d8e0a203fa577484_zaker.html
23. 新浪财经《泡泡玛特，开盘大跌》 https://finance.sina.com.cn/roll/2026-08-21/doc-inipaent8220195.shtml
24. 搜狐《泡泡玛特8月21日收盘跌3.06%，主力资金净流入6.39亿港元》 https://www.sohu.com/a/1065924875_122123195 ——【软】单点资金流 + 目标均价
25. CNBC《Labubu maker Pop Mart shares fall as key ex-China sales data drop, Citi cuts price target》（2026-08-21） https://www.cnbc.com/2026/08/21/labubu-maker-pop-mart-shares-fall-after-sales-drop-in-asia-americas-.html （正文 403，仅取标题）
26. Yahoo 财经《美银证券：泡泡玛特上半年业绩逊预期 下调盈利预测及目标价至153元 维持中性》 https://hk.finance.yahoo.com/news/大行-美銀證券-泡泡瑪特-09992-hk-042330296.html
27. 新浪财经《Labubu神话破灭？三大投行同步下调泡泡玛特目标价》 https://finance.sina.com.cn/stock/relnews/hk/2026-03-26/doc-inhsicus0215560.shtml

### 段永平权益披露（DI 转述）
28. 新浪财经《刚说"10年不卖"，持仓比例骤降！段永平泡泡玛特权益生变》（2026-08-05） https://finance.sina.com.cn/stock/zqgd/2026-08-05/doc-inimhiec5173737.shtml ——**7.65% → 5.55% 关键源**
29. 新浪财经《段永平举牌后首次减持泡泡玛特，持股比例降至5.55%》（2026-08-05） https://finance.sina.cn/chanjing/gsxw/2026-08-05/detail-inimhiei4549914.d.html
30. 中国证券报《知名投资人段永平：10年内大概率不卖泡泡玛特》（2026-07-23） https://jnzstatic.cs.com.cn/zzb/htmlInfo/128525.html
31. 腾讯新闻《段永平再度加仓泡泡玛特：三轮买入超38亿》 https://news.qq.com/rain/a/20260714A08RQQ00
32. 北京商报（2026-05-28 首次举牌 5.69%） https://www.bbtnews.com.cn/2026/0528/594621.shtml

### 派息与回购
33. 新浪财经《泡泡玛特2025年收益同比暴增185%，将派发股息2.38元/股》 https://finance.sina.com.cn/jjxw/2026-03-25/doc-inhseqfw1027953.shtml
34. 证券之星《泡泡玛特(09992.HK)：截至二零二五年十二月三十一日止年度的末期股息内容摘要》 https://4g.stockstar.com/detail/AN2026032500022497
35. 雪球《一年赚131亿只分25%，泡泡玛特的真实股东回报能力有多强》 https://xueqiu.com/8326595589/402098356 ——**派付率 25.0% 独立双源**
36. 新浪财经《泡泡玛特：斥资约6亿港元回购股份》（2026-03-26） https://finance.sina.com.cn/wm/2026-03-26/doc-inhsikav8945574.shtml
37. 新浪财经《泡泡玛特已累计回购1122万股公司股份》（2026-04-03） https://finance.sina.com.cn/roll/2026-04-03/doc-inhtferc8856768.shtml
37b. **旧窗口回购明细（2026 年 1 月约 3.48 亿 HKD；3/26–4/2 连续 6 个交易日约 13.97 亿，含 3/30 斥资 1.99 亿回购 134 万股、价区间 144.3–153.5 HKD；1–4 月累计约 17.44 亿）** —— 源自**控制者 2026-09-13 人工前端复核**（裁定 §14），未逐笔回指单一 URL，标【硬-转述 + 人工复核】

### 二级市场与 IP 热度
38. 证券时报《黄牛暂缓收购、价格大跳水》 https://www.stcn.com/article/detail/3564151.html
39. 腾讯新闻《从一"布"难求到跌破官方价》（2026-01-06） https://news.qq.com/rain/a/20260106A04OW100
40. 羊城晚报《Labubu不用抢了，二手市场跌破原价》 https://news.ycwb.com/ikimvkjtkn/content_53892834.htm
41. 封面新闻《星星人新品上线秒空！59元隐藏款二手价冲高近千元后又"腰斩"》 http://www.thecover.cn/news/G2RzbuuCJ7yH90qSdq8Jkw==
42. 封面新闻《二级市场星星人价格反超Labubu》 https://www.thecover.cn/news/LoBe9YYnjsCH90qSdq8Jkw==
43. 腾讯新闻《"复古理发店"发售半小时二手跌超30%》（2026-08-24） https://news.qq.com/rain/a/20260824A0648700

### 竞品与历史锚
44. 36氪《2026上半年的潮玩市场——泡泡玛特"踩刹车"、新势力蓄力》 https://36kr.com/p/3875690969640969
45. 新浪《TOP TOY 递表港交所、2025 收入 35.87 亿》 https://finance.sina.com.cn/stock/hkstock/2026-04-01/doc-inhsxzph1929785.shtml
46. 大洋网《名创Q1营收56.88亿、TOP TOY +51.4%》 https://news.dayoo.com/finance/202605/27/171077_54964405.htm
47. kr-asia《Pop Mart's next act gets harder as Labubu growth cools》 https://kr-asia.com/pop-marts-next-act-gets-harder-as-labubu-growth-cools
48. Inside Retail Asia《Can Pop Mart survive Labubu fading?》（2026-08-25） https://insideretail.asia/2026/08/25/can-pop-mart-survive-labubu-fading/
49. Nippon.com《Sanrio》 https://www.nippon.com/en/in-depth/d01053/ ——三丽鸥 2014 峰值后连跌 7 年
50. Statista Sanrio net sales https://www.statista.com/statistics/890835/sanrio-net-sales/
51. stockanalysis Sanrio 统计 https://stockanalysis.com/quote/tyo/8136/statistics/ ——PE-TTM 28.44 / Forward 24.24
52. multiples.vc Bandai Namco https://multiples.vc/public-comps/bandai-namco-valuation-multiples ——16.1x
53. fullratio Hasbro https://fullratio.com/stocks/nasdaq-has/pe-ratio （2026-08-14，16.28）
54. fullratio Mattel https://fullratio.com/stocks/nasdaq-mat/pe-ratio （2026-07-10，8.33）

### 新业务（全部【软】，无数字）
55. 新浪《城市乐园一年"爆改"亮相》 https://finance.sina.com.cn/wm/2026-05-02/doc-inhwpipz5497318.shtml
56. 新浪《乐园票价最高288元》（2026-07-28） https://finance.sina.com.cn/jjxw/2026-07-28/doc-inikkhkm3124345.shtml
57. Seoul Economic Daily《Pop Mart to Open First European Flagship Store in Paris》（2026-09-08） https://en.sedaily.com/international/2026/09/08/pop-mart-to-open-first-european-flagship-store-in-paris
58. 每经《王宁到访LVMH总部》（2026-09-05） https://www.nbd.com.cn/articles/2026-09-05/4573775.html

---

## 12.5 lens 覆盖声明

**本轮无 subsector 专用 lens**——`references/lenses/` 现有 12 份板块专属 lens 覆盖金属（copper / precious / rare-earth）、
半导体（design / equipment / materials / power / storage×2）、PCB-CCL、光纤光缆，**无 designer-toy / 潮玩 / 消费 IP 类 lens**。

命中的横切 lens 与本档落点：

| lens | 角色 | 落点 |
|---|---|---|
| `x-growth.md` | **主** | 跑道 → [§2.2](business.md)；量价与增长质量 → [§3.2](business.md)；结构性 vs 周期性二分 → [§8.1](thesis.md)；成长证据包门控 → [§9.5](valuation.md)；监控 → [§11](index.md) |
| `x-dividend-value.md` | 辅 | 股息 / 派付率 / 回购 → [§3.6](business.md)；双面必答三条 → [§6.6](thesis.md)；股东回报倒推下界 → [§9.6④](valuation.md)；分红削减监控 → [§11](index.md) |
| `x-ai.md` | 仅识别 | [§7](thesis.md)：产品层与业绩层**均判【蹭概念】、零敞口**，不入 owner earnings 基础；AI 作为**反向竞争威胁**落 [§11](index.md) 监控 |

---

## 12.6 免责

本文件及本档全部内容为基于公开信息的分析记录，**不构成投资建议**。
所有估值为情景假设下的推算，实际结果可能显著偏离。数据可能存在错误或滞后，投资决策请自行核实并承担风险。
