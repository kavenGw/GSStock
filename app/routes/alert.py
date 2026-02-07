import logging
import time
from datetime import date, timedelta
from flask import render_template, jsonify, request
from app.routes import alert_bp
from app.services.signal_cache import SignalCacheService
from app.services.position import PositionService
from app.services.earnings import EarningsService
from app.models.category import Category, StockCategory
from app.models.stock import Stock
from app.utils.market_identifier import MarketIdentifier

logger = logging.getLogger(__name__)


def get_categories() -> list:
    """获取分类列表（含持仓股和用户分类，只统计A股）"""
    # 获取持仓股数量（只统计A股）
    latest_date = PositionService.get_latest_date()
    position_count = 0
    if latest_date:
        positions = PositionService.get_snapshot(latest_date)
        position_count = sum(1 for p in positions if MarketIdentifier.is_a_share(p.stock_code))

    # 获取用户分类
    categories = Category.query.filter_by(parent_id=None).all()

    # 统计各分类下的股票数量（只统计A股）
    all_stock_cats = StockCategory.query.all()
    cat_count = {}
    for sc in all_stock_cats:
        if sc.category_id and MarketIdentifier.is_a_share(sc.stock_code):
            cat_count[sc.category_id] = cat_count.get(sc.category_id, 0) + 1

    result = [
        {'id': -1, 'name': '持仓股', 'count': position_count},
    ]

    for cat in categories:
        count = cat_count.get(cat.id, 0)
        for child in cat.children:
            count += cat_count.get(child.id, 0)
        result.append({
            'id': cat.id,
            'name': cat.name,
            'count': count,
        })

    return result


def get_stocks_by_category(category_id: int) -> list:
    """按分类获取股票列表"""
    if category_id == -1:
        # 持仓股（只保留A股）
        latest_date = PositionService.get_latest_date()
        if not latest_date:
            return []
        positions = PositionService.get_snapshot(latest_date)
        return [{'stock_code': p.stock_code, 'stock_name': p.stock_name}
                for p in positions if MarketIdentifier.is_a_share(p.stock_code)]

    # 用户分类
    category = Category.query.get(category_id)
    if not category:
        return []

    cat_ids = [category_id]
    for child in category.children:
        cat_ids.append(child.id)

    stock_cats = StockCategory.query.filter(
        StockCategory.category_id.in_(cat_ids)
    ).all()

    result = []
    for sc in stock_cats:
        # 只保留A股
        if not MarketIdentifier.is_a_share(sc.stock_code):
            continue
        stock = Stock.query.filter_by(stock_code=sc.stock_code).first()
        stock_name = stock.stock_name if stock else sc.stock_code
        result.append({
            'stock_code': sc.stock_code,
            'stock_name': stock_name
        })

    return result


@alert_bp.route('/')
def index():
    """预警页面"""
    categories = get_categories()
    return render_template('alert.html', categories=categories)


