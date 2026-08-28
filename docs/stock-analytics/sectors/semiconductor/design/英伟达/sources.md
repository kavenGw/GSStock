---
doc_type: buffett-section
stock_code: 'NVDA'
stock_name: 英伟达
section: sources
---

# 英伟达（NVDA）— §12 数据来源与局限

## §12.1 一手来源（【硬】：SEC 备案 / 公司公告 / 官方文件）

| # | 文件 | 日期 | URL |
|---|---|---|---|
| 1 | **CFO Commentary on Q2 FY2027 Results（本轮第一硬源，9 页 PDF）** | 2026-08-26 | https://s201.q4cdn.com/141608511/files/doc_financials/2027/Q227/Q2FY27-CFO-Commentary.pdf |
| 2 | **Form 10-Q（accession 0001045810-26-000075，季度截至 2026-07-26）** | 2026-08-26 | https://www.sec.gov/Archives/edgar/data/1045810/000104581026000075/nvda-20260726.htm |
| 3 | 业绩新闻稿（8-K Ex-99.1） | 2026-08-26 | https://www.sec.gov/Archives/edgar/data/1045810/000104581026000073/q2fy27pr.htm ／ https://nvidianews.nvidia.com/news/nvidia-announces-financial-results-for-second-quarter-fiscal-2027 |
| 4 | Q3 FY2026 业绩新闻稿（TTM 基期 + 股权浮盈基数） | 2025-11-19 | https://www.sec.gov/Archives/edgar/data/1045810/000104581025000228/q3fy26pr.htm |
| 5 | Q4 FY2026 业绩新闻稿（TTM 基期 + FY26 全年股权浮盈 $8,918M） | 2026-02-25 | https://www.sec.gov/Archives/edgar/data/1045810/000104581026000019/q4fy26pr.htm |
| 6 | Vera Rubin 进入 full production 官宣 | 2026-05-31 | https://nvidianews.nvidia.com/news/vera-rubin-full-production-agentic-ai-factory |

**【硬-】电话会管理层原话**（毛利率 71–72% / 72–73%、FY2028 约 +70%、内存成本、supply-constrained 表述）：**A1 未取得电话会逐字记录原文**（singjupost / alphastreet / CNBC live blog 均返回 403），本档所引为**两个以上独立媒体一致引述**，可信度高但**非一手记录**，故统一标记为【硬-】：
https://247wallst.com/investing/2026/08/27/nvidia-surges-6-as-a-70-growth-forecast-overrides-a-memory-margin-warning-amd-and-intel-tick-up/ ／ https://finance.yahoo.com/technology/ai/articles/nvidia-q2-earnings-call-highlights-230417656.html ／ https://finance.biggo.com/news/US_NVDA_2026-08-26

## §12.2 行情与估值锚

| 项 | 来源 | 日期 |
|---|---|---|
| 收盘价 $227.98 / 股本 24.147B / 市值 $5,505.03B / 52 周区间 / 估值倍数 | https://stockanalysis.com/stocks/nvda/ 及 /statistics/ /history/ /dividend/ /financials/；控制者腾讯口径交叉一致（收盘价双源一致） | 2026-08-27 收盘 |
| **quote_guard 断言** | `python scripts/quote_guard.py --code NVDA --price 227.98 --volume 297197891 --ts "2026-08-27 16:00:00" --shares 24147000000 --market-cap 5505034000000` → **通过，价×股本偏差 0.00%，EXIT=0** | 2026-08-28 |
| comps（AMD / AVGO / TSM / MRVL，同为 2026-08-27 收盘） | https://stockanalysis.com/stocks/amd/statistics/ 等 | 2026-08-27 |
| 卖方一致预期 FY2027 / FY2028 | https://stockanalysis.com/stocks/nvda/forecast/（FY27 $9.27，34 位，"as of Aug 27, 2026"）／ https://finance.yahoo.com/quote/NVDA/analysis/（FY27 $9.05 / FY28 $13.13） | 2026-08-28 取数 |

