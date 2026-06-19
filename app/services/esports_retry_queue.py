"""赛事推送调度层重试队列

5min × 3 轮挂起重试。状态进程内字典 + APScheduler 一次性 job。
设计文档：docs/plans/2026-05-07-esports-retry-queue-design.md
"""
import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

logger = logging.getLogger(__name__)

_CST = timezone(timedelta(hours=8))
_RETRY_INTERVAL_MINUTES = 5
_MAX_ATTEMPTS = 3


@dataclass
class _PendingUnit:
    date: date
    kind: str  # 'lol' | 'nba' | 'worldcup'
    name: str
    attempts: int = 1


_pending: dict[str, _PendingUnit] = {}


def _key(date_, kind, name):
    return f"{date_.isoformat()}:{kind}:{name}"


def _schedule_retry(key):
    """挂一次性 job，在 now + 5min 触发 _retry_one(key)。被测试 monkeypatch 替换。"""
    from app.scheduler.engine import scheduler_engine
    from apscheduler.triggers.date import DateTrigger

    run_at = datetime.now(_CST) + timedelta(minutes=_RETRY_INTERVAL_MINUTES)

    def _job():
        with scheduler_engine.app.app_context():
            _retry_one(key)

    scheduler_engine.scheduler.add_job(
        _job,
        trigger=DateTrigger(run_date=run_at),
        id=f"esports_retry:{key}",
        replace_existing=True,
    )


def enqueue(date_, kind, name):
    """首轮失败入口。同 key 已 pending 时幂等。"""
    key = _key(date_, kind, name)
    if key in _pending:
        return
    _pending[key] = _PendingUnit(date=date_, kind=kind, name=name, attempts=1)
    _schedule_retry(key)
    logger.info(f'[赛事重试] enqueue {key}')


def _retry_one(key):
    unit = _pending.get(key)
    if unit is None:
        return

    today = datetime.now(_CST).date()
    if unit.date != today:
        _pending.pop(key, None)
        logger.info(f'[赛事重试] 跨日丢弃 {key}')
        return

    try:
        matches = _refetch(unit)
        if matches is not None:
            _push_supplement(unit, matches)
            _pending.pop(key, None)
            logger.info(f'[赛事重试] 补推成功 {key}')
            return
    except Exception as e:
        logger.warning(
            f'[赛事重试] {key} 拉取/推送异常 {type(e).__name__}: {e}',
            exc_info=True,
        )

    unit.attempts += 1
    if unit.attempts <= _MAX_ATTEMPTS:
        _schedule_retry(key)
        logger.info(f'[赛事重试] 第 {unit.attempts - 1} 轮失败 {key}，已挂下轮')
        return

    _push_failed(unit)
    _pending.pop(key, None)
    logger.warning(f'[赛事重试] 终告失败 {key}')


def _refetch(unit):
    from app.services.esports_service import EsportsService
    from app.config.esports_config import LOL_LEAGUES
    yesterday = unit.date - timedelta(days=1)
    if unit.kind == 'lol':
        league_id = LOL_LEAGUES.get(unit.name)
        if league_id is None:
            return None
        return EsportsService._fetch_lol_esports_schedule(league_id, unit.date, yesterday)
    if unit.kind == 'nba':
        return EsportsService.get_nba_schedule(today=unit.date)
    if unit.kind == 'worldcup':
        from app.services.worldcup_service import WorldCupService
        return WorldCupService.get_worldcup_schedule(today=unit.date)
    return None


def _push_supplement(unit, matches):
    if unit.kind == 'lol':
        _push_lol_supplement(unit.name, matches)
    elif unit.kind == 'nba':
        _push_nba_supplement(matches)
    elif unit.kind == 'worldcup':
        _push_worldcup_supplement(matches)


