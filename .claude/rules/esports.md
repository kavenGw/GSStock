---
paths:
  - "app/services/esports*"
  - "app/services/worldcup*"
---
# 赛事推送（NBA / LoL / 世界杯）

> **何时读**：改 esports_service.py / worldcup_service.py、调推送时机、调试失败重试队列

| 环境变量 | 说明 | 默认值 |
|---------|------|-------|
| `ESPORTS_ENABLED` | NBA + LoL 总开关 | `true` |
| `NBA_ENABLED` | 单独关 NBA | `true` |
| `WORLDCUP_ENABLED` | 世界杯开关 | `true` |
| `ESPORTS_FETCH_TIMEOUT` | 赛事 API 超时（秒） | `15` |
| `ESPORTS_NBA_MONITOR_INTERVAL` | NBA 比分轮询（分钟） | `15` |
| `ESPORTS_LOL_MONITOR_INTERVAL` | LoL 比分轮询（分钟） | `30` |
| `ESPORTS_WORLDCUP_MONITOR_INTERVAL` | 世界杯比分轮询（分钟） | `5` |
| `ESPORTS_PRE_MATCH_MINUTES` | 赛前提醒提前量（分钟） | `30` |

**推送逻辑**：
- 每日 07:00 `esports_daily_schedule` 推**昨日结果 + 今日赛程**到 `news_nba` / `news_lol` / `news_worldcup`，是赛事推送**唯一入口**，勿再挂到每日简报（曾造成双推）。NBA 按 `NBA_TEAM_MONITOR` 过滤球队；LoL 覆盖 LPL/LCK/先锋赛/Worlds/MSI；世界杯全量不过滤。
- 赛前提醒、比分变化（仅变化时推）、终场比分；NBA 18:00 额外 setup 覆盖当晚；世界杯靠 22:00 与 5:00 setup 覆盖凌晨/白天场次。
- **失败重试**：拉取失败挂起 5min × 3 轮，任一轮成功立即补推，3 轮全失败才推「数据获取失败」。状态在进程内 `esports_retry_queue.py`，重启丢失（接受漏一次）。
- `_fetch_*` 返回 None（失败）vs 空 dict（无赛事）语义与日志要求见 notifications.md。

数据源：NBA / 世界杯用 ESPN API（同源同结构），LoL 用 LoL Esports API。世界杯数据层独立 `worldcup_service.py`（平局/点球/半场语义自洽），`EsportsMonitorService` 以 `match_type='worldcup'` 分支复用提醒/轮询/重试框架。赛事结束后删 `worldcup_service.py` + `worldcup_config.py` + 各处 worldcup 分支与 `CHANNEL_WORLDCUP`。
