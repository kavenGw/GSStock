# news_daily 每日 8 点推送精简 — 移除「关键信号」与「高点回退提醒」

> 状态：已批准 · 日期：2026-08-08 · 频道：news_daily

## 背景

每日简报策略（`daily_briefing`，`0 8 * * *`）向 `news_daily` 频道推送时包含两块内容，与其他模块的推送信息重叠：

- **⚡关键信号**：由 `NotificationService.format_alert_signals()` 生成，读 `signal_cache` 里 A 股的买卖信号（缩量突破/新高/顶部巨量/MA5 交叉）。同一份 signal_cache 已被 `price_alert` 策略在盘中每 5 分钟推送（覆盖持仓股）。
- **📉高点回退提醒**：由 `DailyBriefingStrategy._push_pullback_alert()` 生成，推 90 日高点回退 ≤ -5% 的标的。回退中的标的大概率已被盯盘 `watch_alert` 的支撑跌破 / 盘中急跌 / TD九转告警覆盖，8 点再推一遍属重复提示。

目标：让 8 点推送只保留不可替代的内容，降低噪音。

## 范围

仅精简每日 8 点推送。不改动 `price_alert`、`watch_alert`、`/value_dip` 页面的任何行为。

## 改动设计

### 1. 移除「⚡关键信号」全链路

文件：`app/services/notification.py`、`app/llm/prompts/daily_briefing.py`

- 删除 `NotificationService.format_alert_signals()` 方法（全仓唯一消费者是 `push_daily_report`）。
- `push_daily_report()`：
  - 删除 `alerts = NotificationService.format_alert_signals(...)` 赋值；
  - 删除 `all_data` 中的 `'alert_signals'` 键（不再作为 GLM「今日核心观点」的输入）；
  - 删除 `msg1_parts` 中 `if alerts.get('text')` 分支。
- `build_briefing_blocks(briefing_text, alerts_text, core_insights, action_suggestions)`：删除 `alerts_text` 形参及其对应的 blocks 构建分支；唯一调用点同步改为 `build_briefing_blocks(briefing['text'], core_insights, action_suggestions)`。
- `app/llm/prompts/daily_briefing.py`：从 `label_map` 删除 `'alert_signals': '预警信号'`，并删除 `build_daily_briefing_prompt` docstring 中对应的说明行。

结果：news_daily 的 Message 1（要点）内容变为「🎯今日核心观点 + 💡操作建议 + 📊持仓概览」。

### 2. 移除「📉高点回退提醒」

文件：`app/strategies/daily_briefing/__init__.py`

- 删除 `_push_pullback_alert()` 与 `_format_pullback_message()` 两个静态方法；
- 删除 `_scan_weekday()` 末尾的 `self._push_pullback_alert()` 调用。

`ValueDipService.get_pullback_ranking()` 与 `/value_dip` 页面保持不变，仍可按需查看。

**连带测试**（编写计划时发现，spec 初稿遗漏）：`_format_pullback_message` 有 4 个现存测试直接调用，需同步处理——

- `tests/test_value_dip_briefing.py::test_pullback_message_uses_market` → 删除，该文件改为纯移除守卫测试；
- `tests/test_pullback_support_resistance.py` 的 `test_format_renders_support_and_resistance` / `test_format_omits_missing_sr` / `test_format_renders_single_side` → 删除；同文件的 `test_calc_changes_attaches_support_resistance` / `test_calc_changes_sr_none_when_insufficient_data` 测的是 `ValueDipService`（保留组件），**必须保留**。

### 3. 保留 `_refresh_signal_cache()`

`DailyBriefingStrategy._refresh_signal_cache()` 虽然最初是为「关键信号」而建，但必须保留：

- `price_alert` 策略（`*/5 9-15 * * 1-5`）读取同一份 signal_cache 推送持仓股当日信号；
- 该方法覆盖 `_get_all_watched_codes()`（持仓 + 关注全集），范围宽于 `watch_realtime._refresh_watch_signals()`（仅 `WATCH_CODES` 盯盘池）。删除会导致不在盯盘池的持仓股当日信号缺失，`price_alert` 盘中漏推。

改动后它的下游消费者从两个（每日简报 + price_alert）收敛为一个（price_alert）。

### 4. 文档同步

`.claude/rules/notifications.md` 的「Slack 推送排版规范」章节以 `📉 *高点回退提醒*` 作为标题格式示例，该推送下线后需改为仍存在的推送标题（如 `📊 *持仓概览*`），避免规则文档引用已删除的代码。

## 验证

1. 全量单测：`PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/ -v`
   现有测试无一处直接引用 `format_alert_signals` / `_push_pullback_alert`，此步主要防 `build_briefing_blocks` 签名变更的连带破坏。
2. 冒烟：在 `create_app()` 上下文中调用一次 `NotificationService.push_daily_report()`（或直接调 `build_briefing_blocks` 与 `build_daily_briefing_prompt`）确认不抛异常、生成的 blocks 结构合法。
3. 全仓 grep 确认无残留引用：`format_alert_signals`、`alerts_text`、`alert_signals`、`_push_pullback_alert`、`_format_pullback_message`。

## 非目标

- 不调整 Message 3（市场与数据）、盯盘分析消息、GitHub Release 推送的任何内容。
- 不修改 `price_alert` 的推送阈值或频率。
- 不下线 `ValueDipService` 或 `/value_dip` 路由。
