---
doc_type: buffett-section
stock_code: '00100'
stock_name: MiniMax
section: sources
---

# MiniMax — §12 数据来源 & 局限

## 12.1 主要来源（逐条含日期与强度）

**一手 / 硬**

- **2026 中期业绩公告**（截至 2026-06-30 六个月，**2026-08-26 17:41 HKT 港交所披露易刊发**，21 页，安永按 HKSRE 2410 审阅）：https://www1.hkexnews.hk/listedco/listconews/sehk/2026/0826/2026082600680.pdf ——**本档全部财务数字（收入/分部/毛利/费用/亏损/资产负债/或有负债/治理偏离）均取自此，正文页码即指该 PDF**
- 业绩新闻稿（PR Newswire，公司发布，2026-08-26）：https://www.prnewswire.com/news-releases/minimax-announces-first-half-2026-financial-results-302860489.html
- 刊发日预告（2026-08-14）：https://www.prnewswire.com/apac/news-releases/minimax-to-report-2026-interim-financial-results-on-august-26-2026-302851744.html ／ https://finance.sina.com.cn/roll/2026-08-14/doc-ininhtfh4080609.shtml
- **FY2025 全年业绩公告**（2026-03-02 盘后，本档 TTM 分母的另一半与 2H2025 反推基期）：https://www.minimax.io/news/minimax-global-announces-full-year-2025-financial-results
- **行情锚**：腾讯行情源 `qt.gtimg.cn`，2026-08-26 16:08:05 收盘 HK$303.00、成交量 7,381,383、总市值 1,058.18 亿 HKD、总股本 349,235,308 股。`scripts/quote_guard.py` 通过，**价×股本偏差 0.00%**
- **AA Intelligence Index v4.1.1**（取数 2026-08-26，AA 官网一手页面）：https://artificialanalysis.ai/models/minimax-m3 （M3 = 45，open weights #8/107）／ https://artificialanalysis.ai/models/kimi-k3 （K3 max = 60，#1/107）／ https://artificialanalysis.ai/leaderboards/models （总榜第 44 位，变体级）／ https://artificialanalysis.ai/models/comparisons/kimi-k3-vs-minimax-m3
- **AA 旧版口径对照（仅供历史对照，不得单独引用）**：https://artificialanalysis.ai/articles/minimax-m3 （M3 发布时 55 分）／ https://x.com/ArtificialAnlys/status/2064066303863005254 ／ https://artificialanalysis.ai/articles/kimi-k3-achieves-3-in-the-artificial-analysis-intelligence-index-comparable-to-opus-4-8-and-gpt-5-5
- **《人工智能拟人化互动服务管理暂行办法》**（五部门 2026-04-10 公布，**2026-07-15 施行**）：https://www.cac.gov.cn/2026-04/10/c_1777558395078289.htm ／ 五部门公布通稿 https://www.cac.gov.cn/2026-04/10/c_1777558395023172.htm ／ 新华网 https://www.news.cn/politics/20260410/bc2a2172b4d64a539cf253e75044b494/c.html
- **港股通 2026-08-06 生效**：https://www.cs.com.cn/ssgs/01/2026/08/05/detail_2026080510029605.html
- **Palantir FY2026 收入指引**（对标分母）：https://seekingalpha.com/news/4624208-palantir-outlines-2026-revenue-of-8_15b-8_158b-as-u-s-commercial-guidance-rises-above-3_424b
- **金山办公 H1-2026 营收 33.13 亿元（+24.69%）**（对标）：https://finance.sina.com.cn/jjxw/2026-08-19/doc-ininwiep9253484.shtml

**软 / 媒体转述（正文均已标级）**

