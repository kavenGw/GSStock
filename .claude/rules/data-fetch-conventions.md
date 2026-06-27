# 数据获取坑点约定

> **何时读**：写新数据获取脚本、首次调用 akshare 某接口、抓 PDF 调研纪要、按 stock_name 反查代码、新浪/cninfo/巨潮源切换、腾讯 HTTP 行情字段 / 港股 q=hk 取数 / A+H 市值自洽校验
> **不必读**：调用现有 UnifiedStockDataService 而不新增数据源

## akshare 财务取数接口约定

- **多年财务时序首选**：`ak.stock_financial_abstract_ths(symbol, indicator="按年度")` — 唯一对全市场（主板/创业板/科创板）稳定返回的接口，含 ROE/毛利率/净利率/营收/净利/现金流/周转/负债率
- **单季财务时序（含单季扣非/营收YoY/单季毛利率净利率）**：`ak.stock_financial_abstract_ths(symbol, indicator="按单季度")` —— 返回**最旧在前**，取最近期需 `df[df['报告期']>='YYYY-01-01']` 过滤。**单季扣非此接口可取，勿在档里写"未披露"**。
- **投研财务对比一律先用最新一期单季季报刷新、年报仅作对照**：comps / buffett / 季报点评的营收/净利/毛利率对比优先取最新单季（如 2026Q1），年报口径的结论（营收趋势、盈利成色）常被最新季报翻转。**单季归母可能靠非经常性损益转正而扣非仍亏——盈利质量看扣非不看归母**。
- **PE/PB 5 年历史分位**：`ak.stock_zh_valuation_baidu(symbol, indicator="市盈率(TTM)"|"市净率", period="近5年")`
- **主营业务构成**：`ak.stock_zygc_em(symbol='SZ300757')`（symbol 必带 `SZ`/`SH` 前缀）。同一 `(股票代码, 报告日期)` 返回多行，靠 `分类类型` 列区分三种切片：行业分类（NaN）/ 按产品分类 / 按地区分类。用途：buffett 分析定 sector/subsector、判"主业收入第一权重"、识别境内外占比与海外敞口。取最新一期：`df[df['报告日期']==df['报告日期'].max()]`
- **避坑**：
  - `ak.stock_financial_analysis_indicator(symbol)` 对部分主板代码（如 603986）返回空，不可作默认
  - `ak.stock_a_indicator_lg` 已从 akshare 移除，AttributeError
  - `ak.stock_zh_a_spot_em` / `stock_individual_info_em` 频繁被东财限流（RemoteDisconnected）；实时价改用 `UnifiedStockDataService.get_realtime_prices()`

## get_realtime_prices 批量优先

一次性脚本 / 批处理逻辑里**先用 `get_realtime_prices(all_codes)` 一次取所有，再字典查表**，不要在循环里逐 code 调。逐 code 调用偶发返回 `current_price=0` 或 `None`（疑似内存缓存层与并行 `force_refresh` 调度互动产生过期条目），批量调用稳定。下游计算（如 `target_shares = floor(target_value / price / 100) × 100`）只要 price=0 就静默给出 0 股，掩盖数据问题。

## stock_name 反查 stock_code

`Stock.stock_name` 是完整名（如 "光迅科技"/"舒华体育"），上层数据（supply_chain / docs frontmatter）常用半截关键词（"光迅"/"舒华"）。精确匹配 `WHERE stock_name=?` 经常返回空；推荐二级 fallback：先精确，失败 `WHERE stock_name LIKE ?||'%'`，多于 1 行视为冲突放弃。

## yfinance 港股代码格式

yfinance 港股（实时价/历史）**只认 4 位补零** `<4位>.HK`：`1810.HK` / `9992.HK` / `0189.HK`。裸数字（`01810`）或 5 位补零（`09992.HK`、`01024.HK`）一律 `KeyError` 无价。归一：`f"{int(code.upper().removesuffix('.HK')):04d}.HK"`。

`MarketIdentifier.identify` **只认 `.HK` 后缀**——裸数字港股（`01810`）会 fallback 成美股走 yfinance 无效 ticker。消费来自 yaml/frontmatter 的 HK 代码（其形态不统一）喂给 `get_realtime_prices` 前必须先归一为 `.HK`，或用上游已有的 `market` 字段判断（参考 `app/routes/valuations.py:_fetch_code`）。

