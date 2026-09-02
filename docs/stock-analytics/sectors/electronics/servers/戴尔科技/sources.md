---
doc_type: buffett-section
stock_code: 'DELL'
stock_name: 戴尔科技
section: sources
---

# 戴尔科技 — §12 数据来源与局限

> 结论与评级见 [index.md](index.md)；生意见 [business.md](business.md)；论点见 [thesis.md](thesis.md)；估值见 [valuation.md](valuation.md)；事件回写见 [events.md](events.md)；结构性引用见 [related.md](related.md)。
>
> **数据基准日：2026-09-01 盘后**（Q2 FY2027 8-K 已披露）｜**估值主锚：$466.53（2026-09-02 盘前）**｜**对照价：$425.00（9/1 收盘）**

---

## §12.1 证据分级约定

本档全部数字按三级标注，正文中出现即为该条的分级：

| 标记 | 含义 | 可作何用 |
|---|---|---|
| **【硬】** | SEC 原始申报文件（8-K / 10-Q / DEF 14A / Form 4）或公司官方新闻稿的原表数字 | 可作裁决依据 |
| **【软】** | 第三方机构（TrendForce / IDC / ABI）、卖方、媒体转述，含对电话会与 IR deck 的转述 | 仅作交叉，不单独裁决 |
| **【推算】** | 本档或 A1 从硬数字派生（减法、桥表、外推），方法已在正文写明可复核 | 须与「披露」严格区分 |
| **【假说】** | 机理自洽但**无任何公开量化证据** | **不得当结论写** |
| **【缺】** | 未找到公开证据 | 明写「未找到」，**不许编** |

---

## §12.2 【硬】一手来源（本轮实取，非二手转述）

| # | 文件 | URL | 本档用途 |
|---|---|---|---|
| 1 | **8-K EX-99.1 · Q2 FY27 财报**（filed 2026-09-01，accession `0001571996-26-000039`，附件 585,822 bytes） | https://www.sec.gov/Archives/edgar/data/1571996/000157199626000039/exhibit991earnings8kq2fy27.htm | 损益表、资产负债表、现金流量表、分部表（ISG 三线 + CSG）、GAAP→non-GAAP 调节、Q3/FY27 指引。**本档几乎全部硬数字的来源** |
| 2 | 8-K 主文件（`dell-20260901`） | https://www.sec.gov/Archives/edgar/data/0001571996/000157199626000039/dell-20260901.htm | 确认财报发布日为 **2026-09-01**（旧档与控制者前置观察的「8 月下旬」时序错位由此闭合） |
| 3 | **Q1 FY27 10-Q**（截至 2026-05-01，accession `0001571996-26-000030`） | https://www.sec.gov/Archives/edgar/data/0001571996/000157199626000030/dell-20260501.htm | 分类股本（封面页 648,107,991 股）、**core debt vs DFS debt 拆分**、7:1 公式与「no recourse to Dell Technologies」原文、Q1 回购分月表（均价 $147.05）、Q1 资产负债表（股东权益 −$1,404M）、Voting Rights 附注 |
| 4 | **2026 DEF 14A**（记录日 2026-04-27） | https://www.sec.gov/Archives/edgar/data/0001571996/000119312526226734/d132444ddef14a.htm | MD stockholders **77.5% 投票权 / 45.7% 经济权益**、SLP **13.4%**、controlled company 认定、三类股期末股数、迁册德州议案的双类别过半门槛 |
| 5 | **Form 4 × 47 份**（2026-06-01 起全量遍历，逐份解析 XML 原文） | https://www.sec.gov/Archives/edgar/data/1571996/000119312526301094/ 等 | 内部人交易裁定：7/8 那批 $420–428 减持的申报人是 **Silver Lake**（Egon Durban 以 director-by-deputization 申报）；**Michael Dell 零申报** |
| 6 | EDGAR submissions JSON | https://data.sec.gov/submissions/CIK0001571996.json | 确认 **Q2 FY27 10-Q 截至 2026-09-02 尚未发布** |
| 7 | 8-K（2026-06-25，迁册德州获股东批准） | https://www.sec.gov/Archives/edgar/data/0001571996/000157199626000036/dell-20260625.htm | [events.md](events.md) 治理事件 |
| 8 | PRE 14A（FY2026，股数基准日 2025-12-02） | https://www.sec.gov/Archives/edgar/data/0001571996/000119312526203969/d132444dpre14a.htm | Michael Dell as-converted 持股的交叉核对 |
| 9 | 公司官方新闻稿 · Q2 FY27 业绩 | https://investors.delltechnologies.com/news-releases/news-release-details/dell-technologies-delivers-second-quarter-fiscal-2027-financial ／ https://www.businesswire.com/news/home/20260901574850/en/Dell-Technologies-Delivers-Second-Quarter-Fiscal-2027-Financial-Results | AI 订单 $60.9B、backlog $95B、股东回报公司口径 $4.3B |
| 10 | 公司官方新闻稿 · 长期财务框架（SAM，2025-10-07） | https://investors.delltechnologies.com/news-releases/news-release-details/dell-technologies-increases-its-long-term-financial-framework | 穿越周期目标 **营收 +7–9% / non-GAAP EPS +15%+ / 返还 >80% 调整后 FCF** —— 本档「当前是峰值」的最有力证据，且出自公司自己口径 |
| 11 | 公司官方新闻稿（2026-03-16，首家出货 NVIDIA GB300 工作站） | https://www.dell.com/en-us/dt/corporate/newsroom/announcements/detailpage.press-releases~usa~2026~03~dell-technologies-first-to-ship-nvidia-gb300-desktop-for-autonomous-ai-agents-with-nvidia-openshell.htm | [events.md](events.md) 产品层事件 |
| 12 | HP Inc. 官方新闻稿 · Q3 FY26（2026-08-26） | https://www.hp.com/us-en/newsroom/press-releases/2026/hp-inc-reports-fiscal-2026-third-quarter-results.html | 内存放大器**决定性反例之一**：PS 经营利润率同比 −0.8pt、PC 出货 −16% |

