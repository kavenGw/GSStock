# 盯盘实时分析完成后 Slack 推送

## 背景

`WatchRealtimeStrategy` 每15分钟调用 `WatchAnalysisService.analyze_stocks('realtime')` 进行 AI 分析，结果存入 `WatchAnalysis` 表，但分析完成后不推送通知，前端被动轮询获取。

## 目标

实时分析完成后，通过 Slack 推送所有股票的分析摘要（含支撑/阻力位），让用户无需打开页面即可获取最新分析。

## 方案

在 `NotificationService` 新增 `push_realtime_analysis(results)` 方法，由 `WatchRealtimeStrategy.scan()` 在分析完成后调用。

不走 Signal/Event Bus 体系（实时分析是"汇总报告"而非"交易信号"，与每日简报推送模式一致）。

## 消息格式

```
📊 盯盘实时分析 (14:30)
贵州茅台(600519): 🟢买入 突破关键压力位1850，量能放大
  支撑: 1750 / 1700 | 压力: 1850 / 1900
格力电器(000651): 🟡持有 横盘震荡，关注支撑位38.5
  支撑: 38.5 / 37.0 | 压力: 40.0 / 42.0
AAPL: 🔴卖出 跌破5日均线，短线偏弱
  支撑: 178 / 175 | 压力: 185 / 190
```

信号图标映射：`buy`→🟢买入, `sell`→🔴卖出, `hold`→🟡持有, `watch`→⚪观望

## 改动点

### 1. `app/services/notification.py` — 新增 `push_realtime_analysis()`

```python
@staticmethod
def push_realtime_analysis(analyses: dict) -> bool:
    """推送盯盘实时分析结果到 Slack"""
```

- 入参：`WatchAnalysisService.analyze_stocks('realtime')` 的返回值（`dict[code, dict[period, data]]`）
- 从 `WatchService.get_watch_list()` 获取 `name_map`
- 提取每只股票的 `realtime` 分析：signal、summary、support_levels、resistance_levels
- 格式化为上述消息格式
- 调用 `send_slack()` 发送
- 无分析结果时不发送

### 2. `app/strategies/watch_realtime/__init__.py` — 调用推送

在 `scan()` 方法中，`analyze_stocks('realtime')` 成功后调用 `push_realtime_analysis(results)`：

```python
results = WatchAnalysisService.analyze_stocks('realtime', force=True)
logger.info('[盯盘实时] 分析完成')

from app.services.notification import NotificationService
NotificationService.push_realtime_analysis(results)
```

## 数据流

```
WatchRealtimeStrategy.scan() [每15分钟]
  → WatchAnalysisService.analyze_stocks('realtime', force=True)
  → 返回 analyses dict
  → NotificationService.push_realtime_analysis(analyses)
    → 格式化消息（股票名、信号、摘要、支撑/阻力位）
    → send_slack()
```

## 边界条件

- Slack 未配置：`send_slack()` 内部处理，返回 False
- 分析结果为空（无盯盘股票/全部失败）：不发送
- 某只股票缺少 realtime 分析：跳过该股票
- 支撑/阻力位为空列表：显示 `-`
