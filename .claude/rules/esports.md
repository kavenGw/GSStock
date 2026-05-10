# 赛事推送（NBA / LoL）

> **何时读**：改 app/services/esports_service.py、调整 NBA/LoL 推送时机、调试失败重试队列、修改赛程预告 / 赛前提醒 / 比分变化推送
> **不必读**：股票 / 新闻 / 持仓相关任何内容

## 赛事推送配置

| 环境变量 | 说明 | 默认值 |
|---------|------|-------|
| `ESPORTS_ENABLED` | 是否启用赛事推送 | `true` |
| `ESPORTS_FETCH_TIMEOUT` | 赛事API请求超时（秒） | `15` |
| `ESPORTS_NBA_MONITOR_INTERVAL` | NBA 比分轮询间隔（分钟） | `15` |
| `ESPORTS_LOL_MONITOR_INTERVAL` | LoL 比分轮询间隔（分钟） | `30` |
| `ESPORTS_PRE_MATCH_MINUTES` | 赛前提醒（开赛前N分钟） | `30` |

**推送逻辑**：
- 每日赛程预告：`esports_daily_schedule` 策略 07:00 推送当日 NBA/LoL 赛程到 `news_nba` / `news_lol`（NBA 按 `NBA_TEAM_MONITOR` 过滤关注球队；LoL 覆盖 LPL/LCK/先锋赛/Worlds/MSI）
- 赛前提醒：比赛开始前30分钟推送
- 比分变化：仅在比分发生变化时推送（避免重复通知）
- 比赛结束：自动检测并推送最终比分
- NBA晚间调度：每天18:00额外执行一次NBA监控设置，覆盖当晚比赛
- 失败重试：单联赛 / 整 NBA 拉取失败时，挂起 5min × 3 轮调度层重试，期间任意一轮成功立即"补推"该联赛，3 轮全失败才推"数据获取失败（已重试 3 次）"。状态进程内 `app/services/esports_retry_queue.py` 维护，进程重启丢失（接受最多漏一次补推）。

数据源：NBA 用 ESPN API（无需认证），LoL 用 LoL Esports API（LPL/LCK/国际赛事/先锋赛）。