def _push_lol_supplement(league, matches):
    from app.services.notification import NotificationService
    from app.config.notification_config import CHANNEL_LOL
    from app.config.esports_config import LOL_ALWAYS_SHOW

    today_matches = matches.get('today') or []
    if not today_matches:
        if league in LOL_ALWAYS_SHOW:
            NotificationService.send_slack(
                f'🎮 *LoL 补充* — *{league}*\n今日无赛事',
                CHANNEL_LOL,
            )
        return

    lines = [f'🎮 *LoL 补充* — *{league}* ({len(today_matches)}场)']
    for m in sorted(today_matches, key=lambda x: x.get('start_time') or '99:99'):
        t = m.get('start_time') or '--:--'
        lines.append(f'  · {t}  {m["team1"]} vs {m["team2"]}')
    NotificationService.send_slack('\n'.join(lines), CHANNEL_LOL)


def _push_nba_supplement(nba):
    from app.services.notification import NotificationService
    from app.config.notification_config import CHANNEL_NBA
    from app.config.esports_config import NBA_TEAM_MONITOR, NBA_TEAM_NAMES

    games = nba.get('today') or []
    monitored_cn = {NBA_TEAM_NAMES.get(k, k) for k, v in NBA_TEAM_MONITOR.items() if v}
    if monitored_cn:
        games = [g for g in games if g['home'] in monitored_cn or g['away'] in monitored_cn]

    if not games:
        NotificationService.send_slack('🏀 *NBA 补充*\n无关注球队比赛', CHANNEL_NBA)
        return

    lines = [f'🏀 *NBA 补充* ({len(games)}场)']
    for g in sorted(games, key=lambda x: x.get('start_time') or '99:99'):
        t = g.get('start_time') or '--:--'
        lines.append(f'  · {t}  {g["away"]} vs {g["home"]}')
    NotificationService.send_slack('\n'.join(lines), CHANNEL_NBA)


def _push_worldcup_supplement(sched):
    from app.services.notification import NotificationService
    from app.config.notification_config import CHANNEL_WORLDCUP

    games = sched.get('today') or []
    if not games:
        NotificationService.send_slack('⚽ *世界杯 补充*\n今日无比赛', CHANNEL_WORLDCUP)
        return
    lines = [f'⚽ *世界杯 补充* ({len(games)}场)']
    for g in sorted(games, key=lambda x: x.get('start_time') or '99:99'):
        t = g.get('start_time') or '--:--'
        lines.append(f'  · {t}  {g["home"]} vs {g["away"]}')
    NotificationService.send_slack('\n'.join(lines), CHANNEL_WORLDCUP)


def _push_failed(unit):
    from app.services.notification import NotificationService
    from app.config.notification_config import CHANNEL_LOL, CHANNEL_NBA, CHANNEL_WORLDCUP

    if unit.kind == 'lol':
        NotificationService.send_slack(
            f'🎮 *LoL — {unit.name}* 数据获取失败（已重试 {_MAX_ATTEMPTS} 次）',
            CHANNEL_LOL,
        )
    elif unit.kind == 'nba':
        NotificationService.send_slack(
            f'🏀 *今日 NBA 赛程* 数据获取失败（已重试 {_MAX_ATTEMPTS} 次）',
            CHANNEL_NBA,
        )
    elif unit.kind == 'worldcup':
        NotificationService.send_slack(
            f'⚽ *今日世界杯赛程* 数据获取失败（已重试 {_MAX_ATTEMPTS} 次）',
            CHANNEL_WORLDCUP,
        )


def clear_for_date(date_):
    """测试 / 运维清理用，移除指定日期的所有挂起 unit 与对应 APScheduler job。"""
    from app.scheduler.engine import scheduler_engine
    from apscheduler.jobstores.base import JobLookupError

    keys = [k for k, u in _pending.items() if u.date == date_]
    for k in keys:
        _pending.pop(k, None)
        try:
            scheduler_engine.scheduler.remove_job(f"esports_retry:{k}")
        except JobLookupError:
            pass
