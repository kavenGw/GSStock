# 赛事实时监控 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 每日简报后自动为当天 NBA/LoL 比赛创建独立定时任务，按固定间隔轮询比分并推送 Slack

**Architecture:** EsportsMonitorService 管理 per-match APScheduler interval job 的生命周期。每日简报触发创建，比赛结束或超时自动销毁。服务器重启后从 API 重新拉取赛程恢复监控。

**Tech Stack:** Flask, APScheduler, httpx, Slack Webhook

**Spec:** `docs/plans/2026-03-21-esports-monitor-design.md`

---

## File Structure

| 文件 | 职责 | 变更类型 |
|-----|------|---------|
| `app/config/esports_config.py` | 新增监控间隔环境变量 | 修改 |
| `app/scheduler/engine.py` | 导出模块级单例 + 启动恢复 | 修改 |
| `app/__init__.py` | 改用导入的单例 | 修改 |
| `app/services/esports_service.py` | 扩展 match_id/三态 status + 新增批量实时查询 | 修改 |
| `app/services/esports_monitor_service.py` | 监控 job 生命周期管理 | 新建 |
| `app/services/notification.py` | status 值 `finished` → `completed` + `in_progress` 处理 | 修改 |
| `app/strategies/daily_briefing/__init__.py` | 简报后触发监控创建 | 修改 |
| `.env.sample` | 新增配置项 | 修改 |
| `CLAUDE.md` | 同步环境变量文档 | 修改 |
| `README.md` | 同步环境变量文档 | 修改 |

---

### Task 1: 新增监控间隔配置

**Files:**
- Modify: `app/config/esports_config.py:1-6`

- [ ] **Step 1: 添加监控间隔环境变量**

在 `app/config/esports_config.py` 的 `ESPORTS_FETCH_TIMEOUT` 后追加：

```python
# 赛事实时监控
ESPORTS_NBA_MONITOR_INTERVAL = int(os.getenv('ESPORTS_NBA_MONITOR_INTERVAL', '60'))
ESPORTS_LOL_MONITOR_INTERVAL = int(os.getenv('ESPORTS_LOL_MONITOR_INTERVAL', '30'))
```

- [ ] **Step 2: Commit**

```bash
git add app/config/esports_config.py
git commit -m "feat: 新增赛事监控间隔配置"
```

---

### Task 2: Scheduler 模块级单例

**Files:**
- Modify: `app/scheduler/engine.py:1-143`
- Modify: `app/__init__.py:287-298`

- [ ] **Step 1: 在 engine.py 末尾添加模块级单例**

在 `app/scheduler/engine.py` 文件末尾（`shutdown` 方法之后）追加：

```python
scheduler_engine = SchedulerEngine()
```

- [ ] **Step 2: 修改 create_app() 使用导入的单例**

在 `app/__init__.py` 中，将第 287-298 行的 scheduler 创建改为：

```python
from app.scheduler.engine import scheduler_engine
# ...（保留现有的 registry.discover() 等）
if not app.debug or _os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
    scheduler_engine.init_app(app)
```

只替换 `SchedulerEngine` 相关的导入和实例化。保留同一代码块中的其他导入（`event_bus`、`notification_manager` 等）。即：删除 `from app.scheduler.engine import SchedulerEngine` 和 `scheduler = SchedulerEngine()` / `scheduler.init_app(app)`，替换为导入和使用 `scheduler_engine` 单例。

- [ ] **Step 3: Commit**

```bash
git add app/scheduler/engine.py app/__init__.py
git commit -m "refactor: scheduler 改为模块级单例"
```

---

### Task 3: EsportsService 扩展 — NBA match_id 和三态 status

**Files:**
- Modify: `app/services/esports_service.py:66-140`

- [ ] **Step 1: 修改 _fetch_espn_scoreboard 返回 match_id、三态 status 和实时数据**