## 腾讯 HTTP 行情源取数坑

实时价格和分时K线优先使用腾讯HTTP接口（并发安全、无需限速）：
- 实时价格批量：`http://qt.gtimg.cn/q=sh600519,sz000001`（GBK编码，`~`分隔）
  - `q=` 字段索引：`[1]=name [3]=price [4]=prev_close [5]=open [6]=volume(手) [32]=change_pct [38]=换手率 [39]=PE_TTM [41]=年高 [42]=年低 [45]=市值(亿) [46]=PB`（亏损股 PE 为负值，与 baidu 估值分位接口结合用来判当前 PB/PE 在历史分位）
- 分钟K线：`http://web.ifzq.gtimg.cn/appstock/app/kline/mkline?param=sh600519,m1,,240`
- 日K线：`http://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=sh600519,day,...`
- **字段顺序**：`[datetime, open, close, high, low, volume]`（close在第2位，非标准OHLC）
- **XD（除息日）字段失真**：分红除息当日 `q=` 接口 name 带 `XD` 前缀，且 52 周高/低字段 `[41]/[42]` 返回失真值（如现价 51.7 却报 52.92/50.78），**不可信**；price/PE_TTM/市值/PB 仍可靠。需 52 周区间改用 baidu 估值接口。
- **[41]/[42] 非除息日也可能失真**：即便非 XD 日，年高/年低字段偶尔返回**近现价窄区间**（实测 600362 现价 40.49 却报年高 40.90/年低 39.65，明显非真实 52 周），疑为近期区间而非 52 周口径；判 52 周区间/分位一律以 baidu 估值接口为准，勿信 [41]/[42]。
- **只取实时价的一次性脚本直连 HTTP 优先**：`urllib.request` 拉 `qt.gtimg.cn/q=sh600519,sz000001,...` 比走 `create_app() + UnifiedStockDataService` 快 5x+ 且无副作用（即便 `SCHEDULER_ENABLED=0`，create_app 仍会启 crawl4ai 抓 google 新闻产生数十行噪音日志）；服务化路径仅在需要缓存 / 指数 / OHLC 时才走
- **港股取数字段不同**：`q=hk03690`（GBK/`~`分隔）字段索引与 A 股不一致，**勿照搬 A 股 [39]PE/[45]市值/[46]PB**；港股市值/PE(TTM)/PB/PS/52周区间改用 WebFetch `stockanalysis.com/quote/hkg/<code>/statistics/`（URL 用**去前导 0** 代码：`hkg/2631` 通、`hkg/02631` 报 404）或 Yahoo `<code>.HK`，交叉验证 2 源（市值口径常分歧）。亏损港股 PE(TTM)=N/A，估值锚改看 PS / PB / Forward PE
  - **A+H 标的 H 口径市值自洽校验**：
    > A+H 选哪一地口径作跟踪主体的**决策铁律**见 portfolio-valuations.md；此处只讲 H 口径市值的取数自洽校验。
    stockanalysis 的 market cap 对 A+H 双重上市股**股本口径可能错**（实测 02631 报 794 亿 HKD→反推 8 亿股，与 A 股总市值÷A股价自洽总股本 4.85 亿矛盾）；H 口径全公司市值一律用「**A 股总市值 ÷ A 股价反推总股本 × H 股现价**」自洽校验，**AH 折价 = H 口径市值 ÷ (A 市值×1.08) − 1**（RMB→HKD）。腾讯 `q=hk<code>` 取 H 股现价可靠，但勿 `print` 其中文 name 字段（cp950 报错），只取 `f[3]` 价。

## 研究取数约定

- **新浪 IR 调研 PDF**（`file.finance.sina.com.cn/cn/diaoyan/...`）：WebFetch 返回二进制 blob 无法解析，**不要重试**。Fallback 顺序：① 新浪网页版同内容（`finance.sina.com.cn/stock/...`）② cninfo 直链 PDF（`static.cninfo.com.cn/finalpage/.../*.PDF`，多数可解析）③ 东财财富号 / stcn / 21 经济网摘要稿
- 同一调研纪要常被多家媒体改写发布，交叉验证 2-3 家即可锁定核心数字
