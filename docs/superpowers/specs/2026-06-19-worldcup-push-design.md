# news_worldcup 推送设计（2026 FIFA 世界杯）

> 日期：2026-06-19 ｜ 范围：仅 2026 FIFA 世界杯（6/11–7/19，美加墨），临时性赛事推送
> 落地方式：混合（方式 C）——数据层独立、监控调度层泛化复用

## 背景与目标

仿现有 `news_nba` 推送，新增 `news_worldcup` 频道，覆盖 2026 世界杯**全部比赛**（48 队 / 104 场），提供与 NBA 等价的**全套**推送：

1. 每日赛程预告（07:00）
2. 赛前 30 分钟提醒
3. 进球 / 比分变化推送
4. 终场比分

赛事 7 月结束后，删除独立模块 + 各共享文件的 `worldcup` 分支即可净退场。

## 关键决策

| 项 | 决策 |
|---|---|
| 赛事范围 | 仅 2026 FIFA 世界杯，临时性 |
| 推送哪些比赛 | 全部比赛，无球队过滤 |
| 推送类型 | 全套 4 类（仿 NBA） |
| 架构 | 方式 C：数据层独立 `WorldCupService`，泛化复用 `EsportsMonitorService` 调度 |
| 频道名 | `news_worldcup`（ASCII，规避 Slack 非 ASCII 频道名风险） |
| 轮次标注 | 不标（不区分 1/8、1/4 等） |
| 终场奖杯 | 胜方加 🏆；平局无奖杯 |
| 数据源 | ESPN soccer API：`.../sports/soccer/fifa.world/scoreboard`（与 NBA 同源同结构） |

## 组件与文件改动

### 1. 频道常量 — 改 `app/config/notification_config.py`
新增 `CHANNEL_WORLDCUP = 'news_worldcup'`。需在 Slack 工作区先建好该频道。

### 2. 配置 — 新建 `app/config/worldcup_config.py`（隔离，便于删除）
```python
WORLDCUP_ENABLED = os.getenv('WORLDCUP_ENABLED', 'true').lower() == 'true'
ESPORTS_WORLDCUP_MONITOR_INTERVAL = int(os.getenv('ESPORTS_WORLDCUP_MONITOR_INTERVAL', '5'))  # 进球频率低，5min 轮询
ESPN_SOCCER_WC_URL = 'https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard'
WORLDCUP_MAX_DURATION_HOURS = 3   # 90'+伤停+中场+加时/点球
WORLDCUP_TEAM_NAMES = { 'Brazil': '巴西', 'Argentina': '阿根廷', ... }  # 参赛队 EN→CN
```
`ESPORTS_FETCH_TIMEOUT` 沿用 `esports_config` 已有常量，不重复定义。

### 3. 数据层 — 新建 `app/services/worldcup_service.py`
`WorldCupService`（静态方法，仿 `EsportsService` 形状）：
- `get_worldcup_schedule(today=None)` → `{'today': [...], 'yesterday': [...]}`，全部失败返回 `None`
- `get_worldcup_schedule_by_date(target_date)` → `list[game]` 或 `None`（供监控层按次日日期取数）
- `get_worldcup_live_scores()` → `{match_id: game}` 或 `None`
- `_fetch_espn_soccer(date)` → 复用 NBA 的 ESPN 解析骨架（主客队按 `homeAway` 识别 / 比分 / `pre|in|post` 状态映射 / UTC→北京时区换算 / `_beijing_date` 多日去重）

足球专属字段（在 game dict 中追加）：
- `status_detail`：上半场 `23'` / 中场 `HT` / 下半场 `67'` / 加时 `ET` / 终场 `FT`（取 ESPN `status.type.shortDetail`）
- `pens`：点球大战比分 tuple（取 ESPN competitor `shootoutScore`），淘汰赛平局后才出现，否则 `None`

`game` 结构：
```python
{'match_id', 'home', 'away', 'home_score', 'away_score',
 'status': 'scheduled'|'in_progress'|'completed',
 'start_time': 'HH:MM', '_beijing_date': date,
 'status_detail': str, 'pens': (int, int)|None}
```

失败语义遵循项目约定：`None` = 获取失败（已重试耗尽）；空 `{'today': [], 'yesterday': []}` = API 成功但无赛事。异常分支 `logger.warning(... exc_info=True)` 带 `type(e).__name__`。

- `format_score(game, final=False)`：**足球专用比分格式化**（与篮球 `_format_score` 分离），作为可插拔回调注入监控层。

### 4. 比分格式（足球语义）

| 场景 | 格式 |
|---|---|
| 进行中 | `⚽ 巴西 1 - 0 中国 \| 下半场 67'` |
| 平局（终场/进行中） | `⚽ 中国 1 - 1 巴西 \| 终场` |
| 分出胜负（终场） | `⚽ 🏆 *巴西 2* - 1 中国 \| 终场`（胜方加粗 + 🏆） |
| 点球决胜 | `⚽ 🏆 *巴西* 1(4) - 1(2) 中国 \| 点球` |

