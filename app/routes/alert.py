import logging
from datetime import date, timedelta
from flask import render_template, jsonify, request
from app.routes import alert_bp
from app.services.signal_cache import SignalCacheService
from app.services.position import PositionService
from app.services.earnings import EarningsService
from app.services.backtest import BacktestService
from app.models.category import Category, StockCategory
from app.models.stock import Stock
from app.utils.market_identifier import MarketIdentifier
from app.utils.log_utils import log_operation

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
    """获取指定分类的预警数据（快速路径：只做DB查询+60天OHLC+已缓存信号）"""
    days = request.args.get('days', 60, type=int)
    categories_param = request.args.get('categories', '')
    target_date = date.today()

    enabled_category_ids = set()
    if categories_param:
        for cat_id in categories_param.split(','):
            try:
                enabled_category_ids.add(int(cat_id.strip()))
            except ValueError:
                pass

    result = {
        'categories': [],
        'stocks': [],
        'ohlc_data': {},
        'signals': {'buy_signals': [], 'sell_signals': []},
    }

    with log_operation(logger, "预警.数据") as op:
        try:
            categories = get_categories()
            result['categories'] = categories

            all_stocks = []
            stock_name_map = {}

            if not enabled_category_ids:
                op.set_message('未启用任何分类，跳过')
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

            if not all_stocks:
                return jsonify(result)

            stock_codes = [s['stock_code'] for s in all_stocks]

            # 60天 OHLC（多数命中缓存，很快）
            trend_data = PositionService.get_trend_data(stock_codes, target_date, days=days)

            if trend_data and trend_data.get('stocks'):
                for stock_data in trend_data['stocks']:
                    code = stock_data.get('stock_code')
                    result['ohlc_data'][code] = stock_data.get('data', [])

                # 只读取已缓存的信号（不重新计算）
                end_date = target_date
                start_date = end_date - timedelta(days=days)
                all_signals = SignalCacheService.get_cached_signals_with_names(
                    stock_codes, stock_name_map, start_date, end_date
                )
                result['signals'] = all_signals

            # 投资建议（DB查询）
            advice_map = {}
            try:
                stocks_with_advice = Stock.query.filter(Stock.stock_code.in_(stock_codes)).all()
                advice_map = {s.stock_code: s.investment_advice for s in stocks_with_advice if s.investment_advice}
            except Exception as e:
                logger.warning(f'[预警.数据] 获取投资建议失败: {e}')

            result['stocks'] = [{
                'code': s['stock_code'],
                'name': s['stock_name'],
                'categoryId': s['category_id'],
                'categoryName': s['category_name'],
                'investment_advice': advice_map.get(s['stock_code'])
            } for s in all_stocks]

            op.set_message(f'{len(result["ohlc_data"])}只股票, days={days}')
            return jsonify(result)
        except Exception as e:
            logger.error(f'[预警.数据] 处理失败: {e}', exc_info=True)
            return jsonify({'error': str(e)}), 500


@alert_bp.route('/api/signals/refresh', methods=['POST'])
def refresh_signals():
    """异步刷新信号缓存：获取365天OHLC并重新计算信号"""
    data = request.get_json(silent=True) or {}
    stock_codes = data.get('stock_codes', [])

    if not stock_codes:
        return jsonify({'status': 'ok', 'updated': 0})

    with log_operation(logger, "预警.信号刷新") as op:
        try:
            target_date = date.today()
            stocks = Stock.query.filter(Stock.stock_code.in_(stock_codes)).all()
            stock_name_map = {s.stock_code: s.stock_name for s in stocks}

            year_result = PositionService.get_trend_data(stock_codes, target_date, days=365)
            updated = 0
            if year_result and year_result.get('stocks'):
                SignalCacheService.update_signals_from_trend_data(year_result, stock_name_map)
                updated = len(year_result['stocks'])

            op.set_message(f'{updated}只')
            return jsonify({'status': 'ok', 'updated': updated})
        except Exception as e:
            logger.error(f'[预警.信号刷新] 信号刷新失败: {e}', exc_info=True)
            return jsonify({'error': str(e)}), 500


@alert_bp.route('/api/earnings')
def get_earnings_data():
    """异步获取财报/PE数据"""
    codes_param = request.args.get('codes', '')
    stock_codes = [c.strip() for c in codes_param.split(',') if c.strip()]

    if not stock_codes:
        return jsonify({})

    with log_operation(logger, "预警.财报") as op:
        try:
            earnings_dates = EarningsService.get_earnings_dates(stock_codes)
            pe_ratios = EarningsService.get_pe_ratios(stock_codes)

            result = {}
            for code in stock_codes:
                earnings = earnings_dates.get(code, {})
                pe = pe_ratios.get(code, {})
                result[code] = {
                    'last_earnings_date': earnings.get('last_earnings_date'),
                    'next_earnings_date': earnings.get('next_earnings_date'),
                    'days_until_next': earnings.get('days_until_next'),
                    'is_today': earnings.get('is_today', False),
                    'pe_ttm': pe.get('pe_ttm'),
                    'pe_display': pe.get('pe_display', '暂无数据'),
                    'pe_status': pe.get('pe_status', 'na'),
                    'market': earnings.get('market', 'unknown')
                }

            op.set_message(f'{len(stock_codes)}只')
            return jsonify(result)
        except Exception as e:
            logger.error(f'[预警.财报] 获取财报数据失败: {e}', exc_info=True)
            return jsonify({'error': str(e)}), 500


@alert_bp.route('/api/backtest/signals')
def backtest_signals():
    """信号回测"""
    stock_code = request.args.get('stock_code')
    lookback_days = request.args.get('days', 365, type=int)

    if not stock_code:
        return jsonify({'error': '缺少 stock_code 参数'}), 400

    try:
        service = BacktestService()
        result = service.backtest_signals(stock_code, lookback_days)
        return jsonify(result)
    except Exception as e:
        logger.error(f'[预警.回测] 信号回测失败 {stock_code}: {e}', exc_info=True)
        return jsonify({'error': str(e)}), 500


@alert_bp.route('/api/backtest/win-rates')
def backtest_win_rates():
    """各信号类型的历史胜率"""
    try:
        service = BacktestService()
        result = service.get_signal_win_rates()
        return jsonify(result)
    except Exception as e:
        logger.error(f'[预警.回测] 获取信号胜率失败: {e}', exc_info=True)
        return jsonify({'error': str(e)}), 500