### §12.2.1 取数方法：SEC 直连 403 的破解（本轮方法论沉淀）

**问题**：`WebFetch` 直连 `www.sec.gov` 与 `investors.delltechnologies.com/static-files/` 全程 **HTTP 403**（前一棒 A1 因此零落盘）。
**解法**（本轮所有 SEC 原文均经此通道取得，**非媒体转述**）：

1. 用 `curl` 并带 **`User-Agent: <姓名> <邮箱>`** 请求头 —— 这是 SEC 的强制要求，**无此头必 403**，加上即全部 200。
2. 提交历史走 `https://data.sec.gov/submissions/CIK<10 位补零>.json`。
3. **单份文件清单必须走 `.../index.json`** —— EDGAR 的 HTML 目录页已改 JS 渲染，抓不到链接。
4. Form 4 原文取同目录下的 `ownership.xml` / `wk-form4_*.xml`，`<ownershipDocument>` 结构可直接解析 `rptOwnerName` / `transactionCode` / `transactionPricePerShare` / `<footnote>`。
5. **Dell IR 站 `static-files` 即使带浏览器 UA 仍 403**（Akamai）→ IR deck 只能靠第三方转述，一律标【软】。

> 一次性解析脚本（`scripts/_a1_dell_*.py` 六个）按仓规**已全部删除、未入库**。

---

## §12.3 【软】二手来源（仅作交叉，不作裁决依据）

