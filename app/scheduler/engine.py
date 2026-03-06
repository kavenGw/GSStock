"""APScheduler 调度引擎"""
import logging
from datetime import datetime
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
            trigger = CronTrigger.from_crontab(strategy.schedule)
            schedule_desc = strategy.schedule

            try:
                self.scheduler.add_job(
                    self._run_strategy,
                    trigger=trigger,
                    args=[strategy.name],
                    id=f'strategy_{strategy.name}',
                    replace_existing=True,
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
        logger.info(f'[调度器] 启动完成，{len(registered)} 个任务: {", ".join(registered)}')

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
