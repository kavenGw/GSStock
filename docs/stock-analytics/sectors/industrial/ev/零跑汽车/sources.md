---
doc_type: buffett-section
stock_code: '09863'
stock_name: 零跑汽车
section: sources
---

# 零跑汽车 — §12 数据来源 & 局限

> 返回 [index](index.md)｜[§1–§5 生意](business.md)｜[§6–§8 论点](thesis.md)｜[§9 估值](valuation.md)

## 12.1 证据分级约定

**【硬】** = 公司公告 / 财报原文 / 业绩会实录 / 官方月度交付；**【软】** = 媒体推算 / 卖方 / 第三方站点；**【缺】** = 未找到公开证据。
**三路采证数字冲突一律以 A1 数据锚为准并在正文显式标注**，不静默取一个（本轮 8 项冲突的裁定见 [§9.11 B 表](valuation.md)）。

## 12.2 一手源（港交所披露易原文 PDF）

| 文件 | URL | 日期 | 本档用到的页 |
|---|---|---|---|
| **零跑 2025 年度业绩公告** | https://www1.hkexnews.hk/listedco/listconews/sehk/2026/0316/2026031601215_c.pdf | 2026-03-16 | p7 出口 67,052 台｜p9 服务及其他销售/碳积分归因｜p10 公司口径现金定义、经调整净利、FY2025 OCF 126.2 亿｜p16 完整利润表（归母 5.384 亿）｜p17 资产负债表｜p23 单一经营分部 + 按客户位置划分收入｜p24 无单一客户 ≥10% 声明｜p30 贸易应收构成（关联方 82.9%）｜p31 应收账龄｜p34 应付账龄 + 应付票据质押｜p33 关联方借款｜附注 32 资本承担 53.44 亿 |
| **零跑 2025 中期报告（全文）** | https://www.hkexnews.hk/listedco/listconews/sehk/2025/0929/2025092901673_c.pdf | 2025-09-29 | p45 现金流量表（2025H1 OCF 28.58 亿、capex 19.67 亿）｜p79 关联方定价样板句｜p80 对 Stellantis 系销售 21.16 亿｜p82 对 Stellantis 系贸易应收 22.70 亿 |

**⚠️ 2026 中期业绩公告（2026-08-24）PDF 原文 URL 未取得【缺】**——公司 IR 页返回空内容，hkexnews 站内检索需 POST，多轮检索未拿到直链。**报表级数据取自 stockanalysis.com 结构化财报页（数据源为交易所申报），并与中文媒体转载的公告要点逐项交叉，全部一致。** 上述两份 PDF 确立了零跑的**披露格式基线**，用于判定「中报会/不会披露什么」。

## 12.3 行情与估值锚