> ⚠️ **yfinance `previous_close`=219.53 是异常值，已弃用**——它既不等于 8/25 收盘（$213.05）也不等于 8/26 收盘（$209.66）。本档一律以 stockanalysis 历史表的 $209.66 为 8/26 收盘。

## §12.3 第三方与媒体来源（【软】，附不确定度）

| 主题 | 来源 | 不确定度 |
|---|---|---|
| TrendForce：2026 ASIC 型 AI 服务器出货占比 27.8%、ASIC +44.6% vs GPU +16.1% | trendforce.com（2026-01-20 / 03-18 / 08-03） | 中（**出货台数口径，不可与收入或「训练负载」口径互换**） |
| 中国 H200：批准量可能 <20 万颗、实际到货约配额 13%（限制方是北京） | TrendForce（2026-07-09）／ TechTimes（2026-08-20） | 中 |
| Hyperscaler capex 与融资结构（2026 $690–800B；债务占 capex 9%→32% LTM；Alphabet $84.75B 股权融资） | insight.factset.com ／ tmtfinance.com ／ futurumgroup.com | **高（预测性质）** |
| 2027 capex 分口径锚（四家 $934.5B / Moody's 近 $1T / GS $1.01T / JPM 约 $1.0T / MS 约 $1.2T / 管理层前五大 $1.3T） | io-fund（2026-08-05）／ computeforecast.com ／ datacenterdynamics.com ／ 电话会转述 | 高（主体范围各异，**须并列披露**） |
| AI 加速器收入份额 70–75%（另一估 80–85%） | 多家第三方 / 部分为 SEO 类站点 | **中低（机构分歧 10ppt 以上，须并列）** |
| New Street Research：2028 年推理专用算力份额或降至 20–30% | 券商 | 高（单一机构预测） |
| BofA：AI 数据中心系统 TAM 2030 年 $1.7T | 券商 | 中 |
| CoreWeave 债务 $35B、季度净利息 $640M、2026-07 贷款 SOFR+425–450bp 被迫上调、股价 −52% | capacityglobal.com ／ techtimes.com ／ 多源 | 中（CDS 隐含 50% 违约概率一条**来源可靠度中低**） |
| GPU 租赁价：Silicon Data B200 指数 $5.45/GPU-hour；AIMultiple 挂牌中位 $6.22（区间 $3.75–$16.11） | silicondata.com/products/silicon-index/b200 ／ aimultiple.com/gpu-index | 中（Silicon Data **页面无时戳，日期不可确认**；AIMultiple 为**挂牌价非成交价**，2026-08-25） |
| AI 服务器整机提价 >15%（Vera Rubin / GB 系列，2027 年初批次） | tomshardware.com ／ trendforce.com（2026-08-25） | 中（媒体转述，**非公司披露**） |
| 折旧年限：Amazon 6→5 年（营业利润冲击 $700M）；Meta 延至 5.5 年（减少冲击 $2.9B） | 各公司披露（2025） | 低（公司披露）／ 汇总口径为中 |
| Michael Burry 指控：2026–2028 累计少提折旧约 $176B（另一口径约 $200B） | 自述 + 自建模型 | **高（单方指控，非监管披露）** |
| comps 最新季 DC/AI 增速（AMD +107% / AVGO +143% / MRVL +46%） | 各公司 IR ／ datacenterdynamics.com | 中（**财季截止日不同，不可直接横比**） |
| MRVL 2026-08-27 盘后 −7.80% | stockanalysis 快照 | 中（**未取得次日收盘确认**） |
| NVIDIA 拟以 $12.9B 收购 Hugging Face | The Information 首报 → CNBC / Fortune 转述（2026-08-27） | **高·传闻。公司未确认、未发 8-K、协议未签署、可能告吹。本档只作一句带过，不进入任何估值情景。** |
| 与 6 家资本方（Apollo/BlackRock/Blackstone/Brookfield/Goldman Sachs/KKR）签 MOU 筹建独立融资平台 | 10-Q Item 1A 自述【硬】＋ 规模数字【软】 | 10-Q 明写「可能不会形成正式协议」，**只作观察项** |
| OpenAI / Anthropic 合计 ARR > $105B（2026-08）；Goldman：2026–2031 累计 AI capex 约 $7.6T、需 2030 前做到 $1T ARR | 第三方追踪 / 券商 | **高（口径不一，须固定同一追踪源）** |

