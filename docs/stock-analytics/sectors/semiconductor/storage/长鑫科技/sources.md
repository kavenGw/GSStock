---
doc_type: buffett-section
stock_code: '688825'
stock_name: 长鑫科技
section: sources
---
# 长鑫科技 — §12 来源、方法与局限

## §12 数据来源与核验边界

本轮检索和行情核验日期为2026-10-30。标【硬】为公司公告、官网、监管或原厂披露；【软】为机构研究预测及二手材料；【缺】为未取得足够公开证据。财务与股本最终按官方报表统一，不把机构预测混成公司指引。

### 12.1 公司报表与公告

| 来源 | 日期/页码 | 本轮用途 |
|---|---|---|
| [2026第三季度报告，巨潮正式PDF](https://static.cninfo.com.cn/finalpage/2026-10-31/1225649723.PDF)【硬】 | 公告日期10月31日、报告落款10月30日；上交所接口记录10月30日18:19:10已上线；13页，未经审计 | p1—2累计与Q3数据、环比及G6样片；p6—9资产负债、股本；p9—11利润；p12—13现金流 |
| [2026半年度报告](https://static.cninfo.com.cn/finalpage/2026-08-29/1225529543.PDF)【硬】 | 8月29日，192页，未经审计 | p9财务指标、p32毛利口径、p66—71主表、p117—118存货准备、p151—152现金桥、p180资本承诺；用于累计减法 |
| [前三季计提资产减值准备公告](https://static.cninfo.com.cn/finalpage/2026-10-31/1225649689.PDF)【硬】 | 10月31日公告、10月30日晚上线，2页 | 存货/在建/固定资产/信用分项；累计损益不冒充期末准备余额 |
| [集中竞价回购方案](https://static.cninfo.com.cn/finalpage/2026-10-31/1225649694.PDF)【硬】 | 同日晚披露，8页 | 金额、价格上限、股东会及上市满6个月条件；p5最新股本与限售比例、p6减持意向边界 |
| [超募资金投资新项目公告](https://static.cninfo.com.cn/finalpage/2026-09-29/1225586345.PDF)【硬】 | 9月29日，7页 | p1—2净募资/净超募、研发及后道130/50亿元，30/37个月工期；董事会计划不等于达产 |
| [2026半年报业绩说明会](https://roadshow.cnstock.com/fbh/cxkj202606)【硬：管理层口径】 | 9月7日 | 具名客户合作、服务器贡献方向、HBM及新品利润未量化的披露边界 |

采证最初通过东财公告API镜像查到正文，上交所new路径下载曾返回空白页；随后已从巨潮取得完整13页PDF并逐页提取。正式数字以上表巨潮全文为准，不保留“仅见新闻/镜像”的初期局限，也不声称空白PDF已核实全文。

历史2025年度归母18.7486亿元、2025前三季归母−52.7997亿元、2025Q4销售额份额7.67%等继承招股书与旧档已核基线；本轮未重新审阅完整历史招股书，不把历史份额标成当前份额。旧平铺档迁移后的历史依据在Git可查，不在新正文保留死链。

### 12.2 技术、原厂与行业来源

- 【硬】[长鑫LPDDR6量产商用公告](https://www.cxmt.com/news/info_96.html)，2026-09-07；[英文同源](https://www.cxmt.com/en/news/info_21.html)。16Gb单颗粒与16GB封装容量分开；12800Mbps为峰值、10667Mbps为搭配SoC运行速率。公司内部测试收益不当作全应用统一提升。
- 【硬】[G5及24Gb LPDDR5X量产公告](https://www.cxmt.com/news/info_97.html)，2026-09-20。11.95nm有源区半间距、统一换算8Gb的DPW提升，不等于良率、全公司bit供给或成本同比例变动。
- 【硬】[长鑫DDR5/LPDDR5X产品展示](https://www.cxmt.com/en/news/info_20.html)，2025-11-23。旧“仅有legacy产品”的绝对说法本就不严谨。
- 【硬】[三星2026Q3业绩](https://news.samsung.com/global/samsung-electronics-announces-third-quarter-2026-results)，2026-10-29。AI产品组合、服务器DDR5增供与竞争可逆性。
- 【硬】[SK海力士2026Q3业绩](https://news.skhynix.com/en/q3-2026-business-results/)，2026-10-28。M15X爬坡、2027投资、LTA需求能见度；旧细粒度月产能和投产日未复核，不沿用为硬数。
- 【硬】[美光Manassas扩产公告](https://investors.micron.com/news/press-release/2026/Micron-Advances-Made-in-America-Memory-With-Manufacturing-Expansion-in-Virginia/default.aspx)，2026-05-22。长生命周期DDR4/LP4供给反证；[DDR4产品目录](https://www.micron.com/products/memory/dram-components/ddr4-sdram/part-catalog)同时有生产与EOL型号，不能认定全品类退出。
- 【软：机构原始预测】[TrendForce Q4价格展望](https://www.trendforce.com/presscenter/news/20260930-13258.html)，2026-09-30。常规DRAM合约价预计+10%—15%、NAND+15%—20%，前者非服务器专属指数，后者非长鑫主业。
- 【软：机构报价】[TrendForce价格页](https://www.trendforce.com/price/dram/dram_contract)，采证快照2026-10-30 11:00 GMT+8。特定规格现货不能替代公司ASP；动态页后续可能变化。
- 【软：机构观察】[10月21日存储现货更新](https://www.trendforce.com/news/2026/10/21/insights-memory-spot-price-update-ddr5-supply-tight-ddr4-trading-subdued-despite-0-84-gain-in-mainstream-prices)，价格观察截至10月20日。渠道库存和终端成交差异，不等于长鑫自身库存天数。
- 【软：机构原始预测】[AI服务器需求预测修订](https://www.trendforce.com/presscenter/news/20261014-13269.html)，2026-10-14。32.2%为2026出货增速预测、2027近36%；不把整机TAM当长鑫SAM。

### 12.3 行情、政策与已纠正错误

行情双源：[腾讯sh688825](https://qt.gtimg.cn/q=sh688825)，2026-10-30 16:14:38；[新浪sh688825](https://hq.sinajs.cn/list=sh688825)，15:34:59（接口需新浪Referer）。收盘41.80元，成交285,513,767股、121.4502亿元；本次科创板腾讯字段量与新浪股数一致，不能照搬普通A股“手”的字段单位。股本以Q3及回购方案为准。

已跑quote_guard，代码带sh前缀、股本与市值自洽，exit0。因快照为收盘后的接口更新时间，按技能收盘锚规则使用allow-preopen；脚本固定打印“竞价参考价”警告，不代表本次真实成交快照是开盘竞价。接口PB14.11分母滞后，正文采用Q3权益重算11.0464倍；不沿用旧PB或首日高价。

政策来源为[2026-06-10国防部1260H名单公告](https://www.govinfo.gov/content/pkg/FR-2026-06-10/pdf/2026-11571.pdf)及[2026-02-17 FAR拟议采购规则](https://www.federalregister.gov/documents/2026/02/17/2026-03065/federal-acquisition-regulation-prohibition-on-certain-semiconductor-products-and-services)。1260H与BIS实体清单不同，Proposed Rule与最终规则不同，联邦采购与全球商业销售不同。本轮未完成BIS全实体最新清单逐项核检，也未取得采购最终规则，执行状态保留待核；不提供法律适用判断。

本轮明确撤回旧“无高端产品/固定落后2—3代”“少数损益稳定24%”“当前隐含利润为顶部2.1倍”和“账面净资产无条件托底”。旧H1预估、绿鞋前股本、预测权益基数均替换。A2早期财务数字及A3最初SSE原文链接已由A1最终官方PDF统一；不存在静默择取不同利润口径的处理。

### 12.4 仍影响结论的缺口

| 缺口 | 对判断的影响 |
|---|---|
| bit出货、ASP、产品结构及良率的同口径分拆 | 无法精算量价/技术贡献；正常化毛利需宽情景 |
| G5全公司占比、LPDDR6独立收入、G6量产时间 | 技术里程碑不能直接变全公司盈利预测 |
| HBM项目、收入和长期客户 | 不计HBM利润，不声称公司绝无相关研发 |
| 分厂利润与少数权益经济归属 | 无法解释全部归母降速原因，未来归母份额为假设 |
| 9M完整D&A、维护capex、研发及营运资金桥 | OE为模型估计，不能把集团FCF全给归母 |
| 受限资金、其他非流动负债及可自由分派现金 | 不单加全部集团净现金，另列敏感性 |
| Q3存货准备余额、分项计提/转回 | 无法判余额比率>8%是否触发 |
| 同机构连续两季份额与服务器合约价实际指数 | 不拼不同机构数据，不把预测判成已实现 |
| 全部老股逐条锁定期限 | 不把2027某日概括成所有限售股同日释放 |
| 超募方案股东会最终决议与真实付款进度 | 方案公告已触发监控，尚不能视作达产或已支出 |
| 最新完整BIS逐实体与联邦采购最终规则 | 政策触发器待核，不能把缺证记作未触发 |

上述缺口没有通过引用更多软材料消失。估值的正常化收入、毛利、费用、税率、经济份额、维护开支、未来现金路径和概率均为分析者判断，可复算但不代表可精确预测。估值变化与触发器留在正文便于下期核验。

本分析是公开信息研究，不构成投资建议。