在 `_fetch_espn_scoreboard` 方法中修改 game dict 构建逻辑（约第 120-136 行）：

1. 提取 `event['id']` 作为 `match_id`
2. status 三态映射：`post` → `completed`，`in` → `in_progress`，其他 → `scheduled`
3. 在 `in_progress` 状态下也提取比分
4. 提取 `quarter` 和 `game_clock`

```python
# 在 state = ... 之后
match_id = event.get('id', '')

# 三态 status
if state == 'post':
    status = 'completed'
elif state == 'in':
    status = 'in_progress'
else:
    status = 'scheduled'

# 实时比赛数据
quarter = ''
game_clock = ''
if state == 'in':
    status_detail = status_obj.get('type', {}).get('shortDetail', '')
    # shortDetail 格式如 "Q3 5:32" 或 "Halftime"
    quarter = status_detail

game = {
    'match_id': match_id,
    'home': home_cn,
    'away': away_cn,
    'status': status,
    'start_time': start_time,
    '_beijing_date': beijing_date,
    'home_score': None,
    'away_score': None,
    'quarter': quarter,
}

# completed 和 in_progress 都提取比分
if state in ('post', 'in'):
    try:
        game['home_score'] = int(home_info.get('score', 0))
        game['away_score'] = int(away_info.get('score', 0))
    except (ValueError, TypeError):
        pass
```

同时更新 `get_nba_schedule` 方法的 docstring（第 28 行），将 `'scheduled'|'finished'` 改为 `'scheduled'|'in_progress'|'completed'`。

- [ ] **Step 2: 更新 notification.py 中 NBA status 引用**

`app/services/notification.py:721` — `_format_nba_section` 中将 `g['status'] == 'finished'` 改为 `g['status'] in ('completed', 'in_progress')`，使进行中的比赛也显示当前比分。

- [ ] **Step 3: Commit**

```bash
git add app/services/esports_service.py app/services/notification.py
git commit -m "feat: NBA 数据增加 match_id、三态 status 和实时比分"
```

---

### Task 4: EsportsService 扩展 — LoL match_id 和三态 status

**Files:**
- Modify: `app/services/esports_service.py:177-271`

- [ ] **Step 1: 修改 _fetch_lol_esports_schedule 返回 match_id 和三态 status**

在 `_fetch_lol_esports_schedule` 方法中修改 match dict 构建逻辑（约第 225-245 行）：

1. 提取 match ID：`match_info.get('id', '')`
2. status 三态：`completed` → `completed`，`inProgress` → `in_progress`，其他 → `scheduled`
3. `in_progress` 状态也提取局数

```python
match_info = event.get('match', {})
teams = match_info.get('teams', [])
if len(teams) < 2:
    continue

state = event.get('state', '')
# 三态 status
if state == 'completed':
    status = 'completed'
elif state == 'inProgress':
    status = 'in_progress'
else:
    status = 'scheduled'

match = {
    'match_id': match_info.get('id', ''),
    'team1': teams[0].get('name', ''),
    'team2': teams[1].get('name', ''),
    'status': status,
    'start_time': event_time,
    'score1': None,
    'score2': None,
}

# completed 和 in_progress 都提取局数
if state in ('completed', 'inProgress'):
    result_obj = teams[0].get('result', {})
    result_obj2 = teams[1].get('result', {})
    if result_obj and result_obj2:
        match['score1'] = result_obj.get('gameWins', 0)
        match['score2'] = result_obj2.get('gameWins', 0)
```

同时更新 `get_lol_schedule` 方法的 docstring（第 149 行），将 `'scheduled'|'finished'` 改为 `'scheduled'|'in_progress'|'completed'`。

- [ ] **Step 2: 更新 notification.py 中 LoL status 引用**

`app/services/notification.py:740` — `_format_lol_section` 中将 `m['status'] == 'finished'` 改为 `m['status'] in ('completed', 'in_progress')`，使进行中的比赛也显示当前比分。

