"""2026 FIFA 世界杯赛事数据（ESPN soccer 源，临时赛事结束后整文件删除）"""
import logging
import time
from datetime import datetime, timedelta, timezone

import httpx

from app.config.esports_config import ESPORTS_FETCH_TIMEOUT
from app.config.worldcup_config import ESPN_SOCCER_WC_URL, WORLDCUP_TEAM_NAMES

logger = logging.getLogger(__name__)

_CST = timezone(timedelta(hours=8))

# ESPN shortDetail → 中文状态尾标；分钟串（如 "67'"）不在表中则原样透传
_STATUS_CN = {
    'HT': '中场', 'Halftime': '中场',
    'FT': '终场', 'Full Time': '终场',
    'AET': '加时结束', 'Pens': '点球',
}


class WorldCupService:
    """获取 2026 世界杯赛程与实时比分"""

    @staticmethod
    def get_worldcup_schedule(today=None):
        """今日赛程 + 昨日结果；全部失败返回 None"""
        if today is None:
            today = datetime.now(_CST).date()
        yesterday = today - timedelta(days=1)

        all_games = []
        any_success = False
        for offset in range(3):
            d = today - timedelta(days=offset)
            games = WorldCupService._fetch_soccer_scoreboard(d)
            if games is not None:
                any_success = True
                all_games.extend(games)
        if not any_success:
            return None

        result = {'today': [], 'yesterday': []}
        seen = set()
        for game in all_games:
            beijing_date = game.pop('_beijing_date', None)
            key = (game['home'], game['away'], game.get('start_time'))
            if key in seen:
                continue
            seen.add(key)
            if beijing_date == today:
                result['today'].append(game)
            elif beijing_date == yesterday:
                result['yesterday'].append(game)
        return result

    @staticmethod
    def get_worldcup_schedule_by_date(target_date):
        """指定北京日期赛程；失败返回 None"""
        all_games = []
        any_success = False
        for offset in [-1, 0]:
            d = target_date + timedelta(days=offset)
            games = WorldCupService._fetch_soccer_scoreboard(d)
            if games is not None:
                any_success = True
                all_games.extend(games)
        if not any_success:
            return None

        result = []
        seen = set()
        for game in all_games:
            beijing_date = game.pop('_beijing_date', None)
            key = (game['home'], game['away'], game.get('start_time'))
            if key in seen:
                continue
            seen.add(key)
            if beijing_date == target_date:
                result.append(game)
        return result

    @staticmethod
    def get_worldcup_live_scores():
        """当天所有比赛实时比分 {match_id: game}；失败返回 None"""
        today = datetime.now(_CST).date()
        all_games = []
        any_success = False
        for offset in range(3):
            d = today - timedelta(days=offset)
            games = WorldCupService._fetch_soccer_scoreboard(d)
            if games is not None:
                any_success = True
                all_games.extend(games)
        if not any_success:
            return None
        seen = set()
        result = {}
        for g in all_games:
            g.pop('_beijing_date', None)
            mid = g.get('match_id')
            if mid and mid not in seen:
                seen.add(mid)
                result[mid] = g
        return result

    @staticmethod
    def _fetch_soccer_scoreboard(game_date, _max_retries=2):
        """拉取指定日期 ESPN soccer scoreboard；失败返回 None"""
        date_str = game_date.strftime('%Y%m%d')
        for attempt in range(_max_retries + 1):
            try:
                return WorldCupService._do_fetch_soccer(date_str)
            except Exception as e:
                if attempt < _max_retries:
                    logger.info(f'[世界杯] ESPN第{attempt + 1}次获取失败，重试: '
                                f'{type(e).__name__}: {e}')
                    time.sleep(2)
                else:
                    logger.warning(f'[世界杯] ESPN获取失败（已重试{_max_retries}次）: '
                                   f'{type(e).__name__}: {e}', exc_info=True)
                    return None

    @staticmethod
    def _do_fetch_soccer(date_str):
        resp = httpx.get(ESPN_SOCCER_WC_URL, params={'dates': date_str},
                         timeout=ESPORTS_FETCH_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        game_date = datetime.strptime(date_str, '%Y%m%d').date()

        games = []
        for event in data.get('events', []):
            competition = event.get('competitions', [{}])[0]
            competitors = competition.get('competitors', [])
            if len(competitors) < 2:
                continue

            home_info = away_info = None
            for c in competitors:
                if c.get('homeAway') == 'home':
                    home_info = c
                elif c.get('homeAway') == 'away':
                    away_info = c
            if not home_info or not away_info:
                continue

            home_name = home_info.get('team', {}).get('displayName', '')
            away_name = away_info.get('team', {}).get('displayName', '')
            home_cn = WORLDCUP_TEAM_NAMES.get(home_name, home_name)
            away_cn = WORLDCUP_TEAM_NAMES.get(away_name, away_name)

            status_obj = event.get('status', {})
            state = status_obj.get('type', {}).get('state', '')
            short_detail = status_obj.get('type', {}).get('shortDetail', '')

            start_utc = event.get('date', '')
            start_time = ''
            beijing_date = game_date
            if start_utc:
                try:
                    dt = datetime.fromisoformat(start_utc.replace('Z', '+00:00'))
                    start_time = dt.astimezone(_CST).strftime('%H:%M')
                    beijing_date = dt.astimezone(_CST).date()
                except (ValueError, TypeError):
                    pass

            if state == 'post':
                status = 'completed'
            elif state == 'in':
                status = 'in_progress'
            else:
                status = 'scheduled'

            game = {
                'match_id': event.get('id', ''),
                'home': home_cn,
                'away': away_cn,
                'status': status,
                'start_time': start_time,
                '_beijing_date': beijing_date,
                'home_score': None,
                'away_score': None,
                'status_detail': short_detail,
                'pens': None,
                'home_winner': bool(home_info.get('winner')),
                'away_winner': bool(away_info.get('winner')),
            }
            if state in ('post', 'in'):
                try:
                    raw_h = home_info.get('score')
                    raw_a = away_info.get('score')
                    game['home_score'] = int(raw_h) if raw_h is not None else None
                    game['away_score'] = int(raw_a) if raw_a is not None else None
                except (ValueError, TypeError):
                    pass
                hp = home_info.get('shootoutScore')
                ap = away_info.get('shootoutScore')
                if hp is not None and ap is not None:
                    try:
                        game['pens'] = (int(hp), int(ap))
                    except (ValueError, TypeError):
                        pass
            games.append(game)
        return games
