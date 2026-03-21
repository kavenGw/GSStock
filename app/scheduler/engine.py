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

        self.scheduler.start()
        atexit.register(self.shutdown)
        logger.info(f'[调度器] 启动完成，{len(registered)} 个任务: {", ".join(registered)}')
        self._check_daily_push_catchup(app)

    def _check_daily_push_catchup(self, app):
        """检查是否需要补发每日推送"""
        from datetime import date, time

        now = datetime.now()
        today = date.today()

        if today.weekday() >= 5:
            return
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
                from app.services.notification import NotificationService
                results = NotificationService.push_daily_report()
                if results.get('slack'):
                    logger.info('[调度器] 每日推送补发成功')
                else:
                    logger.warning('[调度器] 每日推送补发失败或未配置')
            except Exception as e:
                logger.error(f'[调度器] 每日推送补发失败: {e}')

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
