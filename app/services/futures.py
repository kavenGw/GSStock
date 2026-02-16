import logging
from datetime import date, datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

from app.utils.db_retry import with_db_retry

from app import db
from app.models.metal_trend_cache import MetalTrendCache
from app.models.index_trend_cache import IndexTrendCache
from app.services.valuation import ValuationService
from app.config.stock_codes import (
    FUTURES_CODES, INDEX_CODES, CATEGORY_CODES, CATEGORY_NAMES
)

logger = logging.getLogger(__name__)


class CategoryCodeResolver:
    @staticmethod
    def get_codes_for_category(category: str) -> list[str]:
        """返回给定分类的代码列表

        合并配置文件中的期货/指数代码 + 数据库中该分类的股票

        Args:
            category: 分类标识符 ('heavy_metals', 'gold', 'copper', 'aluminum', 'silver', 'etf', 'positions', 'custom')

        Returns:
            股票/期货代码列表
        """
        if category == 'etf':
            return CategoryCodeResolver._get_etf_codes()

        if category == 'positions':
            return CategoryCodeResolver._get_position_codes()

        # 配置文件中的非股票代码
        config_codes = CATEGORY_CODES.get(category, [])

        # 从数据库获取该分类的股票
        db_codes = CategoryCodeResolver._get_stocks_for_category(category)

        # 合并，配置代码在前
        all_codes = list(config_codes)
        for code in db_codes:
            if code not in all_codes:
                all_codes.append(code)

        return all_codes

    @staticmethod
    def _get_stocks_for_category(category: str) -> list[str]:
        """从数据库获取指定分类的股票代码"""
        from app.models.category import Category, StockCategory

        # 分类标识到中文名称的映射
        category_name = CATEGORY_NAMES.get(category)
        if not category_name:
            return []

        # 查找分类（支持父分类和子分类）
        codes = []
        categories = Category.query.filter(Category.name == category_name).all()
        for cat in categories:
            # 获取该分类下的所有股票
            stock_categories = StockCategory.query.filter_by(category_id=cat.id).all()
            codes.extend([sc.stock_code for sc in stock_categories])
            # 获取子分类的股票
            for child in cat.children:
                child_scs = StockCategory.query.filter_by(category_id=child.id).all()
                codes.extend([sc.stock_code for sc in child_scs])

        return codes

    @staticmethod
    def _get_etf_codes() -> list[str]:
        """动态获取所有ETF代码"""
        from app.models.stock import Stock
        codes = []
        # 从 FUTURES_CODES 获取 ETF
        for code, info in FUTURES_CODES.items():
            if 'ETF' in info['name'].upper():
                codes.append(code)
        # 从 Stock 表获取 ETF
        for stock in Stock.query.all():
            if 'ETF' in stock.stock_name.upper() and stock.stock_code not in codes:
                codes.append(stock.stock_code)
        return codes

    @staticmethod
    def _get_position_codes() -> list[str]:
        """从最新持仓快照获取股票代码"""
        from app.services.position import PositionService

        latest_date = PositionService.get_latest_date()
        if not latest_date:
            return []

        positions = PositionService.get_snapshot(latest_date)
        codes = [p.stock_code for p in positions if p.stock_code]
        return codes

    @staticmethod
    def get_category_name(category: str) -> str:
        """返回分类的显示名称

        Args:
            category: 分类标识符

        Returns:
            分类显示名称
        """
        return CATEGORY_NAMES.get(category, category)


