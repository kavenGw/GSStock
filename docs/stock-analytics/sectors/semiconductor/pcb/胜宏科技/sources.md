---
doc_type: buffett-section
stock_code: '02476'
stock_name: 胜宏科技
section: sources
---
# 胜宏科技 — §12 数据来源与局限

> 结论摘要与评级见 [index.md](index.md)；估值口径见 [valuation.md](valuation.md)。

## §12 数据来源

### 12.1 一手来源【硬】

| 来源 | 日期 | 用途 |
|---|---|---|
| **《胜宏科技（惠州）股份有限公司 2026 年半年度报告》**，巨潮资讯网公告 ID 1225522515<br>`http://static.cninfo.com.cn/finalpage/2026-08-28/1225522515.PDF`<br>详情页 `http://www.cninfo.com.cn/new/disclosure/detail?stockCode=300476&announcementId=1225522515&orgId=9900024582` | 2026-08-28 | 全部 26H1 财务数据、非经常性损益明细、在建工程进度、股本演进、股东情况、分红、风险章节、管理层讨论 |
| 2026 年第一季度报告 | 2026-04-29 | 26Q1 基线（营收 55.19 亿 / 归母 12.88 亿 / 扣非 12.57 亿 / 毛利率 34.46%），用于 Q2 单季拆解 |
| H 股全球发售相关公告 `http://static.cninfo.com.cn/finalpage/2026-04-21/1225142557.PDF` | 2026-04-21 | H 股 110,227,500 股 @209.88 HKD、超额配售权行使、控股股东被动稀释 28.13% → 27.71% |
| 《关于控股股东之一致行动人解除质押及部分股份质押的公告》 | 2026-08-12 | 确认存在常规滚动质押（**未读全文，标【软】**） |
| 股票交易异常波动公告（三日涨幅偏离 30%） | 2026-08-07 | 「在手订单持续增长、部分客户已释放 2027–2028 年长期需求」 |
| 澄清公告（否认份额腰斩、丢一供） | 2026-07-13 | 订单合作稳定 |
| 2026-08-28 同日另发：控股股东一致行动协议公告、第五届董事会第十八次会议决议、募集资金专项报告、非经营性资金占用汇总表 | 2026-08-28 | 报告期无非经营性资金占用 |
| NVIDIA FY27Q2 财报电话会 | 2026-08-26 | Vera Rubin 已进入 full production；10 月季度指引隐含 YoY +89%；毛利率指引 74.0% |

### 12.2 行情与财务数据接口【硬】

| 来源 | 取数时点 | 内容 |
|---|---|---|
| 腾讯行情 `http://qt.gtimg.cn/q=sz300476,hk02476` | 2026-08-27 收盘（A 时戳 16:14:48 / H 时戳 16:08:32） | A 263.05 CNY / 市值 2,585.22 亿；H 253.00 HKD / 市值 2,486.4456 亿 HKD；总股本 982,784,813；PE-TTM 51.44（A）。**quote_guard 双验通过，价×股本偏差 0.00%** |
| open.er-api.com | 2026-08-28 00:02 UTC | **HKD → CNY = 0.859478** |
| akshare `stock_financial_abstract_ths` | 2026-08-28 | 2023 起多年财务时序，与中报原文逐项交叉一致 |
| akshare `stock_zh_valuation_baidu` | 2026-08-27 | PE-TTM 五年分位 **72.1%**（913 交易日样本，min 14.82 / 中位 32.80 / max 107.18） |
| akshare `stock_yjbb_em`（date=20260630） | 2026-08-28 | 沪电 / 深南 / 生益 / 鹏鼎 26H1 横比 |
| 腾讯行情（comps） | 2026-08-27 | 沪电 002463 / 深南 002916 / 鹏鼎 002938 / 生益 600183 / 景旺 603228 收盘价、市值、PE、PB |

### 12.3 三方与媒体来源【软】

