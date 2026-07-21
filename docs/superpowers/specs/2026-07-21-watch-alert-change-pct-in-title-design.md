# news_watch 告警标题行前置当日涨幅

## 背景与问题

`news_watch` 频道的盯盘合并告警（`NotificationService.push_watch_alerts`，一股一条）标题行只有 `emoji + 名称(代码) + [优先级]`，当日涨幅埋在第三行上下文里，需往下读才能看到具体幅度：

```
🟢 *长电科技(600584)*  [MID]
跌破支撑 76.94 | 当前 76.58
涨幅 -0.53% | 量比 0.0x | 距上方阻力 90.41(+18.1%)
```

emoji 已按当日涨跌上色（🔴涨/🟢跌/⚪平/⚠️缺失，见 `2026-07-21-watch-alert-color-by-daily-change-design.md`），但"颜色"和"幅度"分处两行，扫一眼只得方向、不得量级。

## 目标

把当日涨幅数字紧跟在颜色 emoji 后面提到标题行，一眼同时读到"颜色 + 幅度"；第三行不再重复显示涨幅（遵循 `notifications.md`「同一信息避免重复出现」）。

## 最终格式

```
🟢 -0.53% *长电科技(600584)*  [MID]
跌破支撑 76.94 | 当前 76.58
量比 0.0x | 距上方阻力 90.41(+18.1%)
```

## 改动点

### 1. `app/services/notification.py:push_watch_alerts`

标题行拼装。emoji 四态判定逻辑不动（复用现有 `a.change_percent`）。新增：`change_percent` 非空时在 emoji 后插入 `{chg:+.2f}%`。

- 有涨幅：`f'{emoji} {chg:+.2f}% *{a.name}({a.code})*  [{a.priority}]'`
- 缺失（`chg is None`，emoji=⚠️）：不拼数字 → `f'{emoji} *{a.name}({a.code})*  [{a.priority}]'`

### 2. `app/services/watch_signal_pipeline.py:_build_context`

删除 `涨幅 {chg:+.2f}%` 段（现 120-122 行），第三行只留量比 / 区间位置。

- `ConsolidatedAlert.change_percent` 字段**仍照常填充**（`process()` 里 `change_percent=prices.get(code, {}).get('change_percent')` 不动）——标题行上色和数字都靠它，只是不再进 context 文本。
- **连带效应**：某股既无量比也无区间位置时，`context_line` 变空串；现有 `push_watch_alerts` 已有 `if a.context_line` 守卫（不追加空行），无需额外处理。

### 3. `tests/test_watch_signal_pipeline.py`

- 更新现有 `test_push_skips_low_and_formats_high`：断言标题行含 `+X.XX%`，且 context 文本**不再含**"涨幅"。
- 标题格式各态用例：涨（🔴 `+2.30%`）/ 跌（🟢 `-0.53%`）/ 平（⚪ `+0.00%`）。
- 缺失用例：`change_percent=None` → emoji=⚠️ 且标题**不含**百分号数字。
- context 断言：`_build_context` 产出不含"涨幅"，量比/区间位置仍在。

## 明确不改的范围

- emoji 上色规则（🔴/🟢/⚪/⚠️ 四态）、优先级过滤（LOW 静默）、主/次信号行、第三行的量比与区间位置格式。
- `NotificationService.push_realtime_analysis`（AI 买卖建议语义，非价格颜色）。
- `ConsolidatedAlert` 的字段结构（`change_percent`/`direction` 均保留）。

## 验收标准

1. 有涨幅的告警标题行为 `{emoji} {±X.XX%} *名称(代码)* [优先级]`，涨🔴/跌🟢/平⚪。
2. `change_percent` 缺失时标题为 `⚠️ *名称(代码)* [优先级]`，不含数字。
3. 第三行不再出现"涨幅"，量比 / 区间位置照旧；三者全无时不产生空行。
4. `tests/test_watch_signal_pipeline.py` 全绿，含各态标题格式与缺失用例。