| 内容 | 来源 | 本档处理 |
|---|---|---|
| **电话会管理层原话**（CFO "we would not expect every benefit to continue at this level"、"excluding the mix impact of AI servers, gross margin rates are up year-over-year"；COO "DRAM, DRAM, followed by NAND, NAND"、"there's a notion of inflation inside our growth"、"optimized the bits and bytes"、"demand outran supply"） | https://www.benzinga.com/news/26/09/61564313/dell-technologies-q2-2027-earnings-call-complete-transcript ／ https://www.investing.com/news/transcripts/earnings-call-transcript-dell-beats-q2-2027-estimates-shares-rebound-after-hours-93CH-4884715 | **全部标【软】**（Benzinga 直连 403，经 Investing.com 转述）。**归因桥表依赖其中的 AI「mid-single-digit」口头口径 —— 这是本档最重要推导的软肋，见 §12.5** |
| **IR deck 数字**：core leverage 0.8x、现金及投资 $14.2B、Q3 AI 收入约 $19B、AI 客户 6,500+、TTM 调整后 FCF $18.1B、自 FY23 累计回报 $18.3B、Q3 指引区间 $49.0B±$0.5B / EPS $6.50±$0.10、opex 占营收 8%（42 年最低） | https://www.investing.com/news/company-news/dell-q2-fy27-slides-ai-server-backlog-hits-95b-revenue-up-58-93CH-4884718 | Dell IR 站 403，只能取转述。**其中 $14.2B 已用 8-K 表验算精确吻合（现金 11,569 + 长期投资 2,679 = 14,248），可信度提升为准硬** |
| **服务器 DRAM / NAND 合约价与供需展望**：1Q26 +90~95%、2Q26 +58~63%、3Q26 +13~18%；2026 全年 server DRAM 约 +270%、eSSD 约 +235%；**DRAM 紧到 2027 全年、NAND 2027 转松**；新产能实质放量 2H27、显著产出 2028；2027 server DRAM+HBM 位元供给 +27%；原厂 2026 capex 美光 +23% / SK 海力士 +17% / 三星 +11%；**内存占 CSP capex 47%(2026) → 68%(2027)** | TrendForce 新闻稿：https://www.trendforce.com/presscenter/news/20260709-13140.html ／ https://www.trendforce.com/presscenter/news/20260730-13158.html ／ https://www.trendforce.com/presscenter/news/20260803-13161.html ／ https://www.trendforce.com/presscenter/news/20260825-13198.html ／ https://www.trendforce.com/presscenter/news/20260703-13134.html | 付费机构口径，**全部【软】**。本档的周期定位（[thesis.md §8.1](thesis.md)）与最重要的一条营收端反噬路径均以此为据 |
| DDR4 单颗现货 $42.45（2026-08-07 历史最高）、64GB RDIMM $450 → >$900 的 90 天翻倍 | https://tech-insider.org/dram-ram-price-crisis-2026/ ／ https://tech-insider.org/memory-chip-shortage-2026-ai-consumer-electronics/ | 【软·三方媒体，可靠性中等】。仅作方向佐证，不进任何算术 |
| 内存涨幅趋缓、消费端触及可承受上限 | https://www.tomshardware.com/pc-components/ram/memory-price-surge-begins-to-cool-as-consumers-hit-affordability-limit-ai-demand-still-keeps-dram-and-nand-prices-climbing-through-q3-2026 | 【软】。与 Morgan Stanley「百年一遇的内存通胀」的定性**不矛盾** —— 趋缓 ≠ 下跌 |
| 服务器硬件涨价、Lenovo/HPE 提价 10–15% 与 Cisco 对含内存产品线提价 | https://www.theitvortex.com/rising-server-hardware-prices-2026/ ／ https://getuniqcli.com/news/hpe-hp-price-increase-2026 ／ https://serverspace.us/about/blog/why-server-hardware-is-getting-more-expensive-in-2026-and-what-you-can-do-about-it/ | 【软】。**Dell 的 17% vs 同业 10–15% 的幅度分化是「定价租金」而非「被动转嫁」的关键量化痕迹** |
| **AI 服务器 / 服务器市场 TAM**：TrendForce 2026 AI 服务器出货量 +~31%、Top-9 CSP capex $886.7B(2026) → 约 $1.3T(2027)；IDC 全球服务器市场 $647.0B(2026) → $930.6B(2027)；Grand View AI 服务器市场 $157.0B(2026) → $598.1B by 2033 | https://www.idc.com/promo/servers/ ／ https://www.grandviewresearch.com/industry-analysis/ai-server-market-report | **口径分歧必须并列写明**（[thesis.md §7.2](thesis.md)）：TrendForce 是**出货量**、IDC 是**金额**，约 12ppt 差额主要是内存涨价的单机 ASP 通胀。Grand View 标【软·质量低】 |
| 厂商份额：OEM 侧 Dell 20% / HPE 15% / 浪潮 12% / 联想 11% / SMCI 9%（2024 口径）；ODM 侧鸿海约 40%、广达 25–30%，台系四家 2025Q4 合计 53.2%；**ODM 的 AI 服务器营收利润率区间 5.3%–8.3%** | https://www.abiresearch.com/blog/ai-server-market-size-vendor-shares-and-investment-drivers ／ https://www.ldeepai.com/tech-hub/ai-server-odm-market-analysis-2026-growth-forecast/ | 【软·2024 口径已旧】。**本档禁用份额论证 Dell 卡位**（口径不可比），份额数据仅作量级参照 |
| 竞争维度从硬件本体转向 AIOps / 液冷 / 部署服务 | https://www.datacenterknowledge.com/servers/ai-server-market-update-vendors-shift-from-silicon-to-services | 【软】。既是差异化机会，也**反证硬件本体无壁垒** |
| **AI capex 二阶导**：Big-5 2026 合计指引 $775–800B（约 2024 年 $238B 的 3 倍）、2025 基数约 $410B → 2026 约 +77%；2027 预计突破 $1T 但增速降至 +25–30% | https://alcapitaladvisory.com/research/intelligence/ai-infrastructure.html ／ https://www.tomshardware.com/tech-industry/big-tech/big-techs-ai-spending-plans-reach-725-billion | 【软】 |
| 数据中心物理约束（变压器/开关柜/电池 + 电力）：截至 2026-05-16 美国 2026 管线约一半在延期 | https://about.bnef.com/insights/data-centers/ai-data-center-build-advances-at-full-speed-five-things-to-know/ ／ https://tech-insider.org/us-ai-data-center-delays-cancellations-7gw-capacity-crisis-2026/ | 【软】 |
| **反驳点**：「2026 年美国数据中心产能一半被取消」被 SemiAnalysis 明确驳斥为夸大 | https://newsletter.semianalysis.com/p/stop-saying-half-of-2026-us-datacenter | 【软】。**本档不得把「延期」写成「取消」** |
| **Neo Cloud 杠杆**：CoreWeave 截至 2026-06-30 总债务 $35B、单季 capex $9.4B、单季净利息 $640M（去年同期 $267M）；2026-08-10 完成 $2.6B DDTL（约 5 年期而底层客户合同平均约 3 年）；CoreWeave 否认微软合同取消；Core Scientific 交易终止 | https://capacityglobal.com/news/coreweaves-debt-hits-35bn/ ／ https://investors.coreweave.com/news/news-details/2026/CoreWeave-Closes-2-6-Billion-Loan-Facility-Expanding-Financing-Flexibility-for-AI-Infrastructure/default.aspx ／ https://www.globaldatacenterhub.com/p/coreweaves-85b-quarter-when-gpu-debt-went-investment-grade ／ https://english.aawsat.com/technology/5119145-ai-firm-coreweave-denies-contract-cancellations-microsoft ／ https://www.datacenterdynamics.com/en/news/coreweave-core-scientific-deal-ended/ | 【软】。**风险真实、对 Dell 的传导零兑现** —— 未找到任何 Neo Cloud 对 Dell 砍单/延付/违约的公开证据 |
| Dell 告知大客户「未来价格无法保证」，部分协议长达 5 年 | https://finance.yahoo.com/sectors/technology/articles/dell-tells-biggest-customers-cant-153017929.html | 【软】。**backlog 名义金额的可比性弱于固定价订单** |
| AI 客户数超 6,500 家、近三季新增 3,300 家 | https://cryptobriefing.com/dell-customer-count-surpasses-6500-ai-demand/ | 【软】。**只有客户数，无分客户类型的收入/backlog 拆分** |
| 卖方与第三方分歧：Morgan Stanley Equal-weight **$434**、InvestingPro fair value **$378**、BofA **$505**、Wells Fargo **$545**、Evercore ISI **$550**、27 家均值 **$510**；Morgan Stanley 另判 ISG 经营利润率 FY27/FY28 维持约 11%、Dell 相对 AI 基础设施同业有 30% 估值溢价（历史最高）；Trefis 给出 Q4 FY26 ISG 14.8% / Q1 FY27 10.5%；「Dell 已从组装盒子变成 AI 收费站」的多头分析 | https://www.trefis.com/articles/613288/dells-multiple-falls-on-servers-it-cannot-build-fast-enough/2026-08-27 ／ https://www.investing.com/analysis/dells-ai-toll-bridge-is-paved-with-record-margins-200681535 ／ https://fortune.com/2026/06/30/dells-ai-boom-real-but-so-is-profit-margin-hit/ ／ https://www.fool.com/investing/2026/08/31/dell-reports-tuesday-and-its-server-margin-is-where-the-ai-memory-bill-finally-reaches-the-stock/ | 【软】。**分歧本身是结论**（$378–$550 跨度 45%），见 [valuation.md §9.4](valuation.md)。**卖方目标价不进本档任何算术** |
| $9.7B / 五年期 DoD ESA II 软件协议及其治理观察点 | https://www.cnbc.com/2026/05/27/dell-dod-pentagon-software-deal-digital-infrastructure-trump.html ／ https://www.cdomagazine.tech/us-federal-news-bureau/war-department-signs-9-7-bn-deal-with-dell-to-modernize-digital-infrastructure | 【软】。**未找到任何调查、指控或监管行动**认定存在不当行为 → 中性记录，不作定性结论（[events.md](events.md)） |
| 9/1 单日 −6.80% 的成因与同业对照（SMCI −1.53% / HPE −2.62% / SPY −0.5%）、财报后盘后反弹 | https://247wallst.com/investing/2026/09/01/dell-falls-4-ahead-of-earnings-as-its-266-rally-raises-the-bar-super-micro-and-hewlett-packard-enterprise-slip/ ／ https://www.cnbc.com/2026/09/01/dell-q2-earnings-report-2027.html ／ https://ng.investing.com/news/stock-market-news/earnings-call-transcript-dell-beats-q2-2027-estimates-shares-rebound-after-hours-93CH-2681755 | 【软】 |
| HPE Q3 FY26 前值与指引参考 | https://ca.investing.com/news/stock-market-news/hp-q3-fy26-slides-revenue-hits-157b-but-margin-concerns-weigh-93CH-4818386 ／ https://finance.yahoo.com/markets/stocks/articles/hewlett-packard-enterprise-co-hpe-050021719.html | 【软】 |
| 内部人交易的二手转述（总法律顾问 Rothberg 卖出 20,000 股 / $8.2M） | https://www.marketscreener.com/news/dell-technologies-insider-sold-shares-worth-8-200-000-according-to-a-recent-sec-filing-ce7f5cddd98ff325 | 【软】，已被 §12.2 第 5 项的 Form 4 全量遍历**取代** |
| DRAM 周期位置指标 | https://www.useluminix.com/reports/industry-analysis/dram-cycle-position-analysis-peak-timing-indicators | 【软·质量低】，仅备查，未进正文 |

