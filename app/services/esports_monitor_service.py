"""赛事实时比分监控服务

优化功能:
1. 赛前10分钟提醒
2. NBA: 每15分钟检查比分，仅在比分变化时推送
3. LoL: 每30分钟检查比分，仅在比分变化时推送
4. 比赛结束时推送最终比分
"""
import logging
from datetime import datetime, timedelta, timezone
from threading import Lock

from app.config.esports_config import (
    ESPORTS_ENABLED, ESPORTS_NBA_MONITOR_INTERVAL, ESPORTS_LOL_MONITOR_INTERVAL,
    ESPORTS_PRE_MATCH_MINUTES, NBA_TEAM_MONITOR,
)

logger = logging.getLogger(__name__)

_CST = timezone(timedelta(hours=8))

# 比分状态存储（用于检测变化）
_score_state = {}
_score_state_lock = Lock()


def _get_score_key(match_type, match_id):
    """生成比分状态的 key"""
    return f'{match_type}_{match_id}'


def _get_last_score(match_type, match_id):
    """获取上次记录的比分"""
    key = _get_score_key(match_type, match_id)
    with _score_state_lock:
        return _score_state.get(key)


def _update_score(match_type, match_id, score1, score2, status):
    """更新比分状态"""
    key = _get_score_key(match_type, match_id)
    with _score_state_lock:
        _score_state[key] = {
            'score1': score1,
            'score2': score2,
            'status': status,
        }


def _clear_score(match_type, match_id):
    """清除比分状态（比赛结束后）"""
    key = _get_score_key(match_type, match_id)
    with _score_state_lock:
        _score_state.pop(key, None)


def _has_score_changed(match_type, match_id, new_score1, new_score2, new_status):
    """检测比分是否发生变化"""
    last = _get_last_score(match_type, match_id)
    if last is None:
        return True  # 首次记录，视为变化

    # 比分变化
    if last['score1'] != new_score1 or last['score2'] != new_score2:
        return True

    # 状态变化（scheduled -> in_progress -> completed）
    if last['status'] != new_status:
        return True

    return False


