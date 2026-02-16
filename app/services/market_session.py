"""交易时段与智能TTL服务

根据不同市场的交易状态，提供智能的缓存策略：
- 交易时段内: 短TTL (30分钟)
- 收盘后: 长TTL (次日开盘前有效)
- 非交易日: 无限TTL (下个交易日开盘前有效)
"""
import logging
from datetime import date, datetime, timedelta
from typing import Optional

from app.services.trading_calendar import TradingCalendarService
from app.utils.market_identifier import MarketIdentifier

logger = logging.getLogger(__name__)


# TTL 常量
TTL_TRADING = timedelta(minutes=30)    # 交易时段内 TTL
TTL_INFINITE = timedelta(days=365)     # 表示"无限"的大TTL


class SmartCacheStrategy:
    """智能缓存策略"""

    @classmethod
    def get_market_for_code(cls, stock_code: str) -> str:
        """根据股票代码获取市场类型"""
        market = MarketIdentifier.identify(stock_code)
        if market:
            return market
        # 期货代码识别
        if stock_code.endswith('.CMX') or stock_code.startswith('GC=') or stock_code.startswith('SI='):
            return 'COMEX'
        return 'US'  # 默认美股

    @classmethod
    def get_ttl(cls, stock_code: str, cache_type: str = 'price') -> timedelta:
        """获取股票的缓存TTL

        根据市场状态返回合适的TTL：
        - 交易中: 30分钟
        - 已收盘: 次日开盘前
        - 非交易日: 下个交易日开盘前

        Args:
            stock_code: 股票代码
            cache_type: 缓存类型

        Returns:
            TTL时长
        """
        market = cls.get_market_for_code(stock_code)
        market_now = TradingCalendarService.get_market_now(market)
        today = market_now.date()

        # 非交易日 - 返回到下个交易日开盘的时间
        if not TradingCalendarService.is_trading_day(market, today):
            next_trading = TradingCalendarService.get_next_trading_day(market, today)
            open_time, _ = TradingCalendarService.get_market_hours(market, next_trading)
            if open_time:
                next_open = datetime.combine(next_trading, open_time)
                tz = TradingCalendarService._get_timezone(market)
                next_open = tz.localize(next_open)
                ttl = next_open - market_now
                if ttl.total_seconds() > 0:
                    return ttl
            return TTL_INFINITE

        # 交易日
        if TradingCalendarService.is_market_open(market, market_now):
            # 交易中 - 短TTL
            return TTL_TRADING

        if TradingCalendarService.is_after_close(market, market_now):
            # 已收盘 - 到次日开盘
            next_trading = TradingCalendarService.get_next_trading_day(market, today)
            open_time, _ = TradingCalendarService.get_market_hours(market, next_trading)
            if open_time:
                next_open = datetime.combine(next_trading, open_time)
                tz = TradingCalendarService._get_timezone(market)
                next_open = tz.localize(next_open)
                ttl = next_open - market_now
                if ttl.total_seconds() > 0:
                    return ttl
            return TTL_INFINITE

        # 开盘前 - 到开盘时间
        open_time, _ = TradingCalendarService.get_market_hours(market, today)
        if open_time:
            today_open = datetime.combine(today, open_time)
            tz = TradingCalendarService._get_timezone(market)
            today_open = tz.localize(today_open)
            ttl = today_open - market_now
            if ttl.total_seconds() > 0:
                return ttl

        return TTL_TRADING

    @classmethod
    def is_cache_valid(cls, stock_code: str, last_fetch_time: datetime,
                       cache_type: str = 'price') -> bool:
        """检查缓存是否仍然有效

        Args:
            stock_code: 股票代码
            last_fetch_time: 最后获取时间
            cache_type: 缓存类型

        Returns:
            True 如果缓存有效
        """
        if last_fetch_time is None:
            return False

        market = cls.get_market_for_code(stock_code)
        market_now = TradingCalendarService.get_market_now(market)

        # 确保 last_fetch_time 有时区
        if last_fetch_time.tzinfo is None:
            tz = TradingCalendarService._get_timezone(market)
            last_fetch_time = tz.localize(last_fetch_time)

        # 获取该时间点的TTL
        cache_age = market_now - last_fetch_time
        ttl = cls.get_ttl(stock_code, cache_type)

        return cache_age < ttl

    @classmethod
    def is_data_complete(cls, stock_code: str, cache_date: date) -> bool:
        """判断指定日期的数据是否完整

        数据完整的条件：
        1. 该日期是交易日
        2. 当前时间已过该日收盘时间

        Args:
            stock_code: 股票代码
            cache_date: 数据日期

        Returns:
            True 如果数据已完整（收盘后的完整数据）
        """
        market = cls.get_market_for_code(stock_code)
        market_now = TradingCalendarService.get_market_now(market)
        today = market_now.date()

        # 未来日期，数据不可能完整
        if cache_date > today:
            return False

        # 非交易日，没有数据，视为"完整"
        if not TradingCalendarService.is_trading_day(market, cache_date):
            return True

        # 历史交易日（今天之前），数据完整
        if cache_date < today:
            return True

        # 今天的交易日，检查是否已收盘
        return TradingCalendarService.is_after_close(market, market_now)

    @classmethod
    def should_refresh(cls, stock_code: str, last_fetch_time: datetime = None,
                       cache_date: date = None) -> bool:
        """判断是否需要刷新数据

        综合考虑：
        1. 数据是否完整（收盘后的完整数据不需要刷新）
        2. 缓存是否过期（根据智能TTL判断）
        3. 市场是否在交易（非交易时间不需要刷新）

        Args:
            stock_code: 股票代码
            last_fetch_time: 最后获取时间
            cache_date: 缓存数据日期

        Returns:
            True 如果需要刷新
        """
        market = cls.get_market_for_code(stock_code)
        market_now = TradingCalendarService.get_market_now(market)
        today = market_now.date()

        # 如果请求的是历史日期的数据，且数据已完整，不需要刷新
        if cache_date and cache_date < today:
            if cls.is_data_complete(stock_code, cache_date):
                if last_fetch_time is not None:
                    return False

        # 非交易日不需要刷新
        should_fetch, reason = TradingCalendarService.should_fetch_data(market)
        if not should_fetch:
            if last_fetch_time is not None:
                logger.debug(f"[市场时段] {stock_code} 不需要刷新: {reason}")
                return False

        # 没有缓存，需要刷新
        if last_fetch_time is None:
            return True

        # 检查缓存是否过期
        return not cls.is_cache_valid(stock_code, last_fetch_time)

    @classmethod
    def get_effective_cache_date(cls, stock_code: str) -> date:
        """获取有效的缓存日期

        根据市场状态返回应该使用的缓存日期：
        - 交易日开盘后: 今天
        - 交易日开盘前: 前一交易日
        - 非交易日: 前一交易日

        Args:
            stock_code: 股票代码

        Returns:
            有效的缓存日期
        """
        market = cls.get_market_for_code(stock_code)
        market_now = TradingCalendarService.get_market_now(market)
        today = market_now.date()

        # 交易日
        if TradingCalendarService.is_trading_day(market, today):
            # 开盘后用今天
            if not TradingCalendarService.is_before_open(market, market_now):
                return today
            # 开盘前用前一交易日
            return TradingCalendarService.get_last_trading_day(market, today)

        # 非交易日用前一交易日
        return TradingCalendarService.get_last_trading_day(market, today)


