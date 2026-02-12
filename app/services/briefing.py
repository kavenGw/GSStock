"""每日简报服务

提供每日简报所需的所有数据聚合，包括：
- 关键股票昨日行情（TSLA, GOOG, NVDA, AAPL, WDC, MU, SK海力士）
- 主要指数昨日行情（纳指100, 上证, 深证, 创业板, 日经225）
- ETF溢价率监控（纳指ETF富国, 美国50ETF易方达）
- 板块评级（根据美股表现评级A股板块风险）
"""
import logging
from datetime import datetime, date
from typing import Optional

from app.config.sector_ratings import SECTOR_RATING_CONFIG

logger = logging.getLogger(__name__)


# 配置常量
STOCK_CATEGORIES = {
    'storage': {'name': '存储芯片', 'order': 1},
    'tech_giant': {'name': '科技巨头', 'order': 2},
    'semiconductor': {'name': '半导体供应链', 'order': 3},
    'cpu': {'name': 'CPU', 'order': 4},
    'other': {'name': '其他', 'order': 99}
}

BRIEFING_STOCKS = [
    {'code': 'TSLA', 'name': '特斯拉', 'market': 'US', 'category': 'tech_giant'},
    {'code': 'GOOG', 'name': '谷歌', 'market': 'US', 'category': 'tech_giant'},
    {'code': 'NVDA', 'name': '英伟达', 'market': 'US', 'category': 'tech_giant'},
    {'code': 'AAPL', 'name': '苹果', 'market': 'US', 'category': 'tech_giant'},
    {'code': 'WDC', 'name': '西部数据', 'market': 'US', 'category': 'storage'},
    {'code': 'MU', 'name': '美光', 'market': 'US', 'category': 'storage'},
    {'code': 'SNDK', 'name': '闪迪', 'market': 'US', 'category': 'storage'},
    {'code': 'TSM', 'name': '台积电', 'market': 'US', 'category': 'semiconductor'},
    {'code': '3037.TW', 'name': '欣兴电子', 'market': 'TW', 'category': 'semiconductor'},
    {'code': '005930.KS', 'name': '三星电子', 'market': 'KR', 'category': 'storage'},
    {'code': '000660.KS', 'name': 'SK海力士', 'market': 'KR', 'category': 'storage'},
    {'code': 'STX', 'name': '希捷', 'market': 'US', 'category': 'storage'},
    {'code': 'AMD', 'name': 'AMD', 'market': 'US', 'category': 'cpu'},
    {'code': 'INTC', 'name': '英特尔', 'market': 'US', 'category': 'cpu'},
]

INDEX_CATEGORIES = {
    'china_a': {'name': '大A指数', 'order': 1},
    'asia': {'name': '亚洲指数', 'order': 2},
    'us': {'name': '美国指数', 'order': 3}
}

BRIEFING_INDICES = [
    {'code': '^DJI', 'name': '道琼斯', 'region': 'us'},
    {'code': '^NDX', 'name': '纳指100', 'region': 'us'},
    {'code': '^GSPC', 'name': '标普500', 'region': 'us'},
    {'code': '^KS11', 'name': '韩国KOSPI', 'region': 'asia'},
    {'code': '000001.SS', 'name': '上证指数', 'region': 'china_a'},
    {'code': '399001.SZ', 'name': '深证成指', 'region': 'china_a'},
    {'code': '399006.SZ', 'name': '创业板指', 'region': 'china_a'},
    {'code': '^N225', 'name': '日经225', 'region': 'asia'},
]

BRIEFING_FUTURES = [
    {'code': 'NQ=F', 'name': '纳指100期货'},
    {'code': 'GC=F', 'name': '纽金期货'},
    {'code': 'SI=F', 'name': '纽银期货'},
    {'code': 'HG=F', 'name': '纽铜期货'},
]

BRIEFING_ETFS = [
    {'code': '159941', 'name': '纳指ETF富国'},
    {'code': '513850', 'name': '美国50ETF易方达'},
]

# 溢价率阈值
BUY_THRESHOLD = 3.0   # ≤3% 建议买入
SELL_THRESHOLD = 6.0  # ≥6% 建议卖出

