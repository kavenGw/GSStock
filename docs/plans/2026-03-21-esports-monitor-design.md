# 赛事实时监控设计

## 概述

在每日简报推送赛程信息的基础上，增加赛事实时比分监控功能。每日简报完成后，自动为当天的 NBA/LoL 比赛创建独立的 APScheduler 定时任务，按固定间隔轮询比分并推送到 Slack。

## 核心需求

1. 每日简报（8:30am）后，为当天比赛创建 per-match 监控 job
2. NBA 每 1 小时轮询一次，LoL 每 30 分钟轮询一次
3. 每次轮询推送当前比分快照（无论是否有变化）
4. 比赛结束后自动移除 job
5. 服务器重启后重新拉取赛程，为未结束的比赛重建 job

## 整体架构

```
每日简报 (8:30am)
    │
    ├── push_daily_report() — 推送简报
    │
    └── EsportsMonitorService.setup_match_monitors()
            │
            ├── 检查 ESPORTS_ENABLED 开关
            ├── EsportsService 拉取当天赛程（返回含 match_id 和三态 status 的数据）
            │
            └── 遍历每场比赛（上限 MAX_MONITOR_JOBS=20）:
                    │
                    ├── 已结束 → 跳过
                    ├── 未开始 → 创建 APScheduler job，start_date = 比赛开始时间
                    └── 进行中 → 创建 APScheduler job，立即开始
                          │
                          interval: NBA=1h, LoL=30min
                          job_id: "esports_monitor_{match_type}_{match_id}"

每个 job 执行时:
    1. 调用 API 获取该场比赛最新比分
    2. 推送 Slack 消息
    3. 检查比赛是否结束 → 是则 remove_job() 并推送最终比分
    4. 检查是否超过最大监控时长 → 是则 remove_job()

服务器重启时:
    scheduler.init_app() 末尾 → EsportsMonitorService.recover_monitors()
        └── 同 setup_match_monitors() 逻辑，为未结束的比赛重建 job
        └── try/except 包裹，失败只 log warning 不阻塞启动
```

## Scheduler 实例访问

当前 `SchedulerEngine` 在 `create_app()` 中是局部变量。需要将其暴露为可访问的实例。

**方案**：在 `app/scheduler/engine.py` 中创建模块级单例：

```python
# engine.py 末尾
scheduler_engine = SchedulerEngine()
```

`create_app()` 中改为：
```python
from app.scheduler.engine import scheduler_engine
scheduler_engine.init_app(app)
```

`EsportsMonitorService` 通过导入获取：
```python
from app.scheduler.engine import scheduler_engine
# 使用 scheduler_engine.scheduler.add_job() / remove_job()
```

## EsportsMonitorService 设计

**文件**：`app/services/esports_monitor_service.py`（新建）

```python
class EsportsMonitorService:
    JOB_PREFIX = "esports_monitor_"
    MAX_MONITOR_JOBS = 20  # 防止异常数据创建过多 job
    NBA_MAX_DURATION_HOURS = 5
    LOL_MAX_DURATION_HOURS = 8

    def __init__(self, app=None):
        self.app = app or current_app._get_current_object()

    def setup_match_monitors(self):
        """每日简报后调用，为当天比赛创建监控 job"""
        # 0. 检查 ESPORTS_ENABLED，为 False 直接 return
        # 1. 清理已有的赛事监控 job（避免重复）
        # 2. 拉取当天 NBA + LoL 赛程
        # 3. 遍历每场比赛，调用 _create_monitor_job()
        # 4. job 数量超过 MAX_MONITOR_JOBS 时截断并 log warning

    def recover_monitors(self):
        """服务器启动时调用，try/except 包裹"""
        # try: setup_match_monitors()
        # except: log warning，不阻塞启动

    def _create_monitor_job(self, match_info):
        """为单场比赛创建 APScheduler interval job"""
        # match_info 包含: match_id, match_type(nba/lol), start_time, teams
        # job_id = f"{JOB_PREFIX}{match_type}_{match_id}"
        # 已结束 → 跳过
        # 未开始 → start_date = 比赛开始时间
        # 进行中 → 立即开始（next_run_time=now）

    def _poll_match(self, match_type, match_id, teams_desc, start_time):
        """单个 job 的执行函数，在 app context 内执行"""
        with self.app.app_context():
            # 1. 检查超时（超过 MAX_DURATION → remove_job）
            # 2. 调用 EsportsService 获取最新比分
            # 3. 格式化并推送 Slack
            # 4. 比赛结束 → remove_job() + 推送最终比分

    def _cleanup_monitors(self):
        """清理所有 esports_monitor_ 前缀的 job"""
```

### App Context 处理

`EsportsMonitorService` 持有 Flask `app` 引用（与 `SchedulerEngine` 模式一致）。`_poll_match` 通过 `with self.app.app_context()` 包裹执行，确保数据库访问和 Slack 推送正常工作。

### match_info 数据结构

```python
{
    "match_id": "401656789",        # ESPN event.id / LoL match.id
    "match_type": "nba",            # "nba" 或 "lol"
    "start_time": datetime(...),    # 北京时间开赛时间
    "status": "in_progress",        # "scheduled" / "in_progress" / "completed"
    "home_team": "湖人",
    "away_team": "勇士",
    "league": "NBA"                 # 或 "LPL"/"LCK" 等
}
```

### 关键细节

- `_poll_match` 通过 `self.app.app_context()` 获取 Flask 上下文
- job 使用 `misfire_grace_time=None` 避免错过的轮询堆积
- setup 时先 cleanup 再创建，确保幂等
- 超时保护：NBA 最多监控 5 小时，LoL 最多 8 小时，超时自动 remove job