class TradingAdviceCalculator:
    @staticmethod
    def calculate_advice(trend_data: dict, timeframe: str) -> dict:
        """根据走势数据计算交易建议

        Args:
            trend_data: FuturesService 返回的数据格式，包含 stocks 和 data points
            timeframe: '7d', '30d', 或 '365d'

        Returns:
            {
                'overall': 'buy'|'sell'|'hold'|'watch',
                'stocks': [
                    {
                        'code': 'AU0',
                        'name': '沪金主连',
                        'advice': 'buy',
                        'reason': '月度涨幅 +8.5%',
                        'change_pct': 8.5
                    },
                    ...
                ]
            }
        """
        if not trend_data or not trend_data.get('stocks'):
            return {'overall': 'watch', 'stocks': []}

        timeframe_map = {'7d': '7天', '30d': '月度', '365d': '年度'}
        timeframe_name = timeframe_map.get(timeframe, timeframe)

        stock_advices = []
        advice_scores = {'buy': 2, 'hold': 1, 'watch': 0, 'sell': -1}
        total_score = 0

        for stock in trend_data['stocks']:
            if not stock.get('data') or len(stock['data']) < 2:
                continue

            # 计算整体涨跌幅（基于最后一个数据点的 change_pct）
            last_data_point = stock['data'][-1]
            change_pct = last_data_point.get('change_pct', 0)

            advice = TradingAdviceCalculator.get_advice_for_change(change_pct)
            reason = f"{timeframe_name}涨幅 {'+' if change_pct >= 0 else ''}{change_pct:.1f}%"

            stock_advices.append({
                'code': stock['stock_code'],
                'name': stock['stock_name'],
                'advice': advice,
                'reason': reason,
                'change_pct': change_pct
            })

            total_score += advice_scores.get(advice, 0)

        # 计算总体建议
        if not stock_advices:
            overall = 'watch'
        else:
            avg_score = total_score / len(stock_advices)
            if avg_score > 1.5:
                overall = 'buy'
            elif avg_score > 0.5:
                overall = 'hold'
            elif avg_score > -0.5:
                overall = 'watch'
            else:
                overall = 'sell'

        return {
            'overall': overall,
            'stocks': stock_advices
        }

    @staticmethod
    def get_advice_for_change(change_pct: float) -> str:
        """将百分比涨跌幅映射到建议类别

        逻辑:
        - change_pct > 5%: 'buy' (强势上涨)
        - 2% < change_pct <= 5%: 'hold' (弱势上涨，持有现有仓位)
        - -2% <= change_pct <= 2%: 'watch' (中性，等待方向)
        - -5% <= change_pct < -2%: 'hold' (弱势下跌，持有观望)
        - change_pct < -5%: 'sell' (强势下跌)
        """
        if change_pct > 5:
            return 'buy'
        elif 2 < change_pct <= 5:
            return 'hold'
        elif -2 <= change_pct <= 2:
            return 'watch'
        elif -5 <= change_pct < -2:
            return 'hold'
        else:  # change_pct < -5
            return 'sell'


