# 盯盘币安永续

盯盘页新增独立“币安永续”区域，展示现有 `WATCH_CODES` 与商品基准中有已核实映射的合约。映射维护在 `app/config/binance_config.py`，不通过拼接股票代码猜测合约，不自动以同公司的另一上市地股票或相关 ETF 替代原标的。

当前映射包括 NVDA、AMD、LITE、Anthropic、SOXX、SK 海力士、长鑫存储、MiniMax、智谱、腾讯、小米、泡泡玛特，以及 WTI、布伦特、黄金、白银。新增盯盘标的后，须核实合约标的并补充映射才会纳入。移出盯盘池或商品基准的条目不再展示、监控或推送。

## 行情与价格口径

`BinancePerpetualService` 使用公开 REST 行情，无需币安账户密钥。每分钟后台获取 `/fapi/v1/ticker/24hr` 和 `/fapi/v1/premiumIndex`；`/fapi/v1/exchangeInfo` 每十五分钟校验一次交易状态、永续类型、报价资产和标的类型。支持 `PERPETUAL` 与 `TRADIFI_PERPETUAL`，只接收 `TRADING` 合约。

`GET /watch/perpetuals` 只读进程缓存，不请求交易所或发送通知。页面每六十秒刷新，展示成交价、滚动 24 小时涨跌、标记价格、当前资金费率、下次资金结算时间和最后行情时间。费率由小数乘以 100 转成百分比，不年化，也不假设所有合约都是八小时结算。页面时间使用北京时间。

腾讯优先选择 `TENCENTUSDT`（USDT 计价）；小米使用 `HK1810USDT`，明确标注 HKD quanto 报价。Quanto 按港币标的价格报价，以 USDT 结算，不能把显示价格当作按汇率换算的美元股价。商品合约标注“商品永续”，与原有商品期货分别展示。纳指不以 QQQ 替代，兆易创新 A 股不以其 H 股合约替代。

接口失败、字段缺失、非有限数、非正价格、合约无效或行情超过 180 秒时，合约显示“行情不可用”，保留最后更新时间，旧价格不参与异动判断。失败仅记录异常类型和 HTTP 状态，不记录令牌或响应正文。批量请求失败会清空全部价格窗口；单合约无效只清空对应窗口。前端请求失败也会隐藏旧报价。

## Slack 与调度

自动发现的 `binance_watch` 策略每分钟运行，独立于股票交易日历，周末也运行：

- 以连续缓存采样计算十五分钟成交价变化，达到 ±3% 推送异动，同一合约双方向共用三十分钟冷却。
- 初次启动、断线恢复后先积累十五分钟数据；相邻采样间隔超过 180 秒重置窗口。采样存在分钟级误差，十五分钟基点允许最多九十秒偏差，不使用更早数据冒充十五分钟变化。
- 每天北京时间 09:00、21:00 各发一次摘要，包含不可用条目的状态；由 UTC+8 显式换算，不依赖服务器时区。调度每分钟触发，允许前五分钟内发送或重试，窗口之外不补发。
- 两类消息均发到既有 `CHANNEL_WATCH`（`news_watch`），标题带“币安永续”。只有 Slack 返回成功才记录冷却或摘要已发送状态；失败下次扫描重试。

异动继续使用精简分行格式：先显示“币安永续 · 15分钟上涨/下跌 ±x.xx%”，再显示加粗的名称与合约代码，下一行显示最新价（保留实际报价单位）及 24 小时涨跌。多标的之间空行分隔，每个异动标的各自显示方向与幅度。

定时摘要使用 Slack 原生 Block Kit `table`，复用 `notification_tables.table_messages` 的表格和纯文本正文。列为“标的、合约、最新价、24小时涨跌、状态”，按滚动 24 小时涨跌幅降序排列，不可用标的置底。最新价保留实际报价单位；不可用行情的最新价与涨跌幅显示“—”，状态列保留最后更新时间，不展示旧价格。标题保留北京时间，超过二十个标的时分页，每条消息一张表。

表格发送失败时立即尝试纯文本摘要；表格或回退文字发送成功后记录当前摘要已发送，两者均失败则在五分钟窗口内重试。异动提醒格式不变。合约类型、标记价和资金费率仍可在盯盘页查看。

缓存、窗口、冷却和摘要去重均保存在进程内，重启后重新预热，摘要发送窗口内重启可能重复推送。沿用项目 `gunicorn.conf.py` 的单 worker 部署约定；多进程独立缓存不能保证共享行情或推送去重。没有新增数据库表或迁移。

部署需重启应用，以注册 `strategy_binance_watch`，并启用既有调度器和 `SLACK_BOT_TOKEN`。页面首次加载可能等待一个扫描周期；调度器未启用时显示行情不可用。

表格沿用现有 Slack Bot 和 `chat.postMessage`，无需图片上传权限或服务器中文字体。表格格式遵循 [Slack 官方 table block 文档](https://docs.slack.dev/reference/block-kit/blocks/table-block/)。

可选环境变量：

| 变量 | 默认值 | 含义 |
| --- | --- | --- |
| `BINANCE_FUTURES_BASE_URL` | `https://fapi.binance.com` | USDⓈ-M 行情根地址 |
| `BINANCE_ALERT_THRESHOLD_PCT` | `3` | 十五分钟绝对涨跌阈值，百分数 |
| `BINANCE_ALERT_COOLDOWN_MINUTES` | `30` | 同合约成功推送后的冷却分钟数 |

## 验证

沿用仓库现有 pytest：`python -m pytest tests/services/test_binance_perpetual.py tests/services/test_binance_watch.py tests/api/test_watch_perpetuals.py tests/test_watch_extended_alert.py tests/test_watch_prices_indices.py -q`。通知测试全部使用模拟发送，不发送真实 Slack；真实行情单独做只读接口验证。

表格专项验证：`python -m pytest tests/services/test_binance_watch.py tests/services/test_notification_tables.py -q`，覆盖排序、报价单位、不可用行情、分页、表格失败回退、北京时间早晚时段和成功去重。

官方来源：[行情接口](https://developers.binance.info/en/docs/catalog/core-trading-derivatives-trading-usd-s-m-futures/api/rest-api/market-data)、[股票永续与 NVIDIA 标的说明](https://www.binance.com/en/support/announcement/detail/1aa8f5f80e4a4afcab149e653fd3113d)、[港股 USDT 与 Quanto 口径](https://www.binance.com/en-AE/support/announcement/detail/18724cba64a048938986a98bbb257258)。
