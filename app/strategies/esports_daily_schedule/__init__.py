"""每日赛事安排推送 — 每天 07:00 推送今日 NBA 和 LoL 赛程

失败联赛不直接推 "数据获取失败"，而是挂起 5min × 3 轮重试。
详见 docs/plans/2026-05-07-esports-retry-queue-design.md
"""
import logging
from datetime import datetime, timedelta, timezone

from app.strategies.base import Strategy, Signal

logger = logging.getLogger(__name__)

_CST = timezone(timedelta(hours=8))


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
        return []

    @staticmethod
    def _push_nba_today():
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

            games = nba.get('today') or []
            monitored_cn = {NBA_TEAM_NAMES.get(k, k) for k, v in NBA_TEAM_MONITOR.items() if v}
            if monitored_cn:
                games = [g for g in games if g['home'] in monitored_cn or g['away'] in monitored_cn]

            if not games:
                NotificationService.send_slack('🏀 *今日 NBA 赛程*\n无关注球队比赛', CHANNEL_NBA)
                return

            lines = [f'🏀 *今日 NBA 赛程* ({len(games)}场)', '']
            for g in sorted(games, key=lambda x: x.get('start_time') or '99:99'):
                t = g.get('start_time') or '--:--'
                lines.append(f'  · {t}  {g["away"]} vs {g["home"]}')
            NotificationService.send_slack('\n'.join(lines), CHANNEL_NBA)
            logger.info(f'[赛事安排] NBA 推送 {len(games)} 场')
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
                matches = data.get('today') or []
                if not matches and league not in LOL_ALWAYS_SHOW:
                    continue
                if not matches:
                    sections.append(f'*{league}*\n今日无赛事')
                    continue
                total += len(matches)
                lines = [f'*{league}* ({len(matches)}场)']
                for m in sorted(matches, key=lambda x: x.get('start_time') or '99:99'):
                    t = m.get('start_time') or '--:--'
                    lines.append(f'  · {t}  {m["team1"]} vs {m["team2"]}')
                sections.append('\n'.join(lines))

            if not sections:
                return
            header = f'🎮 *今日 LoL 赛程* ({total}场)' if total else '🎮 *今日 LoL 赛程*'
            NotificationService.send_slack(header + '\n\n' + '\n\n'.join(sections), CHANNEL_LOL)
            logger.info(f'[赛事安排] LoL 推送 {total} 场')
        except Exception as e:
            logger.error(f'[赛事安排] LoL 推送失败: {type(e).__name__}: {e}', exc_info=True)
