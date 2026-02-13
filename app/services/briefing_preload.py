"""简报数据预加载服务

启动时在后台线程预加载简报所需数据，避免首次打开等待。
交易时段（9:00-16:00）每5分钟自动刷新。
"""
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, time

logger = logging.getLogger(__name__)

PRELOAD_INTERVAL = 300  # 5分钟
TRADING_START = time(9, 0)
TRADING_END = time(16, 0)

_app = None


def start_background_preload(app):
    """启动后台预加载线程"""
    global _app
    _app = app

    def _run():
        with app.app_context():
            _do_preload()
            _schedule_refresh(app)

    t = threading.Thread(target=_run, daemon=True, name='briefing-preload')
    t.start()
    logger.info('[简报预加载] 后台预加载线程已启动')


def _do_preload():
    """分三波预加载简报数据"""
    from app.services.briefing import BriefingService

    logger.info('[简报预加载] 开始预加载简报数据')

    # 第一波：核心数据
    wave1 = {
        '股票价格': lambda: BriefingService.get_stocks_basic_data(False),
        '指数数据': lambda: BriefingService.get_indices_data(False),
        '期货数据': lambda: BriefingService.get_futures_data(False),
    }
    _run_wave('第一波', wave1)

    # 第二波：分析数据（依赖第一波的股票价格）
    wave2 = {
        '技术指标': lambda: BriefingService.get_stocks_technical_data(False),
        'A股板块': lambda: BriefingService.get_cn_sectors_data(False),
        '美股板块': lambda: BriefingService.get_us_sectors_data(False),
        '板块评级': lambda: BriefingService.get_sector_ratings(None, False),
        'ETF溢价': lambda: BriefingService.get_etf_premium_data(False),
    }
    _run_wave('第二波', wave2)

    # 第三波：辅助数据
    wave3 = {
        'PE估值': lambda: BriefingService.get_stocks_pe_data(False),
        '财报日期': lambda: BriefingService.get_stocks_earnings_data(False),
        '财报预警': lambda: BriefingService.get_earnings_alert_data(),
    }
    _run_wave('第三波', wave3)

    logger.info('[简报预加载] 简报数据预加载完成')


def _run_wave(wave_name, tasks):
    """并发执行一波预加载任务，每个线程带 app context"""
    def _task_with_context(fn):
        with _app.app_context():
            return fn()

    with ThreadPoolExecutor(max_workers=len(tasks)) as executor:
        futures = {
            executor.submit(_task_with_context, fn): name
            for name, fn in tasks.items()
        }
        for future in as_completed(futures):
            name = futures[future]
            try:
                future.result()
                logger.debug(f'[简报预加载] {name} 完成')
            except Exception as e:
                logger.warning(f'[简报预加载] {name} 失败: {e}')


def _schedule_refresh(app):
    """交易时段定时刷新"""
    import time as time_mod

    while True:
        time_mod.sleep(PRELOAD_INTERVAL)
        now = datetime.now().time()
        if TRADING_START <= now <= TRADING_END:
            try:
                with app.app_context():
                    _do_preload()
            except Exception as e:
                logger.warning(f'[简报预加载] 定时刷新失败: {e}')