class FuturesService:
    @staticmethod
    def _get_cached_prices(metal_code: str, start_date: date, end_date: date) -> dict[date, dict]:
        """查询缓存中的价格和成交量数据"""
        cached = MetalTrendCache.query.filter(
            MetalTrendCache.metal_code == metal_code,
            MetalTrendCache.date >= start_date,
            MetalTrendCache.date <= end_date
        ).all()
        return {c.date: {'price': c.price, 'volume': c.volume} for c in cached}

    @staticmethod
    @with_db_retry
    def _save_to_cache(metal_code: str, data_points: list[dict]):
        """保存价格和成交量数据到缓存"""
        for dp in data_points:
            dp_date = datetime.strptime(dp['date'], '%Y-%m-%d').date()
            existing = MetalTrendCache.query.filter_by(
                metal_code=metal_code,
                date=dp_date
            ).first()
            if existing:
                existing.price = dp['price']
                existing.volume = dp.get('volume')
                existing.created_at = datetime.utcnow()
            else:
                cache = MetalTrendCache(
                    metal_code=metal_code,
                    date=dp_date,
                    price=dp['price'],
                    volume=dp.get('volume')
                )
                db.session.add(cache)
        db.session.commit()

    @staticmethod
    def _get_cached_index_prices(index_code: str, start_date: date, end_date: date) -> dict[date, dict]:
        """查询缓存中的指数价格和成交量数据"""
        cached = IndexTrendCache.query.filter(
            IndexTrendCache.index_code == index_code,
            IndexTrendCache.date >= start_date,
            IndexTrendCache.date <= end_date
        ).all()
        return {c.date: {'price': c.price, 'volume': c.volume} for c in cached}

    @staticmethod
    @with_db_retry
    def _save_index_to_cache(index_code: str, data_points: list[dict]):
        """保存指数价格和成交量数据到缓存"""
        for dp in data_points:
            dp_date = datetime.strptime(dp['date'], '%Y-%m-%d').date()
            existing = IndexTrendCache.query.filter_by(
                index_code=index_code,
                date=dp_date
            ).first()
            if existing:
                existing.price = dp['price']
                existing.volume = dp.get('volume')
                existing.created_at = datetime.utcnow()
            else:
                cache = IndexTrendCache(
                    index_code=index_code,
                    date=dp_date,
                    price=dp['price'],
                    volume=dp.get('volume')
                )
                db.session.add(cache)
        db.session.commit()

    @staticmethod
    def _fetch_from_api(code: str, info: dict, start_date: date, end_date: date, days: int) -> tuple[str, list[dict] | None]:
        """通过统一服务获取数据"""
        from app.services.unified_stock_data import unified_stock_data_service

        try:
            yf_code = info['yf_code']
            result = unified_stock_data_service.get_trend_data([yf_code], days)
            stocks = result.get('stocks', [])

            if not stocks:
                return code, None

            stock_data = stocks[0]
            ohlc_data = stock_data.get('data', [])

            if len(ohlc_data) < 2:
                return code, None

            data_points = []
            for dp in ohlc_data:
                data_points.append({
                    'date': dp['date'],
                    'price': round(float(dp['close']), 2),
                    'volume': dp.get('volume')
                })

            return code, data_points
        except Exception as e:
            logger.warning(f"[期货] 获取 {code} 数据失败: {e}")
            return code, None

    @staticmethod
    def get_trend_data(days: int = 30, force_refresh: bool = False) -> dict:
        """获取重金属期货30天走势数据，支持缓存"""
        today = date.today()
        end_date = today
        start_date = end_date - timedelta(days=days + 10)

        cached_count = 0
        fetched_count = 0
        last_update = None

        # 1. 在主线程中获取所有缓存数据
        all_cached_data = {}
        codes_to_fetch = []
        for code in FUTURES_CODES:
            cached_data = FuturesService._get_cached_prices(code, start_date, end_date)
            all_cached_data[code] = cached_data

            # 判断是否需要从 API 获取
            if force_refresh or today not in cached_data or len(cached_data) < days // 2:
                codes_to_fetch.append(code)

        # 2. 并发获取 API 数据（不涉及数据库操作）
        api_results = {}
        if codes_to_fetch:
            with ThreadPoolExecutor(max_workers=4) as executor:
                futures = {
                    executor.submit(
                        FuturesService._fetch_from_api,
                        code,
                        FUTURES_CODES[code],
                        start_date,
                        end_date,
                        days
                    ): code
                    for code in codes_to_fetch
                }
                for future in as_completed(futures):
                    code, data_points = future.result()
                    if data_points:
                        api_results[code] = data_points

        # 3. 在主线程中保存到缓存
        for code, data_points in api_results.items():
            FuturesService._save_to_cache(code, data_points)
            fetched_count += len(data_points)
            last_update = datetime.now()

        # 4. 合并数据并生成结果
        results = []
        for code, info in FUTURES_CODES.items():
            cached_data = all_cached_data.get(code, {})

            # 如果有 API 数据，转换并合并
            if code in api_results:
                for dp in api_results[code]:
                    dp_date = datetime.strptime(dp['date'], '%Y-%m-%d').date()
                    cached_data[dp_date] = {'price': dp['price'], 'volume': dp.get('volume')}

            # 过滤出目标日期范围的数据
            filtered_dates = sorted([d for d in cached_data.keys() if d >= (end_date - timedelta(days=days))])[-days:]

            if len(filtered_dates) < 2:
                continue

            # 计算归一化涨跌幅
            base_price = cached_data[filtered_dates[0]]['price']
            data_points = []
            for d in filtered_dates:
                item = cached_data[d]
                price = item['price']
                change_pct = (price - base_price) / base_price * 100
                data_points.append({
                    'date': d.strftime('%Y-%m-%d'),
                    'price': round(price, 2),
                    'change_pct': round(change_pct, 2),
                    'volume': item.get('volume')
                })

            # 计算缓存命中数
            if code not in api_results:
                cached_count += len(filtered_dates)

            # 计算估值
            prices = [dp['price'] for dp in data_points]
            valuation = ValuationService.calculate_valuation(code, prices)

            results.append({
                'stock_code': code,
                'stock_name': info['name'],
                'data': data_points,
                'valuation': valuation
            })

        # 获取日期范围
        all_dates = set()
        for r in results:
            for dp in r['data']:
                all_dates.add(dp['date'])

        sorted_dates = sorted(all_dates)
        date_range = {
            'start': sorted_dates[0] if sorted_dates else None,
            'end': sorted_dates[-1] if sorted_dates else None
        }

        return {
            'stocks': results,
            'date_range': date_range,
            'cache_info': {
                'cached_count': cached_count,
                'fetched_count': fetched_count,
                'last_update': last_update.strftime('%Y-%m-%d %H:%M:%S') if last_update else None
            }
        }

    @staticmethod
    def get_index_trend_data(days: int = 30, force_refresh: bool = False) -> dict:
        """获取指数30天走势数据，支持缓存"""
        today = date.today()
        end_date = today
        start_date = end_date - timedelta(days=days + 10)

        cached_count = 0
        fetched_count = 0
        last_update = None

        all_cached_data = {}
        codes_to_fetch = []
        for code in INDEX_CODES:
            cached_data = FuturesService._get_cached_index_prices(code, start_date, end_date)
            all_cached_data[code] = cached_data

            if force_refresh or today not in cached_data or len(cached_data) < days // 2:
                codes_to_fetch.append(code)

        api_results = {}
        if codes_to_fetch:
            with ThreadPoolExecutor(max_workers=4) as executor:
                futures = {
                    executor.submit(
                        FuturesService._fetch_from_api,
                        code,
                        INDEX_CODES[code],
                        start_date,
                        end_date,
                        days
                    ): code
                    for code in codes_to_fetch
                }
                for future in as_completed(futures):
                    code, data_points = future.result()
                    if data_points:
                        api_results[code] = data_points

        for code, data_points in api_results.items():
            FuturesService._save_index_to_cache(code, data_points)
            fetched_count += len(data_points)
            last_update = datetime.now()

        results = []
        for code, info in INDEX_CODES.items():
            cached_data = all_cached_data.get(code, {})

            if code in api_results:
                for dp in api_results[code]:
                    dp_date = datetime.strptime(dp['date'], '%Y-%m-%d').date()
                    cached_data[dp_date] = {'price': dp['price'], 'volume': dp.get('volume')}

            filtered_dates = sorted([d for d in cached_data.keys() if d >= (end_date - timedelta(days=days))])[-days:]

            if len(filtered_dates) < 2:
                continue

            base_price = cached_data[filtered_dates[0]]['price']
            data_points = []
            for d in filtered_dates:
                item = cached_data[d]
                price = item['price']
                change_pct = (price - base_price) / base_price * 100
                data_points.append({
                    'date': d.strftime('%Y-%m-%d'),
                    'price': round(price, 2),
                    'change_pct': round(change_pct, 2),
                    'volume': item.get('volume')
                })

            if code not in api_results:
                cached_count += len(filtered_dates)

            # 计算估值
            prices = [dp['price'] for dp in data_points]
            valuation = ValuationService.calculate_valuation(code, prices)

            results.append({
                'stock_code': code,
                'stock_name': info['name'],
                'data': data_points,
                'valuation': valuation
            })

        all_dates = set()
        for r in results:
            for dp in r['data']:
                all_dates.add(dp['date'])

        sorted_dates = sorted(all_dates)
        date_range = {
            'start': sorted_dates[0] if sorted_dates else None,
            'end': sorted_dates[-1] if sorted_dates else None
        }

        return {
            'stocks': results,
            'date_range': date_range,
            'cache_info': {
                'cached_count': cached_count,
                'fetched_count': fetched_count,
                'last_update': last_update.strftime('%Y-%m-%d %H:%M:%S') if last_update else None
            }
        }

    @staticmethod
    def get_custom_trend_data(codes: list[str], days: int = 30) -> dict:
        """获取自定义走势数据（通过统一服务）"""
        from app.services.unified_stock_data import unified_stock_data_service
        from app.models.stock import Stock

        if not codes:
            return {'stocks': [], 'date_range': {'start': None, 'end': None}}

        # 构建代码到名称的映射
        name_map = {}
        yf_codes = []

        for code in codes:
            if code in FUTURES_CODES:
                name_map[FUTURES_CODES[code]['yf_code']] = FUTURES_CODES[code]['name']
                yf_codes.append(FUTURES_CODES[code]['yf_code'])
            elif code in INDEX_CODES:
                name_map[INDEX_CODES[code]['yf_code']] = INDEX_CODES[code]['name']
                yf_codes.append(INDEX_CODES[code]['yf_code'])
            else:
                # 股票
                stock = Stock.query.filter_by(stock_code=code).first()
                name_map[code] = stock.stock_name if stock else code
                yf_codes.append(code)

        # 通过统一服务获取数据
        result = unified_stock_data_service.get_trend_data(yf_codes, days)

        # 转换结果格式
        results = []
        all_dates = set()

        for stock_data in result.get('stocks', []):
            stock_code = stock_data['stock_code']
            data_list = stock_data.get('data', [])

            if len(data_list) < 2:
                continue

            # 转换为价格格式
            data_points = []
            for dp in data_list:
                data_points.append({
                    'date': dp['date'],
                    'price': dp['close'],
                    'change_pct': dp.get('change_pct', 0),
                    'volume': dp.get('volume')
                })
                all_dates.add(dp['date'])

            # 找回原始代码
            original_code = stock_code
            for code in codes:
                if code in FUTURES_CODES and FUTURES_CODES[code]['yf_code'] == stock_code:
                    original_code = code
                    break
                elif code in INDEX_CODES and INDEX_CODES[code]['yf_code'] == stock_code:
                    original_code = code
                    break

            results.append({
                'stock_code': original_code,
                'stock_name': name_map.get(stock_code, stock_code),
                'data': data_points
            })

        sorted_dates = sorted(all_dates)
        return {
            'stocks': results,
            'date_range': {
                'start': sorted_dates[0] if sorted_dates else None,
                'end': sorted_dates[-1] if sorted_dates else None
            }
        }

    @staticmethod
    def get_available_codes() -> dict:
        """获取可选数据项列表，分组显示"""
        from app.models.stock import Stock
        from app.models.category import StockCategory

        indices = [{'code': code, 'name': info['name']} for code, info in INDEX_CODES.items()]

        # 期货分为普通期货和 ETF
        futures_list = []
        etfs = []
        for code, info in FUTURES_CODES.items():
            item = {'code': code, 'name': info['name']}
            if 'ETF' in info['name'].upper():
                etfs.append(item)
            else:
                futures_list.append(item)

        # 获取股票板块映射（从 StockCategory 表）
        stock_cat_map = {}
        for sc in StockCategory.query.all():
            if sc.category:
                stock_cat_map[sc.stock_code] = sc.category.name

        # 股票按板块分组（从 Stock 表获取所有股票）
        stock_groups = {}
        added_codes = set()

        # 从 Stock 表获取所有股票
        for stock in Stock.query.all():
            code = stock.stock_code
            name = stock.stock_name

            # ETF 单独分组
            if 'ETF' in name.upper():
                etfs.append({'code': code, 'name': name})
                added_codes.add(code)
                continue

            # 从数据库获取分类
            cat_name = stock_cat_map.get(code, '其他')
            if cat_name not in stock_groups:
                stock_groups[cat_name] = []
            stock_groups[cat_name].append({'code': code, 'name': name})
            added_codes.add(code)

        return {
            'indices': indices,
            'futures': futures_list,
            'etfs': etfs,
            'stock_groups': stock_groups
        }

    @staticmethod
    def get_category_trend_data(category: str, days: int = 30, force_refresh: bool = False) -> dict:
        """获取特定分类的走势数据

        Args:
            category: 分类标识符 ('heavy_metals', 'gold', 'copper', 'aluminum', 'silver')
            days: 历史数据天数
            force_refresh: 强制刷新（即使有缓存也从 API 获取）

        Returns:
            与 get_trend_data() 相同格式: {stocks: [...], date_range: {...}, cache_info: {...}}
        """
        codes = CategoryCodeResolver.get_codes_for_category(category)
        return FuturesService.get_custom_trend_data(codes, days)