## EsportsService 扩展

### 现有方法改造

现有 `_fetch_espn_scoreboard()` 和 `_fetch_lol_esports_schedule()` 需要扩展返回数据：

**NBA (`_fetch_espn_scoreboard`)**：
- 提取 `event['id']` 作为 `match_id`
- status 三态映射：`state == 'post'` → `completed`，`state == 'in'` → `in_progress`，其他 → `scheduled`
- 提取 `quarter`（节数）和 `game_clock`（比赛时钟）用于实时推送

**LoL (`_fetch_lol_esports_schedule`)**：
- 提取 match ID
- status 三态映射：增加 `state == 'inProgress'` → `in_progress` 的处理

### 新增方法

```python
def get_nba_live_scores(self):
    """获取当天所有 NBA 比赛实时比分（批量）"""
    # 调用 ESPN scoreboard API（一次返回当天所有比赛）
    # 返回: {match_id: {teams, score, quarter, game_clock, status}}

def get_lol_live_scores(self):
    """获取当天所有 LoL 比赛实时比分（批量）"""
    # 调用 LoL schedule API
    # 返回: {match_id: {teams, score, status}}
```

### API 调用策略

ESPN scoreboard API 一次返回当天所有比赛，无需按单场查询。当多场 NBA 比赛同时进行时，各 job 独立调用 `get_nba_live_scores()` 再按 `match_id` 过滤。LoL 同理。

> 注：如果未来发现 LoL Esports 的 `getSchedule` 在比赛进行中不返回实时局数，可能需要改用 `getLiveMatches` 或 `getEventDetails` 端点，实现时需验证。

## 推送消息格式

```
NBA 进行中:  🏀 湖人 105-98 勇士 | Q3 5:32
LoL 进行中:  🎮 [LPL] EDG 1-1 WBG | 第3局进行中
比赛结束:    🏆 湖人 118-110 勇士 | 全场结束
```

每场比赛独立推送一条 Slack 消息。

## 调度集成

### 每日简报触发

在 `notification.py` 的 `push_daily_report()` 末尾调用：
```python
def push_daily_report(self):
    # ... 现有简报逻辑 ...
    # 简报推送完成后，创建赛事监控
    try:
        from app.services.esports_monitor_service import EsportsMonitorService
        EsportsMonitorService().setup_match_monitors()
    except Exception as e:
        logger.error(f'赛事监控创建失败: {e}')
```

### 重启恢复

在 `app/scheduler/engine.py` 的 `init_app()` 中，调度器启动后调用（非 `create_app()`，确保 scheduler 已就绪）：

```python
def init_app(self, app):
    # ... 现有策略注册和 scheduler.start() ...
    # 调度器启动后，恢复赛事监控
    self._recover_esports_monitors(app)

def _recover_esports_monitors(self, app):
    try:
        with app.app_context():
            from app.services.esports_monitor_service import EsportsMonitorService
            EsportsMonitorService(app).recover_monitors()
    except Exception as e:
        logger.warning(f'[调度器] 赛事监控恢复失败（不影响启动）: {e}')
```

### APScheduler job 管理

- 获取 scheduler 实例：`from app.scheduler.engine import scheduler_engine`，使用 `scheduler_engine.scheduler`
- 添加 job：`scheduler.add_job(func, 'interval', minutes=interval, id=job_id, start_date=start_time, misfire_grace_time=None)`
- 移除 job：`scheduler.remove_job(job_id)`
- 清理：遍历 `scheduler.get_jobs()`，移除 `JOB_PREFIX` 前缀的

### 边界情况

- 8:30am 简报时比赛已结束 → 跳过，不创建 job
- 8:30am 简报时比赛正在进行 → 立即创建 job 并首次轮询
- 重启时当天无比赛 → 无操作
- 重启时已过当天所有比赛 → 全部跳过
- API 不可用（网络问题）→ log warning，不阻塞启动/简报
- job 数量超过 20 → 截断并 log warning
- 比赛状态长时间未更新 → 超时自动清理（NBA 5h / LoL 8h）
- `ESPORTS_ENABLED=false` → 不创建任何监控 job

## 配置

### 新增环境变量

| 环境变量 | 说明 | 默认值 |
|---------|------|-------|
| `ESPORTS_NBA_MONITOR_INTERVAL` | NBA 比分轮询间隔（分钟） | `60` |
| `ESPORTS_LOL_MONITOR_INTERVAL` | LoL 比分轮询间隔（分钟） | `30` |

在 `app/config/esports_config.py` 中读取。

### 不新增的内容

- 不新增数据库模型（无需持久化监控状态）
- 不新增前端页面（纯后台推送）
- 不新增 Flask 路由

## 文件变更清单

| 文件 | 变更 |
|-----|------|
| `app/services/esports_monitor_service.py` | **新建** — 监控 job 生命周期管理 |
| `app/services/esports_service.py` | **修改** — 现有方法增加 match_id/三态 status，新增批量实时查询方法 |
| `app/services/notification.py` | **修改** — `push_daily_report()` 末尾调用 setup |
| `app/config/esports_config.py` | **修改** — 新增监控间隔配置 |
| `app/scheduler/engine.py` | **修改** — 导出模块级单例，`init_app()` 末尾调用 recover |
| `CLAUDE.md` | **修改** — 同步新增环境变量 |
| `README.md` | **修改** — 同步新增环境变量 |
| `.env.sample` | **修改** — 新增配置项 |
