"""缓存验证器

实现8小时缓存有效期验证逻辑，用于控制数据获取频率。
"""
import logging
from datetime import datetime, date, timedelta
from app.models.unified_cache import UnifiedStockCache

logger = logging.getLogger(__name__)

# 缓存有效期：8小时
CACHE_TTL_HOURS = 8


class CacheValidator:
    """缓存有效性验证器"""

    @staticmethod
    def is_cache_valid(stock_code: str, cache_type: str, cache_date: date = None) -> bool:
        """检查缓存是否在8小时有效期内

        Args:
            stock_code: 股票代码
            cache_type: 缓存类型
            cache_date: 缓存日期，默认为当天

        Returns:
            True 如果缓存有效，False 如果缓存过期或不存在
        """
        if cache_date is None:
            cache_date = date.today()

        cache = UnifiedStockCache.query.filter_by(
            stock_code=stock_code,
            cache_type=cache_type,
            cache_date=cache_date
        ).first()

        if not cache or not cache.last_fetch_time:
            return False

        age = datetime.now() - cache.last_fetch_time
        return age < timedelta(hours=CACHE_TTL_HOURS)

    @staticmethod
    def get_cache_age(stock_code: str, cache_type: str, cache_date: date = None) -> timedelta | None:
        """获取缓存年龄

        Args:
            stock_code: 股票代码
            cache_type: 缓存类型
            cache_date: 缓存日期，默认为当天

        Returns:
            缓存年龄（timedelta），如果缓存不存在则返回 None
        """
        if cache_date is None:
            cache_date = date.today()

        cache = UnifiedStockCache.query.filter_by(
            stock_code=stock_code,
            cache_type=cache_type,
            cache_date=cache_date
        ).first()

        if not cache or not cache.last_fetch_time:
            return None

        return datetime.now() - cache.last_fetch_time

    @staticmethod
    def should_refresh(stock_codes: list, cache_type: str, force: bool = False,
                       cache_date: date = None) -> list:
        """返回需要刷新的股票列表

        Args:
            stock_codes: 股票代码列表
            cache_type: 缓存类型
            force: 是否强制刷新（忽略缓存）
            cache_date: 缓存日期，默认为当天

        Returns:
            需要刷新的股票代码列表
        """
        if force:
            logger.debug(f"强制刷新 {len(stock_codes)} 只股票")
            return list(stock_codes)

        if cache_date is None:
            cache_date = date.today()

        # 获取所有缓存记录
        fetch_times = UnifiedStockCache.get_last_fetch_times(
            stock_codes, cache_type, cache_date
        )

        now = datetime.now()
        ttl = timedelta(hours=CACHE_TTL_HOURS)
        need_refresh = []

        for code in stock_codes:
            last_fetch = fetch_times.get(code)
            if last_fetch is None or (now - last_fetch) >= ttl:
                need_refresh.append(code)

        logger.debug(f"缓存检查: 共 {len(stock_codes)} 只, 需刷新 {len(need_refresh)} 只")
        return need_refresh

    @staticmethod
    def get_valid_cache_codes(stock_codes: list, cache_type: str,
                              cache_date: date = None) -> list:
        """返回缓存仍然有效的股票列表

        Args:
            stock_codes: 股票代码列表
            cache_type: 缓存类型
            cache_date: 缓存日期，默认为当天

        Returns:
            缓存有效的股票代码列表
        """
        if cache_date is None:
            cache_date = date.today()

        fetch_times = UnifiedStockCache.get_last_fetch_times(
            stock_codes, cache_type, cache_date
        )

        now = datetime.now()
        ttl = timedelta(hours=CACHE_TTL_HOURS)
        valid_codes = []

        for code in stock_codes:
            last_fetch = fetch_times.get(code)
            if last_fetch and (now - last_fetch) < ttl:
                valid_codes.append(code)

        return valid_codes

    @staticmethod
    def get_cache_status(stock_codes: list, cache_type: str,
                         cache_date: date = None) -> dict:
        """获取缓存状态信息

        Args:
            stock_codes: 股票代码列表
            cache_type: 缓存类型
            cache_date: 缓存日期，默认为当天

        Returns:
            {
                'total': int,
                'valid': int,
                'expired': int,
                'missing': int,
                'details': {code: {'status': str, 'age_minutes': int | None}}
            }
        """
        if cache_date is None:
            cache_date = date.today()

        fetch_times = UnifiedStockCache.get_last_fetch_times(
            stock_codes, cache_type, cache_date
        )

        now = datetime.now()
        ttl = timedelta(hours=CACHE_TTL_HOURS)

        valid = 0
        expired = 0
        missing = 0
        details = {}

        for code in stock_codes:
            last_fetch = fetch_times.get(code)
            if last_fetch is None:
                missing += 1
                details[code] = {'status': 'missing', 'age_minutes': None}
            elif (now - last_fetch) < ttl:
                valid += 1
                age_minutes = int((now - last_fetch).total_seconds() / 60)
                details[code] = {'status': 'valid', 'age_minutes': age_minutes}
            else:
                expired += 1
                age_minutes = int((now - last_fetch).total_seconds() / 60)
                details[code] = {'status': 'expired', 'age_minutes': age_minutes}

        return {
            'total': len(stock_codes),
            'valid': valid,
            'expired': expired,
            'missing': missing,
            'details': details,
        }
