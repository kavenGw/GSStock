# 港股实时价切腾讯源 + 盯盘提频设计

日期：2026-08-05
状态：已批准

## 背景与问题

盘中急拉推送滞后于实际行情：2026-08-05 13:25 推送建滔积层板（1888.HK）+9.83%（34.18），用户收到推送当下实际已 +12.79%。定位为**推送发出时价格已陈旧**，成因三层叠加：

1. **数据源延迟**：非 A 股实时价全走 yfinance，且实现是取 `ticker.history(period="5d")` 最后一根日线 close 当"实时价"——Yahoo 日线盘中更新本身有延迟，还导致 `name=code`（无股票名）。
2. **预取降频**：`watch_preload` 港股每 3 tick（≈3 分钟）才 `force_refresh` 一次（为 yfinance 限流让路）。
3. **闸门宽松**：`price_freshness` 非 A 股放行到 360s。

急拉行情每分钟可走 1%+，三层叠加造成推送时点位差 3 个百分点。

## 实测验证（2026-08-05）

腾讯 `http://qt.gtimg.cn/q=hk01888,hk03690,hk00700`（GBK、`~` 分隔、78 字段）：

- 关键字段索引与 A 股解析**完全一致**：`[1]`名称 `[3]`现价 `[4]`昨收 `[5]`开盘 `[6]`成交量 `[31]`涨跌 `[32]`涨幅 `[33]`高 `[34]`低。
- `[30]` 行情时间戳（`2026/08/05 13:16:48`）与请求时刻一致，判断为实时。
- 代码格式：`hk` + 5 位补零（`1888.HK` → `hk01888`）。
- 差异点：volume `[6]` 是股数（港股无"1手=100股"概念，每手股数在 `[60]`），不可照搬 A 股 `/100` 转手。

## 设计

### 1. 取数层（`app/services/unified_stock_data.py`）

- `_tencent_code()` 扩展：`.HK` 后缀 → `hk{int(code):05d}`。
- `_fetch_realtime_from_api` 市场分组二分（A / 其他）改三分：
  - A 股：现有负载均衡（腾讯/新浪主、东财备、yfinance 兜底）不动。
  - **港股：腾讯批量优先**（复用 `_fetch_from_tencent`），失败 yfinance 兜底（保留现有 fetch_single 路径）。
  - 美股及其余：yfinance 不动（限流约束仍在）。
- `_fetch_from_tencent` 参数化两处：
  - volume：A 股 `/100` 转手，港股保持股数（与原 yfinance 口径一致，不破坏 Volume 单位契约——契约只约束 A 股为"手"）。
  - `market`：按实际市场标记（`'A'` / `'HK'`），不再写死 `'A'`。

### 2. 预取提频（`app/strategies/watch_preload/__init__.py`）

`_should_refresh_market`：「A 每 tick / 非 A 每 3 tick」→「**A + HK 每 tick** / 其余每 3 tick」。指数退避机制保留：腾讯偶发失败时该市场退避，期间 yfinance 兜底可用。

### 3. 新鲜度闸门（`app/services/price_freshness.py`）

`PRELOAD_INTERVAL_MINUTES = {'A': 1, 'HK': 1}`，港股阈值由公式（2×刷新周期）自动从 360s 收紧到 120s。

### 4. 影响面

- **全局切源**：持仓页、简报、valuations 等所有经 `get_realtime_prices` 的港股调用一并受益，且修复港股 `name=code` 问题。
- **不受影响**：PE/市值基本面链路（独立 yfinance fetch）、美股取价、A 股主链路、`_price_ring` 急拉检测（提频后自然从 3 分钟/点变 1 分钟/点，无需改代码）。

### 5. 测试（`tests/test_*.py` 平铺）

1. `_tencent_code` 港股格式（`1888.HK`→`hk01888`、`03690.HK`→`hk03690`、A 股回归）。
2. 腾讯港股响应解析：用实测样本 fixture，验 price/change_percent/name 正确、volume 不除 100、`market='HK'`。
3. `_should_refresh_market` 新分档（A/HK 每 tick，US 每 3 tick）。
4. freshness 港股阈值 120s（119s 放行 / 121s 拦截）。

### 6. 错误处理

- 腾讯港股请求异常/解析失败 → 落入 yfinance 兜底，行为与现状一致。
- 兜底也失败 → `watch_preload` 现有 backoff 生效，告警侧由新鲜度闸门静默（期望行为）。

### 7. 风险与验证

腾讯港股免费源理论上可能对部分标的延迟；实测时间戳为实时。实现后盘中抽查一次腾讯价 vs 行情软件对照兜底确认。

## 不做的事（YAGNI）

- 不做告警推送前单股 force_refresh（方案 B）：提频 + 实时源后增益 <60s，不值得加分叉。
- 不动美股刷新频率与数据源。
- 不做盯盘内存态持久化（已知限制，另行 spec）。