## §12.4 三路 evidence 的数字冲突处理（一律取 A1，并显式标注）

| # | 冲突项 | A2 / A3 口径 | **A1 口径（本档采用）** | 处理 |
|---|---|---|---|---|
| 1 | **DSO** | A2：51.4 → 59.6 天（+8.2 天，基准 Q4 FY26）；A3：45 → 60 天（基准上季） | **同口径 YoY：Q2 FY26 的 54.1 天 → Q2 FY27 的 59.6 天，恶化 +5.5 天** | A1 做了季节性回测（FY26 Q1→Q2 为 45.7→54.1，+8.4 天；FY27 为 45.4→59.6，+14.2 天）——**Q1→Q2 存在真实季节性，写成「45→60」夸大信号强度**。本档取 A1 的同口径 YoY 读数，并并列客户预收款 $160M → $2.8B 的对冲信号 |
| 2 | **存货跌价计提** | A3：Q2 $784M / H1 $1.6B | **计提毛额 Q2 $985M / H1 $2,100M；转回 −$177M / −$280M；对毛利率净不利 −0.8pp / −1.0pp** | 取 A1（毛额与转回分列，来自 10-Q MD&A） |
| 3 | **非可交易证券余额** | A2 / A3：Note 6 非上市股权账面 $47.898B | **资产负债表科目「Non-marketable securities」$51.157B** | **不是矛盾，是两个行项**。本档在资产负债表语境用 $51.157B、在 Note 6 明细语境用 $47.898B，并各自标注 |
| 4 | **FY2028 non-GAAP EPS 自算** | A3：$15.45 / $15.28 | **$15.82（管理层 +70% 指引推算）** | 取 A1；A3 的差异来自其自设 FY28 股本 23.9B 与 opex 假设 |
| 5 | **2027 hyperscaler capex 的呈现方式** | A3 §B-2：「$934.5B 与 $1.3T 不自洽，**不得并列引用**」 | **应并列为 $0.93T–$1.3T 区间并标口径，上沿为管理层口径且更激进** | 取 A1 校准补充②（逐数溯源到发布方与主体清单）。**A3 的禁令被推翻** |
| 6 | **GPU 租赁价格** | A3 §C-1 L1：保留「B200 三周跌 30% 至 $4.22」并标「数据冲突」 | **该读数为 2026-06 中旬、发布于 2026-06-23、来源为加密媒体转载，已过期且低质，不作任何裁定依据** | 取 A1 校准补充③。本档正文只用当期读数（$5.45 / $6.22），并明写「当前口径下租金较 6 月低点反而回升」 |
| 7 | **Data Center Networking 增速** | 媒体转述「networking +138%」 | **本季未拆分披露 compute vs networking【缺】**；138% 恰等于 ACIE 的同比增速，**高度疑似媒体串号，不予采信** | 取 A1，标【缺】 |

## §12.5 已知局限与【缺】项清单（明写未找到，未编造）

**口径断裂（公司不再披露或本季未披露）**
- **Data Center 的 compute vs networking 本季未拆分披露【缺】。**
- **Gaming / Professional Visualization / Automotive / OEM 单项收入【缺】**——自 FY27Q1 起并入 Edge Computing，公司不再单独披露，**旧档对应字段无法延续**。
- **Q2 单季经营现金流未单列【缺】**（10-Q 只披露 H1 累计 $74.421B）——本档所有现金转化率均为 **H1 口径**，已显式标注。
- **汇兑损益**：财报未单独披露、未提及为重大【缺】。

