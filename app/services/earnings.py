"""财报数据服务

提供统一的财报日期和市盈率数据获取入口。
支持美股/港股（yfinance）和A股（akshare）数据源。
使用24小时缓存有效期（财报数据变化不频繁）。
"""
import logging
import time
from datetime import datetime, date, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

import akshare as ak
import pandas as pd

from app.models.unified_cache import UnifiedStockCache
from app.services.circuit_breaker import circuit_breaker
from app.utils.market_identifier import MarketIdentifier

logger = logging.getLogger(__name__)

# 缓存类型
CACHE_TYPE_EARNINGS = 'earnings'

# 缓存有效期：24小时
EARNINGS_CACHE_TTL_HOURS = 24


# 重试配置
MAX_RETRIES = 3
RETRY_DELAY = 1.0

# 巨潮预约披露：(period, 取数日) -> {code: {...}}，进程内每期次每天只取一次
_disclosure_cache: dict = {}

_DISCLOSURE_PICK_ORDER = ['实际披露', '三次变更', '二次变更', '初次变更', '首次预约']
_DISCLOSURE_CHANGE_COLS = ['三次变更', '二次变更', '初次变更']

# 月份 -> [(报告期中文, 年份偏移)]，覆盖该月可能发生的财报披露
_MONTH_REPORT_PERIODS = {
    1: [('年报', -1)],
    2: [('年报', -1)],
    3: [('年报', -1)],
    4: [('年报', -1), ('一季', 0)],
    5: [('一季', 0)],
    6: [],
    7: [('半年报', 0)],
    8: [('半年报', 0)],
    9: [('半年报', 0), ('三季', 0)],
    10: [('三季', 0)],
    11: [],
    12: [],
}

_PERIOD_KEY_SUFFIX = {'年报': 'A', '一季': 'Q1', '半年报': 'H1', '三季': 'Q3'}


def _today() -> date:
    """便于测试注入"""
    return date.today()


def period_keys_for_window(today: date = None) -> list[tuple[str, str]]:
    """当月与下月覆盖到的报告期，返回 [(akshare 期次参数, period_key)]"""
    if today is None:
        today = _today()

    months = [(today.year, today.month)]
    if today.month == 12:
        months.append((today.year + 1, 1))
    else:
        months.append((today.year, today.month + 1))

    out = []
    for y, m in months:
        for label, offset in _MONTH_REPORT_PERIODS.get(m, []):
            year = y + offset
            pair = (f'{year}{label}', f'{year}{_PERIOD_KEY_SUFFIX[label]}')
            if pair not in out:
                out.append(pair)
    return out


def _cell_date(row, col):
    """把 pandas 单元格转成 date，NaT/NaN/空串一律 None"""
    if col not in row:
        return None
    v = row[col]
    if v is None or (isinstance(v, float) and pd.isna(v)) or v is pd.NaT:
        return None
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    ts = pd.to_datetime(v, errors='coerce')
    if ts is None or pd.isna(ts):
        return None
    return ts.date()


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
                logger.info(f"[财报] 使用过期缓存数据: {stock_code}")
                return json.loads(cache.data_json)
        except Exception as e:
            logger.warning(f"[财报] 获取过期缓存失败 {stock_code}: {e}")
        return None

    @staticmethod
    def _fetch_earnings_yfinance(stock_code: str) -> dict | None:
        """从yfinance获取美股/港股财报数据（接入熔断）"""
        import yfinance as yf

        # 熔断检查
        if not circuit_breaker.is_available('yfinance'):
            logger.info(f'[财报] yfinance已熔断，{stock_code} 尝试过期缓存')
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
                    logger.debug(f"[财报] 获取 {stock_code} calendar 失败: {e}")

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
                    logger.debug(f"[财报] 获取 {stock_code} earnings_dates 失败: {e}")

                circuit_breaker.record_success('yfinance')
                return {
                    'last_earnings_date': last_earnings_date,
                    'next_earnings_date': next_earnings_date,
                    'market': market,
                    'fetch_time': datetime.now().isoformat()
                }

            except Exception as e:
                last_error = e
                error_msg = str(e).lower()
                if 'delisted' in error_msg or 'no data found' in error_msg:
                    logger.debug(f"[财报] 股票 {stock_code} 可能已退市或无数据: {e}")
                    return None

                if attempt < MAX_RETRIES - 1:
                    logger.debug(f"[财报] 获取 {stock_code} 财报数据失败，第{attempt + 1}次重试: {e}")
                    time.sleep(RETRY_DELAY)

        circuit_breaker.record_failure('yfinance')
        if last_error:
            logger.warning(f"[财报] 获取 {stock_code} 财报数据重试{MAX_RETRIES}次后失败: {last_error}")
        return None

    @staticmethod
    def fetch_disclosure_map(period: str) -> dict:
        """巨潮预约披露 -> {股票代码: {'date', 'status', 'detail'}}

        期次未发布时 akshare 对空 DataFrame 硬赋列名会抛 ValueError，此处吞掉返回 {}。
        """
        cache_key = (period, _today())
        if cache_key in _disclosure_cache:
            return _disclosure_cache[cache_key]

        try:
            df = ak.stock_report_disclosure(market='沪深京', period=period)
        except Exception as e:
            logger.info(f'[财报.预约披露] 期次 {period} 暂无数据: {e}')
            _disclosure_cache[cache_key] = {}
            return {}

        result = {}
        for _, row in df.iterrows():
            code = str(row.get('股票代码', '')).strip()
            if not code:
                continue

            picked = None
            for col in _DISCLOSURE_PICK_ORDER:
                picked = _cell_date(row, col)
                if picked:
                    break
            if not picked:
                continue

            actual = _cell_date(row, '实际披露')
            changed = any(_cell_date(row, c) for c in _DISCLOSURE_CHANGE_COLS)
            if actual:
                status = 'confirmed'
            elif changed:
                status = 'changed'
            else:
                status = 'scheduled'

            detail = None
            first = _cell_date(row, '首次预约')
            if changed and first and first != picked:
                detail = f'预约 {first.isoformat()} → {picked.isoformat()}'

            result[code] = {'date': picked, 'status': status, 'detail': detail}

        _disclosure_cache[cache_key] = result
        return result

    @staticmethod
    def _fetch_earnings_akshare(stock_code: str) -> dict | None:
        """从巨潮预约披露获取A股财报日期"""
        try:
            today = _today()
            last_d, next_d = None, None

            for period, _ in period_keys_for_window(today):
                hit = EarningsService.fetch_disclosure_map(period).get(stock_code)
                if not hit:
                    continue
                d = hit['date']
                if d < today:
                    if last_d is None or d > last_d:
                        last_d = d
                elif next_d is None or d < next_d:
                    next_d = d

            return {
                'last_earnings_date': last_d.isoformat() if last_d else None,
                'next_earnings_date': next_d.isoformat() if next_d else None,
                'market': 'A',
                'fetch_time': datetime.now().isoformat()
            }
        except Exception as e:
            logger.warning(f"[财报] {stock_code} 获取A股数据失败: {e}")
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
                        logger.info(f'[财报.PE] {code} API失败，使用过期缓存')
                    else:
                        logger.warning(f'[财报.PE] {code} API失败且无过期缓存')

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
