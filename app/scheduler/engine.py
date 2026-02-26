"""APScheduler 调度引擎"""
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)


class SchedulerEngine:
    def __init__(self):
        self.scheduler = BackgroundScheduler(daemon=True)
        self.app = None

    def init_app(self, app):
        self.app = app
        from app.strategies.registry import registry
        from app.scheduler.event_bus import event_bus

        from app.config.watch_config import WATCH_INTERVAL_MINUTES
        from app.config.news_config import NEWS_INTERVAL_MINUTES

        for strategy in registry.active:
            if strategy.name == 'watch_assistant':
                trigger = IntervalTrigger(minutes=WATCH_INTERVAL_MINUTES)
                schedule_desc = f'every {WATCH_INTERVAL_MINUTES}min'
            elif strategy.name == 'news_monitor':
                trigger = IntervalTrigger(minutes=NEWS_INTERVAL_MINUTES)
                schedule_desc = f'every {NEWS_INTERVAL_MINUTES}min'
            elif not strategy.schedule:
                continue
            else:
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
                logger.info(f'[调度器] 注册 {strategy.name}: {schedule_desc}')
            except Exception as e:
                logger.error(f'[调度器] 注册 {strategy.name} 失败: {e}')

        self.scheduler.start()
        logger.info(f'[调度器] 启动完成，{len(self.scheduler.get_jobs())} 个任务')

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

    def shutdown(self):
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
