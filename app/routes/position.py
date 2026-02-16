from datetime import date
from flask import request, jsonify
from app.routes import position_bp
from app.services.position import PositionService
from app.services.stock import StockService


@position_bp.route('/save', methods=['POST'])
def save():
    data = request.get_json()
    if not data or 'positions' not in data:
        return jsonify({'error': '无效的数据'}), 400

    positions = data['positions']
    overwrite = data.get('overwrite', True)
    overwrite_stocks = data.get('overwrite_stocks', False)
    target_date = date.fromisoformat(data['date']) if 'date' in data else date.today()

    StockService.save_from_positions(positions, overwrite_stocks)
    PositionService.save_snapshot(target_date, positions, overwrite)
    return jsonify({'success': True})


@position_bp.route('/<target_date>')
def get_by_date(target_date):
    from app.models.advice import Advice
    from app.models.config import Config
    from app.services.rebalance import RebalanceService

    target = date.fromisoformat(target_date)
    positions = PositionService.get_snapshot(target)

    if not positions:
        return jsonify({'error': '该日期无数据'}), 404

    advice_list = Advice.query.filter_by(date=target).all()
    advices = {a.stock_code: a.to_dict() for a in advice_list}

    # 获取总资金配置并计算仓位统计
    capital_value = Config.get_value('total_capital')
    total_capital = float(capital_value) if capital_value else None
    position_dicts = [p.to_dict() for p in positions]
    stats = PositionService.calculate_position_stats(position_dicts, total_capital)

    # 获取仓位配平数据
    rebalance_list = RebalanceService.calculate_rebalance(stats['positions'])
    rebalance_data = {r['stock_code']: r for r in rebalance_list}

    return jsonify({
        'positions': stats['positions'],
        'advices': advices,
        'summary': stats['summary'],
        'rebalance_data': rebalance_data,
    })


@position_bp.route('/api/dates')
def get_dates():
    dates = PositionService.get_all_dates()
    return jsonify({'dates': [d.isoformat() for d in dates]})


@position_bp.route('/api/check-today')
def check_today():
    has_existing = PositionService.has_snapshot(date.today())
    return jsonify({'has_existing': has_existing})


@position_bp.route('/api/check-date')
def check_date():
    date_str = request.args.get('date')
    target_date = date.fromisoformat(date_str) if date_str else date.today()
    has_existing = PositionService.has_snapshot(target_date)
    return jsonify({'has_existing': has_existing})


@position_bp.route('/config', methods=['GET'])
def get_config():
    from app.models.config import Config
    value = Config.get_value('total_capital')
    total_capital = float(value) if value else None
    return jsonify({'total_capital': total_capital})


@position_bp.route('/config', methods=['POST'])
def save_config():
    from app.models.config import Config
    data = request.get_json()

    if not data or 'total_capital' not in data:
        return jsonify({'error': '无效的数据'}), 400

    total_capital = data['total_capital']
    if total_capital is None or total_capital <= 0:
        return jsonify({'error': '总资金必须大于0'}), 400

    Config.set_value('total_capital', str(total_capital))
    return jsonify({'success': True})


@position_bp.route('/stock-history/<stock_code>')
def stock_history(stock_code):
    days = request.args.get('days', 7, type=int)
    data = PositionService.get_stock_history(stock_code, days)
    return jsonify(data)


@position_bp.route('/api/trend-data')
def trend_data():
    """获取持仓股票的30天走势数据"""
    from datetime import date as date_type

    date_str = request.args.get('date')
    category = request.args.get('category', 'all')

    target_date = date_type.fromisoformat(date_str) if date_str else date_type.today()

    # 获取指定日期的持仓
    positions = PositionService.get_snapshot(target_date)
    if not positions:
        return jsonify({'stocks': [], 'date_range': {}})

    stock_codes = [p.stock_code for p in positions]

    # 获取走势数据
    trend_data = PositionService.get_trend_data(stock_codes, target_date, days=30)

    # 按分类筛选
    if category != 'all':
        from app.services.category import CategoryService
        category_tree = CategoryService.get_category_tree()

        if category == 'uncategorized':
            # 未分类
            trend_data['stocks'] = [s for s in trend_data['stocks'] if s.get('category_id') is None]
        else:
            category_id = int(category)
            # 找出该分类及其子分类的所有ID
            valid_ids = {category_id}
            for parent in category_tree:
                if parent['id'] == category_id:
                    for child in parent.get('children', []):
                        valid_ids.add(child['id'])
                    break
                for child in parent.get('children', []):
                    if child['id'] == category_id:
                        break

            trend_data['stocks'] = [s for s in trend_data['stocks'] if s.get('category_id') in valid_ids]

    return jsonify(trend_data)


@position_bp.route('/api/combined-trend-data')
def combined_trend_data():
    """获取合并的股票和期货走势数据"""
    import logging
    from datetime import date as date_type
    from app.services.futures import FuturesService

    logger = logging.getLogger(__name__)
    date_str = request.args.get('date')
    target_date = date_type.fromisoformat(date_str) if date_str else date_type.today()

    stocks_data = {'stocks': [], 'date_range': {}}
    futures_data = {'stocks': [], 'date_range': {}}

    # 获取持仓股票走势
    positions = PositionService.get_snapshot(target_date)
    if positions:
        stock_codes = [p.stock_code for p in positions]
        try:
            stocks_data = PositionService.get_trend_data(stock_codes, target_date, days=30)
            for stock in stocks_data['stocks']:
                stock['source'] = 'stock'
        except Exception as e:
            logger.warning(f"[持仓路由] 获取股票走势数据失败: {e}")

    # 获取期货走势
    try:
        futures_data = FuturesService.get_trend_data(days=30)
        for future in futures_data['stocks']:
            future['source'] = 'futures'
    except Exception as e:
        logger.warning(f"[持仓路由] 获取期货走势数据失败: {e}")

    # 合并数据
    combined_stocks = stocks_data['stocks'] + futures_data['stocks']

    # 计算日期范围
    all_dates = set()
    for stock in combined_stocks:
        for dp in stock.get('data', []):
            all_dates.add(dp['date'])

    sorted_dates = sorted(all_dates)
    date_range = {
        'start': sorted_dates[0] if sorted_dates else None,
        'end': sorted_dates[-1] if sorted_dates else None
    }

    return jsonify({
        'stocks': combined_stocks,
        'date_range': date_range
    })
