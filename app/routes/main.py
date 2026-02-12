from flask import render_template, request, jsonify, redirect, url_for
from app.routes import main_bp
from app.services.position import PositionService
from app.services.category import CategoryService
from app.services.rebalance import RebalanceService
from app.services.daily_record import DailyRecordService
from app.services.stock_meta import StockMetaService
from app.models.advice import Advice
from app.models.config import Config
from app.models.daily_snapshot import DailySnapshot


@main_bp.route('/')
def index():
    """Default page redirects to daily briefing"""
    return redirect(url_for('briefing.index'))


@main_bp.route('/dashboard')
def dashboard():
    latest_date = PositionService.get_latest_date()
    positions = []
    advices = {}
    summary = None
    rebalance_data = {}
    daily_profit_data = {}
    profit_history = {}

    # 分类筛选（从 StockMetaService 缓存获取）
    category_filter = request.args.get('category', 'all')
    meta = StockMetaService.get_meta()
    data_version = meta['version']
    category_tree = meta['category_tree']
    stock_categories = meta['stock_categories']
    categories = CategoryService.get_all_categories()

    daily_change = None
    daily_profit_breakdown = []
    if latest_date:
        positions = PositionService.get_snapshot(latest_date)
        advice_list = Advice.query.filter_by(date=latest_date).all()
        advices = {a.stock_code: a.to_dict() for a in advice_list}

        # 获取总资金配置并计算仓位统计
        capital_value = Config.get_value('total_capital')
        total_capital = float(capital_value) if capital_value else None
        position_dicts = [p.to_dict() for p in positions]
        stats = PositionService.calculate_position_stats(position_dicts, total_capital)
        positions = stats['positions']
        summary = stats['summary']

        # 计算每日收益变化（考虑交易影响）
        prev_date = DailyRecordService.get_previous_trading_date(latest_date)
        daily_profit_result = DailyRecordService.get_daily_profit(latest_date, prev_date)
        daily_change = {
            'daily_change': daily_profit_result.get('daily_profit', 0) or 0,
            'daily_change_pct': daily_profit_result.get('daily_profit_pct', 0) or 0,
        }

        # 获取每日收益明细（用于每日收益饼图）
        daily_profit_breakdown = DailyRecordService.get_profit_breakdown(latest_date, prev_date)

        # 计算分类收益数据
        daily_profit_data = PositionService.calculate_category_profit(
            positions, stock_categories, category_tree
        )

        # 获取仓位配平数据
        rebalance_list = RebalanceService.calculate_rebalance(positions)
        rebalance_data = {r['stock_code']: r for r in rebalance_list}

        # 获取每日收益历史数据
        profit_history = DailyRecordService.get_daily_profit_history()

        # 应用分类筛选
        if category_filter == 'uncategorized':
            positions = [p for p in positions if p['stock_code'] not in stock_categories]
        elif category_filter.isdigit():
            cat_id = int(category_filter)
            # 获取该分类及其子分类的所有 ID
            valid_ids = {cat_id}
            for parent in category_tree:
                if parent['id'] == cat_id:
                    valid_ids.update(c['id'] for c in parent.get('children', []))
                    break
            positions = [p for p in positions
                         if stock_categories.get(p['stock_code'], {}).get('category_id') in valid_ids]

        # 按板块排序（未设板块的排在最后）
        def get_category_sort_key(p):
            sc = stock_categories.get(p['stock_code'], {})
            cat_id = sc.get('category_id')
            if cat_id is None:
                return (999999, p['stock_name'])
            return (cat_id, p['stock_name'])
        positions = sorted(positions, key=get_category_sort_key)
    else:
        positions = []

    dates = PositionService.get_all_dates()

    # 获取所有日期的快照数据
    snapshots = DailySnapshot.get_all_snapshots()
    snapshot_map = {s.date.isoformat(): s.to_dict() for s in snapshots}

    return render_template(
        'index.html',
        positions=positions,
        advices=advices,
        summary=summary,
        daily_change=daily_change,
        daily_profit_data=daily_profit_data,
        daily_profit_breakdown=daily_profit_breakdown,
        profit_history=profit_history,
        current_date=latest_date.isoformat() if latest_date else None,
        dates=[d.isoformat() for d in dates],
        category_tree=category_tree,
        categories=categories,
        stock_categories=stock_categories,
        category_filter=category_filter,
        rebalance_data=rebalance_data,
        snapshot_map=snapshot_map,
        data_version=data_version,
    )


@main_bp.route('/api/stock-meta')
def stock_meta():
    """股票元数据API，支持版本号增量检查"""
    v = request.args.get('v', type=int)
    current = StockMetaService.get_version()
    if v == current:
        return jsonify({'changed': False, 'version': current})
    meta = StockMetaService.get_meta()
    return jsonify({'changed': True, **meta})