- [ ] **Step 3: Commit**

```bash
git add app/services/esports_service.py app/services/notification.py
git commit -m "feat: LoL 数据增加 match_id 和三态 status"
```

---

### Task 5: EsportsService 新增批量实时查询方法

**Files:**
- Modify: `app/services/esports_service.py`

- [ ] **Step 1: 添加 get_nba_live_scores 方法**

在 `EsportsService` 类中 `_fetch_espn_scoreboard` 之后添加：

```python
@staticmethod
def get_nba_live_scores():
    """获取当天所有 NBA 比赛实时比分

    Returns:
        dict: {match_id: game_dict} 或 None
    """
    today = datetime.now(_CST).date()
    games = EsportsService._fetch_espn_scoreboard(today)
    if games is None:
        return None
    return {g['match_id']: g for g in games if g.get('match_id')}
```

- [ ] **Step 2: 添加 get_lol_live_scores 方法**

在 `EsportsService` 类中 `_fetch_lol_esports_schedule` 之后添加：

```python
@staticmethod
def get_lol_live_scores():
    """获取当天所有 LoL 比赛实时比分

    Returns:
        dict: {match_id: {match_dict + 'league': str}} 或 None
    """
    today = datetime.now(_CST).date()
    yesterday = today - timedelta(days=1)
    result = {}
    any_success = False
    for league_name, league_id in LOL_LEAGUES.items():
        matches = EsportsService._fetch_lol_esports_schedule(
            league_id, today, yesterday,
        )
        if matches is None:
            continue
        any_success = True
        for m in matches.get('today', []):
            if m.get('match_id'):
                m['league'] = league_name
                result[m['match_id']] = m
    return result if any_success else None
```

- [ ] **Step 3: Commit**

```bash
git add app/services/esports_service.py
git commit -m "feat: EsportsService 新增批量实时比分查询"
```

---

### Task 6: 创建 EsportsMonitorService

**Files:**
- Create: `app/services/esports_monitor_service.py`

- [ ] **Step 1: 创建完整的 EsportsMonitorService**