### §12.3.1 行情源与股本源

| 项 | 值 | 源 |
|---|---|---|
| 9/1 收盘 | $425.00（−6.80%，前收 $456.01，成交 1,473 万股） | yfinance + stockanalysis.com **双源一致** |
| **9/2 盘前** | **$466.53**（yfinance `preMarketPrice`）／ **$460.30**（stockanalysis） | **两源差 1.35%** → 本档一律写成「**盘前、流动性有限、双源区间 $460–467、待收盘复核**」，**不写单点** |
| 52 周区间 | $110.22 – $514.00 | stockanalysis.com |
| PE-TTM（GAAP $17.14） | 24.80×@$425 | stockanalysis.com，自洽 |
| **总股本** | **648,107,991 股**（Class A 276,744,341 / B 46,490,010 / C 324,873,640，10-Q 封面 2026-06-02）；**市值锚 646.14M 股** | 10-Q 封面【硬】+ stockanalysis 646.14M 第二源确认（差 0.30%，来自 6/2 后回购，属正常） |

> **必须防呆的一条**：**yfinance `sharesOutstanding` = 325.0M 只是 Class C**（DEF 14A 原文 325,034,188）。**用它算市值会低估 49.8%。**
> **市值自洽校验**：$425.00 × 646.14M = **$274.61B**，与二源报出市值偏差 **0.0%** ✅。（`scripts/quote_guard.py` 面向腾讯 A 股/港股字段口径，美股盘前价无对应通道，故以此自洽校验替代。）
> **stockanalysis 的 Forward PE 15.22× 隐含前瞻 EPS $27.92，高于公司 FY27 non-GAAP 指引 $25.50** → 它用的是 FY28 或跨年混合一致预期。**本档引用 forward PE 一律自算，不取该字段。**

