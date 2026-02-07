import logging
from datetime import date, datetime, timedelta
from flask import render_template, jsonify, request
from app.routes import heavy_metals_bp
from app.services.futures import FuturesService, CATEGORY_CODES, CATEGORY_NAMES, TradingAdviceCalculator, CategoryCodeResolver
from app.services.wyckoff import WyckoffAutoService
from app.services.wyckoff_score import WyckoffScoreCalculator
from app.services.fed_rate import FedRateService
from app.services.signal_cache import SignalCacheService

logger = logging.getLogger(__name__)


@heavy_metals_bp.route('/')
def index():
    """渲染重金属页面"""
    return render_template('heavy_metals.html')


@heavy_metals_bp.route('/api/trend-data')
def trend_data():
    """获取期货走势数据"""
    force = request.args.get('force', '0') == '1'
    data = FuturesService.get_trend_data(days=30, force_refresh=force)
    return jsonify(data)


@heavy_metals_bp.route('/api/index-trend-data')
def index_trend_data():
    """获取指数走势数据"""
    force = request.args.get('force', '0') == '1'
    data = FuturesService.get_index_trend_data(days=30, force_refresh=force)
    return jsonify(data)


@heavy_metals_bp.route('/api/custom-trend-data')
def custom_trend_data():
    """获取自定义走势数据"""
    codes_str = request.args.get('codes', '')
    codes = [c.strip() for c in codes_str.split(',') if c.strip()]
    data = FuturesService.get_custom_trend_data(codes, days=30)
    return jsonify(data)


@heavy_metals_bp.route('/api/available-codes')
def available_codes():
    """获取可选数据项列表，附加威科夫分析结果"""
    data = FuturesService.get_available_codes()

    # 获取今日威科夫分析结果
    from datetime import date
    wyckoff_results = WyckoffAutoService.get_auto_history(start_date=date.today())
    wyckoff_map = {r['stock_code']: r for r in wyckoff_results}

    # 为股票分组附加威科夫数据
    for group_name, stocks in data.get('stock_groups', {}).items():
        for stock in stocks:
            code = stock['code']
            if code in wyckoff_map:
                w = wyckoff_map[code]
                stock['wyckoff'] = {
                    'phase': w['phase'],
                    'advice': w['advice'],
                    'events': w['events'],
                }

    return jsonify(data)


@heavy_metals_bp.route('/api/category-trend-data')
def category_trend_data():
    """获取特定分类的走势数据

    Query params:
        category (str): 分类标识符 ('heavy_metals', 'gold', 'copper', 'aluminum', 'silver')
        days (int): 历史数据天数 (7, 30, 或 365)
        force (str): '1' 表示强制刷新

    Returns:
        JSON: {stocks: [...], date_range: {...}, cache_info: {...}, signals: {...}}
    """
    category = request.args.get('category', 'heavy_metals')
    days = int(request.args.get('days', 30))
    force = request.args.get('force', '0') == '1'

    logger.info(f'[category-trend-data] 请求分类={category}, 天数={days}')

    # 验证分类
    if category not in CATEGORY_NAMES:
        return jsonify({'error': 'Invalid category'}), 400

    # 获取数据
    data = FuturesService.get_category_trend_data(category, days, force)

    # 信号检测：始终使用年数据计算并缓存
    if data and data.get('stocks'):
        logger.info(f'[category-trend-data] 获取到 {len(data["stocks"])} 只股票数据')

        # 获取股票代码和名称映射
        stock_codes = [s['stock_code'] for s in data['stocks']]
        stock_name_map = {s['stock_code']: s['stock_name'] for s in data['stocks']}

        # 获取年数据用于信号计算
        year_data = FuturesService.get_category_trend_data(category, 365, False)

        if year_data and year_data.get('stocks'):
            # 更新信号缓存
            SignalCacheService.update_signals_from_trend_data(year_data, stock_name_map)

        # 从缓存获取当前日期范围内的信号
        end_date = date.today()
        start_date = end_date - timedelta(days=days)
        all_signals = SignalCacheService.get_cached_signals_with_names(
            stock_codes, stock_name_map, start_date, end_date
        )

        data['signals'] = all_signals
        logger.info(f'[信号检测] 总计: 买点={len(all_signals["buy_signals"])}, 卖点={len(all_signals["sell_signals"])}')

    return jsonify(data)