class EsportsMonitorService:
    """管理赛事监控 APScheduler job 的生命周期"""

    JOB_PREFIX = 'esports_monitor_'
    PRE_MATCH_PREFIX = 'esports_prematch_'
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
                monitored = {k for k, v in NBA_TEAM_MONITOR.items() if v}
                for game in nba.get('today', []):
                    if game.get('match_id') and game['status'] != 'completed':
                        if monitored and not ({game['home'], game['away']} & monitored):
                            continue
                        matches.append({
                            'match_id': game['match_id'],
                            'match_type': 'nba',
                            'status': game['status'],
                            'start_time': game.get('start_time', ''),
                            'teams_desc': f"{game['away']} vs {game['home']}",
                            'league': 'NBA',
                            'home': game['home'],
                            'away': game['away'],
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
                                'team1': match['team1'],
                                'team2': match['team2'],
                            })
        except Exception as e:
            logger.warning(f'[赛事监控] LoL赛程获取失败: {e}')

        if not matches:
            logger.info('[赛事监控] 当天无需监控的比赛')
            return

        if len(matches) > self.MAX_MONITOR_JOBS:
            logger.warning(f'[赛事监控] 比赛数 {len(matches)} 超过上限 {self.MAX_MONITOR_JOBS}，截断')
            matches = matches[:self.MAX_MONITOR_JOBS]

        created_monitors = 0
        created_prematch = 0
        for match in matches:
            if self._create_monitor_job(match):
                created_monitors += 1
            if self._create_pre_match_job(match):
                created_prematch += 1

        logger.info(f'[赛事监控] 创建 {created_monitors} 个监控任务, {created_prematch} 个赛前提醒')

    def recover_monitors(self):
        """服务器启动时恢复监控"""
        try:
            self.setup_match_monitors()
        except Exception as e:
            logger.warning(f'[赛事监控] 恢复失败（不影响启动）: {e}')

    def _create_pre_match_job(self, match_info):
        """创建赛前提醒 job（开赛前N分钟推送一次）"""
        from app.scheduler.engine import scheduler_engine
        from apscheduler.triggers.date import DateTrigger

        match_type = match_info['match_type']
        match_id = match_info['match_id']
        job_id = f'{self.PRE_MATCH_PREFIX}{match_type}_{match_id}'

        # 仅对 scheduled 状态的比赛创建赛前提醒
        if match_info['status'] != 'scheduled':
            return False

        if not match_info.get('start_time'):
            return False

        now = datetime.now(_CST)

        try:
            h, m = map(int, match_info['start_time'].split(':'))
            start_dt = now.replace(hour=h, minute=m, second=0, microsecond=0)

            # 赛前提醒时间
            remind_dt = start_dt - timedelta(minutes=ESPORTS_PRE_MATCH_MINUTES)

            # 如果提醒时间已过，不创建
            if remind_dt <= now:
                return False

            trigger = DateTrigger(run_date=remind_dt)
            scheduler_engine.scheduler.add_job(
                func=self._push_pre_match_notification,
                trigger=trigger,
                args=[match_type, match_id, match_info['teams_desc'],
                      match_info['league'], match_info['start_time']],
                id=job_id,
                replace_existing=True,
                misfire_grace_time=300,  # 5分钟容错
            )
            logger.info(f'[赛事监控] 创建赛前提醒: {job_id} ({match_info["teams_desc"]}, {remind_dt.strftime("%H:%M")})')
            return True
        except (ValueError, TypeError) as e:
            logger.warning(f'[赛事监控] 创建赛前提醒失败 {job_id}: {e}')
            return False
        except Exception as e:
            logger.error(f'[赛事监控] 创建赛前提醒失败 {job_id}: {e}')
            return False

    def _push_pre_match_notification(self, match_type, match_id, teams_desc, league, start_time):
        """推送赛前提醒"""
        with self.app.app_context():
            try:
                from app.services.notification import NotificationService
                from app.config.notification_config import CHANNEL_NBA, CHANNEL_LOL

                channel = CHANNEL_NBA if match_type == 'nba' else CHANNEL_LOL
                emoji = '🏀' if match_type == 'nba' else '🎮'
                league_prefix = f'[{league}] ' if match_type == 'lol' else ''

                msg = f"⏰ {emoji} {league_prefix}{teams_desc} | 比赛将于 {start_time} 开始"
                NotificationService.send_slack(msg, channel)
                logger.info(f'[赛事监控] 赛前提醒已发送: {teams_desc}')
            except Exception as e:
                logger.error(f'[赛事监控] 赛前提醒失败: {e}')

    def _create_monitor_job(self, match_info):
        """为单场比赛创建 interval job"""
        from app.scheduler.engine import scheduler_engine
        from apscheduler.triggers.interval import IntervalTrigger

        match_type = match_info['match_type']
        match_id = match_info['match_id']
        job_id = f'{self.JOB_PREFIX}{match_type}_{match_id}'
        interval = ESPORTS_NBA_MONITOR_INTERVAL if match_type == 'nba' else ESPORTS_LOL_MONITOR_INTERVAL

        now = datetime.now(_CST)

        # 超时截止时间基于比赛开始时间（而非 job 创建时间）
        deadline = now
        if match_info.get('start_time'):
            try:
                h, m = map(int, match_info['start_time'].split(':'))
                deadline = now.replace(hour=h, minute=m, second=0, microsecond=0)
                if deadline < now:
                    deadline = now
            except (ValueError, TypeError):
                pass
        max_hours = self.NBA_MAX_DURATION_HOURS if match_type == 'nba' else self.LOL_MAX_DURATION_HOURS
        deadline = deadline + timedelta(hours=max_hours)

        try:
            trigger = IntervalTrigger(minutes=interval)
            kwargs = {
                'func': self._poll_match,
                'trigger': trigger,
                'args': [match_type, match_id, match_info['teams_desc'],
                         match_info['league'], deadline],
                'id': job_id,
                'replace_existing': True,
                'misfire_grace_time': None,
            }

            if match_info['status'] == 'in_progress':
                kwargs['next_run_time'] = now
            elif match_info['status'] == 'scheduled' and match_info.get('start_time'):
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

    def _poll_match(self, match_type, match_id, teams_desc, league, deadline):
        """轮询单场比赛并推送（仅在比分变化时推送）"""
        with self.app.app_context():
            from app.scheduler.engine import scheduler_engine
            job_id = f'{self.JOB_PREFIX}{match_type}_{match_id}'

            if datetime.now(_CST) > deadline:
                logger.info(f'[赛事监控] {job_id} 已超过截止时间，移除')
                _clear_score(match_type, match_id)
                try:
                    scheduler_engine.scheduler.remove_job(job_id)
                except Exception:
                    pass
                return

            try:
                from app.services.esports_service import EsportsService
                from app.services.notification import NotificationService
                from app.config.notification_config import CHANNEL_NBA, CHANNEL_LOL

                if match_type == 'nba':
                    self._poll_nba_match(match_id, job_id, EsportsService, NotificationService, CHANNEL_NBA, scheduler_engine)
                else:
                    self._poll_lol_match(match_id, job_id, league, EsportsService, NotificationService, CHANNEL_LOL, scheduler_engine)

            except Exception as e:
                logger.error(f'[赛事监控] {job_id} 轮询失败: {e}')

    def _poll_nba_match(self, match_id, job_id, EsportsService, NotificationService, channel, scheduler_engine):
        """轮询 NBA 比赛"""
        scores = EsportsService.get_nba_live_scores()
        if scores is None:
            logger.warning(f'[赛事监控] NBA 比分获取失败')
            return

        game = scores.get(match_id)
        if game is None:
            logger.warning(f'[赛事监控] 未找到比赛 {match_id}')
            return

        home_score = game.get('home_score') or 0
        away_score = game.get('away_score') or 0
        status = game['status']

        # 比赛结束：推送最终比分
        if status == 'completed':
            msg = f"🏆 {game['away']} {away_score}-{home_score} {game['home']} | 全场结束"
            NotificationService.send_slack(msg, channel)
            _clear_score('nba', match_id)
            scheduler_engine.scheduler.remove_job(job_id)
            logger.info(f'[赛事监控] {job_id} 比赛结束，移除')
            return

        # 比赛进行中：仅在比分变化时推送
        if status == 'in_progress':
            if _has_score_changed('nba', match_id, away_score, home_score, status):
                quarter = game.get('quarter', '')
                score_text = f"{game['away']} {away_score}-{home_score} {game['home']}"
                msg = f"🏀 {score_text} | {quarter}" if quarter else f"🏀 {score_text}"
                NotificationService.send_slack(msg, channel)
                _update_score('nba', match_id, away_score, home_score, status)
                logger.info(f'[赛事监控] NBA比分变化: {score_text}')
            else:
                logger.debug(f'[赛事监控] {job_id} 比分未变化，跳过推送')

    def _poll_lol_match(self, match_id, job_id, league, EsportsService, NotificationService, channel, scheduler_engine):
        """轮询 LoL 比赛"""
        scores = EsportsService.get_lol_live_scores()
        if scores is None:
            logger.warning(f'[赛事监控] LoL 比分获取失败')
            return

        match = scores.get(match_id)
        if match is None:
            logger.warning(f'[赛事监控] 未找到比赛 {match_id}')
            return

        score1 = match.get('score1') or 0
        score2 = match.get('score2') or 0
        status = match['status']

        # 比赛结束：推送最终比分
        if status == 'completed':
            msg = f"🏆 [{league}] {match['team1']} {score1}-{score2} {match['team2']} | 比赛结束"
            NotificationService.send_slack(msg, channel)
            _clear_score('lol', match_id)
            scheduler_engine.scheduler.remove_job(job_id)
            logger.info(f'[赛事监控] {job_id} 比赛结束，移除')
            return

        # 比赛进行中：仅在比分变化时推送
        if status == 'in_progress':
            if _has_score_changed('lol', match_id, score1, score2, status):
                msg = f"🎮 [{league}] {match['team1']} {score1}-{score2} {match['team2']} | 进行中"
                NotificationService.send_slack(msg, channel)
                _update_score('lol', match_id, score1, score2, status)
                logger.info(f'[赛事监控] LoL比分变化: {match["team1"]} {score1}-{score2} {match["team2"]}')
            else:
                logger.debug(f'[赛事监控] {job_id} 比分未变化，跳过推送')

    def _cleanup_monitors(self):
        """清理所有赛事监控 job"""
        from app.scheduler.engine import scheduler_engine
        jobs_to_remove = [job for job in scheduler_engine.scheduler.get_jobs()
                          if job.id.startswith(self.JOB_PREFIX) or job.id.startswith(self.PRE_MATCH_PREFIX)]
        removed = 0
        for job in jobs_to_remove:
            job.remove()
            removed += 1
        if removed:
            logger.info(f'[赛事监控] 清理 {removed} 个旧任务')

        # 清理比分状态
        with _score_state_lock:
            _score_state.clear()