- **腾讯 `qt.gtimg.cn/q=hk09863`**（gbk，港股字段索引异于 A 股）：2026-08-25 09:20 与 09:32 两次取数，现价 42.520 HKD、总股本 1,421,812,652 股、总市值 604.55 亿 HKD（自洽校验 42.520 × 14.218 亿股 = 604.55，与 totalMv 604.5547 吻合 ✅）；52 周高/低 69.450 / 32.800；日线自算 YTD −12.55%、50 日均线 37.83
- **stockanalysis.com/quote/hkg/9863/**（statistics / financials，2026-08-24 收盘口径）：市值 608.0 亿 HKD、PS 0.67、PB 3.67、EV/Rev 0.39、200 日均线 44.96 —— 与自算逐项一致，**唯 PE(TTM) 66.44 自身不自洽（608.0/8.24 = 73.8），采信自算 72.8×（盘中）/ 73.2×（8/24 收盘）**
- **汇率双源实测**：open.er-api.com/v6/latest/HKD 与 /CNY（2026-08-25 00:02 UTC）→ 0.859898 / 1.162941；api.frankfurter.app（ECB，2026-08-24）→ 0.85785 / 1.16571。两源差 0.24%，本档统一采 **1 HKD = 0.8599 CNY / 1 CNY = 1.1629 HKD**
- 可比公司（2026-08-24 收盘统一基准日）：小鹏 09868、理想 02015、蔚来 09866、比亚迪 H 01211 —— 收盘价 × 腾讯总股本，均已自洽校验

## 12.4 中报与业绩会（2026-08-24）

- 东方财富图解财报 https://finance.eastmoney.com/a/202608243851241294.html（含「中期分红方案为不分配不转增」）
- 金融界 https://24h.jrj.com.cn/2026/08/24180158217708.shtml ；证券之星 https://finance.stockstar.com/IG2026082400025516.shtml
- 新浪财经 https://finance.sina.com.cn/tech/digi/2026-08-24/doc-inipmhfp0097093.shtml
- **业绩电话会实录（中）** https://cn.investing.com/news/transcripts/article-93CH-3532781
- **业绩电话会实录（英，逐字）** https://www.investing.com/news/transcripts/earnings-call-transcript-leapmotor-posts-strong-h1-2026-growth-trims-profit-outlook-93CH-4873620
- **⚠️ 英文实录已发现四处转写错误**（H1 OCF「CNY 270M」应为 21.7 亿、出口「+72%」应为 +372.6%、Q2 毛利率 +3.2pct 标为「同比」实为环比、「2027 总量 350,000–400,000」低于 2026 年 1–7 月已完成的 45.8 万台故逻辑不成立）。**本档对该源的引用限定在逐字原话且与中文版双向核实过的部分**：西班牙「opening ceremony」/「next year, B10's volume will be around 50,000 units」、CFO「but not that much⋯locally procured parts and components will be more expensive」、2026 海外「we can exceed 150,000 units」、「未重申 100 万辆目标」

## 12.5 交付、产品与产能

- 官方月度交付汇总：IT之家 https://www.ithome.com/0/984/629.htm（2026-08-01）；新京报 https://www.bjnews.com.cn/detail/1785562140168598.html；Stellantis 官方新闻室 https://www.media.stellantis.com/em-en/leapmotor/press/leapmotor-doubles-deliveries-and-breaks-the-100-000-unit-milestone-record-july-performance（2026-08-01）；CnEVPost https://cnevpost.com/2026/08/01/leapmotor-tops-100000-monthly-deliveries/
- **2026Q1 基数三源交叉**：网通社 http://auto.news18a.com/news/storys_258072.html（2026-05-21）；钛媒体 https://www.tmtpost.com/7994049.html；虎嗅 https://www.huxiu.com/article/4858942.html
- 2025 基数：搜狐汽车 https://db.m.auto.sohu.com/model_6357/a/925871190_211762
- 车型：A10 新华网 https://www.news.cn/auto/20260331/8d1e1919f8ca4eb6be1b0cf4421e8ad5/c.html（2026-03-26）；A05 IT之家 https://www.ithome.com/0/988/468.htm（2026-08-11）；D19 http://www.news.cn/auto/20260421/0ad9a0d951fd453c920aba2d0a34ed0c/c.html（2026-04-16）
- 海外产能：Stellantis 官方 https://www.stellantis.com/en/news/press-releases/2026/may/stellantis-and-leapmotor-announce-their-intention-to-take-their-strategic-partnership-to-the-next-level（2026-05-08）；Invest in Spain https://www.investinspain.org/en/news/2026/leapmotor1（2026-07-01，Mallén 电池模组厂）；paultan https://paultan.org/2026/06/04/leapmotor-c10-local-assembly-already-started-at-gurun-plant-b10-ckd-to-follow-in-2-3-months-time/

## 12.6 碳积分、监管、定增

- **碳积分**：新浪财经引 HKEX 关联交易公告 https://finance.sina.com.cn/stock/wbstock/2026-04-01/doc-inhszayn2550487.shtml（2026-04-01，2026 年度上限 28 亿、2025 实际对价 11.096 亿）；Reuters 系 https://energynews.oedigital.com/carbon-emissions/2026/03/31/stellantis-and-chinas-leapmotor-sign-a-carbon-credit-deal-for-europe-and-uk；**⚠️ 太平洋汽车「协议价值 15 亿」为单一来源、与 cap 口径混用，不采信**
- **证监会四连问（2026-06-03）**：新浪财经 https://finance.sina.com.cn/stock/bxjj/2026-06-09/doc-iniavfsr5050035.shtml ；https://news.sina.com.cn/c/2026-06-15/doc-inicnpyq9969807.shtml ；澎湃 https://m.thepaper.cn/newsDetail_forward_33404910
- **定增**：新浪财经 https://finance.sina.com.cn/stock/relnews/hk/2026-01-09/doc-inhfsniy1720278.shtml（发行价「每股 50.03 人民币」）；一汽入股 https://finance.sina.com.cn/stock/relnews/hk/2025-12-29/doc-inhenmhm0150771.shtml
- **全年 50 亿净利原目标（五源独立，均早于 8 月业绩会）**：每经 https://www.nbd.com.cn/articles/2026-03-17/4295088.html ；每经 https://www.nbd.com.cn/articles/2026-05-16/4395465.html ；新浪 https://finance.sina.com.cn/roll/2026-05-16/doc-inhyahap2749878.shtml ；虎嗅、钛媒体（同上）
- **⚠️ 检索噪音**：搜索「零跑 全年净利润目标」常返回「50 亿目标不调整」——**那是 2026-05-16 一季度业绩会口径**，与 8 月中期业绩会的下调节点不可混用

## 12.7 AI / 智驾 / 机器人 / 行业

- 智驾技术路线：量子位 https://www.qbitai.com/2026/03/392948.html（世界模型架构、芯片、OTA 计划表、数千卡算力）
- 智驾免费政策起始：https://cj.sina.com.cn/articles/view/7857141524/1d45277140190237js（**2025-04-10**，非 2024-04）；退费 https://news.qq.com/rain/a/20250412A06S0X00
- 第三方梯队横评：https://auto.sina.cn/2026-07-07/detail-inifxpii1586922.d.html ；https://auto.sina.cn/2026-07-19/detail-iniihzci7918085.d.html ；https://auto.sina.cn/2026-07-22/detail-iniirshq4776748.d.html
- 放弃自研智驾芯片：21 世纪经济报道 https://www.21jingji.com/article/20260617/herald/6592d6ae106e7d37002ca8df8a736fb1.html（2026-06-17，朱江明「AI 智驾芯片，有点过剩了」）
- 机器人实体：每日经济新闻 https://www.nbd.com.cn/articles/2026-07-29/4525535.html（湖州凌昇精密制造，2026-07 设立，注册资本 2.1 亿；含朱江明「3 年回本」红线与「市值仅特斯拉千分之五」表态）
- 一汽 G117 平台许可费中标：https://eu.36kr.com/zh/p/3430942917561737 ；https://chedongxi.com/p/355562.html
- 行业出清：https://finance.sina.com.cn/wm/2026-05-06/doc-inhwxxki3431880.shtml ；产能利用率 国家统计局 https://www.stats.gov.cn/sj/zxfb/202604/t20260416_1963322.html（2026Q1 汽车制造业 70.3%）
- 欧洲 BEV：ACEA https://www.acea.auto/pc-registrations/new-car-registrations-5-7-in-h1-2026-battery-electric-20-7-market-share/ ；零跑全欧增速第一 https://www.autonext.co/news/leapmotor-fastest-growing-brand-europe-h1-2026
- 中国 NEV 总量：中汽协 https://jnzstatic.cs.com.cn/zzb/htmlInfo/113583.html ；乘联会 https://news.qq.com/rain/a/20260126A02W5G00 ；新华社 2026-07 占比破 60% https://www.news.cn/fortune/20260709/2cdb373246df439eab1636a7a50d0682/c.html
- 欧盟 MIP 价格承诺：欧委会 https://policy.trade.ec.europa.eu/news/commission-issues-guidance-document-submission-price-undertaking-offers-battery-electric-vehicles-2026-01-12_en（2026-01-12）
- 原材料：碳酸锂 https://www.chemall.com.cn/mobile/news/show-258797.html（2026-08-14，约 15.0 万元/吨）；车规存储 +180% https://finance.sina.com.cn/tech/roll/2026-07-16/doc-inihzfcz8214083.shtml（另见 [events.md](events.md) 链接的专题档）
- 行业涨价潮：https://finance.sina.com.cn/roll/2026-05-27/doc-inhzhxzt1777586.shtml ；https://www.21jingji.com/article/20260528/herald/4dac98a4e49e753d3fd052e51e77f181.html

---

## 12.8 已知局限（不回避）

1. **2026 中期业绩公告 PDF 原文未取得**。报表数据经 stockanalysis 结构化财报页 + 中文媒体转载逐项交叉一致，可用；但**正文无法引原文页码**，且**应收/应付账龄表、关联方交易明细、现金流量表分项、分部信息**这些只在公告/中报全文里的科目本轮取不到。**2026 中期报告全文预计 2026-09 下旬发布**（2025 版为 2025-09-29），届时应回验 [index §11.3](index.md) 的多条阈值。
2. **「全年净利指引约 30 亿」是单一机构来源**（investing.com 中英双版，非独立交叉），**待公司公告确认**。本档已给敏感性：30 亿 / 20 亿两档下结论均不变（[§6.3](thesis.md)）。
3. **完整 OCF 桥无法闭合**（残差 −47.4 亿），缺 2026 中期现金流量表原文。故 [§6.1](thesis.md) 的营运资本三项表仅作方向性证据，**主结论建立在只依赖资产负债表与利润表期末硬数的 DPO 反事实测算上**。
4. **capex 绝对额与 2026 指引【缺】**，仅有由 FCF 桥反推的约 20.3 亿/半年【自算·软】。
5. **国内产能官方规划表【缺】**——146–151 万辆全部来自媒体推算，且 2026 中报与业绩会**全程未给公司口径产能数字**。**这是结构性披露缺口，不是采证不足**，故 [§9.9](valuation.md) 的扩产达产确定性无法升【硬】。
6. **碳积分 FY2026E 18 亿是本档自设假设**（= H1 口径 ×2，不打满 28 亿 cap）。cap 是上限非承诺，2025 实际为 11.096 亿。**该假设直接影响 base 与 bull 的碳积分块，已设监控阈值「FY2026 实际 <15 亿 = base 下修」。**
7. **证监会四问的正式书面回复公告【缺】**（回复期限约 2026-07-03，截至 2026-08-25 未见公开版本），**是否结案 / 注册生效 / 是否有后续问询亦全部【缺】**。业绩会全程未提及该问询与定增——属**负面确认**（管理层未主动交代进展），但**无证据 ≠ 无事件**。
8. **分车型交付结构【缺】**（公司不按车型披露）；**技术授权收入金额【缺】**（Stellantis 官方稿明确无财务条款，一汽招采平台无金额）；**机器人业务收入/融资/外部估值全部【缺】**。
9. **2026-08 单月交付未发布**（惯例 9/1 公布）；**中报后卖方研报截至采证时未被公开渠道索引**。
10. **零跑仅港股单一上市**（无 A 股、无 ADR），`stock_code: '09863'`、`currency: HKD`，**A+H 双口径铁律不适用**。

> **本文档不构成投资建议。** 所有估值为基于公开信息的场景推演，三情景概率为主观赋权，实际结果可能显著偏离。港股流动性、汇率、监管与地缘政策变化均可能使本文结论失效。