```python
"""赛事实时比分监控服务"""
import logging
from datetime import datetime, timedelta, timezone

from app.config.esports_config import (
    ESPORTS_ENABLED, ESPORTS_NBA_MONITOR_INTERVAL, ESPORTS_LOL_MONITOR_INTERVAL,
)

logger = logging.getLogger(__name__)

_CST = timezone(timedelta(hours=8))


class EsportsMonitorService:
    """管理赛事监控 APScheduler job 的生命周期"""

    JOB_PREFIX = 'esports_monitor_'
    MAX_MONITOR_JOBS = 20
    NBA_MAX_DURATION_HOURS = 5
    LOL_MAX_DURATION_HOURS = 8

    def __init__(self, app):
        self.app = app

    def setup_match_monitors(self):
        """为当天比赛创建监控 job"""
        if not ESPORTS_ENABLED:
            return

        from app.services.esports_service import EsportsService

        self._cleanup_monitors()

        matches = []

        # NBA
        try:
            nba = EsportsService.get_nba_schedule()
            if nba:
                for game in nba.get('today', []):
                    if game.get('match_id') and game['status'] != 'completed':
                        matches.append({
                            'match_id': game['match_id'],
                            'match_type': 'nba',
                            'status': game['status'],
                            'start_time': game.get('start_time', ''),
                            'teams_desc': f"{game['away']} vs {game['home']}",
                            'league': 'NBA',
                        })
        except Exception as e:
            logger.warning(f'[赛事监控] NBA赛程获取失败: {e}')

        # LoL
        try:
            lol = EsportsService.get_lol_schedule()
            if lol:
                for league_name, league_data in lol.items():
                    if league_data is None:
                        continue
                    for match in league_data.get('today', []):
                        if match.get('match_id') and match['status'] != 'completed':
                            matches.append({
                                'match_id': match['match_id'],
                                'match_type': 'lol',
                                'status': match['status'],
                                'start_time': match.get('start_time', ''),
                                'teams_desc': f"{match['team1']} vs {match['team2']}",
                                'league': league_name,
                            })
        except Exception as e:
            logger.warning(f'[赛事监控] LoL赛程获取失败: {e}')

        if not matches:
            logger.info('[赛事监控] 当天无需监控的比赛')
            return

        if len(matches) > self.MAX_MONITOR_JOBS:
            logger.warning(f'[赛事监控] 比赛数 {len(matches)} 超过上限 {self.MAX_MONITOR_JOBS}，截断')
            matches = matches[:self.MAX_MONITOR_JOBS]

        created = 0
        for match in matches:
            if self._create_monitor_job(match):
                created += 1

        logger.info(f'[赛事监控] 创建 {created} 个监控任务')

    def recover_monitors(self):
        """服务器启动时恢复监控"""
        try:
            self.setup_match_monitors()
        except Exception as e:
            logger.warning(f'[赛事监控] 恢复失败（不影响启动）: {e}')

    def _create_monitor_job(self, match_info):
        """为单场比赛创建 interval job"""
        from app.scheduler.engine import scheduler_engine
        from apscheduler.triggers.interval import IntervalTrigger

        match_type = match_info['match_type']
        match_id = match_info['match_id']
        job_id = f'{self.JOB_PREFIX}{match_type}_{match_id}'
        interval = ESPORTS_NBA_MONITOR_INTERVAL if match_type == 'nba' else ESPORTS_LOL_MONITOR_INTERVAL

        now = datetime.now(_CST)
        created_at = now

        try:
            trigger = IntervalTrigger(minutes=interval)
            kwargs = {
                'func': self._poll_match,
                'trigger': trigger,
                'args': [match_type, match_id, match_info['teams_desc'],
                         match_info['league'], created_at],
                'id': job_id,
                'replace_existing': True,
                'misfire_grace_time': None,
            }

            if match_info['status'] == 'in_progress':
                kwargs['next_run_time'] = now
            elif match_info['status'] == 'scheduled' and match_info.get('start_time'):
                # start_time 是 "HH:MM" 格式，转为今天的 datetime
                try:
                    h, m = map(int, match_info['start_time'].split(':'))
                    start_dt = now.replace(hour=h, minute=m, second=0, microsecond=0)
                    if start_dt > now:
                        kwargs['next_run_time'] = start_dt
                    else:
                        kwargs['next_run_time'] = now
                except (ValueError, TypeError):
                    kwargs['next_run_time'] = now

            scheduler_engine.scheduler.add_job(**kwargs)
            logger.info(f'[赛事监控] 创建任务: {job_id} ({match_info["teams_desc"]}, 每{interval}分钟)')
            return True
        except Exception as e:
            logger.error(f'[赛事监控] 创建任务失败 {job_id}: {e}')
            return False

    def _poll_match(self, match_type, match_id, teams_desc, league, created_at):
        """轮询单场比赛并推送"""
        with self.app.app_context():
            from app.scheduler.engine import scheduler_engine
            job_id = f'{self.JOB_PREFIX}{match_type}_{match_id}'

            # 超时检查
            max_hours = self.NBA_MAX_DURATION_HOURS if match_type == 'nba' else self.LOL_MAX_DURATION_HOURS
            if datetime.now(_CST) - created_at > timedelta(hours=max_hours):
                logger.info(f'[赛事监控] {job_id} 超时 {max_hours}h，移除')
                try:
                    scheduler_engine.scheduler.remove_job(job_id)
                except Exception:
                    pass
                return

            try:
                from app.services.esports_service import EsportsService
                from app.services.notification import NotificationService

                if match_type == 'nba':
                    scores = EsportsService.get_nba_live_scores()
                    if scores is None:
                        logger.warning(f'[赛事监控] NBA 比分获取失败')
                        return
                    game = scores.get(match_id)
                    if game is None:
                        logger.warning(f'[赛事监控] 未找到比赛 {match_id}')
                        return

                    if game['status'] == 'completed':
                        msg = f"🏆 {game['away']} {game['away_score']}-{game['home_score']} {game['home']} | 全场结束"
                        NotificationService.send_slack(msg)
                        scheduler_engine.scheduler.remove_job(job_id)
                        logger.info(f'[赛事监控] {job_id} 比赛结束，移除')
                        return

                    if game['status'] == 'in_progress':
                        quarter = game.get('quarter', '')
                        score_text = f"{game['away']} {game['away_score']}-{game['home_score']} {game['home']}"
                        msg = f"🏀 {score_text} | {quarter}" if quarter else f"🏀 {score_text}"
                        NotificationService.send_slack(msg)
                    else:
                        msg = f"🏀 {teams_desc} | 未开始"
                        NotificationService.send_slack(msg)

                else:  # lol
                    scores = EsportsService.get_lol_live_scores()
                    if scores is None:
                        logger.warning(f'[赛事监控] LoL 比分获取失败')
                        return
                    match = scores.get(match_id)
                    if match is None:
                        logger.warning(f'[赛事监控] 未找到比赛 {match_id}')
                        return

                    if match['status'] == 'completed':
                        msg = f"🏆 [{league}] {match['team1']} {match['score1']}-{match['score2']} {match['team2']} | 比赛结束"
                        NotificationService.send_slack(msg)
                        scheduler_engine.scheduler.remove_job(job_id)
                        logger.info(f'[赛事监控] {job_id} 比赛结束，移除')
                        return

                    if match['status'] == 'in_progress':
                        score1 = match.get('score1', 0) or 0
                        score2 = match.get('score2', 0) or 0
                        msg = f"🎮 [{league}] {match['team1']} {score1}-{score2} {match['team2']} | 进行中"
                        NotificationService.send_slack(msg)
                    else:
                        msg = f"🎮 [{league}] {teams_desc} | 未开始"
                        NotificationService.send_slack(msg)

            except Exception as e:
                logger.error(f'[赛事监控] {job_id} 轮询失败: {e}')

    def _cleanup_monitors(self):
        """清理所有赛事监控 job"""
        from app.scheduler.engine import scheduler_engine
        removed = 0
        for job in scheduler_engine.scheduler.get_jobs():
            if job.id.startswith(self.JOB_PREFIX):
                job.remove()
                removed += 1
        if removed:
            logger.info(f'[赛事监控] 清理 {removed} 个旧任务')
```