- **行业景气 / 上游涨价**：财联社 `https://www.cls.cn/detail/2341583`；腾讯新闻 `https://news.qq.com/rain/a/20260616A06FX900`；捷配 `https://www.jiepei.com/design/10199.html`、`https://www.jiepei.com/design/10328.html`；南方财经 `https://www.sfccn.com/2026/8-4/4OMDE1MjBfMjE5ODk4OQ.html`；金融界 `https://m.jrj.com.cn/madapter/stock/2026/08/21080458192291.shtml`；第一财经 `https://www.yicai.com/news/103132369.html`
- **行业 capex / 扩产**：新浪《PCB 资本开支狂飙》`https://www.sina.cn/news/detail/5302183532696250.html`
- **Rubin BOM / 份额纪要**：新浪 `https://www.sina.cn/news/detail/5312763435942662.html`、`https://www.sina.cn/news/detail/5311527039274375.html`、`https://www.sina.cn/news/detail/5295328324753433.html`；雪球 `https://xueqiu.com/1855261132/366851483`；大摩 BOM 拆解转引 `https://finance.sina.com.cn/tech/roll/2026-05-25/doc-inhzcatp2884251.shtml`；东方财富 `https://caifuhao.eastmoney.com/news/20260501153016235564100`
- **Kyber 延迟**：Tom's Hardware `https://www.tomshardware.com/pc-components/gpus/nvidias-kyber-rack-for-rubin-ultra-slips-to-2028`；CNBC `https://www.cnbc.com/2026/07/06/nvidia-kyber-rack-system-delays-manufacturing-taiwan-rubin-chips-.html`（SemiAnalysis 口径，NVIDIA 官方否认）
- **卖方观点**：小摩首次覆盖 600 HKD `https://finance.sina.com.cn/stock/hkstock/hkgg/2026-06-10/doc-iniawxzs5964699.shtml`；小摩下调至 500 HKD `https://finance.sina.com.cn/jjxw/2026-07-21/doc-iniiqquw9234582.shtml`
- **舆情 / 治理**：董事长「电梯门」`https://finance.sina.com.cn/wm/2026-06-08/doc-iniasscn8696835.shtml`、`https://finance.ifeng.com/c/8urPoLCdPy6`；IPO 前套现 `https://m.rccaijing.com/news-7367037161482942172.html`、`https://cj.sina.com.cn/articles/view/2587691232/9a3d08e002001ic1q`；董秘回复业绩预告非强制 `http://finance.sina.com.cn/stock/relnews/dongmiqa/2026-07-31/doc-iniksxpc0938990.shtml`；压哨披露质疑 `https://caifuhao.eastmoney.com/news/20260703180942581790140`
- **同业业绩**：生益 26H1 `https://www.stcn.com/article/detail/4077056.html`；沪电预告 `https://www.ithome.com/0/976/141.htm`
- **股价归因 / 谣言澄清**：`https://www.hstong.com/news/detail/26080801355326603`、`https://finance.sina.com.cn/stock/s/2026-07-14/doc-inihtews5440659.shtml`、`https://m.jiemian.com/article/14561337.html`、`https://finance.ifeng.com/c/8uKD5EfoxYp`
- **公司公开答复**：`https://www.caiwennews.com/article/1507704.shtml`、`https://finance.sina.com.cn/jjxw/2026-05-14/doc-inhxwkue8674974.shtml`

### 12.4 本仓内部来源

- 旧档 `sectors/semiconductor/pcb/2026-06-20-胜宏科技-buffett分析.md`（本轮取代）
- 沪电 2026-08-25 重做档（2025 同口径前五大 53.32% vs 胜宏 41.98%；沪电 26H1 AI 服务器 + HPC 仅占其 PCB 收入 14.1%）
- 结构性关联档见 [related.md](related.md)；事件 theme 见 [events.md](events.md)

## §12.5 已知局限

1. **份额数字全部为【软】证据。** Rubin 单柜价值量占比 71.8%、中板份额 40–50%、谷歌 TPU 份额 >50%、AI 收入占比 >65%、AI 在手订单 +85% —— **无一条来自公司公告或英伟达/谷歌官方**。本档所有涉及份额的判断都建立在券商纪要与自媒体转述之上，**这是本案最大的证据缺口**，也是「确定性档位判定为低」的主要原因。
2. **26H1 中报未披露的关键口径（一律标「未找到公开证据」，本档不用媒体数字替代）**：前五名客户销售额及占比、分产品/分行业/分地区收入拆分、PCB 销量/产量/产销率/单价、下半年业绩指引、在手订单金额、产能利用率、扩产项目达产增量产值、汇兑损失单独金额。
3. **2026 年 200 亿 capex / 180 亿固定资产投资上限的 cninfo 原始公告连续三档未取到**，维持【软·券商汇总口径】。
4. **2020–2022 财务时序本轮未采**（A1 时序自 2023 起完整），故 ROIC 的「10 年平均」标准在本案无法完整应用——已在 [§3.2](business.md) 明写「只有三年的高利润史」。
5. **中报股东表质押列解析存疑**：前两大股东「股份状态」显示「不适用」但数量列与持股数相同，疑为 PDF 表格列错位，**本档不使用「全额质押」表述，不据以定性**。
6. **26Q2 单季数据为 H1 − Q1 派生**（非公司直接披露的单季表），Q1 基线经交叉核对；季节性回测已确认该派生指标对本公司具判别力。
7. **A2 路的两组数据已作废，不出现在本档任何位置**：串档污染数据（营收 59.96 亿 / 归母 23.11 亿，几乎确定为他司数据）、无出处第三方快照（26Q2 营收 67.825 亿）。
8. **三路冲突一律取 A1**：A/H 折价（A1 −17.3% vs A3 估 −11~−13%）、PB（腾讯 6.82 vs 百度 14.85）、PE 五年分位（A1 72.1% vs A3 76.5%）、毛利率方向（中报原文 vs 两条互相矛盾的媒体口径）。逐条对照见 [§9.6(5)](valuation.md)。
9. **无中报后（2026-08-28）的卖方一致预期更新**——中报当天卖方点评尚未出，本档不引用任何「中报后一致预期」。历史上本标的曾流传伪造高盛研报，「2026 净利 128.42 亿（花旗）」这类只在自媒体流传的精确数字已降级处理。
10. **锚价为 2026-08-27 收盘价，非盘中价**；本档写作时 2026-08-28 A 股尚未开盘，中报当日的股价反应未纳入。

---

**本档不构成投资建议。** 所有估值假设均为分析者主观设定，三情景概率赋权是判断而非预测；实际结果可能显著偏离。投资决策请自行独立判断并承担风险。