class BatchCacheStrategy:
    """批量缓存策略"""

    @classmethod
    def filter_need_refresh(cls, stock_codes: list, fetch_times: dict,
                            cache_type: str = 'price', cache_date: date = None) -> list:
        """过滤出需要刷新的股票列表

        Args:
            stock_codes: 股票代码列表
            fetch_times: {stock_code: last_fetch_time} 字典
            cache_type: 缓存类型
            cache_date: 缓存日期

        Returns:
            需要刷新的股票代码列表
        """
        need_refresh = []
        for code in stock_codes:
            last_fetch = fetch_times.get(code)
            if SmartCacheStrategy.should_refresh(code, last_fetch, cache_date):
                need_refresh.append(code)
        return need_refresh

    @classmethod
    def group_by_market(cls, stock_codes: list) -> dict:
        """按市场分组股票代码

        Args:
            stock_codes: 股票代码列表

        Returns:
            {market: [codes]} 字典
        """
        groups = {}
        for code in stock_codes:
            market = SmartCacheStrategy.get_market_for_code(code)
            if market not in groups:
                groups[market] = []
            groups[market].append(code)
        return groups

    @classmethod
    def filter_by_trading_status(cls, stock_codes: list) -> dict:
        """按交易状态过滤股票

        返回各市场的股票及其获取状态

        Args:
            stock_codes: 股票代码列表

        Returns:
            {
                'should_fetch': [codes],      # 应该获取新数据的
                'use_cache': [codes],         # 应该使用缓存的
                'reasons': {code: reason}     # 原因说明
            }
        """
        should_fetch = []
        use_cache = []
        reasons = {}

        groups = cls.group_by_market(stock_codes)

        for market, codes in groups.items():
            fetch, reason = TradingCalendarService.should_fetch_data(market)
            if fetch:
                should_fetch.extend(codes)
                for code in codes:
                    reasons[code] = 'trading'
            else:
                use_cache.extend(codes)
                for code in codes:
                    reasons[code] = reason

        return {
            'should_fetch': should_fetch,
            'use_cache': use_cache,
            'reasons': reasons
        }
