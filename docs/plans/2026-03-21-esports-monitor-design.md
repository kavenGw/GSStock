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
            ├── EsportsService.get_nba/lol_schedule() — 拉取当天赛程
            │
            └── 遍历每场比赛:
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

服务器重启时:
    create_app() → EsportsMonitorService.recover_monitors()
        └── 同 setup_match_monitors() 逻辑，为未结束的比赛重建 job
```

## EsportsMonitorService 设计

**文件**：`app/services/esports_monitor_service.py`（新建）

```python
class EsportsMonitorService:
    JOB_PREFIX = "esports_monitor_"
    NBA_INTERVAL_MINUTES = 60   # 可通过环境变量覆盖
    LOL_INTERVAL_MINUTES = 30   # 可通过环境变量覆盖

    def setup_match_monitors(self):
        """每日简报后调用，为当天比赛创建监控 job"""
        # 1. 清理已有的赛事监控 job（避免重复）
        # 2. 拉取当天 NBA + LoL 赛程
        # 3. 遍历每场比赛，调用 _create_monitor_job()

    def recover_monitors(self):
        """服务器启动时调用"""
        # 直接调用 setup_match_monitors()

    def _create_monitor_job(self, match_info):
        """为单场比赛创建 APScheduler interval job"""
        # match_info 包含: match_id, match_type(nba/lol), start_time, teams
        # job_id = f"{JOB_PREFIX}{match_type}_{match_id}"
        # 已结束 → 跳过
        # 未开始 → start_date = 比赛开始时间
        # 进行中 → 立即开始（next_run_time=now）

    def _poll_match(self, match_type, match_id, teams_desc):
        """单个 job 的执行函数"""
        # 1. 调用 EsportsService 获取最新比分
        # 2. 格式化并推送 Slack
        # 3. 比赛结束 → remove_job() + 推送最终比分

    def _cleanup_monitors(self):
        """清理所有 esports_monitor_ 前缀的 job"""
```

### match_info 数据结构

```python
{
    "match_id": "401656789",        # ESPN/LoL API 的比赛ID
    "match_type": "nba",            # "nba" 或 "lol"
    "start_time": datetime(...),    # 北京时间开赛时间
    "status": "in_progress",        # "scheduled" / "in_progress" / "completed"
    "home_team": "湖人",
    "away_team": "勇士",
    "league": "NBA"                 # 或 "LPL"/"LCK" 等
}
```

### 关键细节

- `_poll_match` 在 Flask app context 内执行
- job 使用 `misfire_grace_time=None` 避免错过的轮询堆积
- setup 时先 cleanup 再创建，确保幂等

## EsportsService 扩展

在现有 `app/services/esports_service.py` 中新增单场比赛实时查询方法。

```python
def get_nba_live_score(self, match_id):
    """获取单场 NBA 比赛实时比分"""
    # 复用 ESPN scoreboard API，按 match_id 过滤
    # 返回: teams, score, quarter, game_clock, status

def get_lol_live_score(self, match_id):
    """获取单场 LoL 比赛实时比分"""
    # 复用 LoL schedule API，按 match_id 过滤
    # 返回: teams, score (BO3/BO5 局数), status
```

不新增 API 端点，复用现有 scoreboard/schedule 接口按 match_id 过滤。

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
    EsportsMonitorService().setup_match_monitors()
```

### 重启恢复

在 `app/__init__.py` 的 `create_app()` 中，调度器启动后调用：
```python
def create_app():
    # ... 现有初始化 ...
    # 调度器启动后
    EsportsMonitorService().recover_monitors()
```

### APScheduler job 管理

- 获取 scheduler 实例：通过 `app/scheduler/engine.py` 的调度器
- 添加 job：`scheduler.add_job(func, 'interval', minutes=interval, id=job_id, start_date=start_time, misfire_grace_time=None)`
- 移除 job：`scheduler.remove_job(job_id)`
- 清理：遍历所有 job，移除 `JOB_PREFIX` 前缀的

### 边界情况

- 8:30am 简报时比赛已结束 → 跳过，不创建 job
- 8:30am 简报时比赛正在进行 → 立即创建 job 并首次轮询
- 重启时当天无比赛 → 无操作
- 重启时已过当天所有比赛 → 全部跳过

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
| `app/services/esports_service.py` | **修改** — 新增单场比赛实时查询方法 |
| `app/services/notification.py` | **修改** — `push_daily_report()` 末尾调用 setup |
| `app/config/esports_config.py` | **修改** — 新增监控间隔配置 |
| `app/__init__.py` | **修改** — 启动时调用 recover |
| `CLAUDE.md` | **修改** — 同步新增环境变量 |
| `README.md` | **修改** — 同步新增环境变量 |
| `.env.sample` | **修改** — 新增配置项 |