- [ ] **Step 2: Commit**

```bash
git add app/services/esports_monitor_service.py
git commit -m "feat: 新建 EsportsMonitorService 赛事实时监控服务"
```

---

### Task 7: 集成 — 每日简报触发 + 启动恢复

**Files:**
- Modify: `app/strategies/daily_briefing/__init__.py:14-29`
- Modify: `app/scheduler/engine.py` (init_app 末尾)

- [ ] **Step 1: 在 DailyBriefingStrategy.scan() 中触发监控创建**

在 `app/strategies/daily_briefing/__init__.py` 的 `scan` 方法中，`push_daily_report` 成功后调用：

```python
def scan(self) -> list[Signal]:
    from app.services.notification import NotificationService

    self._refresh_signal_cache()

    try:
        results = NotificationService.push_daily_report()
        if results.get('slack'):
            logger.info('[每日简报] 推送成功')
            # 推送成功后创建赛事监控
            self._setup_esports_monitors()
        else:
            logger.warning('[每日简报] 推送失败或未配置')
    except Exception as e:
        logger.error(f'[每日简报] 推送失败: {e}')

    return []

@staticmethod
def _setup_esports_monitors():
    try:
        from flask import current_app
        from app.services.esports_monitor_service import EsportsMonitorService
        EsportsMonitorService(current_app._get_current_object()).setup_match_monitors()
    except Exception as e:
        logger.error(f'[每日简报] 赛事监控创建失败: {e}')
```

