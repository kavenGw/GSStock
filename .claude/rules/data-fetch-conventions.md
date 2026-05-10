# 数据获取坑点约定

> **何时读**：写新数据获取脚本、首次调用 akshare 某接口、抓 PDF 调研纪要、按 stock_name 反查代码、新浪/cninfo/巨潮源切换
> **不必读**：调用现有 UnifiedStockDataService 而不新增数据源

## akshare 财务取数接口约定

- **多年财务时序首选**：`ak.stock_financial_abstract_ths(symbol, indicator="按年度")` — 唯一对全市场（主板/创业板/科创板）稳定返回的接口，含 ROE/毛利率/净利率/营收/净利/现金流/周转/负债率
- **PE/PB 5 年历史分位**：`ak.stock_zh_valuation_baidu(symbol, indicator="市盈率(TTM)"|"市净率", period="近5年")`
- **避坑**：
  - `ak.stock_financial_analysis_indicator(symbol)` 对部分主板代码（如 603986）返回空，不可作默认
  - `ak.stock_a_indicator_lg` 已从 akshare 移除，AttributeError
  - `ak.stock_zh_a_spot_em` / `stock_individual_info_em` 频繁被东财限流（RemoteDisconnected）；实时价改用 `UnifiedStockDataService.get_realtime_prices()`

## stock_name 反查 stock_code

`Stock.stock_name` 是完整名（如 "光迅科技"/"舒华体育"），上层数据（supply_chain / docs frontmatter）常用半截关键词（"光迅"/"舒华"）。精确匹配 `WHERE stock_name=?` 经常返回空；推荐二级 fallback：先精确，失败 `WHERE stock_name LIKE ?||'%'`，多于 1 行视为冲突放弃。

## 研究取数约定

- **新浪 IR 调研 PDF**（`file.finance.sina.com.cn/cn/diaoyan/...`）：WebFetch 返回二进制 blob 无法解析，**不要重试**。Fallback 顺序：① 新浪网页版同内容（`finance.sina.com.cn/stock/...`）② cninfo 直链 PDF（`static.cninfo.com.cn/finalpage/.../*.PDF`，多数可解析）③ 东财财富号 / stcn / 21 经济网摘要稿
- 同一调研纪要常被多家媒体改写发布，交叉验证 2-3 家即可锁定核心数字
