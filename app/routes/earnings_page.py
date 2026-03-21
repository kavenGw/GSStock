import logging
from datetime import date
from threading import Thread

from flask import render_template, request, jsonify, current_app

from app.routes import earnings_page_bp
from app import db
from app.models.earnings_snapshot import EarningsSnapshot
from app.models.category import Category, StockCategory

logger = logging.getLogger(__name__)


def _get_categories_with_position():
    """获取所有顶级分类，标记哪些有持仓"""
    from app.models.position import Position
    categories = Category.query.filter_by(parent_id=None).all()

    # 当前持仓的股票代码
    latest_date = db.session.query(db.func.max(Position.date)).scalar()
    held_codes = set()
    if latest_date:
        positions = Position.query.filter_by(date=latest_date).all()
        held_codes = {p.stock_code for p in positions if p.quantity and p.quantity > 0}

    # 各分类的股票代码
    all_sc = StockCategory.query.all()
    cat_codes = {}
    for sc in all_sc:
        cat_id = sc.category_id
        if cat_id:
            cat_codes.setdefault(cat_id, set()).add(sc.stock_code)

    result = []
    for cat in categories:
        cat_ids = [cat.id] + [c.id for c in cat.children]
        codes = set()
        for cid in cat_ids:
            codes |= cat_codes.get(cid, set())

        has_position = bool(codes & held_codes)

        result.append({
            'id': cat.id,
            'name': cat.name,
            'count': len(codes),
            'has_position': has_position,
        })

    return result


@earnings_page_bp.route('/')
def index():
    categories = _get_categories_with_position()
    return render_template('earnings_page.html', categories=categories)


@earnings_page_bp.route('/api/data')
def get_data():
    cat_ids_str = request.args.get('categories', '')
    sort_field = request.args.get('sort', 'pe_dynamic')
    order = request.args.get('order', 'asc')

    if sort_field not in ('pe_dynamic', 'ps_dynamic'):
        sort_field = 'pe_dynamic'

    # 解析板块ID
    cat_ids = []
    if cat_ids_str:
        cat_ids = [int(x) for x in cat_ids_str.split(',') if x.strip().isdigit()]

    # 查快照：优先今天，否则最近一天
    today = date.today()
    snapshot_date = db.session.query(db.func.max(EarningsSnapshot.snapshot_date)).filter(
        EarningsSnapshot.snapshot_date <= today
    ).scalar()

    if not snapshot_date:
        return jsonify({'categories': [], 'stocks': [], 'snapshot_date': None, 'is_today': False})

    # 按板块过滤股票代码
    filtered_codes = None
    if cat_ids:
        # 包含子分类
        all_cat_ids = list(cat_ids)
        for cid in cat_ids:
            cat = Category.query.get(cid)
            if cat:
                all_cat_ids.extend([c.id for c in cat.children])

        scs = StockCategory.query.filter(StockCategory.category_id.in_(all_cat_ids)).all()
        filtered_codes = {sc.stock_code for sc in scs}

    # 查询快照
    query = EarningsSnapshot.query.filter_by(snapshot_date=snapshot_date)
    if filtered_codes is not None:
        query = query.filter(EarningsSnapshot.stock_code.in_(filtered_codes))

    # 排序（NULL 排最后）
    sort_col = getattr(EarningsSnapshot, sort_field)
    if order == 'desc':
        query = query.order_by(db.case((sort_col.is_(None), 1), else_=0), sort_col.desc())
    else:
        query = query.order_by(db.case((sort_col.is_(None), 1), else_=0), sort_col.asc())

    snapshots = query.all()

    # 分类列表
    categories = _get_categories_with_position()

    return jsonify({
        'categories': categories,
        'stocks': [s.to_dict() for s in snapshots],
        'snapshot_date': snapshot_date.isoformat(),
        'is_today': snapshot_date == today,
    })


@earnings_page_bp.route('/api/refresh', methods=['POST'])
def refresh():
    """异步触发快照重新计算"""
    app = current_app._get_current_object()

    def _run():
        with app.app_context():
            from app.strategies.earnings_snapshot import EarningsSnapshotStrategy
            strategy = EarningsSnapshotStrategy()
            strategy.scan()

    Thread(target=_run, daemon=True).start()
    return jsonify({'message': '正在刷新，请稍后刷新页面查看'}), 202
