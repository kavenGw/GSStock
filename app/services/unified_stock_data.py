"""统一股票数据服务

提供统一的股票数据获取入口，整合自选股、走势看板、预警系统的数据获取逻辑。
支持智能TTL控制，根据交易时段动态调整缓存有效期：
- 交易时段内: 30分钟TTL
- 收盘后: 次日开盘前有效
- 非交易日: 下个交易日开盘前有效
"""
import logging
import threading
import pandas as pd
from dataclasses import dataclass, asdict
from datetime import datetime, date, timedelta
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from app import db
from app.models.unified_cache import UnifiedStockCache
from app.services.cache_validator import CacheValidator
from app.services.circuit_breaker import circuit_breaker
from app.services.load_balancer import load_balancer
from app.services.memory_cache import memory_cache
from app.services.trading_calendar import TradingCalendarService
from app.services.market_session import SmartCacheStrategy, BatchCacheStrategy
from app.utils.market_identifier import MarketIdentifier
from app.utils.readonly_mode import is_readonly_mode

logger = logging.getLogger(__name__)


# 数据类型定义
@dataclass
class PriceData:
    """实时价格数据（统一格式）"""
    code: str
    name: str
    price: Optional[float]
    change: Optional[float]
    change_pct: Optional[float]
    volume: Optional[int]
    high: Optional[float]
    low: Optional[float]
    open: Optional[float]
    prev_close: Optional[float]
    last_fetch_time: str  # ISO格式时间戳
    market: str = ''  # 市场类型: 'A', 'US', 'HK'

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class OHLCData:
    """K线数据"""
    date: str  # ISO格式日期
    open: float
    high: float
    low: float
    close: float
    volume: int
    change_pct: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class IndexData:
    """指数数据"""
    index_code: str
    name: str
    current_price: float
    change_percent: float
    change: float
    last_fetch_time: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CacheStats:
    """缓存统计信息"""
    total_entries: int
    hit_count: int
    miss_count: int
    hit_rate: float
    oldest_entry: Optional[str]
    newest_entry: Optional[str]

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class PEData:
    """PE/PB数据"""
    code: str
    name: str
    pe_ttm: Optional[float]
    pe_forward: Optional[float]  # 仅美股/港股
    pb: Optional[float]
    pe_status: str  # low/normal/high/very_high/loss/na
    pe_display: str
    market: str
    last_fetch_time: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ETFNavData:
    """ETF净值数据"""
    code: str
    name: str
    nav: Optional[float]
    last_fetch_time: str

    def to_dict(self) -> dict:
        return asdict(self)


# PE 阈值常量
PE_THRESHOLD_LOW = 15
PE_THRESHOLD_NORMAL = 30
PE_THRESHOLD_HIGH = 200


class DataFetchOrchestrator:
    """数据源并发编排器

    按数据源分组并发获取数据：
    - 不同数据源(akshare/yfinance/tencent)并行获取
    - 同一数据源内串行处理，避免触发限流
    """

    @staticmethod
    def group_by_source(stock_codes: list) -> dict:
        """按数据源分组股票代码

        Returns:
            {
                'akshare': [A股代码],
                'yfinance': [美股/港股/期货代码]
            }
        """
        groups = {
            'akshare': [],  # A股使用akshare
            'yfinance': []  # 美股/港股/期货使用yfinance
        }

        for code in stock_codes:
            market = MarketIdentifier.identify(code)
            if market == 'A':
                groups['akshare'].append(code)
            else:
                groups['yfinance'].append(code)

        return groups

    @staticmethod
    def fetch_parallel(fetch_funcs: dict) -> dict:
        """并行执行多个数据源的获取函数

        Args:
            fetch_funcs: {source_name: (fetch_function, codes)} 字典

        Returns:
            {stock_code: data} 合并后的结果
        """
        results = {}

        with ThreadPoolExecutor(max_workers=len(fetch_funcs)) as executor:
            futures = {}
            for source, (func, codes) in fetch_funcs.items():
                if codes:
                    futures[executor.submit(func, codes)] = source

            for future in as_completed(futures):
                source = futures[future]
                try:
                    source_results = future.result()
                    if source_results:
                        if isinstance(source_results, dict):
                            results.update(source_results)
                        elif isinstance(source_results, list):
                            for item in source_results:
                                if isinstance(item, dict) and 'stock_code' in item:
                                    results[item['stock_code']] = item
                except Exception as e:
                    logger.warning(f"数据源 {source} 获取失败: {e}")

        return results