---

## §12.4 【推算】非披露、由本档或 A1 派生的数字（须与「披露」严格区分）

| 推算项 | 值 | 方法（可复核） |
|---|---|---|
| **ISG +629bps 的归因桥表** | mix 效应 **−20bps**、非 AI 利润率扩张 **+649bps**（= 103%） | 固定 AI 经营利润率 5%（管理层口头中值），反推 Q2 FY26 非 AI 隐含 OM = 12.33%，冻结后套 Q2 FY27 收入结构。见 [thesis.md §6.1](thesis.md) |
| 非 AI 的 ISG 隐含经营利润率 | Q2 FY27 **24.7%–26.8%**（AI@4%–6%）；Q2 FY26 **11.4%–13.3%** | ISG 只披露一个分部利润，减法所得。**给敏感性带而非单点**；AI 放宽到 10% 时仍有 20.4% → 结论对该假设不敏感 |
| Q1 FY27 各项（营收 43,842 / GAAP 毛利额 7,782 / 经营利润 3,656 / 净利 3,438） | — | H1 − Q2 推算，**已用 Q1 FY27 10-Q 原表逐项验证完全一致** → 推算方法可靠 |
| Q2 core debt / DFS related debt | core 约 **$13,900M**、DFS 约 **$20,700M**、**核心净债务约 −$350M（净现金）** | 用公司自陈的 **7:1** 公式外推（Q1 实测吻合度 0.875 = 7/8）。交叉验证：管理层自述 core leverage **0.8x** |
| Q2 经营租赁设备净额 | 约 $3,230M | Q1 实际 2,731 + Q2 调整 FCF 表该项 +496 |
| backlog roll-forward | 51.3 + 60.9 − 16.401 = **95.8** vs 报出 $95B，缺口 ≤0.84% | **倒推，非披露**；公司从不披露取消率本身 |
| 回购授权剩余 | 约 **$10.4B** | Q1 末 $14,181M − Q2 回购 $3,796M |
| FY27 隐含周期顶 EBIT | 约 **$21.9B** | non-GAAP EPS $25.50 × ~650M ÷ 0.8 + 利息 $1.2B。用于 [valuation.md §9.2](valuation.md) 的 EV/EBIT 交叉锚 |
| 三情景正常化参数与每股内在价值 | bear $154.89 / base $214.37 / bull $302.72，期望 **$211.22** | 全部算术明写在 [valuation.md §9.3](valuation.md)，含隐含 PE 自检 |
| AI capex 减速的四情景冲击区间 | 见 [thesis.md §7.6](thesis.md) | 建模口径（EPS 推导、回购未计入、ISG 利润率回落路径以公司自身历史为锚）已随表列出 |
| 传统服务器 +122% 的量价拆分 | 见 [business.md §3.3](business.md) | **公司拒绝量化拆分**，本档给的是三组假设下的区间，不是单点 |