@alert_bp.route('/api/data')
def get_alert_data():
    """获取指定分类的预警数据"""
    start_time = time.time()
    days = request.args.get('days', 60, type=int)
    categories_param = request.args.get('categories', '')
    target_date = date.today()

    # 解析启用的分类 ID
    enabled_category_ids = set()
    if categories_param:
        for cat_id in categories_param.split(','):
            try:
                enabled_category_ids.add(int(cat_id.strip()))
            except ValueError:
                pass

    logger.info(f'[alert/data] 开始处理请求, days={days}, enabled_categories={enabled_category_ids or "all"}')

    result = {
        'categories': [],
        'stocks': [],
        'ohlc_data': {},
        'signals': {'buy_signals': [], 'sell_signals': []},
        'earnings_data': {}
    }

    try:
        # 获取所有分类
        categories = get_categories()
        logger.info(f'[alert/data] 获取到 {len(categories)} 个分类: {[c["name"] for c in categories]}')
        result['categories'] = categories

        # 只收集启用分类的股票
        all_stocks = []
        stock_name_map = {}

        # 未启用任何分类时不获取股票数据
        if not enabled_category_ids:
            logger.info('[alert/data] 未启用任何分类，跳过股票数据获取')
            return jsonify(result)

        for cat in categories:
            if cat['id'] not in enabled_category_ids:
                continue

            stocks = get_stocks_by_category(cat['id'])
            for stock in stocks:
                stock_copy = stock.copy()
                stock_copy['category_id'] = cat['id']
                stock_copy['category_name'] = cat['name']
                all_stocks.append(stock_copy)
                stock_name_map[stock['stock_code']] = stock['stock_name']

        # 统计各分类股票数
        cat_stats = {}
        for stock in all_stocks:
            cat_name = stock.get('category_name', '未分类')
            cat_stats[cat_name] = cat_stats.get(cat_name, 0) + 1
        logger.info(f'[alert/data] 共 {len(all_stocks)} 只股票: {cat_stats}')

        if not all_stocks:
            return jsonify(result)

        stock_codes = [s['stock_code'] for s in all_stocks]

        # 获取 OHLC 数据
        trend_data = PositionService.get_trend_data(stock_codes, target_date, days=days)

        if trend_data and trend_data.get('stocks'):
            # 构建 ohlc_data 映射
            for stock_data in trend_data['stocks']:
                code = stock_data.get('stock_code')
                result['ohlc_data'][code] = stock_data.get('data', [])
            logger.info(f'[alert/data] 获取到 {len(result["ohlc_data"])} 只股票的走势数据')

            # 信号检测：使用年数据计算并缓存
            year_result = PositionService.get_trend_data(stock_codes, target_date, days=365)
            if year_result and year_result.get('stocks'):
                SignalCacheService.update_signals_from_trend_data(year_result, stock_name_map)

            # 获取信号
            end_date = target_date
            start_date = end_date - timedelta(days=days)
            all_signals = SignalCacheService.get_cached_signals_with_names(
                stock_codes, stock_name_map, start_date, end_date
            )
            result['signals'] = all_signals
            buy_count = len(result['signals'].get('buy_signals', []))
            sell_count = len(result['signals'].get('sell_signals', []))
            logger.info(f'[alert/data] 信号检测完成: 买入{buy_count}, 卖出{sell_count}')

        # 获取投资建议
        advice_map = {}
        try:
            stocks_with_advice = Stock.query.filter(Stock.stock_code.in_(stock_codes)).all()
            advice_map = {s.stock_code: s.investment_advice for s in stocks_with_advice if s.investment_advice}
        except Exception as e:
            logger.warning(f'[alert/data] 获取投资建议失败: {e}')

        # 转换股票数据格式
        result['stocks'] = [{
            'code': s['stock_code'],
            'name': s['stock_name'],
            'categoryId': s['category_id'],
            'categoryName': s['category_name'],
            'investment_advice': advice_map.get(s['stock_code'])
        } for s in all_stocks]

        # 获取财报数据
        try:
            logger.info(f'[alert/data] 开始获取 {len(stock_codes)} 只股票的财报/PE数据')
            earnings_dates = EarningsService.get_earnings_dates(stock_codes)
            pe_ratios = EarningsService.get_pe_ratios(stock_codes)

            valid_pe_count = 0
            valid_earnings_count = 0
            for code in stock_codes:
                earnings = earnings_dates.get(code, {})
                pe = pe_ratios.get(code, {})
                result['earnings_data'][code] = {
                    'last_earnings_date': earnings.get('last_earnings_date'),
                    'next_earnings_date': earnings.get('next_earnings_date'),
                    'days_until_next': earnings.get('days_until_next'),
                    'is_today': earnings.get('is_today', False),
                    'pe_ttm': pe.get('pe_ttm'),
                    'pe_display': pe.get('pe_display', '暂无数据'),
                    'pe_status': pe.get('pe_status', 'na'),
                    'market': earnings.get('market', 'unknown')
                }
                if pe.get('pe_ttm') is not None:
                    valid_pe_count += 1
                if earnings.get('next_earnings_date'):
                    valid_earnings_count += 1

            logger.info(f'[alert/data] 财报数据完成: 总{len(result["earnings_data"])}只, 有效PE:{valid_pe_count}, 有效财报日期:{valid_earnings_count}')
        except Exception as e:
            logger.error(f'[alert/data] 获取财报数据失败: {e}', exc_info=True)

        return jsonify(result)
    except Exception as e:
        logger.error(f'[alert/data] 处理失败: {e}', exc_info=True)
        return jsonify({'error': str(e)}), 500
    finally:
        elapsed = time.time() - start_time
        logger.info(f'[alert/data] 请求完成, 耗时 {elapsed:.2f}s')