@heavy_metals_bp.route('/api/trading-advice')
def trading_advice():
    """获取交易建议（含威科夫评分）

    Query params:
        category (str): 分类标识符
        days (int): 历史数据天数 (7, 30, 或 365)

    Returns:
        JSON: {
            overall: 'buy'|'sell'|'hold'|'watch',
            stocks: [{
                code, name, advice, reason, change_pct,
                wyckoff_score, score_details, analysis, investment_advice
            }, ...]
        }
    """
    from app.models.stock import Stock

    category = request.args.get('category', 'heavy_metals')
    days = int(request.args.get('days', 30))

    # 验证分类
    if category not in CATEGORY_NAMES:
        return jsonify({'error': 'Invalid category'}), 400

    # 获取走势数据
    trend_data = FuturesService.get_category_trend_data(category, days)

    # 计算建议
    timeframe = f'{days}d'
    advice = TradingAdviceCalculator.calculate_advice(trend_data, timeframe)

    # 构建估值数据映射
    valuation_map = {}
    if trend_data and 'stocks' in trend_data:
        for s in trend_data['stocks']:
            valuation_map[s['stock_code']] = s.get('valuation')

    # 获取投资建议
    stock_codes = [s['code'] for s in advice.get('stocks', [])]
    advice_map = {}
    try:
        stocks_with_advice = Stock.query.filter(Stock.stock_code.in_(stock_codes)).all()
        advice_map = {s.stock_code: s.investment_advice for s in stocks_with_advice if s.investment_advice}
    except Exception as e:
        logger.warning(f"获取投资建议失败: {e}")

    # 计算威科夫评分（根据时间周期）
    try:
        scores = WyckoffScoreCalculator.calculate_scores(trend_data, category, days)
        score_map = {s['code']: s for s in scores}

        # 合并评分数据和估值数据到 stocks
        for stock in advice['stocks']:
            code = stock['code']
            if code in score_map:
                score_data = score_map[code]
                stock['wyckoff_score'] = score_data.get('score')
                stock['score_details'] = score_data.get('score_details')
                stock['analysis'] = score_data.get('analysis')
            else:
                stock['wyckoff_score'] = None
                stock['score_details'] = None
                stock['analysis'] = None

            # 添加估值数据
            stock['valuation'] = valuation_map.get(code)
            # 添加投资建议
            stock['investment_advice'] = advice_map.get(code)

    except Exception as e:
        logger.error(f"计算威科夫评分失败: {e}")
        # 评分失败不影响原有功能
        for stock in advice['stocks']:
            stock['wyckoff_score'] = None
            stock['score_details'] = None
            stock['analysis'] = None
            stock['valuation'] = valuation_map.get(stock['code'])
            stock['investment_advice'] = advice_map.get(stock['code'])

    return jsonify(advice)


@heavy_metals_bp.route('/api/fed-rate')
def fed_rate():
    """获取美联储利率概率数据

    Returns:
        JSON: {
            current_rate: 4.50,
            next_meeting: '2025-01-29',
            is_meeting_today: false,
            probabilities: {cut: 35.5, hold: 60.2, hike: 4.3},
            expected_change: -25,
            updated_at: '2024-12-28 10:30:00'
        }
    """
    force = request.args.get('force', '0') == '1'
    data = FedRateService.get_rate_probabilities(force_refresh=force)
    return jsonify(data)


@heavy_metals_bp.route('/api/fed-decisions')
def fed_decisions():
    """获取指定日期范围内的 FOMC 决议历史

    Query params:
        start: 开始日期 (YYYY-MM-DD)
        end: 结束日期 (YYYY-MM-DD)

    Returns:
        JSON: [{date, action, bps, rate, label}, ...]
    """
    start = request.args.get('start', '')
    end = request.args.get('end', '')
    decisions = FedRateService.get_decisions_in_range(start, end)
    return jsonify(decisions)


@heavy_metals_bp.route('/api/fed-probabilities')
def fed_probabilities():
    """获取指定日期范围内的每日降息概率

    Query params:
        start: 开始日期 (YYYY-MM-DD)
        end: 结束日期 (YYYY-MM-DD)

    Returns:
        JSON: [{date, cut, hold, hike}, ...]
    """
    start = request.args.get('start', '')
    end = request.args.get('end', '')
    probabilities = FedRateService.get_probabilities_in_range(start, end)
    return jsonify(probabilities)
