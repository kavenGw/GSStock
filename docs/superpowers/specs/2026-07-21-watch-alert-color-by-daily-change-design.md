# news_watch 告警按当日涨跌上色

## 背景与问题

`news_watch` 频道的盯盘合并告警（`NotificationService.push_watch_alerts`，一股一条）当前用**信号方向 `ConsolidatedAlert.direction`** 决定 emoji 颜色：

- `high/above/up/buy/resistance_break` → 🔴
- `low/below/down/sell/support_break` → 🟢

问题：当一只股票当日在涨，但触发的信号是"逼近阻力 / 低于目标价"这类方向落在 `below/support_break` 一侧的信号时，emoji 被判成 🟢（绿），与中文"红涨绿跌"直觉冲突。

实例（SK 海力士 000660.KS）：当日 **+2.35%**（在涨），主信号是"当前 < 目标"（`target_price`，direction 属 `below` 一侧）→ 被上成 🟢。用户期望：颜色只看当日涨跌，应为 🔴。

## 目标

`push_watch_alerts` 的 emoji **只反映当日涨跌幅 `change_percent` 的符号**，与信号方向（逼近阻力/跌破支撑/低于目标等）无关。

## 颜色规则

| 条件 | emoji | 含义 |
|---|---|---|
| `change_percent > 0` | 🔴 | 当日涨 |
| `change_percent < 0` | 🟢 | 当日跌 |
| `change_percent == 0` | ⚪ | 平盘 |
| `change_percent is None` | ⚠️ | 数据缺失 |

## 改动点

### 1. `app/services/watch_signal_pipeline.py`

- `ConsolidatedAlert` 新增字段 `change_percent: float | None = None`。
- `WatchSignalPipeline.process()` 构造每条 `ConsolidatedAlert` 时填入 `change_percent=prices.get(code, {}).get('change_percent')`。数据源与 `_build_context()` 里渲染"涨幅 +X.XX%"同源，已验证在该链路可用。
- `direction` 字段**保留**：仍是这条合并告警的主信号方向、也存在于 `fired_signals` 里，仅不再用于上色，作为描述性元数据留存。

### 2. `app/services/notification.py:push_watch_alerts`

将现有基于 `a.direction` 的 emoji 判断块替换为基于 `a.change_percent` 的判断（按上表四态）。其余推送格式不变：

```
{emoji} *{名称}({代码})*  [{优先级}]
{主信号行}
  · {次信号行}...
{上下文行：涨幅/量比/区间位置}
```

### 3. `tests/test_watch_signal_pipeline.py`

- 更新 `test_push_skips_low_and_formats_high`：给 `high` 用例补 `change_percent=2.30`，仍断言 🔴。
- 新增用例：
  - 跌（`change_percent < 0`）→ 🟢
  - 平盘（`change_percent == 0`）→ ⚪
  - 缺失（`change_percent is None`）→ ⚠️
  - **核心 bug 回归**：`direction='support_break'`（或 `below`）但 `change_percent=+2.35` → 断言 🔴，锁死本次修复场景。
- 新增用例断言 `process()` 能把 `prices` 里的 `change_percent` 灌进返回的 `ConsolidatedAlert`。

## 明确不改的范围

- `NotificationService.push_realtime_analysis`：其 emoji 是 **AI 买卖建议**语义（buy=🔴 / sell=🟢 / hold=🟡 / watch=⚪），非价格颜色，不动。
- `NotificationService.dispatch_signal`：`watch_alert` 已改走信号管线（`scan` 返回 `[]`），该路径对 `news_watch` 已是死代码；`volume_alert` 经此路由到 `news_daily` 频道，不涉及本诉求。均不动。

## 验收标准

1. 当日涨的股票（含触发"逼近阻力/低于目标/跌破支撑"等任意方向信号）在 `news_watch` 一律显示 🔴。
2. 当日跌的股票一律 🟢；平盘 ⚪；`change_percent` 缺失 ⚠️。
3. 推送格式（标题行 / 主次信号行 / 上下文行）与优先级过滤（LOW 静默）行为不变。
4. `tests/test_watch_signal_pipeline.py` 全绿，含核心 bug 回归用例。
