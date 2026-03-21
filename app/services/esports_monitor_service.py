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

                else:
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