# 美股行业ETF配置
US_SECTOR_ETFS = [
    {'code': 'XLK', 'name': '科技'},
    {'code': 'XLF', 'name': '金融'},
    {'code': 'XLE', 'name': '能源'},
    {'code': 'XLV', 'name': '医疗保健'},
    {'code': 'XLY', 'name': '非必需消费'},
    {'code': 'XLP', 'name': '必需消费'},
    {'code': 'XLI', 'name': '工业'},
    {'code': 'XLB', 'name': '材料'},
    {'code': 'XLU', 'name': '公用事业'},
    {'code': 'XLRE', 'name': '房地产'},
    {'code': 'XLC', 'name': '通信服务'},
]


class BriefingService:
    """每日简报服务"""

    @staticmethod
    def get_stocks_basic_data(force_refresh: bool = False) -> dict:
        """获取基础股票数据（价格+投资建议，不含PE和财报）

        使用缓存的收盘价数据，不发起实时API请求。
        """
        from app.services.unified_stock_data import unified_stock_data_service

        stock_codes = [s['code'] for s in BRIEFING_STOCKS]

        sorted_categories = sorted(STOCK_CATEGORIES.items(), key=lambda x: x[1]['order'])
        categories = [{'key': k, 'name': v['name']} for k, v in sorted_categories if k != 'other']
        stocks_by_category = {k: [] for k, _ in sorted_categories}

        prices = {}
        try:
            # 使用缓存的收盘价，不发起实时API请求
            prices = unified_stock_data_service.get_closing_prices(stock_codes)
        except Exception as e:
            logger.error(f"获取股票价格失败: {e}")

        from app.models.stock import Stock
        advice_map = {}
        try:
            stocks_with_advice = Stock.query.filter(Stock.stock_code.in_(stock_codes)).all()
            advice_map = {s.stock_code: s.investment_advice for s in stocks_with_advice if s.investment_advice}
        except Exception as e:
            logger.warning(f"获取投资建议失败: {e}")

        for stock_info in BRIEFING_STOCKS:
            code = stock_info['code']
            category = stock_info.get('category', 'other')
            price_data = prices.get(code)

            stock_item = {
                'code': code,
                'name': stock_info['name'],
                'market': stock_info['market'],
                'category': category,
                'close': None,
                'change_percent': None,
                'volume': None,
                'investment_advice': advice_map.get(code),
                'error': None
            }

            if price_data and not price_data.get('_is_degraded'):
                stock_item['close'] = price_data.get('current_price', 0)
                stock_item['change_percent'] = price_data.get('change_percent', 0)
                stock_item['volume'] = price_data.get('volume', 0)
            else:
                stock_item['error'] = '数据获取失败'

            stocks_by_category[category].append(stock_item)

        stocks_by_category = {k: v for k, v in stocks_by_category.items() if v}

        for category_key in stocks_by_category:
            stocks_by_category[category_key].sort(
                key=lambda x: x['change_percent'] if x['change_percent'] is not None else float('-inf'),
                reverse=True
            )

        categories = [c for c in categories if c['key'] in stocks_by_category]

        cache_time = BriefingService.get_cache_update_time()
        last_update = cache_time if cache_time else datetime.now()

        return {
            'categories': categories,
            'stocks': stocks_by_category,
            'last_update': last_update.strftime('%Y-%m-%d %H:%M:%S')
        }

    @staticmethod
    def get_stocks_pe_data(force_refresh: bool = False) -> dict:
        """获取股票PE数据"""
        from app.services.unified_stock_data import unified_stock_data_service

        stock_codes = [s['code'] for s in BRIEFING_STOCKS]
        pe_data = {}
        try:
            pe_data = unified_stock_data_service.get_pe_data(stock_codes, force_refresh)
        except Exception as e:
            logger.warning(f"获取PE数据失败: {e}")

        result = {}
        for code in stock_codes:
            pe = pe_data.get(code, {})
            if pe:
                result[code] = {
                    'pe_ttm': pe.get('pe_ttm'),
                    'pe_forward': pe.get('pe_forward'),
                    'pe_status': pe.get('pe_status', 'na')
                }

        return result

    @staticmethod
    def get_stocks_earnings_data(force_refresh: bool = False) -> dict:
        """获取股票财报日期数据"""
        from app.services.earnings import EarningsService

        stock_codes = [s['code'] for s in BRIEFING_STOCKS]
        earnings_data = {}
        try:
            earnings_data = EarningsService.get_earnings_dates(stock_codes, force_refresh)
        except Exception as e:
            logger.warning(f"获取财报日期失败: {e}")

        result = {}
        for code in stock_codes:
            earnings = earnings_data.get(code, {})
            if earnings:
                result[code] = {
                    'earnings_date': earnings.get('next_earnings_date'),
                    'days_until_earnings': earnings.get('days_until_next'),
                    'is_earnings_today': earnings.get('is_today', False)
                }

        return result

    @staticmethod
    def get_indices_data(force_refresh: bool = False) -> dict:
        """获取指数数据（按地区分类）

        使用缓存的收盘价数据，不发起实时API请求。

        Returns:
            {
                'regions': [{'key': 'china_a', 'name': '大A指数'}, ...],
                'indices': {
                    'china_a': [index_item, ...],
                    'asia': [index_item, ...],
                    'us': [index_item, ...]
                }
            }
        """
        from app.services.unified_stock_data import unified_stock_data_service
        from app.models.unified_cache import UnifiedStockCache

        today = date.today()
        cache_type = 'briefing_index'

        # 检查整体缓存（不强制刷新时直接使用）
        cache_key = 'BRIEFING_INDICES_V2'
        cached = UnifiedStockCache.get_cached_data(cache_key, cache_type, today)
        if cached and isinstance(cached, dict) and 'regions' in cached:
            return cached

        # 尝试获取过期缓存（最近7天）
        for days_ago in range(1, 8):
            cache_date = today - timedelta(days=days_ago)
            cached = UnifiedStockCache.get_cached_data(cache_key, cache_type, cache_date)
            if cached and isinstance(cached, dict) and 'regions' in cached:
                logger.info(f"[指数数据] 使用{days_ago}天前的缓存")
                return cached

        # 按地区组织结果
        sorted_regions = sorted(INDEX_CATEGORIES.items(), key=lambda x: x[1]['order'])
        regions = [{'key': k, 'name': v['name']} for k, v in sorted_regions]
        indices_by_region = {k: [] for k, _ in sorted_regions}

        # 分离A股指数(.SZ/.SS)和其他指数
        a_share_indices = [idx for idx in BRIEFING_INDICES
                           if idx['code'].endswith('.SZ') or idx['code'].endswith('.SS')]
        other_indices = [idx for idx in BRIEFING_INDICES
                         if not idx['code'].endswith('.SZ') and not idx['code'].endswith('.SS')]

        # A股指数使用缓存
        if a_share_indices:
            a_codes = [idx['code'] for idx in a_share_indices]
            a_data = unified_stock_data_service.get_cached_quotes(a_codes, 'a_index_quote')

            for idx_info in a_share_indices:
                code = idx_info['code']
                region = idx_info.get('region', 'china_a')
                quote = a_data.get(code)
                if quote and quote.get('close') is not None:
                    indices_by_region[region].append({
                        'code': code,
                        'name': idx_info['name'],
                        'close': quote['close'],
                        'change_percent': quote.get('change_percent'),
                        'region': region,
                        'error': None
                    })
                else:
                    indices_by_region[region].append({
                        'code': code,
                        'name': idx_info['name'],
                        'close': None,
                        'change_percent': None,
                        'region': region,
                        'error': '无缓存数据'
                    })

        # 其他指数使用缓存
        if other_indices:
            yf_codes = [idx['code'] for idx in other_indices]
            yf_data = unified_stock_data_service.get_cached_quotes(yf_codes, 'briefing_index_yf')

            for idx_info in other_indices:
                code = idx_info['code']
                region = idx_info.get('region', 'asia')
                quote = yf_data.get(code)
                if quote and quote.get('close') is not None:
                    indices_by_region[region].append({
                        'code': code,
                        'name': idx_info['name'],
                        'close': quote['close'],
                        'change_percent': quote.get('change_percent'),
                        'region': region,
                        'error': None
                    })
                else:
                    indices_by_region[region].append({
                        'code': code,
                        'name': idx_info['name'],
                        'close': None,
                        'change_percent': None,
                        'region': region,
                        'error': '无缓存数据'
                    })

        # 移除空地区
        indices_by_region = {k: v for k, v in indices_by_region.items() if v}
        regions = [r for r in regions if r['key'] in indices_by_region]

        result = {
            'regions': regions,
            'indices': indices_by_region
        }

        return result

    @staticmethod
    def get_futures_data(force_refresh: bool = False) -> list:
        """获取期货数据

        使用缓存的收盘价数据，不发起实时API请求。

        Returns:
            期货数据列表，每项包含：
            - code: 期货代码
            - name: 期货名称
            - close: 收盘价格
            - change_percent: 涨跌幅
            - error: 错误信息（如有）
        """
        from app.services.unified_stock_data import unified_stock_data_service
        from app.models.unified_cache import UnifiedStockCache

        today = date.today()
        cache_type = 'briefing_futures'

        # 检查整体缓存（直接使用）
        cache_key = 'BRIEFING_FUTURES'
        cached = UnifiedStockCache.get_cached_data(cache_key, cache_type, today)
        if cached and isinstance(cached, list):
            return cached

        # 尝试获取过期缓存（最近7天）
        for days_ago in range(1, 8):
            cache_date = today - timedelta(days=days_ago)
            cached = UnifiedStockCache.get_cached_data(cache_key, cache_type, cache_date)
            if cached and isinstance(cached, list):
                logger.info(f"[期货数据] 使用{days_ago}天前的缓存")
                return cached

        # 使用缓存的单项数据
        futures_codes = [f['code'] for f in BRIEFING_FUTURES]
        yf_data = unified_stock_data_service.get_cached_quotes(futures_codes, 'briefing_futures_yf')

        result = []
        for futures_info in BRIEFING_FUTURES:
            code = futures_info['code']
            quote = yf_data.get(code)
            if quote and quote.get('close') is not None:
                result.append({
                    'code': code,
                    'name': futures_info['name'],
                    'close': quote['close'],
                    'change_percent': quote.get('change_percent'),
                    'error': None
                })
            else:
                result.append({
                    'code': code,
                    'name': futures_info['name'],
                    'close': None,
                    'change_percent': None,
                    'error': '无缓存数据'
                })

        return result

    @staticmethod
    def get_cn_sectors_data(force_refresh: bool = False) -> list:
        """获取A股行业板块涨幅前5

        通过 unified 服务获取板块数据（熔断保护+降级）。

        Returns:
            板块数据列表，每项包含：
            - name: 板块名称
            - change_percent: 涨跌幅
            - leader: 领涨股票
            - error: 错误信息（如有）
        """
        from app.services.unified_stock_data import unified_stock_data_service
        from app.models.unified_cache import UnifiedStockCache
        from app.services.cache_validator import CacheValidator

        today = date.today()
        cache_type = 'sector_cn'
        stock_code = 'SECTOR_CN'

        # 检查缓存
        if not force_refresh:
            need_refresh = CacheValidator.should_refresh([stock_code], cache_type, False, today)
            if stock_code not in need_refresh:
                cached = UnifiedStockCache.get_cached_data(stock_code, cache_type, today)
                if cached and isinstance(cached, list):
                    return cached

        all_sectors = unified_stock_data_service.get_cn_sector_data(force_refresh)
        if not all_sectors:
            return []

        # 按涨跌幅降序排序，取前5
        all_sectors.sort(key=lambda x: x.get('change_percent', 0), reverse=True)
        result = []
        for s in all_sectors[:5]:
            result.append({
                'name': s['name'],
                'change_percent': s['change_percent'],
                'leader': s.get('leader', ''),
                'error': None
            })

        # 保存缓存
        UnifiedStockCache.set_cached_data(stock_code, cache_type, result, today)
        return result

    @staticmethod
    def get_us_sectors_data(force_refresh: bool = False) -> list:
        """获取美股行业板块涨幅前5

        使用缓存的收盘价数据，不发起实时API请求。

        Returns:
            板块数据列表，每项包含：
            - code: ETF代码
            - name: 板块名称（中文）
            - change_percent: 涨跌幅
            - error: 错误信息（如有）
        """
        from app.services.unified_stock_data import unified_stock_data_service
        from app.models.unified_cache import UnifiedStockCache

        today = date.today()
        cache_type = 'sector_us'
        stock_code = 'SECTOR_US'

        # 检查整体缓存（直接使用）
        cached = UnifiedStockCache.get_cached_data(stock_code, cache_type, today)
        if cached and isinstance(cached, list):
            return cached

        # 尝试获取过期缓存（最近7天）
        for days_ago in range(1, 8):
            cache_date = today - timedelta(days=days_ago)
            cached = UnifiedStockCache.get_cached_data(stock_code, cache_type, cache_date)
            if cached and isinstance(cached, list):
                logger.info(f"[美股板块] 使用{days_ago}天前的缓存")
                return cached

        # 使用缓存的单项数据
        etf_codes = [etf['code'] for etf in US_SECTOR_ETFS]
        yf_data = unified_stock_data_service.get_cached_quotes(etf_codes, 'sector_us_yf')

        all_sectors = []
        for etf in US_SECTOR_ETFS:
            code = etf['code']
            quote = yf_data.get(code)
            if quote and quote.get('change_percent') is not None:
                all_sectors.append({
                    'code': code,
                    'name': etf['name'],
                    'change_percent': quote['change_percent'],
                    'error': None
                })

        # 按涨跌幅降序排序，取前5
        all_sectors.sort(key=lambda x: x['change_percent'], reverse=True)
        result = all_sectors[:5]

        return result

    @staticmethod
    def get_etf_nav(etf_code: str, force_refresh: bool = False) -> Optional[float]:
        """获取ETF净值

        通过 UnifiedStockDataService 获取 ETF 净值。

        Args:
            etf_code: ETF代码
            force_refresh: 是否强制刷新

        Returns:
            ETF净值，获取失败返回 None
        """
        from app.services.unified_stock_data import unified_stock_data_service

        result = unified_stock_data_service.get_etf_nav([etf_code], force_refresh)
        if etf_code in result:
            return result[etf_code].get('nav')
        return None

    @staticmethod
    def get_etf_premium_data(force_refresh: bool = False) -> list:
        """获取ETF溢价率数据

        获取 ETF 收盘价和净值，计算溢价率并生成买卖信号。
        使用缓存的收盘价数据，不发起实时API请求。
        溢价率 = (价格 / 净值 - 1) × 100%
        ≤3% 建议买入，≥6% 建议卖出，其他为正常区间。

        Returns:
            ETF溢价数据列表，每项包含：
            - code: ETF代码
            - name: ETF名称
            - price: 收盘价格
            - nav: 净值
            - premium_rate: 溢价率
            - signal: buy/sell/normal
            - error: 错误信息（如有）
        """
        from app.services.unified_stock_data import unified_stock_data_service

        result = []
        etf_codes = [etf['code'] for etf in BRIEFING_ETFS]

        # 使用缓存的收盘价，不发起实时API请求
        prices = unified_stock_data_service.get_closing_prices(etf_codes)

        for etf_info in BRIEFING_ETFS:
            code = etf_info['code']
            price_data = prices.get(code)

            # 检查数据有效且非降级
            if not price_data or price_data.get('_is_degraded'):
                result.append({
                    'code': code,
                    'name': etf_info['name'],
                    'price': None,
                    'nav': None,
                    'premium_rate': None,
                    'signal': None,
                    'error': '价格获取失败'
                })
                continue

            price = price_data.get('current_price')
            if not price:
                result.append({
                    'code': code,
                    'name': etf_info['name'],
                    'price': None,
                    'nav': None,
                    'premium_rate': None,
                    'signal': None,
                    'error': '价格数据无效'
                })
                continue

            # 获取净值
            nav = BriefingService.get_etf_nav(code, force_refresh)

            if not nav:
                result.append({
                    'code': code,
                    'name': etf_info['name'],
                    'price': round(price, 3),
                    'nav': None,
                    'premium_rate': None,
                    'signal': None,
                    'error': '无法计算溢价率'
                })
                continue

            # 计算溢价率
            premium_rate = (price / nav - 1) * 100

            # 判断信号
            if premium_rate <= BUY_THRESHOLD:
                signal = 'buy'
            elif premium_rate >= SELL_THRESHOLD:
                signal = 'sell'
            else:
                signal = 'normal'

            result.append({
                'code': code,
                'name': etf_info['name'],
                'price': round(price, 3),
                'nav': round(nav, 3),
                'premium_rate': round(premium_rate, 2),
                'signal': signal,
                'error': None
            })

        return result

    @staticmethod
    def get_cache_update_time() -> Optional[datetime]:
        """获取缓存的实际更新时间

        查询简报相关缓存记录中最早的 last_fetch_time。
        """
        from app.models.unified_cache import UnifiedStockCache

        today = date.today()
        cache_types = ['price', 'sector_cn', 'sector_us', 'etf_nav']

        cache = UnifiedStockCache.query.filter(
            UnifiedStockCache.cache_type.in_(cache_types),
            UnifiedStockCache.cache_date == today
        ).order_by(UnifiedStockCache.last_fetch_time.asc()).first()

        if cache and cache.last_fetch_time:
            return cache.last_fetch_time
        return None

    @staticmethod
    def get_earnings_alert_data() -> dict:
        """获取财报预警数据

        从预警中心选中的股票中筛选未来7天内发布财报的股票。

        Returns:
            {
                'earnings_alerts': [
                    {
                        'code': 'TSLA',
                        'name': '特斯拉',
                        'earnings_date': '2024-01-24',
                        'days_until': 3,
                        'display_text': '3天后'
                    }
                ],
                'has_alerts': True
            }
        """
        from app.services.earnings import EarningsService
        from app.routes.alert import get_categories, get_stocks_by_category

        try:
            # 获取所有分类的股票
            categories = get_categories()
            all_stock_codes = set()

            for cat in categories:
                stocks = get_stocks_by_category(cat['id'])
                for stock in stocks:
                    all_stock_codes.add(stock['stock_code'])

            if not all_stock_codes:
                return {'earnings_alerts': [], 'has_alerts': False}

            # 获取股票名称映射
            from app.models.stock import Stock
            stock_name_map = {}
            stocks = Stock.query.filter(Stock.stock_code.in_(all_stock_codes)).all()
            for s in stocks:
                stock_name_map[s.stock_code] = s.stock_name

            # 获取未来7天内发布财报的股票
            upcoming = EarningsService.get_upcoming_earnings(list(all_stock_codes), days=7)

            # 格式化结果
            alerts = []
            for item in upcoming:
                code = item['code']
                days_until = item['days_until']
                display_text = '今日发布' if item['is_today'] else f"{days_until}天后"

                alerts.append({
                    'stock_code': code,
                    'stock_name': stock_name_map.get(code, item['name']),
                    'earnings_date': item['earnings_date'],
                    'days_until': days_until,
                    'is_today': item['is_today'],
                    'display_text': display_text
                })

            return {
                'earnings_alerts': alerts,
                'has_alerts': len(alerts) > 0
            }

        except Exception as e:
            logger.warning(f"获取财报预警数据失败: {e}")
            return {'earnings_alerts': [], 'has_alerts': False}

    @staticmethod
    def get_stocks_technical_data(force_refresh: bool = False) -> dict:
        """获取股票技术指标数据（评分+MACD信号）"""
        from app.services.unified_stock_data import unified_stock_data_service
        from app.services.technical_indicators import TechnicalIndicatorService

        stock_codes = [s['code'] for s in BRIEFING_STOCKS]

        try:
            trend_result = unified_stock_data_service.get_trend_data(stock_codes, days=60, force_refresh=force_refresh)
        except Exception as e:
            logger.warning(f"获取走势数据失败: {e}")
            return {}

        result = {}
        stocks_data = trend_result.get('stocks', [])
        for stock in stocks_data:
            code = stock.get('stock_code', '')
            ohlcv = stock.get('data', [])
            if not ohlcv:
                continue

            # 转换为dict格式（如果是OHLCData对象）
            if hasattr(ohlcv[0], 'to_dict'):
                ohlcv = [d.to_dict() for d in ohlcv]

            indicators = TechnicalIndicatorService.calculate_all(ohlcv)
            if indicators:
                result[code] = {
                    'score': indicators['score'],
                    'signal': indicators['signal'],
                    'signal_text': indicators['signal_text'],
                    'macd_signal': indicators['macd']['signal'],
                    'rsi_6': indicators['rsi'].get('rsi_6', 0),
                    'rsi_status': indicators['rsi']['status'],
                    'bias_20': indicators['bias']['bias_20'],
                    'bias_warning': indicators['bias']['warning'],
                    'trend_state': indicators['trend']['state'],
                }

        return result

    @staticmethod
    def get_sector_ratings(stocks_data: dict = None, force_refresh: bool = False) -> dict:
        """获取板块评级数据

        根据美股存储板块（WDC、MU、SNDK）的表现，计算综合评分并生成评级。
        评分算法：涨跌幅(60%) + 一致性(30%) + 成交量(10%)

        Args:
            stocks_data: 已获取的股票数据，避免重复请求
            force_refresh: 是否强制刷新

        Returns:
            {
                'storage': {
                    'name': '存储板块',
                    'rating': 'bullish/neutral/bearish',
                    'score': 75,
                    'details': {...},
                    'stocks': [...]
                }
            }
        """
        from app.services.unified_stock_data import unified_stock_data_service

        ratings = {}

        for sector_id, config in SECTOR_RATING_CONFIG.items():
            sector_stocks = config['stocks']
            weights = config['weights']
            thresholds = config['thresholds']

            # 获取股票数据
            stock_list = []
            if stocks_data and 'stocks' in stocks_data:
                # 从已有数据中提取
                for cat_stocks in stocks_data['stocks'].values():
                    for s in cat_stocks:
                        if s['code'] in sector_stocks:
                            stock_list.append({
                                'code': s['code'],
                                'name': s['name'],
                                'change_pct': s.get('change_percent'),
                                'volume': s.get('volume')
                            })
            else:
                # 使用缓存的收盘价
                prices = unified_stock_data_service.get_closing_prices(sector_stocks)
                for code in sector_stocks:
                    price_data = prices.get(code, {})
                    stock_list.append({
                        'code': code,
                        'name': price_data.get('name', code),
                        'change_pct': price_data.get('change_percent'),
                        'volume': price_data.get('volume')
                    })

            # 计算评分
            score, details = BriefingService._calculate_sector_score(stock_list, weights)

            # 映射评级
            if score >= thresholds['bullish']:
                rating = 'bullish'
            elif score < thresholds['bearish']:
                rating = 'bearish'
            else:
                rating = 'neutral'

            ratings[sector_id] = {
                'name': config['name'],
                'rating': rating,
                'score': round(score, 1),
                'details': details,
                'stocks': stock_list
            }

        return ratings

    @staticmethod
    def _calculate_sector_score(stocks: list, weights: dict) -> tuple:
        """计算板块综合评分

        Args:
            stocks: 股票列表，每项包含 change_pct 和 volume
            weights: 权重配置 {'change': 0.6, 'consistency': 0.3, 'volume': 0.1}

        Returns:
            (总分, 详情字典)
        """
        valid_stocks = [s for s in stocks if s.get('change_pct') is not None]

        if not valid_stocks:
            return 50, {'avg_change': 0, 'change_score': 30, 'consistency': '无数据', 'consistency_score': 15, 'volume_score': 5}

        # 1. 涨跌幅得分（60%）
        changes = [s['change_pct'] for s in valid_stocks]
        avg_change = sum(changes) / len(changes)
        # 线性映射：-2% -> 0, +2% -> 60
        change_score = max(0, min(60, (avg_change + 2) / 4 * 60)) * weights['change'] / 0.6

        # 2. 一致性得分（30%）
        up_count = sum(1 for c in changes if c > 0)
        down_count = sum(1 for c in changes if c < 0)
        total = len(changes)

        if up_count == total or down_count == total:
            consistency_score = 30 * weights['consistency'] / 0.3
            consistency_text = f"{total}涨0跌" if up_count == total else f"0涨{total}跌"
        else:
            consistency_score = 15 * weights['consistency'] / 0.3
            consistency_text = f"{up_count}涨{down_count}跌"

        # 3. 成交量得分（10%）- 简化处理，暂时给固定分数
        # 实际应该比较前日成交量，但需要额外API调用
        volume_score = 5 * weights['volume'] / 0.1

        total_score = change_score + consistency_score + volume_score

        details = {
            'avg_change': round(avg_change, 2),
            'change_score': round(change_score, 1),
            'consistency': consistency_text,
            'consistency_score': round(consistency_score, 1),
            'volume_score': round(volume_score, 1)
        }

        return total_score, details
