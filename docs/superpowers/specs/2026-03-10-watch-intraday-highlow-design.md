# 盯盘分时图最高/最低点标注 + 突破通知

## 概述

为盯盘分时图新增当日最高价/最低价标注（红绿实心圆点），并在价格突破已确认的盘中前高/前低时通过 Slack 推送通知。突破检测作为第 5 类信号集成到 watch-alert-push 架构。

## 前端：图表标注

### 实现位置

`app/static/js/watch.js` 的 `renderChart()` 方法

### 标注规则

- 从分时数据 `this.chartData[code]` 中找出 `close` 最大值和最小值及对应时间点
- 最高点：红色实心圆（`#dc3545`，r=5），标签在上方显示价格
- 最低点：绿色实心圆（`#28a745`，r=5），标签在下方显示价格
- 使用 ECharts `markPoint`，与现有 TD 九转 markPoint 合并到同一 series
- 每次 60 秒刷新时随数据更新

### 数据流

纯前端计算，无需后端改动。分时数据已包含每分钟的 `close` 字段。

## 后端：突破检测

### 核心概念

前高/前低的 10 分钟确认窗口：价格创出新高/新低后，若 10 分钟内未被突破，则确认为"前高"/"前低"。之后价格再次突破该价位时触发通知。

### 状态管理

`WatchAlertService` 新增实例变量：

```python
_intraday_extremes = {}
# {code: {
#     'high': float,          # 当前运行最高价
#     'high_time': datetime,  # 最高价出现时间
#     'high_confirmed': bool, # 是否已确认为"前高"
#     'low': float,           # 当前运行最低价
#     'low_time': datetime,   # 最低价出现时间
#     'low_confirmed': bool,  # 是否已确认为"前低"
# }}
```

不持久化，交易日切换时清空。

### 检测流程（每 60 秒）

1. 获取当前价格 `curr_price`
2. `curr_price > high` → 更新 high，重置 `high_confirmed = False`，重置计时
3. `curr_price < low` → 更新 low，重置 `low_confirmed = False`，重置计时
4. 距 `high_time` 已过 10 分钟且 `high_confirmed == False` → 标记 `high_confirmed = True`
5. 距 `low_time` 已过 10 分钟且 `low_confirmed == False` → 标记 `low_confirmed = True`
6. 突破检测：
   - `curr_price > high` 且之前的 high 已 confirmed → 突破前高信号
   - `curr_price < low` 且之前的 low 已 confirmed → 跌破前低信号

### 推送示例

```
贵州茅台(600519) 突破盘中前高 1805.20 ↑ | 当前 1808.50
贵州茅台(600519) 跌破盘中前低 1758.30 ↓ | 当前 1755.10
```

## 集成到 watch-alert-push

### 第 5 类信号

| 信号 | Priority | 冷却 key |
|------|----------|---------|
| 突破盘中前高 | HIGH | `breakthrough:600519:high` |
| 跌破盘中前低 | HIGH | `breakthrough:600519:low` |

### 在 check_alerts() 中的位置

```
check_alerts()
  ├─ _check_integer_crossing()
  ├─ _check_support_resistance()
  ├─ _check_td_sequential()
  ├─ _check_anchor_price()
  └─ _check_intraday_breakthrough()   ← 新增
```

### Signal.data 结构

```python
{
    "stock_code": "600519",
    "alert_type": "breakthrough",
    "direction": "high",  # 或 "low"
    "level": 1805.20,
    "detail": "突破盘中前高 1805.20 ↑ | 当前 1808.50"
}
```

### 复用机制

- 冷却：复用 `WATCH_ALERT_COOLDOWN_SECONDS`（默认 300 秒）
- 推送链路：Signal → EventBus → NotificationManager → Slack
- 调度：复用 `WatchAlertStrategy`（interval_minutes:1）

### 常量

```python
BREAKTHROUGH_CONFIRM_MINUTES = 10  # 硬编码，不新增环境变量
```

## 对现有代码的修改

| 文件 | 修改内容 |
|------|---------|
| `app/static/js/watch.js` | `renderChart()` 新增 high/low markPoint 计算和渲染 |
| `app/services/watch_alert_service.py` | 新增 `_check_intraday_breakthrough()` 方法和 `_intraday_extremes` 状态 |

注意：`watch_alert_service.py` 尚未实现（仅有设计文档），突破检测将随 watch-alert-push 一起实现。
