"""交易日历服务

使用 exchange-calendars 库提供精确的交易日历判断，支持：
- A股 (上海/深圳)
- 美股 (纽约)
- 港股 (香港)
- 韩股 (首尔)
- 台股 (台湾)
- 期货 (芝加哥商品交易所)
"""
import logging
from datetime import date, datetime, time, timedelta
from typing import Optional, Tuple
from functools import lru_cache

import exchange_calendars as xcals
import pytz

logger = logging.getLogger(__name__)


class TradingCalendarService:
    """交易日历服务"""

    # 市场与 exchange-calendars 名称映射
    MARKET_CALENDARS = {
        'A': 'XSHG',    # 上海证券交易所（A股统一用上海日历）
        'US': 'XNYS',   # 纽约证券交易所
        'HK': 'XHKG',   # 香港交易所
        'KR': 'XKRX',   # 韩国交易所
        'TW': 'XTAI',   # 台湾证券交易所
        'COMEX': 'XCME', # 芝加哥商品交易所
    }

    # 市场时区
    MARKET_TIMEZONES = {
        'A': 'Asia/Shanghai',
        'US': 'America/New_York',
        'HK': 'Asia/Hong_Kong',
        'KR': 'Asia/Seoul',
        'TW': 'Asia/Taipei',
        'COMEX': 'America/Chicago',
    }

    # 缓存日历实例
    _calendars = {}

    @classmethod
    def _get_calendar(cls, market: str):
        """获取市场对应的日历实例（带缓存）"""
        if market not in cls._calendars:
            calendar_name = cls.MARKET_CALENDARS.get(market)
            if not calendar_name:
                logger.warning(f"[交易日历] 未知市场 {market}，使用纽约交易所日历")
                calendar_name = 'XNYS'
            try:
                cls._calendars[market] = xcals.get_calendar(calendar_name)
            except Exception as e:
                logger.error(f"[交易日历] 获取日历 {calendar_name} 失败: {e}", exc_info=True)
                cls._calendars[market] = xcals.get_calendar('XNYS')
        return cls._calendars[market]

    @classmethod
    def _get_timezone(cls, market: str):
        """获取市场时区"""
        tz_name = cls.MARKET_TIMEZONES.get(market, 'America/New_York')
        return pytz.timezone(tz_name)

    @classmethod
    def get_market_now(cls, market: str) -> datetime:
        """获取市场当前时间"""
        tz = cls._get_timezone(market)
        return datetime.now(tz)

    @classmethod
    def is_trading_day(cls, market: str, dt: date = None) -> bool:
        """判断是否为交易日

        Args:
            market: 市场类型 ('A', 'US', 'HK', 'COMEX')
            dt: 日期，默认为当天

        Returns:
            True 如果是交易日
        """
        if dt is None:
            dt = date.today()

        calendar = cls._get_calendar(market)
        try:
            return calendar.is_session(dt)
        except Exception as e:
            # 如果日期超出日历范围，使用简单判断
            logger.debug(f"[交易日历] 查询失败 {market} {dt}: {e}")
            return dt.weekday() < 5  # 周一到周五

    @classmethod
    def is_weekend(cls, market: str, dt: date = None) -> bool:
        """判断是否为周末（使用市场本地时间）

        Args:
            market: 市场类型
            dt: 日期，默认为市场当前日期

        Returns:
            True 如果是周末
        """
        if dt is None:
            market_now = cls.get_market_now(market)
            dt = market_now.date()
        return dt.weekday() >= 5

    @classmethod
    def get_last_trading_day(cls, market: str, before: date = None) -> date:
        """获取指定日期之前的最后一个交易日

        Args:
            market: 市场类型
            before: 在此日期之前，默认为今天

        Returns:
            最后一个交易日
        """
        if before is None:
            before = date.today()

        calendar = cls._get_calendar(market)
        try:
            # 获取前一个交易日
            prev_session = calendar.previous_session(before)
            return prev_session.date() if hasattr(prev_session, 'date') else prev_session
        except Exception as e:
            logger.debug(f"[交易日历] 获取前一交易日失败 {market} {before}: {e}")
            # 回退方案：简单往前找
            check_date = before - timedelta(days=1)
            for _ in range(10):
                if check_date.weekday() < 5:
                    return check_date
                check_date -= timedelta(days=1)
            return before - timedelta(days=1)

    @classmethod
    def get_next_trading_day(cls, market: str, after: date = None) -> date:
        """获取指定日期之后的下一个交易日

        Args:
            market: 市场类型
            after: 在此日期之后，默认为今天

        Returns:
            下一个交易日
        """
        if after is None:
            after = date.today()

        calendar = cls._get_calendar(market)
        try:
            next_session = calendar.next_session(after)
            return next_session.date() if hasattr(next_session, 'date') else next_session
        except Exception as e:
            logger.debug(f"[交易日历] 获取下一交易日失败 {market} {after}: {e}")
            check_date = after + timedelta(days=1)
            for _ in range(10):
                if check_date.weekday() < 5:
                    return check_date
                check_date += timedelta(days=1)
            return after + timedelta(days=1)

    @classmethod
    def get_market_hours(cls, market: str, dt: date = None) -> Tuple[Optional[time], Optional[time]]:
        """获取市场交易时间（本地时间）

        Args:
            market: 市场类型
            dt: 日期，默认为今天

        Returns:
            (开盘时间, 收盘时间)，非交易日返回 (None, None)
        """
        if dt is None:
            dt = date.today()

        # 预设各市场的标准交易时间
        MARKET_HOURS = {
            'A': (time(9, 30), time(15, 0)),
            'US': (time(9, 30), time(16, 0)),
            'HK': (time(9, 30), time(16, 0)),
            'KR': (time(9, 0), time(15, 30)),
            'TW': (time(9, 0), time(13, 30)),
            'COMEX': (time(8, 30), time(13, 30)),  # 电子盘时间更长，这里用核心时段
        }

        if not cls.is_trading_day(market, dt):
            return (None, None)

        return MARKET_HOURS.get(market, (time(9, 30), time(16, 0)))

    @classmethod
    def is_market_open(cls, market: str, dt: datetime = None) -> bool:
        """判断市场当前是否在交易时段

        Args:
            market: 市场类型
            dt: 时间，默认为市场当前时间

        Returns:
            True 如果在交易时段内
        """
        if dt is None:
            dt = cls.get_market_now(market)
        elif dt.tzinfo is None:
            tz = cls._get_timezone(market)
            dt = tz.localize(dt)

        # 检查是否是交易日
        if not cls.is_trading_day(market, dt.date()):
            return False

        # 检查是否在交易时间内
        open_time, close_time = cls.get_market_hours(market, dt.date())
        if open_time is None:
            return False

        current_time = dt.time()

        # A股有午休
        if market == 'A':
            morning_session = (time(9, 30) <= current_time <= time(11, 30))
            afternoon_session = (time(13, 0) <= current_time <= time(15, 0))
            return morning_session or afternoon_session

        return open_time <= current_time <= close_time

    @classmethod
    def is_after_close(cls, market: str, dt: datetime = None) -> bool:
        """判断是否已收盘

        Args:
            market: 市场类型
            dt: 时间，默认为市场当前时间

        Returns:
            True 如果今天是交易日且已收盘
        """
        if dt is None:
            dt = cls.get_market_now(market)
        elif dt.tzinfo is None:
            tz = cls._get_timezone(market)
            dt = tz.localize(dt)

        # 非交易日不算"已收盘"
        if not cls.is_trading_day(market, dt.date()):
            return False

        _, close_time = cls.get_market_hours(market, dt.date())
        if close_time is None:
            return False

        return dt.time() > close_time

    @classmethod
    def is_before_open(cls, market: str, dt: datetime = None) -> bool:
        """判断是否未开盘

        Args:
            market: 市场类型
            dt: 时间，默认为市场当前时间

        Returns:
            True 如果今天是交易日但未开盘
        """
        if dt is None:
            dt = cls.get_market_now(market)
        elif dt.tzinfo is None:
            tz = cls._get_timezone(market)
            dt = tz.localize(dt)

        if not cls.is_trading_day(market, dt.date()):
            return False

        open_time, _ = cls.get_market_hours(market, dt.date())
        if open_time is None:
            return False

        return dt.time() < open_time

    @classmethod
    def get_trading_days(cls, market: str, start: date, end: date) -> list:
        """获取日期范围内的所有交易日

        Args:
            market: 市场类型
            start: 开始日期
            end: 结束日期

        Returns:
            交易日列表
        """
        calendar = cls._get_calendar(market)
        try:
            sessions = calendar.sessions_in_range(start, end)
            return [s.date() if hasattr(s, 'date') else s for s in sessions]
        except Exception as e:
            logger.debug(f"[交易日历] 获取交易日范围失败 {market} {start}-{end}: {e}")
            # 回退方案
            result = []
            current = start
            while current <= end:
                if current.weekday() < 5:
                    result.append(current)
                current += timedelta(days=1)
            return result

    @classmethod
    def should_fetch_data(cls, market: str) -> Tuple[bool, str]:
        """判断当前是否应该获取数据

        综合判断：
        - 周末不获取
        - 节假日不获取
        - 开盘前不获取（用昨日数据）

        Args:
            market: 市场类型

        Returns:
            (should_fetch, reason) 元组
        """
        market_now = cls.get_market_now(market)
        today = market_now.date()

        # 周末
        if cls.is_weekend(market, today):
            return (False, 'weekend')

        # 非交易日（节假日）
        if not cls.is_trading_day(market, today):
            return (False, 'holiday')

        # 开盘前
        if cls.is_before_open(market, market_now):
            return (False, 'before_open')

        return (True, 'trading')