## §12.5 【假说】—— 明确不得当结论写

**存货持有收益假说**：用早期低价买入的存货，交付按重置成本重新定价的订单，产生一次性的存货持有收益（inventory holding gain）。
- **它能同时解释三件事**：Q2 毛利率逆季节性扩张 +301bps、CFO "we would not expect every benefit to continue at this level"、Q3 EPS 指引环比 −7.7%。机理自洽、时间线吻合。
- **但公司披露与第三方拆解均无任何量化证据** → **本档标为假说，不作结论、不进任何估值算术**。
- **验证途径**：Q2 FY27 10-Q（预计 2026-09 中旬）的存货明细与 MD&A 毛利讨论。
- 相关的两说并存事实：存货 $21,290M 为历史最高（半年 +104%），管理层**否认提前囤货**，称是 "optimized the bits and bytes we have coming in" + "shaping demand"。**囤货与否无独立证据可判。**

---

## §12.6 【缺】—— 未找到公开证据，明确不编

### §12.6.1 三项**结构性永久缺口**（公司从不披露，不是本轮工具限制）

| 缺口 | 依据 | 对本档的影响 |
|---|---|---|
| **AI 服务器单独的毛利率 / 经营利润率** | 8-K EX-99.1 全文（331 行解析文本）**零处**出现该数字；分部脚注 (f) 明写 "the company only reports **reportable segment operating income**"，脚注 (b) 明写 "the Chief Operating Decision Maker does **not** evaluate depreciation expense by operating segment" | **本档最重要推导（归因桥表）的软肋**：若非 AI 利润率完全没变，要解释掉全部 +629bps，AI 经营利润率须从 5% 跳到 **17.6%**。因公司永不披露，**这条无法用一手数据证死**，只能靠「17.6% 在 GPU 占 BOM 七成以上的机型上不可信」这个产业常识证伪。**因此桥表在正文中一律写成条件式裁定，不写成硬事实。**「AI 敞口【真敏感】」与「AI 的盈利能力永远无法验证」在本档并存，两者不可互相担保 |
| **Neo Cloud 客户信用敞口 / 融资应收的客户结构、分行业、集中度** | 8-K 与电话会均未披露，**分析师在电话会上亦未问** | 融资应收 Q2 单季 +46.5% 是本档能拿到的**最好量化前哨**，但客户是谁、取消条款如何**完全不透明**。这是本轮最大的信息黑洞之一 |
| **backlog 取消率、$95B 的客户类型拆分、AI 订单的合同取消条款** | 公司只给定性方向 "Demand is broadening across Neoclouds, sovereigns, and enterprise customers" | 本档只能给 roll-forward 的**倒推**结论（无恶化证据），且须注明订单/backlog 均为**非 GAAP、未经审计的管理层口径**，无 ASC 606 履约义务口径对账 |

