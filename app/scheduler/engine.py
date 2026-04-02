"""APScheduler 调度引擎"""
import atexit
import logging
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)


class SchedulerEngine:
    def __init__(self):
        self.scheduler = BackgroundScheduler(daemon=True)
        self.app = None

    def init_app(self, app):
        self.app = app
        from app.strategies.registry import registry
        from app.scheduler.event_bus import event_bus

        registered = []
        for strategy in registry.active:
            if not strategy.schedule:
                continue

            try:
                if strategy.schedule.startswith('interval_minutes:'):
                    from apscheduler.triggers.interval import IntervalTrigger as StrategyInterval
                    minutes = int(strategy.schedule.split(':')[1])
                    trigger = StrategyInterval(minutes=minutes)
                    schedule_desc = f'every {minutes}min'
                else:
                    trigger = CronTrigger.from_crontab(strategy.schedule)
                    schedule_desc = strategy.schedule

                self.scheduler.add_job(
                    self._run_strategy,
                    trigger=trigger,
                    args=[strategy.name],
                    id=f'strategy_{strategy.name}',
                    replace_existing=True,
                    coalesce=True,
                    misfire_grace_time=30,
                )
                registered.append(f'{strategy.name}({schedule_desc})')
            except Exception as e:
                logger.error(f'[调度器] 注册 {strategy.name} 失败: {e}')

        from apscheduler.triggers.interval import IntervalTrigger
        from app.config.news_config import NEWS_INTERVAL_MINUTES

        self.scheduler.add_job(
            self._poll_news,
            trigger=IntervalTrigger(minutes=NEWS_INTERVAL_MINUTES),
            id='news_poll',
            replace_existing=True,
            next_run_time=datetime.now(),
        )
        registered.append(f'news_poll(every {NEWS_INTERVAL_MINUTES}min)')

        # NBA 晚间调度（18:00 北京时间，覆盖当晚比赛）
        self.scheduler.add_job(
            self._setup_nba_evening_monitors,
            trigger=CronTrigger(hour=18, minute=0),
            id='nba_evening_monitors',
            replace_existing=True,
            misfire_grace_time=300,
        )
        registered.append('nba_evening_monitors(18:00)')

        self.scheduler.start()
        atexit.register(self.shutdown)
        logger.info(f'[调度器] 启动完成，{len(registered)} 个任务: {", ".join(registered)}')
        self._check_daily_push_catchup(app)
        self._recover_esports_monitors(app)

    def _check_daily_push_catchup(self, app):
        """检查是否需要补发每日推送（含周末 extras）"""
        from datetime import date, time

        now = datetime.now()
        today = date.today()

        if now.time() < time(8, 30):
            return

        from app.services.notification import NotificationService
        if NotificationService.has_daily_push(today):
            logger.info('[调度器] 今日已推送，跳过补发')
            return

        from apscheduler.triggers.date import DateTrigger
        run_time = datetime.now() + timedelta(seconds=30)

        self.scheduler.add_job(
            self._run_daily_push_catchup,
            trigger=DateTrigger(run_date=run_time),
            id='daily_push_catchup',
            replace_existing=True,
        )
        logger.info('[调度器] 今日未推送，将在30秒后补发')

    def _run_daily_push_catchup(self):
        if not self.app:
            return
        with self.app.app_context():
            try:
                from datetime import date
                from app.services.notification import NotificationService
                is_weekend = date.today().weekday() >= 5
                if is_weekend:
                    results = NotificationService.push_daily_extras()
                    label = '周末'
                else:
                    results = NotificationService.push_daily_report()
                    label = '每日'
                if results.get('slack'):
                    logger.info(f'[调度器] {label}推送补发成功')
                    self._setup_esports_monitors_safe()
                else:
                    logger.warning(f'[调度器] {label}推送补发失败或未配置')
            except Exception as e:
                logger.error(f'[调度器] 推送补发失败: {e}')

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

    def _setup_nba_evening_monitors(self):
        """晚间 NBA 监控调度（只清理重建 NBA job，保留 LoL）"""
        if not self.app:
            return
        with self.app.app_context():
            try:
                from app.services.esports_monitor_service import EsportsMonitorService
                EsportsMonitorService(self.app).setup_match_monitors(match_type='nba')
            except Exception as e:
                logger.error(f'[调度器] NBA晚间监控创建失败: {e}')

    def _run_strategy(self, strategy_name: str):
        """在 app context 内执行策略扫描"""
        from app.strategies.registry import registry
        from app.scheduler.event_bus import event_bus

        if not self.app:
            return
        with self.app.app_context():
            strategy = registry.get(strategy_name)
            if not strategy:
                return
            try:
                signals = strategy.scan()
                for signal in signals:
                    event_bus.publish(signal)
                if signals:
                    logger.info(f'[调度器] {strategy_name} 产出 {len(signals)} 个信号')
            except Exception as e:
                logger.error(f'[调度器] {strategy_name} 执行失败: {e}')

    def _poll_news(self):
        if not self.app:
            return
        with self.app.app_context():
            try:
                from app.services.news_service import NewsService
                items, count = NewsService.poll_news()
                if count:
                    logger.info(f'[调度器] 新闻轮询完成，新增 {count} 条')
            except Exception as e:
                logger.error(f'[调度器] 新闻轮询失败: {e}')

    def shutdown(self):
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)


scheduler_engine = SchedulerEngine()
