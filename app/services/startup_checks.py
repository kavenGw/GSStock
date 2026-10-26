"""服务进程内部的启动验证，不执行业务任务或发送通知。"""
from datetime import date
import os

from startup import report


def validate_modules(app):
    from sqlalchemy import inspect, text
    from app import db
    from app.services.market_status import market_status_service, SUPPORTED_MARKETS
    from app.llm.router import llm_router
    from app.services.notification import NotificationService
    from app.scheduler.event_bus import event_bus

    with app.app_context():
        for bind, engine in db.engines.items():
            name = f'database:{bind or "stock"}'
            report(name, 'WAIT')
            with engine.connect() as connection:
                connection.execute(text('SELECT 1'))
                inspector = inspect(connection)
                for table in db.metadatas[bind].sorted_tables:
                    actual = {column['name'] for column in inspector.get_columns(table.name)}
                    missing = set(table.columns.keys()) - actual
                    if missing:
                        raise RuntimeError(f'{name}.{table.name} 缺少字段: {sorted(missing)}')
            report(name)

    report('市场缓存', 'WAIT')
    if market_status_service._cache_date != date.today():
        raise RuntimeError('市场缓存未初始化')
    for market in SUPPORTED_MARKETS:
        state = market_status_service._market_status.get(market, {})
        required = {'is_trading_day', 'is_closed', 'last_trading_date', 'market_date'}
        if required - state.keys():
            raise RuntimeError(f'市场缓存不完整: {market}')
        if any(not isinstance(state[key], date) for key in ('last_trading_date', 'market_date')):
            raise RuntimeError(f'市场缓存日期无效: {market}')
        report(f'market:{market}')

    report('LLM 客户端', 'WAIT')
    llm_router.init_providers()
    report('LLM 客户端', 'PASS' if llm_router.is_available else 'SKIP',
           '仅验证本地初始化，不验证远端凭据')
    if NotificationService.dispatch_signal not in event_bus._handlers:
        raise RuntimeError('通知处理器未订阅')
    report('通知', 'PASS' if NotificationService.get_status()['slack'] else 'SKIP',
           '仅检查配置与事件订阅，不发送消息')
    from app.config.data_sources import get_data_source_status
    for name, state in get_data_source_status().items():
        report(f'data-source:{name}', 'PASS' if state['configured'] else 'SKIP', '配置检查')
    for name in app.blueprints:
        report(f'blueprint:{name}')


def validate_scheduler(engine):
    from app.strategies.registry import registry
    expected = {'news_poll', 'esports_morning_monitors',
                'nba_evening_monitors', 'esports_tomorrow_monitors'}
    expected.update(f'strategy_{strategy.name}' for strategy in registry.active if strategy.schedule)
    missing = expected - {job.id for job in engine.scheduler.get_jobs()}
    if not engine.scheduler.running or missing:
        raise RuntimeError(f'调度器未就绪，缺少任务: {sorted(missing)}')
    for name in sorted(expected):
        report(f'job:{name}')


def register_readiness(app):
    from flask import abort, request

    @app.get('/_startup/ready')
    def startup_ready():
        if request.remote_addr not in ('127.0.0.1', '::1'):
            abort(404)
        return {'ready': True, 'token': os.environ.get('GS_STARTUP_TOKEN')}