### §12.6.2 待 Q2 FY27 10-Q 闭合（预计 2026-09 中旬）

| 缺口 | 本档当前处理 |
|---|---|
| **Q2 回购股数与均价** | 现金流量表回购支出 $3,796M 是【硬】，但股数只在 10-Q 的 Issuer Purchases 表。**Q2 均价 $401 标【未验证】，不是【证伪】**；若成立隐含回购约 946 万股。**对照组已核实**：Q1 均价 **$147.05**（10-Q 分月表按股数加权；按金额口径 $148.0） |
| Q2 core debt / DFS debt 的精确拆分 | 只在 10-Q 披露 → 本档用 7:1 公式外推，见 §12.4 |
| Q2 减值 / 汇兑 / 重组的分项金额 | 8-K 只给合计「其他公司费用 $260M」；汇兑仅隐含在 `Interest and other, net`（Q2 −$254M）中 |
| Class A/B/C 的 2026-07-31 期末精确股数 | 8-K 不按类别披露；本档用 10-Q 封面（2026-06-02）648,107,991 股 + 市值锚 646.14M |
| 存货持有收益假说的量化 | 见 §12.5 |

### §12.6.3 其他明确缺口

- **FY27 全年 capex 指引**：8-K 与电话会**均未给**，Dell 惯例不给 capex 指引 → 可能永不闭合。H1 实数 $2,202M（+77.1%）只能事后取。**这直接导致 bull 证据包 (a) 扩产达产确定性判为【不适用/缺】**（[valuation.md §9.3](valuation.md)）。
- **具名 AI 大客户及其 capex 指引**：公司不披露 → `x-growth` 的分层兑证只能停在「②终端总量兑底」，且终端数据全部【软·第三方机构口径】。
- **口径一致的 Dell AI 服务器市场份额**：各家 TAM 口径与 Dell 收入口径不可比（Dell 口径含整机柜、含转售 GPU 全额）→ **渗透率标【缺】，本轮禁用份额论证卡位**。
- **DRAM/NAND 2026 年 6/7/8 逐月合约价**：在 **TrendForce 付费墙内**（付费 DRAM Monthly Datasheet），本轮只取到季度口径的免费新闻稿。
- **政府补助**：8-K 无披露，未找到公开证据。
- **Dell 在主权 AI / Neo Cloud 大单中的中标价与单项目毛利口径**：此类信息不公开。「Dell 在大单中让价」与「Dell 未让价」**两边都无硬证据，不得编**。
- **HPE Q3 FY26 服务器分部利润率**（与 Dell Q2 FY27 同期）：**2026-09-02 美股盘后**才发布，**【缺·待 9/2 盘后】**。该自然实验本轮**无法闭合**，须下一轮补（[events.md](events.md) 待回写钩子 1）。
- **PC 市场 2026 的 TAM 金额口径**：本轮未取证【缺】，[business.md §2.3](business.md) 只用出货量方向与管理层定性表述。