**未找到公开证据（不得据此推断任一方向）**
- **Kyber NVL144 / NVL576 时间表**：SemiAnalysis 报道未撤稿，英伟达仅回应「Our roadmap is intact」且未给具体日期，**FY27Q2 财报与 10-Q 全文无 Kyber / NVL144 / NVL576 / Rubin Ultra 任何字样**（已对解析全文检索确认）→ **维持未决**，不得因 Q2 大超预期而反向推断已解决（Q2 确认的是 VR200 NVL72 / Oberon 机架世代，与 Rubin Ultra 世代的 Kyber **本就不冲突，对其时点不具判别力**）。
- **主要客户的 CUDA 迁移比例、ROCm / TPU-XLA / Triton 的实际软件栈份额【缺】。**
- **按「训练负载」口径的 ASIC 份额【缺】**——未找到任何机构有此统计，**旧档该假设自设立起即不可检验**。
- **「NVDA 拿 hyperscaler capex 70%+」【缺】**——未找到任何权威口径支持或证伪；粗算 FY27E 营收 ÷ 2026 capex ≈ 50–58%，但**分子分母口径不可比**（capex 含土地/电力/厂房/自建网络），不得据此裁决。
- **出口管制向中端（RTX Pro Blackwell 等）扩散**：2026-08 未见新增公开限制证据【缺】，不得据此写风险已解除或已扩大。
- **十年平均 ROIC【缺】**——公司规模两年内扩大约 5 倍，十年均值对当下无判别力，本档改用均值投入资本口径自算（见 [§3.4](business.md)）。
- **TSM 最新季 HPC / AI 平台收入拆分【缺】**——本轮未取。
- **电话会逐字记录原文【缺】**——多个转录站点返回 403。

**不得混用的口径（已在正文各处标注）**
- 中国「客户总部口径营收 $7.880B / 8.2%」≠「中国 Data Center 算力收入 <1% DC」。
- $1T 可见度 ≠ backlog；$279B 是 **NVDA 欠供应商**的，不是客户欠 NVDA 的。
- 应收集中度的比较基准是 **2026-01-25（FY26 年末）**，不是「一年前」。
- 担保的**违约敞口**（$105B 中已生效分期部分）≠ **年度义务额**（第三方测算 FY28–31 每年 $6–8B）。
- 对 OpenAI 的 $2,500 亿租约担保 / $3,500 亿芯片融资**传闻**，与 10-Q 实际披露的 $105.0B SB Energy 担保**不是同一口径**，不得混用。

**本档主动禁用的数字**
- 管理层 $3–4T TAM（利益相关方自估，与第三方差 2 倍以上）。
- PEG（分母是单年超常增速）——仅在 [§9.5](valuation.md) 作一次旁证提及。
- 思科 2000 年峰值 PE 的具体数值（检索到 472× 与 100–130× 两说，来源可靠度低）——**只作定性对比**。

## §12.6 lens 命中与库缺口备案

本轮命中横切 lens **`x-ai.md` + `x-growth.md`**（`design` 子板块**无板块专属 lens 命中**，`x-dividend-value.md` 因 sector 不在条件集且为高增长再投资标的而不命中）。
**备案（不写进正文）**：`design` 子板块缺一条「AI 算力芯片设计（周期位置 / 客户资本开支依赖 / 生态锁定）」族的板块专属 lens，本轮由周期位置（[§8](thesis.md)）、折旧年限传导（[§8.3](thesis.md)）、监控模板（[§11.1](index.md)）三项代偿。建议后续新增 `ai-accelerator-design.md`。

---

## 免责声明

本文基于 2026-08-28 之前的公开信息撰写，数据截至 2026-08-27 美股收盘。所有前瞻性表述（含管理层指引、第三方预测、三情景估值）均为估计而非事实，可能与实际结果存在重大差异。**本分析不构成投资建议。**