规则：`final=True` 且分出胜负 → 胜方加 🏆 + 加粗；平局无 🏆；点球时括号内为点球比分，🏆 给点球胜方。不标轮次名。

### 5. 监控层泛化 — 改 `app/services/esports_monitor_service.py`
引入 `_MATCH_TYPE_META` 字典：`type → {emoji, channel, max_hours, fetch_live_fn, format_fn}`，把现有 `_poll_nba_match`/`_poll_lol_match` 的 if/elif 收敛为按 meta 查表的 `_poll_generic`，加 `worldcup` 项。

- `setup_match_monitors`：加 worldcup 赛程拉取块（`get_worldcup_schedule` / `get_worldcup_schedule_by_date`），无球队过滤（全部比赛）；非 `completed` 比赛建 monitor + pre-match job。
- `_push_pre_match_notification`：频道 / emoji 改走 `_MATCH_TYPE_META`（emoji `⚽`，channel `news_worldcup`，无 league 前缀）。
- `_poll_worldcup_match`：进行中比分变化推送（仿 `_poll_nba_match`，比分用 `WorldCupService.format_score`），终场推最终比分（含点球比对脏数据重试，仿 LoL 的 completed 重试逻辑——足球进行中 0:0 是常态，不能据 0:0 判脏数据，改用 status 转 completed 时延时复查比分/点球）。
- 常量 `WORLDCUP_MAX_DURATION_HOURS` 接入 meta 的 `max_hours`。

**回归约束**：NBA / LoL 现有行为保持等价（推送文案、job id、轮询逻辑字节级不变）；靠新增单测兜底。

### 6. 每日赛程预告 — 改 `app/strategies/esports_daily_schedule/__init__.py`
加 `_push_worldcup_today()`（在 `scan()` 中调用，07:00），仿 `_push_nba_today`：
- 拉 `get_worldcup_schedule()`，`None` → `enqueue(today, 'worldcup', 'WorldCup')`
- 当日全部场次（无过滤）按开球时间排序，列 `⚽ *今日世界杯赛程* (N场)` + `· HH:MM  A vs B`
- 无赛事 → 推 `⚽ *今日世界杯赛程*\n今日无比赛`

**时区说明**：WC2026 在美加墨，北京时间多落 00:00–11:00。07:00 预告时部分比赛已结束——预告仍列全天场次（与现有 NBA 一致）。实时 / 终场推送靠监控层覆盖：22:00「次日」setup 覆盖凌晨开球场次，5:00 早间 setup 覆盖白天场次，启动恢复兜底。

### 7. 失败重试 — 改 `app/services/esports_retry_queue.py`
`_refetch` / `_push_supplement` / `_push_failed` 加 `kind == 'worldcup'` 分支（与 NBA 对称）：
- `_refetch`：调 `WorldCupService.get_worldcup_schedule(today=unit.date)`
- `_push_supplement`：`⚽ *世界杯 补充* (N场)` + 场次列表
- `_push_failed`：`⚽ *今日世界杯赛程* 数据获取失败（已重试 3 次）`

### 8. 调度引擎 — `app/scheduler/engine.py`
**预计无需改动**：现有 5:00 早间 / 22:00 次日 / 启动恢复 均走 `setup_match_monitors()`（`match_type=None` = 全类型），一旦该方法识别 worldcup 即自动纳入。实现时复核确认（若 None 分支未覆盖 worldcup 则补一行）。

### 9. 测试
- 新建 `tests/test_worldcup_service.py`：
  - ESPN 足球 fixture → `get_worldcup_schedule` 解析（主客队 / 状态 / 北京时区分类 / 去重）
  - `format_score`：进行中 / 平局 / 胜负+🏆 / 点球 四种格式
- 扩展 monitor dispatch 测试：worldcup 类型路由到正确频道 / emoji / format_fn；NBA / LoL 行为不回归。
- 运行：`PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_worldcup_service.py tests/test_esports_*.py -v`

### 10. 文档同步
- `.claude/rules/esports.md`：补 worldcup 推送说明 + 环境变量
- `README.md`：频道表加 `news_worldcup`
- `.env.sample`：加 `WORLDCUP_ENABLED` / `ESPORTS_WORLDCUP_MONITOR_INTERVAL`
- `CLAUDE.md`（如涉及环境变量约定）

## 退场清单（7 月赛事结束后）
删 `app/config/worldcup_config.py` + `app/services/worldcup_service.py` + `tests/test_worldcup_service.py`；移除 `notification_config` 的 `CHANNEL_WORLDCUP`、监控层 `_MATCH_TYPE_META` 的 worldcup 项与 `_poll_worldcup_match`、daily 策略 `_push_worldcup_today`、retry queue 的 worldcup 分支、文档条目。

## 非目标（YAGNI）
- 不做球队关注过滤（全部比赛）
- 不标淘汰赛轮次名
- 不做长期足球框架（欧洲杯 / 世预赛 / 联赛）
- 不持久化比分状态（沿用进程内字典，重启丢失可接受）