- SCMP 引彭博：收入 +283% 但落后全年一致预期 US$363.77M（2026-08-26）：https://www.scmp.com/tech/big-tech/article/3365341/minimax-revenue-surges-283-remains-behind-pace-meet-forecast-amid-crowded-ai-race
- 财联社：大摩业绩前瞻（H1 收入 US$1.15 亿、毛利率 29.5%、经调整净亏 US$2.28 亿）：https://www.cls.cn/detail/2464442
- M3 定价追踪（最低输入价 90 天 −15%）：https://pricepertoken.com/pricing-page/model/minimax-minimax-m3 ／ M3.1 兑现滞后（至 2026-08-18 无 API/定价/权重）：https://aireiter.com/blog/minimax-m3-1-release-api
- 智谱提价（GLM-5.1 +10%，2026-04-08）：https://www.ithome.com/0/936/851.htm ／ Coding Plan 涨幅 30% 起：https://m.cls.cn/detail/2287878 ／ GLM-5.3 发布：https://companies.caixin.com/m/2026-08-14/102474172.html ／ 科创板辅导验收拟募 150 亿：http://www.eeo.com.cn/2026/0618/920349.shtml
- **第二批约 12% 解禁窗口（2026-08 底至 10 月初）**：https://www.tmtpost.com/8059101.html ——**⚠️ 该文对首批解禁规模给出三个互相矛盾的口径（1.46 亿股/63%、1.07 亿股/34.25%、44.85%），一致性差，故本档标【软】并明写「未见港交所一手披露佐证」**
- HKEX 科技 100 指数 2026-08-13 生效：https://www.fx168news.com/article/亚太股市-1073414
- 卖方评级：JPM 2026-08-17 TP 160→260 维持中性 https://finance.sina.com.cn/stock/estate/integration/2026-08-17/doc-ininqxur7052606.shtml ／ 高盛 860 买入 https://gmg.9fzt.com/dynamic/HKSE/00100/b4660f8b3895dde2f2536ca0cf6d4c7a.html
- 星野未成年人模式落地：https://xinwen.bjd.com.cn/content/s6a586870e4b0e45f3fd4b831.html
- 渠道/代理级合作（**不构成具名客户证据**）：绿联科技 https://www.lulian.cn/news/2131.html ／ 卓特视觉 https://hea.china.com/articles/20260807/202608071935741.html
- TAM 口径（**两口径差 8.9 倍，本档并列引用**）：market.us AI companion app 市场 https://market.us/report/ai-companion-app-market/ ／ Statista 2030 US$62 亿（旧档承接）
- 竞争格局：Character.AI MAU https://asotools.io/blog/blog/character-ai-app-market-intelligence-growth-strategy-2026 ／ 陪伴赛道结构 https://digitalhumancorp.com/en/research/best-ai-companion-app-2026 ／ AI 视频横评 https://www.uuaihub.com/blog/ai-video-tools-2026 ／ 海螺榜单登顶（**榜单非份额**）https://zhuanlan.zhihu.com/p/1885356791237439671
- OpenAI / Anthropic 一级估值与 run-rate：https://aibusiness.vc/startups/ai-revenue-leaderboard

**被本档明确禁用的源**

- **stockanalysis.com / Yahoo Finance 的 MiniMax 市值与 PS** —— 两源仍使用 2026-07-14 配售前的 3.1364 亿股，**系统性低估市值 11.2%**；stockanalysis 报的 last close（299.60）实为 8/25 昨收，滞后一日。**全档未使用，旧档的禁用判断本轮再次证实。**

## 12.2 已知局限（以下均为**未找到公开证据**，本档未以任何估计值替代）

