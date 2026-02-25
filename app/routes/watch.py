import json
import logging
from flask import render_template, request, jsonify

from app.routes import watch_bp
from app.services.watch_service import WatchService

logger = logging.getLogger(__name__)


@watch_bp.route('/')
def index():
    return render_template('watch.html')


@watch_bp.route('/list')
def watch_list():
    items = WatchService.get_watch_list()
    return jsonify({'success': True, 'data': items})


@watch_bp.route('/add', methods=['POST'])
def add_stock():
    data = request.get_json()
    code = data.get('stock_code', '').strip()
    name = data.get('stock_name', '').strip()
    if not code:
        return jsonify({'success': False, 'message': '股票代码不能为空'})
    result = WatchService.add_stock(code, name)
    return jsonify(result)


@watch_bp.route('/remove/<stock_code>', methods=['DELETE'])
def remove_stock(stock_code):
    result = WatchService.remove_stock(stock_code)
    return jsonify(result)


@watch_bp.route('/prices')
def prices():
    from app.services.unified_stock_data import unified_stock_data_service
    codes = WatchService.get_watch_codes()
    if not codes:
        return jsonify({'success': True, 'prices': []})
    result = unified_stock_data_service.get_realtime_prices(codes)
    return jsonify({'success': True, 'prices': result.get('prices', [])})


@watch_bp.route('/analyze', methods=['POST'])
def analyze():
    """触发AI分析"""
    from app.services.unified_stock_data import unified_stock_data_service
    from app.llm.router import llm_router
    from app.llm.prompts.watch_analysis import SYSTEM_PROMPT, build_watch_analysis_prompt

    data = request.get_json() or {}
    force = data.get('force', False)

    codes = WatchService.get_watch_codes()
    if not codes:
        return jsonify({'success': True, 'data': {}, 'message': '盯盘列表为空'})

    existing = WatchService.get_all_today_analyses()
    if not force:
        uncalculated = [c for c in codes if c not in existing]
    else:
        uncalculated = codes

    if not uncalculated:
        return jsonify({'success': True, 'data': existing, 'message': '使用今日缓存'})

    trend_result = unified_stock_data_service.get_trend_data(uncalculated, days=30)
    stocks_data = {s['stock_code']: s for s in trend_result.get('stocks', [])}

    price_result = unified_stock_data_service.get_realtime_prices(uncalculated)
    prices_map = {p['code']: p for p in price_result.get('prices', [])}

    provider = llm_router.route('watch_analysis')
    for code in uncalculated:
        stock = stocks_data.get(code, {})
        price_info = prices_map.get(code, {})
        ohlc = stock.get('data', [])
        current_price = price_info.get('price', 0)
        stock_name = stock.get('stock_name', '') or price_info.get('name', code)

        if not ohlc or not current_price or not provider:
            continue

        try:
            prompt = build_watch_analysis_prompt(stock_name, code, ohlc, current_price)
            response = provider.chat([
                {'role': 'system', 'content': SYSTEM_PROMPT},
                {'role': 'user', 'content': prompt},
            ])
            parsed = json.loads(response)
            WatchService.save_analysis(
                stock_code=code,
                support_levels=parsed.get('support_levels', []),
                resistance_levels=parsed.get('resistance_levels', []),
                volatility_threshold=parsed.get('volatility_threshold', 0.02),
                summary=parsed.get('summary', ''),
            )
        except Exception as e:
            logger.error(f"[盯盘AI] {code} 分析失败: {e}")

    all_analyses = WatchService.get_all_today_analyses()
    return jsonify({'success': True, 'data': all_analyses})


@watch_bp.route('/analysis')
def get_analysis():
    analyses = WatchService.get_all_today_analyses()
    return jsonify({'success': True, 'data': analyses})


@watch_bp.route('/stocks/search')
def search_stocks():
    """搜索可添加的股票"""
    from app.models.stock import Stock
    q = request.args.get('q', '').strip()
    if not q:
        stocks = Stock.query.limit(50).all()
    else:
        stocks = Stock.query.filter(
            (Stock.stock_code.contains(q)) | (Stock.stock_name.contains(q))
        ).limit(50).all()
    return jsonify({'success': True, 'data': [
        {'stock_code': s.stock_code, 'stock_name': s.stock_name} for s in stocks
    ]})
