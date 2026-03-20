"""赛事数据获取服务"""
import logging
from datetime import datetime, timedelta, timezone

import httpx

from app.config.esports_config import (
    ESPN_NBA_SCOREBOARD_URL, ESPORTS_FETCH_TIMEOUT, NBA_TEAM_NAMES,
    LOL_ESPORTS_API_BASE, LOL_ESPORTS_API_KEY, LOL_LEAGUES, LOL_ALWAYS_SHOW,
)

logger = logging.getLogger(__name__)

# 北京时间 UTC+8
_CST = timezone(timedelta(hours=8))


class EsportsService:
    """获取 NBA 和 LoL 电竞赛事数据"""

    @staticmethod
    def get_nba_schedule(today=None):
        """获取今日赛程 + 昨日结果

        Returns:
            {'today': [game, ...], 'yesterday': [game, ...]}
            game = {'home': str, 'away': str, 'home_score': int|None,
                    'away_score': int|None, 'status': 'scheduled'|'finished',
                    'start_time': str(HH:MM)}
            返回 None 表示全部获取失败
        """
        if today is None:
            today = datetime.now(_CST).date()
        yesterday = today - timedelta(days=1)

        result = {}
        for label, d in [('today', today), ('yesterday', yesterday)]:
            games = EsportsService._fetch_espn_scoreboard(d)
            if games is None:
                result[label] = None
            else:
                result[label] = games

        # 两个日期都失败时返回 None，区分"获取失败"和"无赛事"
        if result.get('today') is None and result.get('yesterday') is None:
            return None
        return result

    @staticmethod
    def _fetch_espn_scoreboard(game_date):
        """从 ESPN API 获取指定日期的 NBA 赛程

        Returns:
            list[dict] 或 None（获取失败）
        """
        date_str = game_date.strftime('%Y%m%d')
        try:
            resp = httpx.get(
                ESPN_NBA_SCOREBOARD_URL,
                params={'dates': date_str},
                timeout=ESPORTS_FETCH_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()

            games = []
            for event in data.get('events', []):
                competition = event.get('competitions', [{}])[0]
                competitors = competition.get('competitors', [])
                if len(competitors) < 2:
                    continue

                # 通过 homeAway 字段识别主客队（不依赖数组顺序）
                home_info = None
                away_info = None
                for c in competitors:
                    if c.get('homeAway') == 'home':
                        home_info = c
                    elif c.get('homeAway') == 'away':
                        away_info = c
                if not home_info or not away_info:
                    continue

                home_name = home_info.get('team', {}).get('displayName', '')
                away_name = away_info.get('team', {}).get('displayName', '')
                home_cn = NBA_TEAM_NAMES.get(home_name, home_name)
                away_cn = NBA_TEAM_NAMES.get(away_name, away_name)

                status_obj = event.get('status', {})
                state = status_obj.get('type', {}).get('state', '')

                # 解析开赛时间 → 北京时间
                start_utc = event.get('date', '')
                start_time = ''
                if start_utc:
                    try:
                        dt = datetime.fromisoformat(start_utc.replace('Z', '+00:00'))
                        start_time = dt.astimezone(_CST).strftime('%H:%M')
                    except (ValueError, TypeError):
                        pass

                game = {
                    'home': home_cn,
                    'away': away_cn,
                    'status': 'finished' if state == 'post' else 'scheduled',
                    'start_time': start_time,
                    'home_score': None,
                    'away_score': None,
                }
                if state == 'post':
                    try:
                        game['home_score'] = int(home_info.get('score', 0))
                        game['away_score'] = int(away_info.get('score', 0))
                    except (ValueError, TypeError):
                        pass

                games.append(game)
            return games
        except Exception as e:
            logger.warning(f'[赛事.NBA] ESPN获取失败: {e}')
            return None

    @staticmethod
    def get_lol_schedule(today=None):
        """获取所有 LoL 联赛今日赛程 + 昨日结果

        Returns:
            dict: {league_name: {'today': [...], 'yesterday': [...]}} 或 None（全部失败）
            match = {'team1': str, 'team2': str, 'score1': int|None,
                     'score2': int|None, 'status': 'scheduled'|'finished',
                     'start_time': str(HH:MM)}
        """
        if today is None:
            today = datetime.now(_CST).date()
        yesterday = today - timedelta(days=1)

        result = {}
        all_failed = True

        for league_name, league_id in LOL_LEAGUES.items():
            matches = EsportsService._fetch_lol_esports_schedule(
                league_id, today, yesterday,
            )
            if matches is not None:
                all_failed = False
                # 国际赛事（Worlds/MSI）无赛事时不加入结果
                if league_name not in LOL_ALWAYS_SHOW:
                    if not matches['today'] and not matches['yesterday']:
                        continue
                result[league_name] = matches
            else:
                # 获取失败但属于常驻联赛，标记失败
                if league_name in LOL_ALWAYS_SHOW:
                    result[league_name] = None

        return result if not all_failed else None

    @staticmethod
    def _fetch_lol_esports_schedule(league_id, today, yesterday):
        """从 LoL Esports API 获取指定联赛的赛程

        API 返回分页数据（无日期过滤参数），需要翻页查找目标日期。
        策略：从默认页开始，向 older 方向翻页最多3次，直到找到目标日期的事件
        或事件日期早于 yesterday 为止。

        Returns:
            {'today': [match, ...], 'yesterday': [match, ...]} 或 None（获取失败）
        """
        try:
            today_matches = []
            yesterday_matches = []
            page_token = None
            max_pages = 4  # 默认页 + 最多3次翻页

            for _ in range(max_pages):
                params = {'hl': 'zh-CN', 'leagueId': league_id}
                if page_token:
                    params['pageToken'] = page_token

                resp = httpx.get(
                    f'{LOL_ESPORTS_API_BASE}/getSchedule',
                    params=params,
                    headers={'x-api-key': LOL_ESPORTS_API_KEY},
                    timeout=ESPORTS_FETCH_TIMEOUT,
                )
                resp.raise_for_status()
                data = resp.json()

                schedule = data.get('data', {}).get('schedule', {})
                events = schedule.get('events', [])
                found_target_date = False
                earliest_date = None

                for event in events:
                    start_time_str = event.get('startTime', '')
                    if not start_time_str:
                        continue

                    try:
                        dt = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
                        event_date = dt.astimezone(_CST).date()
                        event_time = dt.astimezone(_CST).strftime('%H:%M')
                    except (ValueError, TypeError):
                        continue

                    match_info = event.get('match', {})
                    teams = match_info.get('teams', [])
                    if len(teams) < 2:
                        continue

                    state = event.get('state', '')
                    match = {
                        'team1': teams[0].get('name', ''),
                        'team2': teams[1].get('name', ''),
                        'status': 'finished' if state == 'completed' else 'scheduled',
                        'start_time': event_time,
                        'score1': None,
                        'score2': None,
                    }

                    if state == 'completed':
                        result_obj = teams[0].get('result', {})
                        result_obj2 = teams[1].get('result', {})
                        if result_obj and result_obj2:
                            match['score1'] = result_obj.get('gameWins', 0)
                            match['score2'] = result_obj2.get('gameWins', 0)

                    if event_date == today:
                        today_matches.append(match)
                        found_target_date = True
                    elif event_date == yesterday:
                        yesterday_matches.append(match)
                        found_target_date = True

                    if earliest_date is None or event_date < earliest_date:
                        earliest_date = event_date

                # 已找到目标日期或当前页事件已早于目标日期，停止翻页
                if found_target_date or (earliest_date and earliest_date < yesterday):
                    break

                # 获取 older 页的 token，继续向前翻页
                older_token = schedule.get('pages', {}).get('older')
                if not older_token:
                    break
                page_token = older_token

            return {'today': today_matches, 'yesterday': yesterday_matches}
        except Exception as e:
            logger.warning(f'[赛事.LoL] 联赛{league_id}获取失败: {e}')
            return None