1. **经营活动现金流净额** —— **FY2025 与 1H2026 双缺**。中期业绩公告**完全未列现金流量表**，公司仅在 p.8 定性表述「期内现金需求主要由融资活动所得现金满足」。**这是本档财务证据链上最大的洞**，且因应付账款为半年销售成本的 1.78 倍而更关键。完整中期报告（p.21 称 "will be made available in due course"）刊发后须第一时间补。
2. **分部毛利率（开放平台 vs AI 原生产品）** —— 未披露。收入按两分部拆（p.5/p.17），但**成本与毛利未按分部拆分**。**这是判别毛利率崩塌成因的唯一钥匙，公司连续两期没给。** 本档仅有自算上限推论【软】：数学上限 28.2%。
3. **客户集中度（最大客户、前五大客户占比）** —— 未披露。**B 端跃至 63.4% 后为最大盲区。**
4. **关联交易，及股东方（阿里 / 腾讯 / 小米 / 金山 / 米哈游 / 小红书 / 正大）是否为客户** —— 未披露，中报全文无相关表述与关联方交易章节。
5. **具名企业客户** —— 未披露。仅有 p.2 的总量口径「企业与开发者客户超 100 万、覆盖 100+ 国家」「总用户 3 亿+、230+ 国家和地区」（公司自述，无第三方核验）。
6. **ARR 官方口径与年底 US$1B 目标是否维持** —— **中报全文零次提及 ARR**，管理层既未重申现状也未重申目标。
7. **任何量化业绩指引** —— 无。p.3 Business Outlook 全为定性表述，无收入/毛利率/盈亏平衡时点数字。全年只能依赖彭博一致预期 US$363.77M【软】。
8. **海螺 / Hailuo 的 AI 视频市场份额、Talkie 独立收入** —— 未披露，且**本期颗粒度较 FY2025 倒退**（视频与陪伴合并为「AI 原生产品」单项）。现有全部「登顶」证据均为评测榜/活跃度榜，**没有一条是收入或付费份额**。
9. **AI 视频生成赛道的第三方 TAM 总量口径** —— 本轮再次检索仍未找到。
10. **陪伴赛道 TAM 的可用口径** —— 两个公开口径**相差 8.9 倍**（Statista 2030 US$62 亿 vs market.us 插值约 US$550 亿）。**不是「TAM 大/小」的问题，是没有一个可用的 TAM。** 本档并列引用，不择一。
11. **2027-01-09 解禁的具体股数与一手依据** —— 中报未提，仍属推算。**第二批约 12% 解禁窗口（2026-08 底至 10 月初）亦无港交所一手披露佐证【软】。**
12. **知识产权侵权诉讼的索赔金额与案件数** —— p.20 仅定性「several legal dispute cases」，**无金额、无案件数、无拨备**。
13. **业绩会（2026-08-26 20:00 北京时间）管理层问答纪要** —— 本档成文时尚无公开版本。ARR 是否重申、毛利率崩塌的官方归因、M3.1 时间表三项若在会上给出，应以 stock-research 模式 4 补做并回写 [events.md](events.md)。
14. **智谱（02513.HK）2026 中期业绩** —— 未找到已刊发的公开证据。**导致兄弟档 PS 对标口径不对称**（MiniMax 分母已含 1H2026，智谱仍停在 FY2025），说明见 [related.md](related.md)。
15. **南向资金实际持股比例** —— 港股通 2026-08-06 生效后，实际持股比例至今**未找到可靠一手数据**。卖方对南向流入的测算全部是纳入前的预测，**不能当作已发生的资金流**。
16. **中报后的卖方评级调整与市场定价反应** —— 中报于收市后刊发，**本档成文时尚未出现**。2026-08-27 是关键观察点。
17. **LTV/CAC、留存曲线、分产品 ARPU** —— 两期均未披露。
18. **算力 capex / 租约承诺 / 芯片采购量 / 供应商名单** —— 未披露。**本期首次出现 PP&E 与非流动预付款的大幅增长（合计约 US$174M），但其构成、供应商与承诺期限全部无信息。**
19. **DSO 的同期同口径对照** —— 1H2025 期末应收未披露，半年 vs 全年基期不同，**无法做季节性对照**，故 DSO 仅列【观察项】，不作裁决依据。

## 12.3 声明

- 本档为 **2026-08-05 平铺档的全量重做**（stock-research 模式 2 半年报升模式 1），旧档全部 TTM 口径与三档估值作废，逐条变化见 [valuation.md 相对旧档变化清单](valuation.md)。
- **估值锚定 2026-08-26 港股收盘 HK$303.00，而中报于当日 17:41 才刊发——该价格不含中报信息，市场定价反应最早见于 2026-08-27。**
- 三路采证（A1 数据锚 / A2 论点验证 / A3 lens 专项）出现的数字冲突，**一律以 A1 为准并在正文显式标注**，处置清单见 [valuation.md](valuation.md)「本轮 A 路数据冲突的处置」。
- 汇率全档统一 USD/HKD = 7.8。财报币种为 USD，股价与市值为 HKD。
- **本文档为个人投资研究记录，不构成投资建议。**