- [ ] **Step 2: 在 engine.py init_app 末尾添加恢复调用**

在 `app/scheduler/engine.py` 的 `init_app` 方法中，`self._check_daily_push_catchup(app)` 之后追加：

```python
self._recover_esports_monitors(app)
```

- [ ] **Step 3: 在 _run_daily_push_catchup 中也触发赛事监控**

在 `app/scheduler/engine.py` 的 `_run_daily_push_catchup` 方法中，推送成功后追加赛事监控创建（因为补发路径绕过了 `DailyBriefingStrategy.scan()`）：

```python
def _run_daily_push_catchup(self):
    if not self.app:
        return
    with self.app.app_context():
        try:
            from app.services.notification import NotificationService
            results = NotificationService.push_daily_report()
            if results.get('slack'):
                logger.info('[调度器] 每日推送补发成功')
                self._setup_esports_monitors_safe()
            else:
                logger.warning('[调度器] 每日推送补发失败或未配置')
        except Exception as e:
            logger.error(f'[调度器] 每日推送补发失败: {e}')
```

并添加两个方法：

```python
def _recover_esports_monitors(self, app):
    """启动时恢复赛事监控"""
    try:
        with app.app_context():
            from app.services.esports_monitor_service import EsportsMonitorService
            EsportsMonitorService(app).recover_monitors()
    except Exception as e:
        logger.warning(f'[调度器] 赛事监控恢复失败（不影响启动）: {e}')

def _setup_esports_monitors_safe(self):
    """安全地创建赛事监控（已在 app context 内）"""
    try:
        from app.services.esports_monitor_service import EsportsMonitorService
        EsportsMonitorService(self.app).setup_match_monitors()
    except Exception as e:
        logger.error(f'[调度器] 赛事监控创建失败: {e}')
```

- [ ] **Step 4: Commit**

```bash
git add app/strategies/daily_briefing/__init__.py app/scheduler/engine.py
git commit -m "feat: 集成赛事监控到每日简报、补发和启动恢复"
```

---

### Task 8: 配置文档同步

**Files:**
- Modify: `.env.sample:78-82`
- Modify: `CLAUDE.md`
- Modify: `README.md`

- [ ] **Step 1: 更新 .env.sample**

在 `.env.sample` 赛事推送部分（约第 78-82 行）追加：

```
# 赛事实时监控间隔（分钟）
# ESPORTS_NBA_MONITOR_INTERVAL=60
# ESPORTS_LOL_MONITOR_INTERVAL=30
```

- [ ] **Step 2: 更新 CLAUDE.md**

在 `CLAUDE.md` 的"赛事推送配置"表格中追加两行：

```
| `ESPORTS_NBA_MONITOR_INTERVAL` | NBA 比分轮询间隔（分钟） | `60` |
| `ESPORTS_LOL_MONITOR_INTERVAL` | LoL 比分轮询间隔（分钟） | `30` |
```

- [ ] **Step 3: 更新 README.md**

在 `README.md` 的赛事推送配置表格中追加相同两行。

- [ ] **Step 4: Commit**

```bash
git add .env.sample CLAUDE.md README.md
git commit -m "docs: 同步赛事监控配置到 .env.sample、CLAUDE.md 和 README.md"
```

---

### Task 9: 验证

- [ ] **Step 1: 启动应用验证无报错**

```bash
python run.py
```

检查日志中是否有 `[赛事监控]` 相关输出（如"当天无需监控的比赛"或成功创建监控任务）。

- [ ] **Step 2: 验证 scheduler 单例正常工作**

确认日志中调度器启动成功，策略注册正常。

- [ ] **Step 3: 验证每日简报补发场景**

如果当天未推送过，启动后 30 秒应补发简报并触发赛事监控创建。