class UnifiedStockDataService:
    """统一股票数据服务"""

    # 单例实例
    _instance = None
    _lock = threading.Lock()

    # 缓存统计
    _hit_count = 0
    _miss_count = 0

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, '_fetch_lock'):
            return
        self._fetch_lock = threading.Lock()
        self._stock_name_cache = {}
        self._source_snapshots = {}
        self._snapshot_lock = threading.Lock()
        self._SNAPSHOT_TTL = 120

    def _get_source_snapshot(self, source_key: str):
        with self._snapshot_lock:
            snap = self._source_snapshots.get(source_key)
            if snap and (datetime.now() - snap['timestamp']).total_seconds() < self._SNAPSHOT_TTL:
                return snap['data']
            return None

    def _set_source_snapshot(self, source_key: str, data):
        with self._snapshot_lock:
            self._source_snapshots[source_key] = {
                'data': data,
                'timestamp': datetime.now(),
            }

    def _get_stock_name(self, code: str, data: dict = None) -> str:
        """获取股票名称（用于日志显示）"""
        # 优先从传入数据中获取
        if data:
            name = data.get('name') or data.get('stock_name')
            if name and name != code:
                self._stock_name_cache[code] = name
                return name
        # 从临时缓存获取
        if code in self._stock_name_cache:
            return self._stock_name_cache[code]
        return code

    # ============ 工具方法 ============

    @staticmethod
    def _identify_market(code: str) -> str:
        """识别市场类型（委托给 MarketIdentifier）"""
        return MarketIdentifier.identify(code) or 'US'

    @staticmethod
    def _get_yfinance_symbol(code: str) -> str:
        """获取yfinance格式代码（委托给 MarketIdentifier）"""
        return MarketIdentifier.to_yfinance(code)

    @staticmethod
    def _retry_fetch(fetch_func, stock_code: str, max_retries: int = 3, delay: float = 1.0):
        """带重试的数据获取

        Args:
            fetch_func: 获取函数，返回数据或None
            stock_code: 股票代码（用于日志）
            max_retries: 最大重试次数
            delay: 重试间隔（秒）

        Returns:
            获取到的数据或None
        """
        import time
        last_error = None

        for attempt in range(max_retries):
            try:
                result = fetch_func()
                if result is not None:
                    return result
            except Exception as e:
                last_error = e
                error_msg = str(e).lower()
                # 退市或无数据的情况不需要重试
                if 'delisted' in error_msg or 'no data found' in error_msg:
                    logger.debug(f"股票 {stock_code} 可能已退市或无数据: {e}")
                    return {'error': 'delisted'}

                if attempt < max_retries - 1:
                    logger.debug(f"股票 {stock_code} 获取失败，第{attempt + 1}次重试: {e}")
                    time.sleep(delay)

        if last_error:
            logger.warning(f"股票 {stock_code} 重试{max_retries}次后仍失败: {last_error}, 时间: {datetime.now().isoformat()}")
        return None

    @staticmethod
    def _is_valid_date_format(date_str: str) -> bool:
        """检查日期字符串是否为有效的 YYYY-MM-DD 格式"""
        if not isinstance(date_str, str) or len(date_str) != 10:
            return False
        if date_str[4] != '-' or date_str[7] != '-':
            return False
        try:
            year, month, day = date_str.split('-')
            if not (year.isdigit() and month.isdigit() and day.isdigit()):
                return False
            y, m, d = int(year), int(month), int(day)
            if not (1900 <= y <= 2100 and 1 <= m <= 12 and 1 <= d <= 31):
                return False
            return True
        except ValueError:
            return False

    def _merge_ohlc_data(self, cached_data: list, new_data: list, days: int) -> list:
        """合并 OHLC 数据

        1. 按日期去重（新数据优先）
        2. 按日期排序
        3. 截取最新 N 天
        4. 重新计算 change_pct
        """
        # 按日期建立映射（新数据覆盖旧数据，过滤无效日期）
        date_map = {}
        for dp in cached_data:
            date_str = dp.get('date', '')
            if self._is_valid_date_format(date_str):
                date_map[date_str] = dp.copy()
        for dp in new_data:
            date_str = dp.get('date', '')
            if self._is_valid_date_format(date_str):
                date_map[date_str] = dp.copy()

        # 按日期排序，截取最新 N 天
        sorted_dates = sorted(date_map.keys())[-days:]
        result = [date_map[d] for d in sorted_dates]

        # 重新计算 change_pct（基于第一天收盘价）
        if result:
            base_price = result[0]['close']
            for dp in result:
                dp['change_pct'] = round((dp['close'] - base_price) / base_price * 100, 2)

        return result

    def _get_expired_cache(self, stock_code: str, cache_type: str, reason: str = '') -> dict | None:
        """获取过期缓存数据作为降级方案

        返回的数据会被标记 _is_degraded=True，调用方可根据此标记决定是否使用降级数据。
        """
        try:
            cache = UnifiedStockCache.query.filter_by(
                stock_code=stock_code,
                cache_type=cache_type
            ).order_by(UnifiedStockCache.last_fetch_time.desc()).first()

            if cache and cache.data_json:
                import json
                data = json.loads(cache.data_json)
                data['_is_degraded'] = True
                stock_name = self._get_stock_name(stock_code, data)
                cache_date_str = cache.cache_date.isoformat() if cache.cache_date else '未知'
                fetch_time_str = cache.last_fetch_time.strftime('%m-%d %H:%M') if cache.last_fetch_time else '未知'
                reason_str = f" 原因: {reason}" if reason else ""
                logger.info(f"[降级] {stock_code} {stock_name} 使用过期缓存 ({cache_type}) 数据日期: {cache_date_str}, 获取时间: {fetch_time_str}{reason_str}")
                return data
        except Exception as e:
            logger.warning(f"获取过期缓存失败 {stock_code}: {e}")
        return None

    # ============ 实时价格获取 ============

    def get_realtime_prices(self, stock_codes: list, force_refresh: bool = False) -> dict:
        """获取实时价格数据

        多级缓存策略：内存缓存 → 数据库缓存 → API获取
        - 交易时段内: 30分钟TTL
        - 收盘后/非交易日: 使用缓存不刷新

        Args:
            stock_codes: 股票代码列表
            force_refresh: 是否强制刷新

        Returns:
            {stock_code: PriceData.to_dict()} 字典
        """
        if not stock_codes:
            return {}

        today = date.today()
        cache_type = 'price'

        # 入口日志：统计各市场股票数量
        a_count = sum(1 for c in stock_codes if self._identify_market(c) == 'A')
        other_count = len(stock_codes) - a_count
        logger.info(f"[实时价格] 开始获取: A股 {a_count}只, 其他 {other_count}只")

        result = {}
        remaining_codes = list(stock_codes)
        memory_hit_count = 0
        db_hit_count = 0

        # 第一层：内存缓存（非强制刷新时）
        if not force_refresh:
            memory_cached = memory_cache.get_batch(remaining_codes, cache_type)
            for code, data in memory_cached.items():
                result[code] = data
                memory_hit_count += 1
            remaining_codes = [c for c in remaining_codes if c not in memory_cached]

            if memory_hit_count > 0:
                logger.debug(f"[内存缓存] 命中 {memory_hit_count}只")

        if not remaining_codes:
            logger.info(f"[实时价格] 完成: 请求 {len(stock_codes)}只, 全部内存缓存命中")
            return result

        # 第二层：数据库缓存 + 智能TTL判断
        trading_status = BatchCacheStrategy.filter_by_trading_status(remaining_codes)
        cached_data = UnifiedStockCache.get_cache_with_status(remaining_codes, cache_type, today)

        need_refresh = []

        for code in remaining_codes:
            cache_info = cached_data.get(code)
            stock_name = self._get_stock_name(code, cache_info.get('data') if cache_info else None)

            if force_refresh:
                logger.debug(f"[缓存] {code} {stock_name} 未命中: 强制刷新")
                need_refresh.append(code)
                continue

            # 已有当天完整数据（收盘后），直接使用
            if cache_info:
                data_end = cache_info.get('data_end_date')
                if cache_info.get('is_complete') and data_end == today:
                    result[code] = cache_info['data']
                    memory_cache.set(code, cache_type, cache_info['data'], stable=True)
                    self._hit_count += 1
                    db_hit_count += 1
                    logger.debug(f"[DB缓存] {code} {stock_name} 命中: 完整数据")
                    continue

            # 非交易时间使用缓存
            if code in trading_status['use_cache']:
                if cache_info:
                    result[code] = cache_info['data']
                    memory_cache.set(code, cache_type, cache_info['data'], stable=True)
                    self._hit_count += 1
                    db_hit_count += 1
                    logger.debug(f"[DB缓存] {code} {stock_name} 命中: 非交易时间")
                    continue
                expired_data = self._get_expired_cache(code, cache_type, '非交易时间无有效缓存')
                if expired_data:
                    result[code] = expired_data
                    memory_cache.set(code, cache_type, expired_data, stable=True)
                    continue
                logger.debug(f"[缓存] {code} {stock_name} 未命中: 无缓存")
                need_refresh.append(code)
                continue

            # 交易时间内，使用智能TTL判断
            if cache_info:
                last_fetch = cache_info.get('last_fetch_time')
                if last_fetch and not SmartCacheStrategy.should_refresh(code, last_fetch, today):
                    result[code] = cache_info['data']
                    memory_cache.set(code, cache_type, cache_info['data'])
                    self._hit_count += 1
                    db_hit_count += 1
                    logger.debug(f"[DB缓存] {code} {stock_name} 命中: TTL内")
                    continue
                logger.debug(f"[缓存] {code} {stock_name} 未命中: TTL过期")
            else:
                logger.debug(f"[缓存] {code} {stock_name} 未命中: 无缓存")

            need_refresh.append(code)

        # 第三层：API获取
        if need_refresh:
            # 只读模式下不从外部 API 获取，尝试使用过期缓存
            if is_readonly_mode():
                logger.info(f"[只读模式] 跳过 API 获取 {len(need_refresh)}只，尝试使用过期缓存")
                for code in need_refresh:
                    expired_data = self._get_expired_cache(code, cache_type, '只读模式')
                    if expired_data:
                        result[code] = expired_data
            else:
                self._miss_count += len(need_refresh)
                fetched = self._fetch_realtime_prices(need_refresh)
                result.update(fetched)
                memory_cache.set_batch(fetched, cache_type)

        readonly_msg = " [只读模式]" if is_readonly_mode() else ""
        logger.info(f"[实时价格] 完成{readonly_msg}: 请求 {len(stock_codes)}只, 成功 {len(result)}只 (内存命中 {memory_hit_count}, DB命中 {db_hit_count})")

        return result

    def _fetch_realtime_prices(self, stock_codes: list) -> dict:
        """从外部API获取实时价格（A股用akshare，其他用yfinance）"""
        import yfinance as yf

        result = {}
        today = date.today()
        now_str = datetime.now().isoformat()
        a_share_success = 0
        yf_success = 0

        # 分离A股和非A股
        a_share_codes = []
        other_codes = []
        for code in stock_codes:
            market = self._identify_market(code)
            if market == 'A':
                a_share_codes.append(code)
            else:
                other_codes.append(code)

        logger.debug(f"[实时价格] 分离股票: A股 {len(a_share_codes)}只, 其他 {len(other_codes)}只")

        # A股获取（东方财富优先，yfinance备用）
        if a_share_codes:
            a_share_fetched = self._fetch_a_share_prices(a_share_codes, today, now_str)
            a_share_success = len(a_share_fetched)
            # 判断A股市场是否已收盘
            a_market_closed = TradingCalendarService.is_after_close('A')
            for code, data in a_share_fetched.items():
                result[code] = data
                UnifiedStockCache.set_cached_data(
                    code, 'price', data, today,
                    is_complete=a_market_closed,
                    data_end_date=today if a_market_closed else None
                )

        # 非A股使用yfinance
        if other_codes:
            def fetch_single(code: str) -> tuple:
                """工作线程中只做API调用，不做数据库操作"""
                try:
                    yf_code = self._get_yfinance_symbol(code)
                    market = self._identify_market(code)
                    ticker = yf.Ticker(yf_code)
                    hist = ticker.history(period="5d")
                    if hist.empty or len(hist) < 2:
                        return code, None

                    latest = hist.iloc[-1]
                    prev = hist.iloc[-2]
                    price_val = float(latest['Close'])
                    prev_close = float(prev['Close'])
                    change_val = price_val - prev_close
                    change_pct = (change_val / prev_close * 100) if prev_close else 0

                    return code, {
                        'code': code,
                        'name': code,
                        'current_price': round(price_val, 2),
                        'change': round(change_val, 2),
                        'change_percent': round(change_pct, 2),
                        'volume': int(latest['Volume']) if not pd.isna(latest['Volume']) else None,
                        'high': round(float(latest['High']), 2) if not pd.isna(latest['High']) else None,
                        'low': round(float(latest['Low']), 2) if not pd.isna(latest['Low']) else None,
                        'open': round(float(latest['Open']), 2) if not pd.isna(latest['Open']) else None,
                        'prev_close': round(prev_close, 2),
                        'last_fetch_time': now_str,
                        'market': market,
                    }
                except Exception as e:
                    error_msg = str(e).lower()
                    if 'rate limit' in error_msg or 'too many requests' in error_msg:
                        logger.debug(f"[获取] {code} 失败 (yfinance): 限流")
                        return code, {'rate_limited': True}
                    logger.debug(f"[获取] {code} 失败 (yfinance): {e}")
                    return code, None

            fetched_other = []
            rate_limited_codes = []
            with ThreadPoolExecutor(max_workers=3) as executor:
                futures = {executor.submit(fetch_single, code): code for code in other_codes}
                for future in as_completed(futures):
                    code, data = future.result()
                    if data:
                        if data.get('rate_limited'):
                            rate_limited_codes.append(code)
                        else:
                            result[code] = data
                            fetched_other.append((code, data))
                            stock_name = self._get_stock_name(code, data)
                            logger.debug(f"[获取] {code} {stock_name} 成功 (yfinance)")

            yf_success = len(fetched_other)
            if yf_success > 0:
                logger.info(f"[实时价格] yfinance: 成功 {yf_success}只")

            # 对于被限流的股票，尝试使用过期缓存
            for code in rate_limited_codes:
                expired_data = self._get_expired_cache(code, 'price', 'API限流')
                if expired_data:
                    result[code] = expired_data

            # 主线程中批量保存到缓存，根据各市场收盘状态设置完整性标记
            for code, data in fetched_other:
                market = self._identify_market(code)
                is_closed = TradingCalendarService.is_after_close(market)
                UnifiedStockCache.set_cached_data(
                    code, 'price', data, today,
                    is_complete=is_closed,
                    data_end_date=today if is_closed else None
                )
        return result

    def _fetch_a_share_prices(self, stock_codes: list, today: date, now_str: str) -> dict:
        """获取A股实时价格（负载均衡模式：东方财富/新浪/腾讯轮询分配，yfinance兜底）"""
        import yfinance as yf

        # 各数据源的行情缓存（避免重复拉取全量数据）
        _source_cache = {}

        def fetch_from_eastmoney(codes: list) -> dict:
            result = {}
            try:
                import akshare as ak

                if 'eastmoney' not in _source_cache:
                    stock_map = self._get_source_snapshot('eastmoney_stock')
                    if stock_map is None:
                        stock_df = ak.stock_zh_a_spot_em()
                        stock_map = {}
                        for _, row in stock_df.iterrows():
                            stock_map[row['代码']] = row
                        self._set_source_snapshot('eastmoney_stock', stock_map)
                        logger.info(f"[快照] 东方财富A股数据已缓存: {len(stock_map)}只")
                    else:
                        logger.info(f"[快照命中] 东方财富A股数据: {len(stock_map)}只")

                    etf_map = self._get_source_snapshot('eastmoney_etf')
                    if etf_map is None:
                        try:
                            etf_df = ak.fund_etf_spot_em()
                            etf_map = {}
                            for _, row in etf_df.iterrows():
                                etf_map[row['代码']] = row
                            self._set_source_snapshot('eastmoney_etf', etf_map)
                        except Exception:
                            etf_map = {}

                    combined = {**stock_map, **etf_map}
                    _source_cache['eastmoney'] = combined
                else:
                    combined = _source_cache['eastmoney']

                for code in codes:
                    if code in combined:
                        row = combined[code]
                        result[code] = {
                            'code': code,
                            'name': row.get('名称', code),
                            'current_price': float(row['最新价']) if row['最新价'] else None,
                            'change': float(row.get('涨跌额', 0)) if row.get('涨跌额') else None,
                            'change_percent': float(row['涨跌幅']) if row['涨跌幅'] else None,
                            'volume': int(row['成交量']) if row.get('成交量') else None,
                            'high': float(row['最高']) if row.get('最高') else None,
                            'low': float(row['最低']) if row.get('最低') else None,
                            'open': float(row['今开']) if row.get('今开') else None,
                            'prev_close': float(row['昨收']) if row.get('昨收') else None,
                            'last_fetch_time': now_str,
                            'market': 'A',
                        }

                if result:
                    logger.info(f"[实时价格] 东方财富: 成功 {len(result)}只")
                return result

            except Exception as e:
                logger.warning(f"[实时价格] 东方财富失败: {e}")
                raise

        def fetch_from_sina(codes: list) -> dict:
            result = {}
            try:
                import akshare as ak

                if 'sina' not in _source_cache:
                    stock_map = self._get_source_snapshot('sina_stock')
                    if stock_map is None:
                        stock_df = ak.stock_zh_a_spot()
                        stock_map = {}
                        for _, row in stock_df.iterrows():
                            stock_map[row['代码']] = row
                        self._set_source_snapshot('sina_stock', stock_map)
                        logger.info(f"[快照] 新浪A股数据已缓存: {len(stock_map)}只")
                    else:
                        logger.info(f"[快照命中] 新浪A股数据: {len(stock_map)}只")
                    _source_cache['sina'] = stock_map
                else:
                    stock_map = _source_cache['sina']

                for code in codes:
                    if code in stock_map:
                        row = stock_map[code]
                        result[code] = {
                            'code': code,
                            'name': row.get('名称', code),
                            'current_price': float(row['最新价']) if row['最新价'] else None,
                            'change': float(row.get('涨跌额', 0)) if row.get('涨跌额') else None,
                            'change_percent': float(row['涨跌幅']) if row['涨跌幅'] else None,
                            'volume': int(row['成交量']) if row.get('成交量') else None,
                            'high': float(row['最高']) if row.get('最高') else None,
                            'low': float(row['最低']) if row.get('最低') else None,
                            'open': float(row['今开']) if row.get('今开') else None,
                            'prev_close': float(row['昨收']) if row.get('昨收') else None,
                            'last_fetch_time': now_str,
                            'market': 'A',
                        }

                if result:
                    logger.info(f"[实时价格] 新浪财经: 成功 {len(result)}只")
                return result

            except Exception as e:
                logger.warning(f"[实时价格] 新浪财经失败: {e}")
                raise

        def fetch_from_tencent(codes: list) -> dict:
            """腾讯财经获取函数"""
            try:
                result = self._fetch_from_tencent(codes, now_str)
                if result:
                    logger.info(f"[实时价格] 腾讯财经: 成功 {len(result)}只")
                return result
            except Exception as e:
                logger.warning(f"[实时价格] 腾讯财经失败: {e}")
                raise

        def fetch_from_yfinance(codes: list) -> dict:
            """yfinance兜底获取函数"""
            result = {}

            def fetch_single(code: str) -> tuple:
                try:
                    yf_code = self._get_yfinance_symbol(code)
                    ticker = yf.Ticker(yf_code)
                    hist = ticker.history(period="5d")
                    if hist.empty or len(hist) < 2:
                        return code, None

                    latest = hist.iloc[-1]
                    prev = hist.iloc[-2]
                    price_val = float(latest['Close'])
                    prev_close = float(prev['Close'])
                    change_val = price_val - prev_close
                    change_pct = (change_val / prev_close * 100) if prev_close else 0

                    return code, {
                        'code': code,
                        'name': code,
                        'current_price': round(price_val, 2),
                        'change': round(change_val, 2),
                        'change_percent': round(change_pct, 2),
                        'volume': int(latest['Volume']) if not pd.isna(latest['Volume']) else None,
                        'high': round(float(latest['High']), 2) if not pd.isna(latest['High']) else None,
                        'low': round(float(latest['Low']), 2) if not pd.isna(latest['Low']) else None,
                        'open': round(float(latest['Open']), 2) if not pd.isna(latest['Open']) else None,
                        'prev_close': round(prev_close, 2),
                        'last_fetch_time': now_str,
                        'market': 'A',
                    }
                except Exception as e:
                    logger.debug(f"[获取] {code} 失败 (yfinance): {e}")
                    return code, None

            with ThreadPoolExecutor(max_workers=3) as executor:
                futures = {executor.submit(fetch_single, code): code for code in codes}
                for future in as_completed(futures):
                    code, data = future.result()
                    if data:
                        result[code] = data

            if result:
                logger.info(f"[实时价格] yfinance(A股兜底): 成功 {len(result)}只")
            return result

        # 使用负载均衡器分配任务
        fetch_funcs = {
            'eastmoney': fetch_from_eastmoney,
            'sina': fetch_from_sina,
            'tencent': fetch_from_tencent,
        }

        return load_balancer.fetch_with_balancing(
            stock_codes, fetch_funcs, fallback_func=fetch_from_yfinance
        )

    def _fetch_from_tencent(self, stock_codes: list, now_str: str) -> dict:
        """从腾讯财经获取实时行情"""
        import requests

        result = {}
        if not stock_codes:
            return result

        # 构建腾讯格式代码: sh600519, sz000001
        tencent_codes = []
        code_map = {}
        for code in stock_codes:
            if code.startswith('6'):
                tc = f'sh{code}'
            else:
                tc = f'sz{code}'
            tencent_codes.append(tc)
            code_map[tc] = code

        # 批量请求（每次最多50个）
        batch_size = 50
        for i in range(0, len(tencent_codes), batch_size):
            batch = tencent_codes[i:i + batch_size]
            url = f"http://qt.gtimg.cn/q={','.join(batch)}"

            resp = requests.get(url, timeout=10)
            resp.encoding = 'gbk'

            for line in resp.text.strip().split('\n'):
                if not line or '=' not in line:
                    continue

                # 解析: v_sh600519="1~贵州茅台~600519~1800.00~..."
                parts = line.split('=')
                if len(parts) != 2:
                    continue

                tc = parts[0].replace('v_', '')
                original_code = code_map.get(tc)
                if not original_code:
                    continue

                data_str = parts[1].strip('"')
                fields = data_str.split('~')
                if len(fields) < 35:
                    continue

                try:
                    result[original_code] = {
                        'code': original_code,
                        'name': fields[1],
                        'current_price': float(fields[3]) if fields[3] else None,
                        'prev_close': float(fields[4]) if fields[4] else None,
                        'open': float(fields[5]) if fields[5] else None,
                        'volume': int(float(fields[6])) if fields[6] else None,
                        'high': float(fields[33]) if fields[33] else None,
                        'low': float(fields[34]) if fields[34] else None,
                        'change': float(fields[31]) if fields[31] else None,
                        'change_percent': float(fields[32]) if fields[32] else None,
                        'last_fetch_time': now_str,
                        'market': 'A',
                    }
                except (ValueError, IndexError) as e:
                    logger.debug(f"腾讯数据解析失败 {original_code}: {e}")

        return result

    # ============ OHLC走势数据 ============

    def get_trend_data(self, stock_codes: list, days: int = 60,
                       force_refresh: bool = False) -> dict:
        """获取OHLC走势数据

        多级缓存策略：内存缓存 → 数据库缓存 → API获取
        - 完整数据（收盘后）且 data_end_date 是最近交易日 → 直接返回
        - 有缓存但不完整 → 增量获取缺失数据并合并
        - 无缓存 → 全量获取

        Args:
            stock_codes: 股票代码列表
            days: 获取天数
            force_refresh: 是否强制刷新

        Returns:
            {
                'stocks': [{stock_code, stock_name, data: [OHLCData]}],
                'date_range': {start, end}
            }
        """
        if not stock_codes:
            return {'stocks': [], 'date_range': {'start': None, 'end': None}}

        today = date.today()
        cache_type = f'ohlc_{days}'

        # 入口日志
        logger.info(f"[走势数据] 开始获取: {len(stock_codes)}只股票, {days}天")

        remaining_codes = list(stock_codes)
        memory_hit_stocks = []
        memory_hit_count = 0

        # 第一层：内存缓存（非强制刷新时）
        if not force_refresh:
            memory_cached = memory_cache.get_batch(remaining_codes, cache_type)
            for code, data in memory_cached.items():
                memory_hit_stocks.append(data)
                memory_hit_count += 1
            remaining_codes = [c for c in remaining_codes if c not in memory_cached]

            if memory_hit_count > 0:
                logger.debug(f"[内存缓存] 走势数据命中 {memory_hit_count}只")

        if not remaining_codes:
            all_dates = set()
            for stock in memory_hit_stocks:
                for dp in stock.get('data', []):
                    all_dates.add(dp['date'])
            sorted_dates = sorted(all_dates)
            logger.info(f"[走势数据] 完成: 全部内存缓存命中 {memory_hit_count}只")
            return {
                'stocks': memory_hit_stocks,
                'date_range': {'start': sorted_dates[0] if sorted_dates else None,
                              'end': sorted_dates[-1] if sorted_dates else None}
            }

        # 第二层：数据库缓存 + 智能TTL判断
        trading_status = BatchCacheStrategy.filter_by_trading_status(remaining_codes)
        cached_data = UnifiedStockCache.get_cache_with_status(remaining_codes, cache_type, today)
        data_end_dates = UnifiedStockCache.get_data_end_dates(remaining_codes, cache_type, today)

        cached_stocks = []
        need_refresh = []  # 全量获取
        incremental_codes = []  # (code, missing_days_count, cached_stock_data)
        db_hit_count = 0

        for code in remaining_codes:
            cache_info = cached_data.get(code)
            data_end = data_end_dates.get(code)
            stock_name = self._get_stock_name(code, cache_info.get('data') if cache_info else None)

            if force_refresh:
                logger.debug(f"[缓存] {code} {stock_name} 未命中: 强制刷新")
                need_refresh.append(code)
                continue

            # 情况A: 已完整且 data_end_date 是最近交易日 → 直接使用
            if cache_info and cache_info.get('is_complete') and data_end:
                market = self._identify_market(code)
                last_trading = TradingCalendarService.get_last_trading_day(market, today + timedelta(days=1))
                if data_end >= last_trading:
                    cached_stocks.append(cache_info['data'])
                    memory_cache.set(code, cache_type, cache_info['data'], stable=True)
                    self._hit_count += 1
                    db_hit_count += 1
                    logger.debug(f"[DB缓存] {code} {stock_name} 命中: 完整数据")
                    continue

            # 非交易时间使用缓存（不做增量）
            if code in trading_status['use_cache']:
                if cache_info:
                    cached_stocks.append(cache_info['data'])
                    memory_cache.set(code, cache_type, cache_info['data'], stable=True)
                    self._hit_count += 1
                    db_hit_count += 1
                    logger.debug(f"[DB缓存] {code} {stock_name} 命中: 非交易时间")
                    continue
                expired_data = self._get_expired_cache(code, cache_type, '非交易时间无有效缓存')
                if expired_data:
                    cached_stocks.append(expired_data)
                    memory_cache.set(code, cache_type, expired_data, stable=True)
                    continue
                logger.debug(f"[缓存] {code} {stock_name} 未命中: 无缓存")
                need_refresh.append(code)
                continue

            # 情况B: 有缓存但不完整 → 计算需要增量获取的天数
            if cache_info and data_end:
                market = self._identify_market(code)
                missing_days = TradingCalendarService.get_trading_days(
                    market, data_end + timedelta(days=1), today
                )
                if missing_days:
                    logger.debug(f"[缓存] {code} {stock_name} 需增量: 缺少{len(missing_days)}个交易日")
                    incremental_codes.append((code, len(missing_days) + 5, cache_info['data']))
                    continue
                else:
                    cached_stocks.append(cache_info['data'])
                    memory_cache.set(code, cache_type, cache_info['data'], stable=True)
                    self._hit_count += 1
                    db_hit_count += 1
                    logger.debug(f"[DB缓存] {code} {stock_name} 命中: 无缺失交易日")
                    continue

            # 交易时间内，使用智能TTL判断
            if cache_info:
                last_fetch = cache_info.get('last_fetch_time')
                if last_fetch and not SmartCacheStrategy.should_refresh(code, last_fetch, today):
                    cached_stocks.append(cache_info['data'])
                    memory_cache.set(code, cache_type, cache_info['data'])
                    self._hit_count += 1
                    db_hit_count += 1
                    logger.debug(f"[DB缓存] {code} {stock_name} 命中: TTL内")
                    continue
                logger.debug(f"[缓存] {code} {stock_name} 未命中: TTL过期")
            else:
                logger.debug(f"[缓存] {code} {stock_name} 未命中: 无缓存")

            # 情况C: 无缓存 → 全量获取
            need_refresh.append(code)

        # 缓存决策汇总日志
        logger.info(f"[走势数据] 内存命中 {memory_hit_count}, DB命中 {db_hit_count}, 需刷新 {len(need_refresh)}, 需增量 {len(incremental_codes)}")

        # 全量获取
        fetched_stocks = []
        readonly = is_readonly_mode()

        if need_refresh:
            if readonly:
                # 只读模式下不从外部 API 获取，尝试使用过期缓存
                logger.info(f"[只读模式] 跳过走势数据 API 获取 {len(need_refresh)}只，尝试使用过期缓存")
                for code in need_refresh:
                    expired_data = self._get_expired_cache(code, cache_type, '只读模式')
                    if expired_data:
                        cached_stocks.append(expired_data)
            else:
                self._miss_count += len(need_refresh)
                fetched_stocks = self._fetch_trend_data(need_refresh, days)
                for stock_data in fetched_stocks:
                    code = stock_data.get('stock_code')
                    if code:
                        memory_cache.set(code, cache_type, stock_data)

        # 增量获取
        if incremental_codes:
            if readonly:
                # 只读模式下跳过增量获取，使用现有缓存
                logger.info(f"[只读模式] 跳过增量获取 {len(incremental_codes)}只，使用现有缓存")
                for code, fetch_days, cached_stock_data in incremental_codes:
                    cached_stocks.append(cached_stock_data)
            else:
                self._miss_count += len(incremental_codes)
                for code, fetch_days, cached_stock_data in incremental_codes:
                    new_data = self._fetch_incremental_trend_data(code, fetch_days, days)
                    if new_data:
                        merged_data = self._merge_ohlc_data(
                            cached_stock_data.get('data', []),
                            new_data.get('data', []),
                            days
                        )
                        merged_stock = {
                            'stock_code': code,
                            'stock_name': cached_stock_data.get('stock_name', code),
                            'category_id': cached_stock_data.get('category_id'),
                            'data': merged_data
                        }
                        fetched_stocks.append(merged_stock)

                        # 更新DB缓存和内存缓存
                        market = self._identify_market(code)
                        is_closed = TradingCalendarService.is_after_close(market)
                        data_end_date = None
                        if merged_data:
                            try:
                                data_end_date = date.fromisoformat(merged_data[-1]['date'])
                            except ValueError:
                                pass
                        UnifiedStockCache.set_cached_data(
                            code, cache_type, merged_stock, today,
                            is_complete=is_closed,
                            data_end_date=data_end_date
                        )
                        memory_cache.set(code, cache_type, merged_stock)
                        stock_name = cached_stock_data.get('stock_name', code)
                        logger.debug(f"[增量] {code} {stock_name}: 获取{fetch_days}天, 合并后{len(merged_data)}天")
                    else:
                        stock_name = cached_stock_data.get('stock_name', code)
                        logger.debug(f"[增量] {code} {stock_name}: 获取失败, 使用缓存")
                        cached_stocks.append(cached_stock_data)

        # 合并结果（内存缓存命中 + DB缓存命中 + 新获取）
        all_stocks = memory_hit_stocks + cached_stocks + fetched_stocks

        # 获取日期范围
        all_dates = set()
        for stock in all_stocks:
            for dp in stock.get('data', []):
                all_dates.add(dp['date'])

        sorted_dates = sorted(all_dates)
        date_range = {
            'start': sorted_dates[0] if sorted_dates else None,
            'end': sorted_dates[-1] if sorted_dates else None
        }

        readonly_msg = " [只读模式]" if readonly else ""
        logger.info(f"[走势数据] 完成{readonly_msg}: 成功 {len(all_stocks)}只 (内存 {memory_hit_count}, DB {db_hit_count})")

        return {
            'stocks': all_stocks,
            'date_range': date_range
        }

    def _fetch_trend_data(self, stock_codes: list, days: int) -> list:
        """获取OHLC数据（负载均衡模式：ETF专用接口 / 东方财富/新浪轮询 / yfinance兜底）"""
        import yfinance as yf
        from app.models.stock import Stock
        from app.services.category import CategoryService

        today = date.today()
        start_date = today - timedelta(days=days + 10)
        cache_type = f'ohlc_{days}'

        # 获取股票名称映射
        stock_name_map = {}
        stocks = Stock.query.filter(Stock.stock_code.in_(stock_codes)).all()
        for s in stocks:
            stock_name_map[s.stock_code] = s.stock_name

        stock_categories = CategoryService.get_stock_categories_map(stock_codes)

        # 分离 ETF、普通A股、非A股
        etf_codes = []
        a_share_codes = []
        other_codes = []
        for code in stock_codes:
            market = self._identify_market(code)
            if market == 'A':
                if MarketIdentifier.is_etf(code):
                    etf_codes.append(code)
                else:
                    a_share_codes.append(code)
            else:
                other_codes.append(code)

        logger.debug(f"[走势数据] 分类: ETF {len(etf_codes)}只, A股 {len(a_share_codes)}只, 其他 {len(other_codes)}只")

        results = []

        # 0. ETF 使用专用接口
        if etf_codes:
            etf_results = self._fetch_trend_from_etf(
                etf_codes, days, start_date, today, stock_name_map, stock_categories
            )
            results.extend(etf_results)

        # A股: 使用负载均衡分配到东方财富/新浪
        if a_share_codes:
            def fetch_eastmoney(codes: list) -> dict:
                """东方财富历史数据"""
                try:
                    res = self._fetch_trend_from_eastmoney(
                        codes, days, start_date, today, stock_name_map, stock_categories
                    )
                    circuit_breaker.record_success('eastmoney_hist')
                    return {r['stock_code']: r for r in res}
                except Exception as e:
                    circuit_breaker.record_failure('eastmoney_hist')
                    raise

            def fetch_sina(codes: list) -> dict:
                """新浪历史数据"""
                try:
                    res = self._fetch_trend_from_sina(
                        codes, days, start_date, today, stock_name_map, stock_categories
                    )
                    circuit_breaker.record_success('sina_hist')
                    return {r['stock_code']: r for r in res}
                except Exception as e:
                    circuit_breaker.record_failure('sina_hist')
                    raise

            def fetch_tencent(codes: list) -> dict:
                """腾讯历史数据"""
                try:
                    res = self._fetch_trend_from_tencent(
                        codes, days, start_date, today, stock_name_map, stock_categories
                    )
                    circuit_breaker.record_success('tencent_hist')
                    return {r['stock_code']: r for r in res}
                except Exception as e:
                    circuit_breaker.record_failure('tencent_hist')
                    raise

            def fetch_yfinance_fallback(codes: list) -> dict:
                """yfinance兜底"""
                res = self._fetch_trend_from_yfinance(
                    codes, days, start_date, today, stock_name_map, stock_categories, cache_type
                )
                return {r['stock_code']: r for r in res}

            fetch_funcs = {
                'eastmoney_hist': fetch_eastmoney,
                'sina_hist': fetch_sina,
                'tencent_hist': fetch_tencent,
            }

            a_share_results = load_balancer.fetch_with_balancing(
                a_share_codes, fetch_funcs, fallback_func=fetch_yfinance_fallback
            )
            results.extend(a_share_results.values())

        # 非A股直接使用yfinance
        if other_codes:
            yf_results = self._fetch_trend_from_yfinance(
                other_codes, days, start_date, today, stock_name_map, stock_categories, cache_type
            )
            results.extend(yf_results)

        # 保存到缓存
        for result in results:
            code = result['stock_code']
            data_points = result.get('data', [])

            if data_points:
                first_date = data_points[0].get('date', '')
                if not self._is_valid_date_format(first_date):
                    stock_name = result.get('stock_name', code)
                    logger.warning(f"[走势数据] {code} {stock_name} 数据日期格式异常，跳过缓存: first_date={first_date}")
                    continue

            market = self._identify_market(code)
            is_closed = TradingCalendarService.is_after_close(market)
            data_end = None
            if data_points:
                last_date_str = data_points[-1].get('date')
                if last_date_str:
                    try:
                        data_end = date.fromisoformat(last_date_str)
                    except ValueError:
                        pass
            UnifiedStockCache.set_cached_data(
                code, cache_type, result, today,
                is_complete=is_closed,
                data_end_date=data_end
            )

        logger.debug(f"[走势数据] _fetch_trend_data: 请求 {len(stock_codes)}, 成功 {len(results)}")
        return results

    def _fetch_incremental_trend_data(self, stock_code: str, fetch_days: int, total_days: int) -> dict | None:
        """增量获取单只股票的 OHLC 数据

        Args:
            stock_code: 股票代码
            fetch_days: 需要获取的天数
            total_days: 总天数（用于计算 change_pct 的基准）

        Returns:
            股票数据字典或 None
        """
        import yfinance as yf
        from app.models.stock import Stock

        today = date.today()
        start_date = today - timedelta(days=fetch_days + 5)  # 多取几天防止遗漏

        # 获取股票名称
        stock = Stock.query.filter_by(stock_code=stock_code).first()
        stock_name = stock.stock_name if stock else stock_code

        market = self._identify_market(stock_code)
        is_etf = MarketIdentifier.is_etf(stock_code)

        # ETF 使用专用接口
        if market == 'A' and is_etf:
            try:
                import akshare as ak
                df = ak.fund_etf_hist_em(
                    symbol=stock_code,
                    period="daily",
                    start_date=start_date.strftime('%Y%m%d'),
                    end_date=today.strftime('%Y%m%d'),
                    adjust="qfq"
                )
                if df is not None and not df.empty and len(df) >= 1:
                    data_points = []
                    for _, row in df.iterrows():
                        data_points.append({
                            'date': str(row['日期'])[:10],
                            'open': round(float(row['开盘']), 2),
                            'high': round(float(row['最高']), 2),
                            'low': round(float(row['最低']), 2),
                            'close': round(float(row['收盘']), 2),
                            'change_pct': 0,
                            'volume': int(row['成交量']) if row.get('成交量') else 0
                        })
                    logger.debug(f"增量获取 {stock_code} (ETF): {len(data_points)}天")
                    return {
                        'stock_code': stock_code,
                        'stock_name': stock_name,
                        'data': data_points
                    }
            except Exception as e:
                logger.debug(f"增量获取 {stock_code} (ETF) 失败: {e}")
            # ETF 不 fallback 到 yfinance
            return None

        # A股使用负载均衡（按健康状态选择数据源）
        if market == 'A':
            import akshare as ak
            import requests

            # 数据源获取函数
            def fetch_from_eastmoney():
                df = ak.stock_zh_a_hist(
                    symbol=stock_code,
                    period="daily",
                    start_date=start_date.strftime('%Y%m%d'),
                    end_date=today.strftime('%Y%m%d'),
                    adjust="qfq"
                )
                if df.empty or len(df) < 1:
                    return None
                data_points = []
                for _, row in df.iterrows():
                    data_points.append({
                        'date': str(row['日期'])[:10],
                        'open': round(float(row['开盘']), 2),
                        'high': round(float(row['最高']), 2),
                        'low': round(float(row['最低']), 2),
                        'close': round(float(row['收盘']), 2),
                        'change_pct': 0,
                        'volume': int(row['成交量']) if row.get('成交量') else 0
                    })
                return data_points

            def fetch_from_sina():
                sina_code = f"sh{stock_code}" if stock_code.startswith('6') else f"sz{stock_code}"
                df = ak.stock_zh_a_daily(symbol=sina_code, start_date=start_date.strftime('%Y%m%d'),
                                          end_date=today.strftime('%Y%m%d'), adjust="qfq")
                if df.empty or len(df) < 1:
                    return None
                data_points = []
                for idx, row in df.iterrows():
                    date_str = None
                    if hasattr(idx, 'strftime'):
                        date_str = idx.strftime('%Y-%m-%d')
                    elif 'date' in row.index:
                        date_str = str(row['date'])[:10]
                    if not date_str or not self._is_valid_date_format(date_str):
                        continue
                    data_points.append({
                        'date': date_str,
                        'open': round(float(row['open']), 2),
                        'high': round(float(row['high']), 2),
                        'low': round(float(row['low']), 2),
                        'close': round(float(row['close']), 2),
                        'change_pct': 0,
                        'volume': int(row['volume']) if row.get('volume') else 0
                    })
                return data_points if data_points else None

            def fetch_from_tencent():
                tc = f'sh{stock_code}' if stock_code.startswith('6') else f'sz{stock_code}'
                url = f"http://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={tc},day,{start_date.strftime('%Y-%m-%d')},{today.strftime('%Y-%m-%d')},100,qfq"
                resp = requests.get(url, timeout=10)
                data = resp.json()
                if data.get('code') != 0:
                    return None
                klines = data.get('data', {}).get(tc, {})
                day_data = klines.get('qfqday') or klines.get('day')
                if not day_data or len(day_data) < 1:
                    return None
                data_points = []
                for row in day_data:
                    date_str = row[0]
                    if not self._is_valid_date_format(date_str):
                        continue
                    data_points.append({
                        'date': date_str,
                        'open': round(float(row[1]), 2),
                        'high': round(float(row[3]), 2),
                        'low': round(float(row[4]), 2),
                        'close': round(float(row[2]), 2),
                        'change_pct': 0,
                        'volume': int(float(row[5])) if len(row) > 5 and row[5] else 0
                    })
                return data_points if data_points else None

            # 按健康状态和优先级尝试数据源
            sources = [
                ('sina_hist', fetch_from_sina, '新浪'),
                ('tencent_hist', fetch_from_tencent, '腾讯'),
                ('eastmoney_hist', fetch_from_eastmoney, '东方财富'),
            ]

            for source_key, fetch_func, source_name in sources:
                if not circuit_breaker.is_available(source_key):
                    continue
                try:
                    data_points = fetch_func()
                    if data_points:
                        circuit_breaker.record_success(source_key)
                        logger.debug(f"增量获取 {stock_code} ({source_name}): {len(data_points)}天")
                        return {
                            'stock_code': stock_code,
                            'stock_name': stock_name,
                            'data': data_points
                        }
                except Exception as e:
                    circuit_breaker.record_failure(source_key)
                    logger.debug(f"增量获取 {stock_code} ({source_name}) 失败: {e}")

        # yfinance 兜底
        try:
            yf_code = self._get_yfinance_symbol(stock_code)
            ticker = yf.Ticker(yf_code)
            hist = ticker.history(start=start_date.isoformat(),
                                  end=(today + timedelta(days=1)).isoformat())
            if hist.empty:
                return None

            data_points = []
            for idx, row in hist.iterrows():
                open_price = row['Open']
                high_price = row['High']
                low_price = row['Low']
                close_price = row['Close']
                volume = row.get('Volume', 0)

                if any(pd.isna(v) for v in [open_price, high_price, low_price, close_price]):
                    continue

                data_points.append({
                    'date': idx.strftime('%Y-%m-%d'),
                    'open': round(float(open_price), 2),
                    'high': round(float(high_price), 2),
                    'low': round(float(low_price), 2),
                    'close': round(float(close_price), 2),
                    'change_pct': 0,  # 后续合并时重新计算
                    'volume': int(volume) if not pd.isna(volume) else 0
                })

            if data_points:
                logger.debug(f"增量获取 {stock_code} (yfinance): {len(data_points)}天")
                return {
                    'stock_code': stock_code,
                    'stock_name': stock_name,
                    'data': data_points
                }
        except Exception as e:
            logger.debug(f"增量获取 {stock_code} (yfinance) 失败: {e}")

        return None

    def _fetch_trend_from_etf(self, etf_codes: list, days: int, start_date: date,
                               today: date, stock_name_map: dict, stock_categories: dict) -> list:
        """获取 ETF 历史K线（使用 akshare fund_etf_hist_em）"""
        results = []
        if not etf_codes:
            return results

        try:
            import akshare as ak
            logger.debug(f"[走势数据] 获取ETF历史数据 ({len(etf_codes)}只)...")

            for etf_code in etf_codes:
                try:
                    df = ak.fund_etf_hist_em(
                        symbol=etf_code,
                        period="daily",
                        start_date=start_date.strftime('%Y%m%d'),
                        end_date=today.strftime('%Y%m%d'),
                        adjust="qfq"
                    )
                    if df is None or df.empty or len(df) < 2:
                        stock_name = stock_name_map.get(etf_code, etf_code)
                        logger.debug(f"[获取] {etf_code} {stock_name} ETF数据为空")
                        continue

                    df = df.tail(days)
                    base_price = df['收盘'].iloc[0]
                    data_points = []
                    for _, row in df.iterrows():
                        change_pct = (row['收盘'] - base_price) / base_price * 100
                        data_points.append({
                            'date': str(row['日期'])[:10],
                            'open': round(float(row['开盘']), 2),
                            'high': round(float(row['最高']), 2),
                            'low': round(float(row['最低']), 2),
                            'close': round(float(row['收盘']), 2),
                            'change_pct': round(change_pct, 2),
                            'volume': int(row['成交量']) if row.get('成交量') else 0
                        })

                    if len(data_points) >= 2:
                        sc = stock_categories.get(etf_code, {})
                        stock_name = stock_name_map.get(etf_code, etf_code)
                        results.append({
                            'stock_code': etf_code,
                            'stock_name': stock_name,
                            'category_id': sc.get('category_id'),
                            'data': data_points
                        })
                        logger.debug(f"[获取] {etf_code} {stock_name} 成功 (etf_hist)")

                except Exception as e:
                    stock_name = stock_name_map.get(etf_code, etf_code)
                    logger.debug(f"[获取] {etf_code} {stock_name} 失败 (etf_hist): {e}")

            if results:
                logger.info(f"[走势数据] ETF: 成功 {len(results)}只")

        except Exception as e:
            logger.warning(f"[走势数据] ETF获取失败: {e}")

        return results

    def _fetch_trend_from_eastmoney(self, stock_codes: list, days: int, start_date: date,
                                     today: date, stock_name_map: dict, stock_categories: dict) -> list:
        """从东方财富获取历史K线"""
        import akshare as ak

        results = []
        logger.debug(f"[走势数据] 东方财富获取 ({len(stock_codes)}只)...")

        for stock_code in stock_codes:
            try:
                df = ak.stock_zh_a_hist(
                    symbol=stock_code,
                    period="daily",
                    start_date=start_date.strftime('%Y%m%d'),
                    end_date=today.strftime('%Y%m%d'),
                    adjust="qfq"
                )
                if df.empty or len(df) < 2:
                    continue

                df = df.tail(days)
                base_price = df['收盘'].iloc[0]
                data_points = []
                for _, row in df.iterrows():
                    change_pct = (row['收盘'] - base_price) / base_price * 100
                    data_points.append({
                        'date': str(row['日期'])[:10],
                        'open': round(float(row['开盘']), 2),
                        'high': round(float(row['最高']), 2),
                        'low': round(float(row['最低']), 2),
                        'close': round(float(row['收盘']), 2),
                        'change_pct': round(change_pct, 2),
                        'volume': int(row['成交量']) if row.get('成交量') else 0
                    })

                if len(data_points) >= 2:
                    sc = stock_categories.get(stock_code, {})
                    stock_name = stock_name_map.get(stock_code, stock_code)
                    results.append({
                        'stock_code': stock_code,
                        'stock_name': stock_name,
                        'category_id': sc.get('category_id'),
                        'data': data_points
                    })
                    logger.debug(f"[获取] {stock_code} {stock_name} 成功 (eastmoney_hist)")
            except Exception as e:
                stock_name = stock_name_map.get(stock_code, stock_code)
                logger.debug(f"[获取] {stock_code} {stock_name} 失败 (eastmoney_hist): {e}")

        if results:
            logger.info(f"[走势数据] 东方财富: 成功 {len(results)}只")

        return results

    def _fetch_trend_from_sina(self, stock_codes: list, days: int, start_date: date,
                                today: date, stock_name_map: dict, stock_categories: dict) -> list:
        """从新浪获取历史K线"""
        import akshare as ak

        results = []
        logger.debug(f"[走势数据] 新浪获取 ({len(stock_codes)}只)...")

        for stock_code in stock_codes:
            try:
                sina_code = f"sh{stock_code}" if stock_code.startswith('6') else f"sz{stock_code}"
                df = ak.stock_zh_a_daily(symbol=sina_code, start_date=start_date.strftime('%Y%m%d'),
                                          end_date=today.strftime('%Y%m%d'), adjust="qfq")
                if df.empty or len(df) < 2:
                    continue

                df = df.tail(days)
                base_price = df['close'].iloc[0]
                data_points = []
                for idx, row in df.iterrows():
                    date_str = None
                    if hasattr(idx, 'strftime'):
                        date_str = idx.strftime('%Y-%m-%d')
                    elif 'date' in row.index:
                        date_str = str(row['date'])[:10]

                    if not date_str or not self._is_valid_date_format(date_str):
                        continue

                    change_pct = (row['close'] - base_price) / base_price * 100
                    data_points.append({
                        'date': date_str,
                        'open': round(float(row['open']), 2),
                        'high': round(float(row['high']), 2),
                        'low': round(float(row['low']), 2),
                        'close': round(float(row['close']), 2),
                        'change_pct': round(change_pct, 2),
                        'volume': int(row['volume']) if row.get('volume') else 0
                    })

                if len(data_points) >= 2:
                    sc = stock_categories.get(stock_code, {})
                    stock_name = stock_name_map.get(stock_code, stock_code)
                    results.append({
                        'stock_code': stock_code,
                        'stock_name': stock_name,
                        'category_id': sc.get('category_id'),
                        'data': data_points
                    })
                    logger.debug(f"[获取] {stock_code} {stock_name} 成功 (sina_hist)")
            except Exception as e:
                stock_name = stock_name_map.get(stock_code, stock_code)
                logger.debug(f"[获取] {stock_code} {stock_name} 失败 (sina_hist): {e}")

        if results:
            logger.info(f"[走势数据] 新浪: 成功 {len(results)}只")

        return results

    def _fetch_trend_from_tencent(self, stock_codes: list, days: int, start_date: date,
                                   today: date, stock_name_map: dict, stock_categories: dict) -> list:
        """从腾讯财经获取历史K线"""
        import requests

        results = []
        logger.debug(f"[走势数据] 腾讯获取 ({len(stock_codes)}只)...")

        for stock_code in stock_codes:
            try:
                # 腾讯格式: sh600519 或 sz000001
                if stock_code.startswith('6'):
                    tc = f'sh{stock_code}'
                else:
                    tc = f'sz{stock_code}'

                # 腾讯日K线接口
                url = f"http://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={tc},day,{start_date.strftime('%Y-%m-%d')},{today.strftime('%Y-%m-%d')},{days},qfq"
                resp = requests.get(url, timeout=10)
                data = resp.json()

                if data.get('code') != 0:
                    continue

                klines = data.get('data', {}).get(tc, {})
                # 优先使用前复权数据
                day_data = klines.get('qfqday') or klines.get('day')
                if not day_data or len(day_data) < 2:
                    continue

                day_data = day_data[-days:]
                base_price = float(day_data[0][2])  # 第一天收盘价
                data_points = []

                for row in day_data:
                    # 格式: [日期, 开盘, 收盘, 最高, 最低, 成交量]
                    date_str = row[0]
                    if not self._is_valid_date_format(date_str):
                        continue

                    close_price = float(row[2])
                    change_pct = (close_price - base_price) / base_price * 100
                    data_points.append({
                        'date': date_str,
                        'open': round(float(row[1]), 2),
                        'high': round(float(row[3]), 2),
                        'low': round(float(row[4]), 2),
                        'close': round(close_price, 2),
                        'change_pct': round(change_pct, 2),
                        'volume': int(float(row[5])) if len(row) > 5 and row[5] else 0
                    })

                if len(data_points) >= 2:
                    sc = stock_categories.get(stock_code, {})
                    stock_name = stock_name_map.get(stock_code, stock_code)
                    results.append({
                        'stock_code': stock_code,
                        'stock_name': stock_name,
                        'category_id': sc.get('category_id'),
                        'data': data_points
                    })
                    logger.debug(f"[获取] {stock_code} {stock_name} 成功 (tencent_hist)")

            except Exception as e:
                stock_name = stock_name_map.get(stock_code, stock_code)
                logger.debug(f"[获取] {stock_code} {stock_name} 失败 (tencent_hist): {e}")

        if results:
            logger.info(f"[走势数据] 腾讯: 成功 {len(results)}只")

        return results

    def _fetch_trend_from_yfinance(self, stock_codes: list, days: int, start_date: date,
                                    today: date, stock_name_map: dict, stock_categories: dict,
                                    cache_type: str) -> list:
        """从yfinance获取历史K线"""
        import yfinance as yf

        logger.debug(f"[走势数据] 尝试yfinance ({len(stock_codes)}只)...")

        def fetch_single(stock_code: str) -> dict | None:
            yf_code = self._get_yfinance_symbol(stock_code)
            try:
                ticker = yf.Ticker(yf_code)
                hist = ticker.history(start=start_date.isoformat(),
                                      end=(today + timedelta(days=1)).isoformat())
                if hist.empty:
                    return None

                hist = hist.tail(days)
                if len(hist) < 2:
                    return None

                base_price = hist['Close'].iloc[0]
                data_points = []
                for idx, row in hist.iterrows():
                    open_price = row['Open']
                    high_price = row['High']
                    low_price = row['Low']
                    close_price = row['Close']
                    volume = row.get('Volume', 0)

                    if any(pd.isna(v) for v in [open_price, high_price, low_price, close_price]):
                        continue

                    change_pct = (close_price - base_price) / base_price * 100
                    data_points.append({
                        'date': idx.strftime('%Y-%m-%d'),
                        'open': round(float(open_price), 2),
                        'high': round(float(high_price), 2),
                        'low': round(float(low_price), 2),
                        'close': round(float(close_price), 2),
                        'change_pct': round(change_pct, 2),
                        'volume': int(volume) if not pd.isna(volume) else 0
                    })

                if len(data_points) < 2:
                    return None

                sc = stock_categories.get(stock_code, {})
                return {
                    'stock_code': stock_code,
                    'stock_name': stock_name_map.get(stock_code, stock_code),
                    'category_id': sc.get('category_id'),
                    'data': data_points
                }

            except Exception as e:
                error_msg = str(e).lower()
                stock_name = stock_name_map.get(stock_code, stock_code)
                if 'delisted' in error_msg or 'no timezone found' in error_msg or 'no data found' in error_msg:
                    logger.debug(f"[获取] {stock_code} {stock_name} 失败 (yfinance): 退市或无数据")
                elif 'rate limit' in error_msg or 'too many requests' in error_msg:
                    logger.debug(f"[获取] {stock_code} {stock_name} 失败 (yfinance): 限流")
                    return {'stock_code': stock_code, 'rate_limited': True}
                else:
                    logger.debug(f"[获取] {stock_code} {stock_name} 失败 (yfinance): {e}")
                return None

        results = []
        rate_limited_codes = []
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {executor.submit(fetch_single, code): code for code in stock_codes}
            for future in as_completed(futures):
                result = future.result()
                if result:
                    if result.get('rate_limited'):
                        rate_limited_codes.append(result['stock_code'])
                    else:
                        results.append(result)
                        stock_name = result.get('stock_name', result['stock_code'])
                        logger.debug(f"[获取] {result['stock_code']} {stock_name} 成功 (yfinance)")

        for code in rate_limited_codes:
            expired_data = self._get_expired_cache(code, cache_type, 'API限流')
            if expired_data:
                results.append(expired_data)

        if results:
            logger.info(f"[走势数据] yfinance: 成功 {len(results)}只")
        return results

    # ============ 指数数据 ============

    def get_indices_data(self, target_date: date = None,
                         force_refresh: bool = False) -> dict:
        """获取指数数据

        使用智能缓存策略：指数统一使用A股市场时间判断

        Args:
            target_date: 目标日期
            force_refresh: 是否强制刷新

        Returns:
            {index_code: IndexData.to_dict()} 字典
        """
        import yfinance as yf
        from app.models.index_trend_cache import IndexTrendCache

        if target_date is None:
            target_date = date.today()

        INDEX_CODES = {
            'sh000001': '000001.SS',
            'sz399001': '399001.SZ',
            'sz399006': '399006.SZ',
            'sh000300': '000300.SS',
        }

        CHINEXT_ETF_CODE = '159915.SZ'

        name_map = {
            'sh000001': '上证指数',
            'sz399001': '深证成指',
            'sz399006': '创业板指',
            'sh000300': '沪深300',
        }

        index_codes = list(INDEX_CODES.keys())
        cache_type = 'index'

        # 使用智能缓存策略（指数统一用A股市场时间）
        should_fetch, reason = TradingCalendarService.should_fetch_data('A')

        # 获取缓存数据和状态
        cached_data = UnifiedStockCache.get_cache_with_status(index_codes, cache_type, target_date)

        results = {}
        need_refresh = []

        for code in index_codes:
            cache_info = cached_data.get(code)

            if force_refresh:
                need_refresh.append(code)
                continue

            # 已完整的数据不需要刷新
            if cache_info and cache_info.get('is_complete'):
                results[code] = cache_info['data']
                self._hit_count += 1
                continue

            # 非交易时间使用缓存
            if not should_fetch:
                if cache_info:
                    results[code] = cache_info['data']
                    self._hit_count += 1
                else:
                    need_refresh.append(code)
                continue

            # 交易时间内，使用智能TTL判断
            if cache_info:
                last_fetch = cache_info.get('last_fetch_time')
                # 指数用 sh000001 代表性地判断
                if last_fetch and not SmartCacheStrategy.should_refresh('600519', last_fetch, target_date):
                    results[code] = cache_info['data']
                    self._hit_count += 1
                    continue

            need_refresh.append(code)

        # 获取需要刷新的数据
        if need_refresh:
            # 只读模式下不从外部 API 获取，尝试使用过期缓存
            if is_readonly_mode():
                logger.info(f"[只读模式] 跳过指数数据 API 获取 {len(need_refresh)}只，尝试使用过期缓存")
                for code in need_refresh:
                    expired_data = self._get_expired_cache(code, cache_type, '只读模式')
                    if expired_data:
                        results[code] = expired_data
                return results

            self._miss_count += len(need_refresh)
            now_str = datetime.now().isoformat()

            # 获取创业板ETF涨跌幅
            chinext_etf_change_pct = None
            try:
                etf_ticker = yf.Ticker(CHINEXT_ETF_CODE)
                etf_hist = etf_ticker.history(period='5d')
                if len(etf_hist) >= 2:
                    etf_latest = etf_hist.iloc[-1]
                    etf_prev = etf_hist.iloc[-2]
                    chinext_etf_change_pct = (float(etf_latest['Close']) - float(etf_prev['Close'])) / float(etf_prev['Close']) * 100
            except Exception as e:
                logger.warning(f"创业板ETF数据获取失败: {e}")

            for local_code in need_refresh:
                yf_code = INDEX_CODES.get(local_code)
                if not yf_code:
                    continue

                try:
                    # 先尝试从数据库缓存获取
                    caches = IndexTrendCache.query.filter(
                        IndexTrendCache.index_code == local_code,
                        IndexTrendCache.date <= target_date
                    ).order_by(IndexTrendCache.date.desc()).limit(2).all()

                    if caches:
                        latest = caches[0]
                        latest_price = latest.price

                        if local_code == 'sz399006' and len(caches) == 1 and chinext_etf_change_pct is not None:
                            change_pct = chinext_etf_change_pct
                            change = latest_price * change_pct / 100
                        elif len(caches) > 1:
                            prev = caches[1]
                            change = latest_price - prev.price
                            change_pct = (change / prev.price * 100) if prev.price else 0
                        else:
                            change = 0
                            change_pct = 0

                        data = {
                            'index_code': local_code,
                            'name': name_map.get(local_code, local_code),
                            'current_price': round(latest_price, 2),
                            'change_percent': round(change_pct, 2),
                            'change': round(change, 2),
                            'last_fetch_time': now_str,
                        }
                        results[local_code] = data
                        is_closed = TradingCalendarService.is_after_close('A')
                        UnifiedStockCache.set_cached_data(
                            local_code, cache_type, data, target_date,
                            is_complete=is_closed,
                            data_end_date=target_date if is_closed else None
                        )
                    else:
                        # 从yfinance获取
                        ticker = yf.Ticker(yf_code)
                        hist = ticker.history(period='5d')
                        if not hist.empty:
                            # 保存到IndexTrendCache
                            for idx, row in hist.iterrows():
                                trade_date = idx.date()
                                existing = IndexTrendCache.query.filter_by(
                                    index_code=local_code, date=trade_date
                                ).first()
                                if not existing:
                                    cache = IndexTrendCache(
                                        index_code=local_code,
                                        date=trade_date,
                                        price=float(row['Close']),
                                        volume=int(row['Volume']) if row['Volume'] else None,
                                    )
                                    db.session.add(cache)
                            db.session.commit()

                            latest = hist.iloc[-1]
                            prev = hist.iloc[-2] if len(hist) > 1 else latest
                            change = float(latest['Close']) - float(prev['Close'])
                            change_pct = (change / float(prev['Close']) * 100) if prev['Close'] else 0

                            data = {
                                'index_code': local_code,
                                'name': name_map.get(local_code, local_code),
                                'current_price': round(float(latest['Close']), 2),
                                'change_percent': round(change_pct, 2),
                                'change': round(change, 2),
                                'last_fetch_time': now_str,
                            }
                            results[local_code] = data
                            is_closed = TradingCalendarService.is_after_close('A')
                            UnifiedStockCache.set_cached_data(
                                local_code, cache_type, data, target_date,
                                is_complete=is_closed,
                                data_end_date=target_date if is_closed else None
                            )

                except Exception as e:
                    logger.warning(f"获取指数 {local_code} 数据失败: {e}")

        return results

    # ============ PE/PB数据 ============

    def get_pe_data(self, stock_codes: list, force_refresh: bool = False) -> dict:
        """获取PE/PB数据

        Args:
            stock_codes: 股票代码列表
            force_refresh: 是否强制刷新

        Returns:
            {stock_code: PEData.to_dict()} 字典
        """
        if not stock_codes:
            return {}

        # A股不获取PE数据
        stock_codes = [c for c in stock_codes if self._identify_market(c) != 'A']
        if not stock_codes:
            return {}

        today = date.today()
        cache_type = 'pe'
        now_str = datetime.now().isoformat()

        logger.info(f"[PE数据] 开始获取: 美股/港股 {len(stock_codes)}只")

        # 检查缓存（PE缓存24小时有效）
        result = {}
        need_refresh = []
        cache_hit_count = 0

        for code in stock_codes:
            if force_refresh:
                need_refresh.append(code)
                continue

            cached = UnifiedStockCache.get_cached_data(code, cache_type, today)
            if cached:
                # 检查24小时有效期
                cache_record = UnifiedStockCache.query.filter_by(
                    stock_code=code, cache_type=cache_type, cache_date=today
                ).first()
                if cache_record and cache_record.last_fetch_time:
                    age = datetime.now() - cache_record.last_fetch_time
                    if age < timedelta(hours=24):
                        result[code] = cached
                        cache_hit_count += 1
                        self._hit_count += 1
                        stock_name = cached.get('name', code)
                        logger.debug(f"[缓存] {code} {stock_name} 命中: PE缓存有效")
                        continue

            need_refresh.append(code)

        # 获取需要刷新的数据
        if need_refresh:
            # 只读模式下不从外部 API 获取，尝试使用过期缓存
            if is_readonly_mode():
                logger.info(f"[只读模式] 跳过 PE 数据 API 获取 {len(need_refresh)}只，尝试使用过期缓存")
                for code in need_refresh:
                    expired_data = self._get_expired_cache(code, cache_type, '只读模式')
                    if expired_data:
                        result[code] = expired_data
            else:
                self._miss_count += len(need_refresh)
                fetched = self._fetch_pe_data(need_refresh, today, now_str)
                result.update(fetched)

        readonly_msg = " [只读模式]" if is_readonly_mode() else ""
        logger.info(f"[PE数据] 完成{readonly_msg}: 请求 {len(stock_codes)}只, 成功 {len(result)}只 (缓存命中 {cache_hit_count}只)")
        return result

    def _fetch_pe_data(self, stock_codes: list, today: date, now_str: str) -> dict:
        """从外部API获取PE数据（美股/港股用yfinance）"""
        import yfinance as yf

        result = {}

        if stock_codes:
            def fetch_single(code: str) -> tuple:
                try:
                    yf_code = self._get_yfinance_symbol(code)
                    market = self._identify_market(code)
                    ticker = yf.Ticker(yf_code)
                    info = ticker.info

                    if not info:
                        return code, None

                    pe_ttm = info.get('trailingPE')
                    pe_forward = info.get('forwardPE')
                    pb = info.get('priceToBook')

                    if pe_ttm is not None:
                        pe_ttm = round(float(pe_ttm), 2)
                    if pe_forward is not None:
                        pe_forward = round(float(pe_forward), 2)
                    if pb is not None:
                        pb = round(float(pb), 2)

                    pe_status, pe_display = self._format_pe_status(pe_ttm)

                    data = {
                        'code': code,
                        'name': info.get('shortName', code),
                        'pe_ttm': pe_ttm,
                        'pe_forward': pe_forward,
                        'pb': pb,
                        'pe_status': pe_status,
                        'pe_display': pe_display,
                        'market': market,
                        'last_fetch_time': now_str,
                    }
                    return code, data

                except Exception as e:
                    logger.debug(f"[获取] {code} PE失败 (yfinance): {e}")
                    return code, None

            yf_success = 0
            with ThreadPoolExecutor(max_workers=3) as executor:
                futures = {executor.submit(fetch_single, code): code for code in stock_codes}
                for future in as_completed(futures):
                    code, data = future.result()
                    if data:
                        result[code] = data
                        yf_success += 1
                        UnifiedStockCache.set_cached_data(code, 'pe', data, today)
                        logger.debug(f"[获取] {code} {data['name']} PE成功 (yfinance)")
                    else:
                        expired = self._get_expired_cache(code, 'pe', 'yfinance获取失败')
                        if expired:
                            result[code] = expired

            if yf_success > 0:
                logger.info(f"[PE数据] yfinance: 成功 {yf_success}只")

        return result

    def _format_pe_status(self, pe_ttm: float | None) -> tuple:
        """格式化PE状态"""
        if pe_ttm is None:
            return 'na', '暂无数据'
        if pe_ttm < 0:
            return 'loss', '亏损'
        if pe_ttm <= PE_THRESHOLD_LOW:
            return 'low', str(round(pe_ttm, 1))
        if pe_ttm <= PE_THRESHOLD_NORMAL:
            return 'normal', str(round(pe_ttm, 1))
        if pe_ttm <= PE_THRESHOLD_HIGH:
            return 'high', str(round(pe_ttm, 1))
        return 'very_high', str(round(pe_ttm, 1))

    # ============ 通用批量报价 ============

    def get_yfinance_batch_quotes(self, symbols: list, cache_type: str,
                                   force_refresh: bool = False) -> dict:
        """通用 yfinance 批量报价获取（指数/期货/ETF等）

        Args:
            symbols: yfinance 格式代码列表
            cache_type: 缓存类型标识
            force_refresh: 是否强制刷新

        Returns:
            {symbol: {'close': float, 'change_percent': float, 'name': str}}
        """
        if not symbols:
            return {}

        today = date.today()
        now_str = datetime.now().isoformat()

        # 缓存检查
        result = {}
        need_fetch = []

        if not force_refresh:
            for sym in symbols:
                cached = UnifiedStockCache.get_cached_data(sym, cache_type, today)
                if cached:
                    cache_record = UnifiedStockCache.query.filter_by(
                        stock_code=sym, cache_type=cache_type, cache_date=today
                    ).first()
                    if cache_record and cache_record.last_fetch_time:
                        age = datetime.now() - cache_record.last_fetch_time
                        if age < timedelta(hours=8):
                            result[sym] = cached
                            self._hit_count += 1
                            continue
                need_fetch.append(sym)
        else:
            need_fetch = list(symbols)

        if not need_fetch:
            return result

        # yfinance 熔断检查
        if not circuit_breaker.is_available('yfinance'):
            logger.info(f"[yfinance批量] yfinance已熔断，尝试过期缓存")
            for sym in need_fetch:
                expired = self._get_expired_cache(sym, cache_type, 'yfinance熔断')
                if expired:
                    result[sym] = expired
            return result

        self._miss_count += len(need_fetch)

        # 并行获取
        def fetch_single(sym: str) -> tuple:
            import yfinance as yf
            try:
                ticker = yf.Ticker(sym)
                hist = ticker.history(period='5d')
                if hist.empty or len(hist) < 2:
                    return sym, None

                latest = hist.iloc[-1]
                prev = hist.iloc[-2]
                close = float(latest['Close'])
                prev_close = float(prev['Close'])
                change_pct = ((close - prev_close) / prev_close * 100) if prev_close else 0

                return sym, {
                    'close': round(close, 2),
                    'change_percent': round(change_pct, 2),
                    'name': sym,
                    'last_fetch_time': now_str,
                }
            except Exception as e:
                logger.debug(f"[yfinance批量] {sym} 获取失败: {e}")
                return sym, None

        success_count = 0
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {executor.submit(fetch_single, sym): sym for sym in need_fetch}
            for future in as_completed(futures):
                sym, data = future.result()
                if data:
                    result[sym] = data
                    success_count += 1
                    UnifiedStockCache.set_cached_data(sym, cache_type, data, today)
                else:
                    expired = self._get_expired_cache(sym, cache_type, 'yfinance获取失败')
                    if expired:
                        result[sym] = expired

        if success_count > 0:
            circuit_breaker.record_success('yfinance')
            logger.info(f"[yfinance批量] 成功 {success_count}/{len(need_fetch)}只 (cache_type={cache_type})")
        elif need_fetch:
            circuit_breaker.record_failure('yfinance')
            logger.warning(f"[yfinance批量] 全部失败 {len(need_fetch)}只")

        return result

    def get_a_share_index_quotes(self, index_codes: list,
                                  force_refresh: bool = False) -> dict:
        """A股指数数据获取（负载均衡：东方财富/新浪，yfinance兜底）

        Args:
            index_codes: 指数代码列表（如 '000001.SS', '399001.SZ'）
            force_refresh: 是否强制刷新

        Returns:
            {code: {'close': float, 'change_percent': float, 'name': str}}
        """
        if not index_codes:
            return {}

        today = date.today()
        cache_type = 'a_index_quote'
        now_str = datetime.now().isoformat()

        # 缓存检查
        result = {}
        need_fetch = []

        if not force_refresh:
            for code in index_codes:
                cached = UnifiedStockCache.get_cached_data(code, cache_type, today)
                if cached:
                    cache_record = UnifiedStockCache.query.filter_by(
                        stock_code=code, cache_type=cache_type, cache_date=today
                    ).first()
                    if cache_record and cache_record.last_fetch_time:
                        age = datetime.now() - cache_record.last_fetch_time
                        if age < timedelta(hours=8):
                            result[code] = cached
                            self._hit_count += 1
                            continue
                need_fetch.append(code)
        else:
            need_fetch = list(index_codes)

        if not need_fetch:
            return result

        self._miss_count += len(need_fetch)

        def fetch_index_eastmoney(codes: list) -> dict:
            import akshare as ak
            res = {}
            try:
                df = ak.stock_zh_index_spot_em()
                if df is None or df.empty:
                    return res
                idx_map = {}
                for _, row in df.iterrows():
                    raw_code = str(row.get('代码', ''))
                    idx_map[raw_code] = row

                for code in codes:
                    pure_code = code.split('.')[0]
                    row = idx_map.get(pure_code)
                    if row is not None:
                        close_val = row.get('最新价')
                        change_val = row.get('涨跌幅')
                        data = {
                            'close': round(float(close_val), 2) if close_val else None,
                            'change_percent': round(float(change_val), 2) if change_val else None,
                            'name': row.get('名称', code),
                            'last_fetch_time': now_str,
                        }
                        res[code] = data

                if res:
                    logger.info(f"[A股指数] 东方财富: 成功 {len(res)}只")
            except Exception as e:
                logger.warning(f"[A股指数] 东方财富失败: {e}")
                raise
            return res

        def fetch_index_sina(codes: list) -> dict:
            import akshare as ak
            res = {}
            try:
                df = ak.stock_zh_index_spot_sina()
                if df is None or df.empty:
                    return res
                idx_map = {}
                for _, row in df.iterrows():
                    raw_code = str(row.get('代码', ''))
                    idx_map[raw_code] = row

                for code in codes:
                    pure_code = code.split('.')[0]
                    # 新浪格式：sh000001, sz399001
                    if code.endswith('.SS'):
                        sina_code = f"sh{pure_code}"
                    elif code.endswith('.SZ'):
                        sina_code = f"sz{pure_code}"
                    else:
                        sina_code = pure_code

                    row = idx_map.get(sina_code)
                    if row is not None:
                        close_val = row.get('最新价')
                        change_val = row.get('涨跌幅')
                        data = {
                            'close': round(float(close_val), 2) if close_val else None,
                            'change_percent': round(float(change_val), 2) if change_val else None,
                            'name': row.get('名称', code),
                            'last_fetch_time': now_str,
                        }
                        res[code] = data

                if res:
                    logger.info(f"[A股指数] 新浪: 成功 {len(res)}只")
            except Exception as e:
                logger.warning(f"[A股指数] 新浪失败: {e}")
                raise
            return res

        def fetch_index_yfinance(codes: list) -> dict:
            """yfinance兜底"""
            res = {}
            for code in codes:
                try:
                    import yfinance as yf
                    ticker = yf.Ticker(code)
                    hist = ticker.history(period='5d')
                    if hist.empty or len(hist) < 2:
                        continue
                    latest = hist.iloc[-1]
                    prev = hist.iloc[-2]
                    close = float(latest['Close'])
                    prev_close = float(prev['Close'])
                    change_pct = ((close - prev_close) / prev_close * 100) if prev_close else 0
                    res[code] = {
                        'close': round(close, 2),
                        'change_percent': round(change_pct, 2),
                        'name': code,
                        'last_fetch_time': now_str,
                    }
                except Exception as e:
                    logger.debug(f"[A股指数] yfinance兜底 {code} 失败: {e}")
            return res

        fetch_funcs = {
            'eastmoney': fetch_index_eastmoney,
            'sina': fetch_index_sina,
        }

        fetched = load_balancer.fetch_with_balancing(
            need_fetch, fetch_funcs, fallback_func=fetch_index_yfinance
        )

        # 保存缓存
        for code, data in fetched.items():
            result[code] = data
            UnifiedStockCache.set_cached_data(code, cache_type, data, today)

        return result

    def get_cn_sector_data(self, force_refresh: bool = False) -> list:
        """A股板块数据获取（熔断保护+过期缓存降级）

        Returns:
            板块列表 [{'name': str, 'change_percent': float, 'leader': str}]
        """
        today = date.today()
        cache_type = 'cn_sector'
        cache_key = 'CN_SECTOR_ALL'
        now_str = datetime.now().isoformat()

        # 缓存检查
        if not force_refresh:
            cached = UnifiedStockCache.get_cached_data(cache_key, cache_type, today)
            if cached and isinstance(cached, list):
                cache_record = UnifiedStockCache.query.filter_by(
                    stock_code=cache_key, cache_type=cache_type, cache_date=today
                ).first()
                if cache_record and cache_record.last_fetch_time:
                    age = datetime.now() - cache_record.last_fetch_time
                    if age < timedelta(hours=8):
                        self._hit_count += 1
                        return cached

        # 熔断检查
        if not circuit_breaker.is_available('eastmoney'):
            logger.info("[A股板块] 东方财富已熔断，尝试过期缓存")
            expired = self._get_expired_cache(cache_key, cache_type, '东方财富熔断')
            if expired and isinstance(expired, list):
                return expired
            return []

        self._miss_count += 1

        try:
            import akshare as ak
            df = ak.stock_board_industry_name_em()
            if df is None or df.empty:
                circuit_breaker.record_failure('eastmoney')
                return []

            circuit_breaker.record_success('eastmoney')

            result = []
            for _, row in df.iterrows():
                result.append({
                    'name': row['板块名称'],
                    'change_percent': round(float(row['涨跌幅']), 2),
                    'leader': row['领涨股票'],
                })

            # 保存缓存
            UnifiedStockCache.set_cached_data(cache_key, cache_type, result, today)
            logger.info(f"[A股板块] 获取成功: {len(result)}个板块")
            return result

        except Exception as e:
            logger.warning(f"[A股板块] 获取失败: {e}")
            circuit_breaker.record_failure('eastmoney')
            expired = self._get_expired_cache(cache_key, cache_type, 'API获取失败')
            if expired and isinstance(expired, list):
                return expired
            return []

    # ============ ETF净值 ============

    def get_etf_nav(self, etf_codes: list, force_refresh: bool = False) -> dict:
        """获取ETF净值数据

        Args:
            etf_codes: ETF代码列表
            force_refresh: 是否强制刷新

        Returns:
            {etf_code: ETFNavData.to_dict()} 字典
        """
        if not etf_codes:
            return {}

        today = date.today()
        cache_type = 'etf_nav'
        now_str = datetime.now().isoformat()

        logger.info(f"[ETF净值] 开始获取: {len(etf_codes)}只")

        result = {}
        need_refresh = []
        cache_hit_count = 0

        for code in etf_codes:
            if force_refresh:
                need_refresh.append(code)
                continue

            cached = UnifiedStockCache.get_cached_data(code, cache_type, today)
            if cached:
                result[code] = cached
                cache_hit_count += 1
                self._hit_count += 1
                logger.debug(f"[缓存] {code} 命中: ETF净值缓存")
                continue

            need_refresh.append(code)

        # 获取需要刷新的数据
        if need_refresh:
            # 只读模式下不从外部 API 获取，尝试使用过期缓存
            if is_readonly_mode():
                logger.info(f"[只读模式] 跳过 ETF 净值 API 获取 {len(need_refresh)}只，尝试使用过期缓存")
                for code in need_refresh:
                    expired_data = self._get_expired_cache(code, cache_type, '只读模式')
                    if expired_data:
                        result[code] = expired_data
            else:
                self._miss_count += len(need_refresh)
                fetched = self._fetch_etf_nav(need_refresh, today, now_str)
                result.update(fetched)

        readonly_msg = " [只读模式]" if is_readonly_mode() else ""
        logger.info(f"[ETF净值] 完成{readonly_msg}: 请求 {len(etf_codes)}只, 成功 {len(result)}只 (缓存命中 {cache_hit_count}只)")
        return result

    def _fetch_etf_nav(self, etf_codes: list, today: date, now_str: str) -> dict:
        """使用负载均衡获取ETF净值"""
        from app.services.load_balancer import load_balancer

        cache_type = 'etf_nav'

        def fetch_via_fund_info(codes: list) -> dict:
            """通过 fund_etf_fund_info_em 获取历史净值（T-1）"""
            import akshare as ak
            import time
            result = {}

            for code in codes:
                try:
                    df = ak.fund_etf_fund_info_em(
                        fund=code,
                        start_date=(today - timedelta(days=30)).strftime('%Y%m%d'),
                        end_date=today.strftime('%Y%m%d')
                    )
                    if df is not None and not df.empty:
                        last_row = df.iloc[-1]
                        nav = float(last_row['单位净值'])
                        if nav > 0:
                            result[code] = {
                                'code': code,
                                'name': f"ETF_{code}",
                                'nav': round(nav, 4),
                                'last_fetch_time': now_str,
                            }
                            logger.debug(f"[etf_fund_info] {code} 净值={nav}")
                    time.sleep(0.3)
                except Exception as e:
                    logger.debug(f"[etf_fund_info] {code} 失败: {e}")

            return result

        def fetch_via_spot(codes: list) -> dict:
            import akshare as ak
            result = {}

            try:
                etf_map = self._get_source_snapshot('eastmoney_etf')
                if etf_map is None:
                    df = ak.fund_etf_spot_em()
                    if df is None or df.empty:
                        return result
                    etf_map = {str(row.get('代码', '')): row for _, row in df.iterrows()}
                    self._set_source_snapshot('eastmoney_etf', etf_map)
                    logger.info(f"[快照] ETF数据已缓存: {len(etf_map)}只")
                else:
                    logger.info(f"[快照命中] ETF数据: {len(etf_map)}只")

                for code in codes:
                    row = etf_map.get(code)
                    if row is None:
                        continue

                    nav = None
                    if 'IOPV实时估值' in row.index:
                        val = row['IOPV实时估值']
                        if val and val != '-':
                            try:
                                nav = round(float(val), 4)
                            except (ValueError, TypeError):
                                pass

                    if nav is None and '最新价' in row.index:
                        val = row['最新价']
                        if val and val != '-':
                            try:
                                nav = round(float(val), 4)
                            except (ValueError, TypeError):
                                pass

                    if nav:
                        name = row.get('名称', f'ETF_{code}')
                        result[code] = {
                            'code': code,
                            'name': name,
                            'nav': nav,
                            'last_fetch_time': now_str,
                        }
                        logger.debug(f"[etf_spot] {code} {name} 净值={nav}")

            except Exception as e:
                logger.warning(f"[etf_spot] 获取失败: {e}")

            return result

        fetch_funcs = {
            'etf_fund_info': fetch_via_fund_info,
            'etf_spot': fetch_via_spot,
        }

        result = load_balancer.fetch_with_balancing(
            etf_codes,
            fetch_funcs,
            fallback_func=None
        )

        # 保存到缓存（在主线程的应用上下文中）
        for code, data in result.items():
            UnifiedStockCache.set_cached_data(code, cache_type, data, today)

        return result

    # ============ 缓存管理 ============

    def get_cache_stats(self) -> CacheStats:
        """获取缓存统计信息"""
        today = date.today()

        # 统计总条目数
        total_entries = UnifiedStockCache.query.filter_by(cache_date=today).count()

        # 计算命中率
        total_requests = self._hit_count + self._miss_count
        hit_rate = (self._hit_count / total_requests * 100) if total_requests > 0 else 0

        # 获取最老和最新条目
        oldest = UnifiedStockCache.query.order_by(UnifiedStockCache.created_at.asc()).first()
        newest = UnifiedStockCache.query.order_by(UnifiedStockCache.created_at.desc()).first()

        return CacheStats(
            total_entries=total_entries,
            hit_count=self._hit_count,
            miss_count=self._miss_count,
            hit_rate=round(hit_rate, 2),
            oldest_entry=oldest.created_at.isoformat() if oldest else None,
            newest_entry=newest.created_at.isoformat() if newest else None,
        )

    def clear_cache(self, stock_codes: list = None, cache_type: str = None) -> int:
        """清除缓存

        Args:
            stock_codes: 股票代码列表，为空则清除所有
            cache_type: 缓存类型，为空则清除所有类型

        Returns:
            删除的记录数
        """
        # 清除数据库缓存
        count = UnifiedStockCache.clear_cache(stock_codes, cache_type)

        # 清除内存缓存
        if stock_codes:
            for code in stock_codes:
                memory_cache.invalidate(code, cache_type)
        else:
            memory_cache.invalidate(None, cache_type)

        logger.info(f"清除缓存: {count} 条记录 (DB), 内存缓存已同步清除")
        return count

    def reset_stats(self):
        """重置统计计数"""
        self._hit_count = 0
        self._miss_count = 0
        memory_cache.reset_stats()


# 创建单例实例
unified_stock_data_service = UnifiedStockDataService()
