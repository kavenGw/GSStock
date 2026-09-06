---
paths:
  - "app/services/**"
  - "scripts/**"
---
# 数据获取坑点约定

> **何时读**：写新取数脚本、首次调用某 akshare 接口、腾讯 HTTP 行情字段、港股取数、A+H 市值校验、抓调研 PDF、按 stock_name 反查代码

## akshare 财务接口

- **多年财务时序**：`ak.stock_financial_abstract_ths(symbol, indicator="按年度")`，唯一对全市场稳定的接口（ROE/毛利率/净利率/营收/净利/现金流/周转/负债率）。
- **单季时序（含单季扣非）**：同接口 `indicator="按单季度"`，返回最旧在前，取近期用 `df[df['报告期']>='YYYY-01-01']`。单季扣非可取，勿写「未披露」。
- **投研对比以最新单季为主、年报为对照**，年报结论常被最新季报翻转；盈利质量看扣非不看归母。
- **PE/PB 5 年分位**：`ak.stock_zh_valuation_baidu(symbol, indicator="市盈率(TTM)"|"市净率", period="近5年")`。
- **主营构成**：`ak.stock_zygc_em(symbol='SZ300757')`（必带 `SZ`/`SH`），同一报告期多行，按 `分类类型` 分行业/产品/地区切片，取 `df['报告日期'].max()`。用于定 sector/subsector 与海外敞口。
- **避坑**：`stock_financial_analysis_indicator` 对部分主板代码返回空；`stock_a_indicator_lg` 已移除；`stock_zh_a_spot_em` / `stock_individual_info_em` 常被东财限流，实时价改用 `UnifiedStockDataService.get_realtime_prices()`。

## 实时价与代码归一

- **批量优先**：`get_realtime_prices(all_codes)` 一次取全，再字典查表；循环逐 code 调偶发返回 0/None，下游 `floor(value/price/100)*100` 会静默给 0 股。
- **stock_name 反查 code**：`Stock.stock_name` 是全名，上层常用半截关键词。先精确匹配，失败再 `LIKE ?||'%'`，多于 1 行视为冲突放弃。
- **yfinance 港股只认 4 位补零** `1810.HK`：归一 `f"{int(code.upper().removesuffix('.HK')):04d}.HK"`。`MarketIdentifier.identify` 只认 `.HK` 后缀，裸数字港股会误判为美股；来自 yaml/frontmatter 的 HK 代码喂 `get_realtime_prices` 前先归一（参考 `app/routes/valuations.py:_fetch_code`）。

## 腾讯 HTTP 行情源

并发安全、无需限速，实时价与分时优先用它。

- 实时价批量：`http://qt.gtimg.cn/q=sh600519,sz000001`（GBK，`~` 分隔）。字段：`[1]name [3]price [4]prev_close [5]open [6]volume(手) [32]change_pct [38]换手 [39]PE_TTM [45]市值(亿) [46]PB`。
- 分钟 K：`web.ifzq.gtimg.cn/appstock/app/kline/mkline?param=sh600519,m1,,240`；日 K：`.../fqkline/get?param=sh600519,day,...`。字段顺序 `[datetime, open, close, high, low, volume]`（close 在第 2 位）。
- **`[41]/[42]` 年高/年低不可信**（除息日与非除息日都可能失真），**`[47]/[48]` 是涨跌停价不是 52 周区间**。52 周区间一律用日 K 拉一年 qfq 或 baidu 估值接口。
- **一次性脚本只取实时价直连 HTTP**，比 `create_app()` 快 5x 且无副作用；需缓存/指数/OHLC 才走服务化路径。
- **港股 `q=r_hk<code>`**（78 字段）：实时价字段索引与 A 股一致（`[3]`价 `[4]`昨收 `[6]`量为股 `[30]`时间戳），已接入主链路。**裸 `q=hk<code>` 是 15 分钟延迟口径**，主链路一律 `r_hk`。估值字段索引与 A 股不同，勿照搬 `[39]/[45]/[46]`；港股市值/PE/PB/52 周改用 WebFetch `stockanalysis.com/quote/hkg/<去前导0代码>/statistics/` 或 Yahoo `<code>.HK`，两源交叉。亏损港股 PE=N/A，锚改 PS/PB/Forward PE。勿 `print` 中文 name 字段（cp950）。
- **A+H 标的 H 口径市值自洽校验**：stockanalysis 对 A+H 股本口径可能错。全公司市值用「A 股总市值 ÷ A 股价反推总股本 × H 股现价」；AH 折价 = H 口径市值 ÷ (A 市值×1.08) − 1。选哪一地口径的决策铁律见 portfolio-valuations.md。

## 研究取数

- 新浪 IR 调研 PDF（`file.finance.sina.com.cn/cn/diaoyan/...`）WebFetch 返回二进制，**不要重试**。Fallback：① 新浪网页版 ② cninfo 直链 PDF ③ 东财财富号 / stcn / 21 经济网摘要稿。
- 同一纪要多家改写，交叉 2-3 家即可锁定核心数字。