---

## §12.7 已知冲突与本档的取舍

**纪律：三路证据（A1 数据锚 / A2 论点验证 / A3 lens 专项）冲突时，硬数字一律以 A1 的 SEC 原文为准，并在正文显式标注冲突，不静默取一个。**
八条具体冲突（股东赤字 −$1,427M vs −$1,404M、调整后 FCF 的口径方向、非 AI 隐含 OM 的区间、Q1 回购均价、"绝大部分" vs 103%、YTD AI 订单、总股本、正常化参数）**已逐条列在 [valuation.md 末尾的「A2/A3 与 A1 的数字冲突」小节](valuation.md)**，此处不重复。

另有三条**引用禁令**：

1. **IR deck 转述的「YTD AI 服务器订单 $131.7B」** 与公司季度口径相加 $85.3B（Q1 $24.4B + Q2 $60.9B）对不上，差 $46.4B，很可能是「自 FY25 起累计」或另有口径 → **【软·存疑·勿引用】**。需要 YTD 订单时用 **$85.3B**。
2. **Morgan Stanley 的「bull $272 / base $170 / bear $108」** 与其 2026-06-01 上调至 $448 的动作互相矛盾，几乎确定是升级前的旧版本 → **本档不引用**。
3. **市场一致预期 non-GAAP EPS 写「约 $4.9」，不写单点**（Investing.com $4.87、另一源 $4.95，供应商口径不同属正常）。营收一致预期 $44.84B vs 实际 $46.971B，超 +4.8%；EPS 实际 $7.04，超预期约 **42%**。

---

## §12.8 已知局限

1. **本档最重要的单条发现（归因桥表）是推导而非披露**，其成立依赖管理层口头的 AI「mid-single-digit」口径，且**永远无法用一手数据证死**（§12.6.1）。本档已给敏感性带（AI@4%–10% 结论均不变）并写明证伪门槛，但读者须知这不是硬事实。
2. **估值主锚 $466.53 是盘前价**，流动性有限、双源区间 $460–467，**待收盘复核**。本档已同时给出 $425.00 对照价口径下的全部安全边际，两个口径的结论方向一致（−54.7% vs −50.3%）。
3. **Q2 FY27 10-Q 尚未发布**，四项数字仍处【未验证/推算】状态（§12.6.2），其中 Q2 回购均价 $401 若被推翻，将改变 [business.md §5.4](business.md) 对资本配置质量的下修幅度（但不改变「>80% 调整后 FCF 是机械政策」这条结构性判断，后者不依赖该数字）。
4. **HPE Q3 FY26 的自然实验缺席**（9/2 盘后才发），"内存放大器是行业普遍还是 Dell 特有"这一问本轮只能靠 HP Inc.（PC 端）与 HPE Q2 FY26（滞后一季）两个反例作答，证据强度低于同期直接对照。
5. **正常化参数是主观选择而非中性估计**：营收 $155–175B、经营利润率 7.5%–10%、倍数 12–15x —— 其中倍数**低于**卖方共识隐含倍数、也低于公司五年 PE 中位数约 16x，属明确的保守侧选择，理由（增量边际利润率低于存量 → 不具备倍数扩张资格）已在 [valuation.md §9.3](valuation.md) 写明，读者可据此自行调参。
6. **本档不覆盖 Dell 的软件/服务续约经济性、DFS 的利差与资金成本明细、以及 CSG 的商用/消费拆分驱动**，三者均非本轮重审触发变量，未做专门采证。
7. **不构成投资建议。** 本档是公开信息的整理与推理，不含非公开信息，不预测股价，读者应自行核实并独立决策。
