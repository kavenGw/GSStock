"""财报数据服务

提供统一的财报日期和市盈率数据获取入口。
支持美股/港股（yfinance）和A股（akshare）数据源。
使用24小时缓存有效期（财报数据变化不频繁）。
"""
import logging
import time
from datetime import datetime, date, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

from app.models.unified_cache import UnifiedStockCache
from app.services.circuit_breaker import circuit_breaker
from app.utils.market_identifier import MarketIdentifier

logger = logging.getLogger(__name__)

# 缓存类型
CACHE_TYPE_EARNINGS = 'earnings'

# 缓存有效期：24小时
EARNINGS_CACHE_TTL_HOURS = 24

# PE阈值
PE_THRESHOLD_LOW = 15       # 低估参考
PE_THRESHOLD_NORMAL = 30    # 正常上限
PE_THRESHOLD_HIGH = 200     # 高估上限

# 重试配置
MAX_RETRIES = 3
RETRY_DELAY = 1.0


class EarningsService:
    """财报数据服务"""

    @staticmethod
    def _is_cache_valid(stock_code: str, cache_date: date = None) -> bool:
        """检查缓存是否在24小时有效期内"""
        if cache_date is None:
            cache_date = date.today()

        cache = UnifiedStockCache.query.filter_by(
            stock_code=stock_code,
            cache_type=CACHE_TYPE_EARNINGS,
            cache_date=cache_date
        ).first()

        if not cache or not cache.last_fetch_time:
            return False

        age = datetime.now() - cache.last_fetch_time
        return age < timedelta(hours=EARNINGS_CACHE_TTL_HOURS)

    @staticmethod
    def _should_refresh(stock_codes: list, force: bool = False, cache_date: date = None) -> list:
        """返回需要刷新的股票列表"""
        if force:
            return list(stock_codes)

        if cache_date is None:
            cache_date = date.today()

        fetch_times = UnifiedStockCache.get_last_fetch_times(
            stock_codes, CACHE_TYPE_EARNINGS, cache_date
        )

        now = datetime.now()
        ttl = timedelta(hours=EARNINGS_CACHE_TTL_HOURS)
        need_refresh = []

        for code in stock_codes:
            last_fetch = fetch_times.get(code)
            if last_fetch is None or (now - last_fetch) >= ttl:
                need_refresh.append(code)

        return need_refresh

    @staticmethod
    def _get_from_cache(stock_code: str, cache_date: date = None) -> dict | None:
        """从缓存获取财报数据"""
        if cache_date is None:
            cache_date = date.today()

        return UnifiedStockCache.get_cached_data(
            stock_code, CACHE_TYPE_EARNINGS, cache_date
        )

    @staticmethod
    def _save_to_cache(stock_code: str, data: dict, cache_date: date = None) -> None:
        """保存财报数据到缓存"""
        if cache_date is None:
            cache_date = date.today()

        UnifiedStockCache.set_cached_data(
            stock_code, CACHE_TYPE_EARNINGS, data, cache_date
        )

    @staticmethod
    def _get_expired_cache(stock_code: str) -> dict | None:
        """获取过期缓存数据作为降级方案"""
        try:
            cache = UnifiedStockCache.query.filter_by(
                stock_code=stock_code,
                cache_type=CACHE_TYPE_EARNINGS
            ).order_by(UnifiedStockCache.last_fetch_time.desc()).first()

            if cache and cache.data_json:
                import json
                logger.info(f"使用过期缓存数据: {stock_code} (earnings)")
                return json.loads(cache.data_json)
        except Exception as e:
            logger.warning(f"获取过期缓存失败 {stock_code}: {e}")
        return None

    @staticmethod
    def _fetch_earnings_yfinance(stock_code: str) -> dict | None:
        """从yfinance获取美股/港股财报数据（接入熔断）"""
        import yfinance as yf

        # 熔断检查
        if not circuit_breaker.is_available('yfinance'):
            logger.info(f'[earnings] yfinance已熔断，{stock_code} 尝试过期缓存')
            return EarningsService._get_expired_cache(stock_code)

        yf_code = MarketIdentifier.to_yfinance(stock_code)
        market = MarketIdentifier.identify(stock_code) or 'US'
        last_error = None

        for attempt in range(MAX_RETRIES):
            try:
                ticker = yf.Ticker(yf_code)

                last_earnings_date = None
                next_earnings_date = None

                try:
                    calendar = ticker.calendar
                    if calendar is not None:
                        if hasattr(calendar, 'get'):
                            earnings_date = calendar.get('Earnings Date')
                            if earnings_date:
                                if isinstance(earnings_date, list) and len(earnings_date) > 0:
                                    next_earnings_date = str(earnings_date[0])[:10]
                        elif hasattr(calendar, 'loc'):
                            if 'Earnings Date' in calendar.index:
                                val = calendar.loc['Earnings Date']
                                if hasattr(val, 'iloc'):
                                    next_earnings_date = str(val.iloc[0])[:10]
                                else:
                                    next_earnings_date = str(val)[:10]
                except Exception as e:
                    logger.debug(f"获取 {stock_code} calendar 失败: {e}")

                try:
                    earnings_dates = ticker.earnings_dates
                    if earnings_dates is not None and len(earnings_dates) > 0:
                        today = date.today()
                        past_dates = []
                        future_dates = []

                        for idx in earnings_dates.index:
                            d = idx.date() if hasattr(idx, 'date') else idx
                            if isinstance(d, date):
                                if d < today:
                                    past_dates.append(d)
                                else:
                                    future_dates.append(d)

                        if past_dates:
                            last_earnings_date = max(past_dates).isoformat()
                        if future_dates and not next_earnings_date:
                            next_earnings_date = min(future_dates).isoformat()
                except Exception as e:
                    logger.debug(f"获取 {stock_code} earnings_dates 失败: {e}")

                pe_ttm = None
                try:
                    info = ticker.info
                    if info:
                        pe_ttm = info.get('trailingPE')
                        if pe_ttm is not None:
                            pe_ttm = round(float(pe_ttm), 2)
                except Exception as e:
                    logger.warning(f"[earnings/pe] {stock_code} yfinance获取PE失败: {e}")

                circuit_breaker.record_success('yfinance')
                return {
                    'last_earnings_date': last_earnings_date,
                    'next_earnings_date': next_earnings_date,
                    'pe_ttm': pe_ttm,
                    'market': market,
                    'fetch_time': datetime.now().isoformat()
                }

            except Exception as e:
                last_error = e
                error_msg = str(e).lower()
                if 'delisted' in error_msg or 'no data found' in error_msg:
                    logger.debug(f"股票 {stock_code} 可能已退市或无数据: {e}")
                    return None

                if attempt < MAX_RETRIES - 1:
                    logger.debug(f"获取 {stock_code} 财报数据失败，第{attempt + 1}次重试: {e}")
                    time.sleep(RETRY_DELAY)

        circuit_breaker.record_failure('yfinance')
        if last_error:
            logger.warning(f"获取 {stock_code} 财报数据重试{MAX_RETRIES}次后失败: {last_error}")
        return None

    @staticmethod
    def _fetch_earnings_akshare(stock_code: str) -> dict | None:
        """从akshare获取A股财报数据（委托unified服务获取PE）"""
        from app.services.unified_stock_data import unified_stock_data_service

        try:
            pe_ttm = None

            if not MarketIdentifier.is_etf(stock_code):
                pe_data = unified_stock_data_service.get_pe_data([stock_code])
                stock_pe = pe_data.get(stock_code)
                if stock_pe:
                    pe_ttm = stock_pe.get('pe_ttm')
                    if pe_ttm is not None:
                        pe_ttm = round(pe_ttm, 2)

            return {
                'last_earnings_date': None,
                'next_earnings_date': None,
                'pe_ttm': pe_ttm,
                'market': 'A',
                'fetch_time': datetime.now().isoformat()
            }

        except Exception as e:
            logger.warning(f"[earnings/pe] {stock_code} 获取A股数据失败: {e}")
            return None

    @staticmethod
    def get_earnings_dates(stock_codes: list, force_refresh: bool = False) -> dict:
        """获取财报日期数据

        Args:
            stock_codes: 股票代码列表
            force_refresh: 是否强制刷新

        Returns:
            {
                'TSLA': {
                    'code': 'TSLA',
                    'name': 'TSLA',
                    'last_earnings_date': '2024-01-24',
                    'next_earnings_date': '2024-04-23',
                    'days_until_next': 5,
                    'is_today': False,
                    'market': 'US'
                }
            }
        """
        if not stock_codes:
            return {}

        today = date.today()
        result = {}

        # 检查哪些需要刷新
        need_refresh = EarningsService._should_refresh(stock_codes, force_refresh, today)

        # 从缓存获取有效数据
        if not force_refresh:
            cached_data = UnifiedStockCache.get_batch_cached_data(
                stock_codes, CACHE_TYPE_EARNINGS, today
            )
            for code, data in cached_data.items():
                if code not in need_refresh:
                    result[code] = EarningsService._format_earnings_result(code, data)

        # 获取需要刷新的数据
        if need_refresh:
            # 按市场分类
            a_share_codes = []
            other_codes = []
            for code in need_refresh:
                market = MarketIdentifier.identify(code)
                if market == 'A':
                    a_share_codes.append(code)
                elif market in ['US', 'HK']:
                    other_codes.append(code)
                else:
                    # 台股、韩股暂不支持，返回空数据
                    result[code] = {
                        'code': code,
                        'name': code,
                        'last_earnings_date': None,
                        'next_earnings_date': None,
                        'days_until_next': None,
                        'is_today': False,
                        'market': market or 'unknown'
                    }

            # 并发获取非A股数据
            if other_codes:
                fetched = EarningsService._fetch_batch_yfinance(other_codes)
                for code, data in fetched.items():
                    EarningsService._save_to_cache(code, data, today)
                    result[code] = EarningsService._format_earnings_result(code, data)

            # 获取A股数据
            for code in a_share_codes:
                data = EarningsService._fetch_earnings_akshare(code)
                if data:
                    EarningsService._save_to_cache(code, data, today)
                    result[code] = EarningsService._format_earnings_result(code, data)
                else:
                    # 尝试降级使用过期缓存
                    expired = EarningsService._get_expired_cache(code)
                    if expired:
                        result[code] = EarningsService._format_earnings_result(code, expired)
                    else:
                        result[code] = {
                            'code': code,
                            'name': code,
                            'last_earnings_date': None,
                            'next_earnings_date': None,
                            'days_until_next': None,
                            'is_today': False,
                            'market': 'A'
                        }

        return result

    @staticmethod
    def _fetch_batch_yfinance(stock_codes: list) -> dict:
        """并发获取美股/港股财报数据"""
        result = {}

        def fetch_single(code: str) -> tuple:
            data = EarningsService._fetch_earnings_yfinance(code)
            return code, data

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(fetch_single, code): code for code in stock_codes}
            for future in as_completed(futures):
                code, data = future.result()
                if data:
                    result[code] = data
                else:
                    # 尝试降级使用过期缓存
                    expired = EarningsService._get_expired_cache(code)
                    if expired:
                        result[code] = expired
                        logger.info(f'[earnings/pe] {code} API失败，使用过期缓存')
                    else:
                        logger.warning(f'[earnings/pe] {code} API失败且无过期缓存')

        return result

    @staticmethod
    def _format_earnings_result(code: str, data: dict) -> dict:
        """格式化财报日期结果"""
        today = date.today()
        next_date_str = data.get('next_earnings_date')
        days_until = None
        is_today = False

        if next_date_str:
            try:
                next_date = datetime.strptime(next_date_str[:10], '%Y-%m-%d').date()
                days_until = (next_date - today).days
                if days_until < 0:
                    # 财报日期已过，不显示
                    next_date_str = None
                    days_until = None
                else:
                    is_today = days_until == 0
            except (ValueError, TypeError):
                pass

        return {
            'code': code,
            'name': code,
            'last_earnings_date': data.get('last_earnings_date'),
            'next_earnings_date': next_date_str,
            'days_until_next': days_until,
            'is_today': is_today,
            'market': data.get('market', 'unknown')
        }

    @staticmethod
    def get_pe_ratios(stock_codes: list, force_refresh: bool = False) -> dict:
        """获取市盈率数据

        通过 UnifiedStockDataService 获取 PE 数据。

        Args:
            stock_codes: 股票代码列表
            force_refresh: 是否强制刷新

        Returns:
            {
                'TSLA': {
                    'code': 'TSLA',
                    'pe_ttm': 45.6,
                    'pe_label': 'TTM',
                    'pe_display': '45.6',
                    'pe_status': 'high',  # 'low'/'normal'/'high'/'very_high'/'loss'/'na'
                    'market': 'US'
                }
            }
        """
        if not stock_codes:
            return {}

        from app.services.unified_stock_data import unified_stock_data_service

        # 通过统一服务获取 PE 数据
        pe_data = unified_stock_data_service.get_pe_data(stock_codes, force_refresh)

        # 转换为原有格式
        result = {}
        for code, data in pe_data.items():
            result[code] = {
                'code': code,
                'pe_ttm': data.get('pe_ttm'),
                'pe_label': 'TTM' if data.get('pe_ttm') is not None else None,
                'pe_display': data.get('pe_display', '暂无数据'),
                'pe_status': data.get('pe_status', 'na'),
                'market': data.get('market', 'unknown')
            }

        # 对于未获取到数据的股票，返回默认值
        for code in stock_codes:
            if code not in result:
                market = MarketIdentifier.identify(code)
                result[code] = {
                    'code': code,
                    'pe_ttm': None,
                    'pe_label': None,
                    'pe_display': '暂无数据',
                    'pe_status': 'na',
                    'market': market or 'unknown'
                }

        return result

    @staticmethod
    def _format_pe_result(code: str, data: dict) -> dict:
        """格式化市盈率结果"""
        pe_ttm = data.get('pe_ttm')
        pe_status = 'na'
        pe_display = '暂无数据'

        if pe_ttm is not None:
            if pe_ttm < 0:
                pe_status = 'loss'
                pe_display = '亏损'
            elif pe_ttm <= PE_THRESHOLD_LOW:
                pe_status = 'low'
                pe_display = str(round(pe_ttm, 1))
            elif pe_ttm <= PE_THRESHOLD_NORMAL:
                pe_status = 'normal'
                pe_display = str(round(pe_ttm, 1))
            elif pe_ttm <= PE_THRESHOLD_HIGH:
                pe_status = 'high'
                pe_display = str(round(pe_ttm, 1))
            else:
                pe_status = 'very_high'
                pe_display = '>200'

        return {
            'code': code,
            'pe_ttm': pe_ttm,
            'pe_label': 'TTM' if pe_ttm is not None else None,
            'pe_display': pe_display,
            'pe_status': pe_status,
            'market': data.get('market', 'unknown')
        }

    @staticmethod
    def get_upcoming_earnings(stock_codes: list, days: int = 7) -> list:
        """获取即将发布财报的股票列表

        Args:
            stock_codes: 股票代码列表
            days: 未来天数（默认7天）

        Returns:
            按 earnings_date 升序排列的股票列表:
            [
                {
                    'code': 'TSLA',
                    'name': 'TSLA',
                    'earnings_date': '2024-01-24',
                    'days_until': 3,
                    'is_today': False
                }
            ]
        """
        if not stock_codes:
            return []

        earnings_data = EarningsService.get_earnings_dates(stock_codes)
        today = date.today()
        upcoming = []

        for code, data in earnings_data.items():
            next_date_str = data.get('next_earnings_date')
            if not next_date_str:
                continue

            try:
                next_date = datetime.strptime(next_date_str[:10], '%Y-%m-%d').date()
                days_until = (next_date - today).days

                if 0 <= days_until <= days:
                    upcoming.append({
                        'code': code,
                        'name': data.get('name', code),
                        'earnings_date': next_date_str[:10],
                        'days_until': days_until,
                        'is_today': days_until == 0
                    })
            except (ValueError, TypeError):
                continue

        # 按财报日期升序排列
        upcoming.sort(key=lambda x: x['earnings_date'])
        return upcoming
