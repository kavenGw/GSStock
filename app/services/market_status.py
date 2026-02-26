"""市场状态服务 — 启动时缓存各市场今日开市状态"""
import logging
from datetime import date
from typing import Optional

from app.services.trading_calendar import TradingCalendarService
from app.services.market_session import SmartCacheStrategy

logger = logging.getLogger(__name__)

SUPPORTED_MARKETS = ['A', 'US', 'HK', 'KR', 'TW', 'JP']


class MarketStatusService:
    """市场状态服务（单例），启动时初始化，当日有效"""
    _instance = None
    _market_status: dict = {}
    _cache_date: Optional[date] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def initialize(self):
        """启动时调用，查询各市场今日状态"""
        today = date.today()
        if self._cache_date == today:
            return

        self._market_status = {}
        for market in SUPPORTED_MARKETS:
            market_now = TradingCalendarService.get_market_now(market)
            market_today = market_now.date()
            is_trading = TradingCalendarService.is_trading_day(market, market_today)
            is_closed = TradingCalendarService.is_after_close(market, market_now) if is_trading else False
            last_trading = TradingCalendarService.get_last_trading_day(market, market_today)

            self._market_status[market] = {
                'is_trading_day': is_trading,
                'is_closed': is_closed,
                'last_trading_date': last_trading,
                'market_date': market_today,
            }
            logger.info(f"[市场状态] {market}: 交易日={is_trading}, 已收盘={is_closed}, 上一交易日={last_trading}")

        self._cache_date = today
        logger.info(f"[市场状态] 初始化完成，缓存日期={today}")

    def _ensure_initialized(self):
        """确保已初始化且未跨天"""
        if self._cache_date != date.today():
            self.initialize()

    def get_price_date(self, market: str) -> date:
        """返回应显示的价格日期（最近收盘价日期）"""
        self._ensure_initialized()
        status = self._market_status.get(market)
        if not status:
            return SmartCacheStrategy.get_effective_cache_date(market)

        if status['is_trading_day'] and status['is_closed']:
            return status['market_date']
        return status['last_trading_date']

    def should_use_realtime(self, market: str) -> bool:
        """是否应获取实时价格（盯盘助手用）"""
        self._ensure_initialized()
        status = self._market_status.get(market, {})
        return status.get('is_trading_day', False) and not status.get('is_closed', True)

    def get_status(self, market: str) -> dict:
        """获取市场完整状态"""
        self._ensure_initialized()
        return self._market_status.get(market, {})

    def get_all_status(self) -> dict:
        """获取所有市场状态"""
        self._ensure_initialized()
        return dict(self._market_status)


market_status_service = MarketStatusService()
