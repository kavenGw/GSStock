"""每日赛事安排推送 — 每天 07:00 推送昨日结果 + 今日 NBA 和 LoL 赛程

失败联赛不直接推 "数据获取失败"，而是挂起 5min × 3 轮重试。
详见 docs/plans/2026-05-07-esports-retry-queue-design.md
"""
import logging
from datetime import datetime, timedelta, timezone

from app.strategies.base import Strategy, Signal

logger = logging.getLogger(__name__)

_CST = timezone(timedelta(hours=8))


def _sorted_by_time(matches):
    return sorted(matches, key=lambda x: x.get('start_time') or '99:99')


def _is_played(m, score_key):
    """已开赛（进行中/已结束且有比分）→ 昨日段按比分展示"""
    return m['status'] in ('completed', 'in_progress') and m.get(score_key) is not None


class EsportsDailyScheduleStrategy(Strategy):
    name = "esports_daily_schedule"
    description = "每日赛事安排（07:00 今日 NBA/LoL 赛程）"
    schedule = "0 7 * * *"
    needs_llm = False

    def scan(self) -> list[Signal]:
        from app.config.esports_config import ESPORTS_ENABLED
        if not ESPORTS_ENABLED:
            return []

        self._push_nba_today()
        self._push_lol_today()
        self._push_worldcup_today()
        return []

    @staticmethod
    def _push_nba_today():
        from app.config.esports_config import NBA_ENABLED
        if not NBA_ENABLED:
            return
        from app.services.esports_service import EsportsService
        from app.services.notification import NotificationService
        from app.config.notification_config import CHANNEL_NBA
        from app.config.esports_config import NBA_TEAM_MONITOR, NBA_TEAM_NAMES
        from app.services.esports_retry_queue import enqueue

        try:
            nba = EsportsService.get_nba_schedule()
            if nba is None:
                today = datetime.now(_CST).date()
                enqueue(today, 'nba', 'NBA')
                return

            monitored_cn = {NBA_TEAM_NAMES.get(k, k) for k, v in NBA_TEAM_MONITOR.items() if v}

            def _filtered(key):
                games = nba.get(key) or []
                if monitored_cn:
                    games = [g for g in games
                             if g['home'] in monitored_cn or g['away'] in monitored_cn]
                return games

            yesterday, today = _filtered('yesterday'), _filtered('today')

            lines = ['🏀 *NBA*', '']
            if not yesterday:
                lines.append('昨日: 无关注球队比赛')
            else:
                lines.append(f'昨日 ({len(yesterday)}场)')
                for g in _sorted_by_time(yesterday):
                    if _is_played(g, 'away_score'):
                        lines.append(
                            f'  · {g["away"]} {g["away_score"]}-{g["home_score"]} {g["home"]}')
                    else:
                        lines.append(f'  · {g["away"]} vs {g["home"]} 未开赛')
            lines.append('')
            if not today:
                lines.append('今日: 无关注球队比赛')
            else:
                lines.append(f'今日 ({len(today)}场)')
                for g in _sorted_by_time(today):
                    t = g.get('start_time') or '--:--'
                    lines.append(f'  · {t}  {g["away"]} vs {g["home"]}')

            NotificationService.send_slack('\n'.join(lines), CHANNEL_NBA)
            logger.info(f'[赛事安排] NBA 推送 昨日{len(yesterday)}场 / 今日{len(today)}场')
        except Exception as e:
            logger.error(f'[赛事安排] NBA 推送失败: {type(e).__name__}: {e}', exc_info=True)

    @staticmethod
    def _push_lol_today():
        from app.services.esports_service import EsportsService
        from app.services.notification import NotificationService
        from app.config.notification_config import CHANNEL_LOL
        from app.config.esports_config import LOL_ALWAYS_SHOW
        from app.services.esports_retry_queue import enqueue

        try:
            lol = EsportsService.get_lol_schedule()
            today = datetime.now(_CST).date()
            if lol is None:
                for league in LOL_ALWAYS_SHOW:
                    enqueue(today, 'lol', league)
                return

            sections = []
            total = 0
            for league in ['LPL', 'LCK', '先锋赛', 'Worlds', 'MSI']:
                if league not in lol:
                    continue
                data = lol[league]
                if data is None:
                    enqueue(today, 'lol', league)
                    continue
                prev = data.get('yesterday') or []
                matches = data.get('today') or []
                if not prev and not matches and league not in LOL_ALWAYS_SHOW:
                    continue
                total += len(matches)

                lines = [f'*{league}*']
                if not prev:
                    lines.append('昨日: 无赛事')
                else:
                    lines.append(f'昨日 ({len(prev)}场)')
                    for m in _sorted_by_time(prev):
                        if _is_played(m, 'score1'):
                            lines.append(
                                f'  · {m["team1"]} {m["score1"]}-{m["score2"]} {m["team2"]}')
                        else:
                            lines.append(f'  · {m["team1"]} vs {m["team2"]} 未开赛')
                if not matches:
                    lines.append('今日: 无赛事')
                else:
                    lines.append(f'今日 ({len(matches)}场)')
                    for m in _sorted_by_time(matches):
                        t = m.get('start_time') or '--:--'
                        lines.append(f'  · {t}  {m["team1"]} vs {m["team2"]}')
                sections.append('\n'.join(lines))

            if not sections:
                return
            header = f'🎮 *LoL 赛程* (今日{total}场)' if total else '🎮 *LoL 赛程*'
            NotificationService.send_slack(header + '\n\n' + '\n\n'.join(sections), CHANNEL_LOL)
            logger.info(f'[赛事安排] LoL 推送 今日 {total} 场')
        except Exception as e:
            logger.error(f'[赛事安排] LoL 推送失败: {type(e).__name__}: {e}', exc_info=True)

    @staticmethod
    def _push_worldcup_today():
        from app.config.worldcup_config import WORLDCUP_ENABLED
        if not WORLDCUP_ENABLED:
            return
        from app.services.worldcup_service import WorldCupService
        from app.services.notification import NotificationService
        from app.config.notification_config import CHANNEL_WORLDCUP
        from app.services.esports_retry_queue import enqueue

        try:
            sched = WorldCupService.get_worldcup_schedule()
            if sched is None:
                today = datetime.now(_CST).date()
                enqueue(today, 'worldcup', 'WorldCup')
                return

            yesterday = sched.get('yesterday') or []
            games = sched.get('today') or []

            lines = ['⚽ *世界杯赛程*', '']
            if not yesterday:
                lines.append('昨日: 无比赛')
            else:
                lines.append(f'昨日 ({len(yesterday)}场)')
                for g in _sorted_by_time(yesterday):
                    if g['status'] == 'completed':
                        score = WorldCupService.format_score(g, final=True)
                        lines.append(f'  · {score.removeprefix("⚽ ")}')
                    else:
                        lines.append(f'  · {g["home"]} vs {g["away"]} 未开赛')
            lines.append('')
            if not games:
                lines.append('今日: 无比赛')
            else:
                lines.append(f'今日 ({len(games)}场)')
                for g in _sorted_by_time(games):
                    t = g.get('start_time') or '--:--'
                    lines.append(f'  · {t}  {g["home"]} vs {g["away"]}')

            NotificationService.send_slack('\n'.join(lines), CHANNEL_WORLDCUP)
            logger.info(
                f'[赛事安排] 世界杯 推送 昨日{len(yesterday)}场 / 今日{len(games)}场')
        except Exception as e:
            logger.error(f'[赛事安排] 世界杯 推送失败: {type(e).__name__}: {e}',
                         exc_info=True)
