"""走势看板数据预加载服务

启动时在后台线程预加载各分类的走势数据，避免冷启动延迟。
交易时段（9:00-16:00）每5分钟自动刷新。
"""
import logging
import threading
from datetime import datetime, time

from app.config.stock_codes import CATEGORY_NAMES

logger = logging.getLogger(__name__)

PRELOAD_INTERVAL = 300  # 5分钟
TRADING_START = time(9, 0)
TRADING_END = time(16, 0)

# 排除不需要预加载的分类
SKIP_CATEGORIES = {'custom', 'positions'}


def start_background_preload(app):
    """启动后台预加载线程"""
    def _run():
        with app.app_context():
            _do_preload()
            _schedule_refresh(app)

    t = threading.Thread(target=_run, daemon=True, name='heavy-metals-preload')
    t.start()
    logger.info('[预加载] 走势看板后台预加载线程已启动')


def _do_preload():
    """遍历分类预加载30天走势数据"""
    from app.services.futures import FuturesService

    categories = [k for k in CATEGORY_NAMES if k not in SKIP_CATEGORIES]
    logger.info(f'[预加载] 开始预加载走势数据: {len(categories)} 个分类')

    for category in categories:
        try:
            FuturesService.get_category_trend_data(category, 30, False)
            logger.debug(f'[预加载] {category} 完成')
        except Exception as e:
            logger.warning(f'[预加载] {category} 失败: {e}')

    logger.info('[预加载] 走势看板数据预加载完成')


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
                logger.warning(f'[预加载] 定时刷新失败: {e}')
