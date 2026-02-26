import json
import logging
from datetime import datetime
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
    from app.strategies.registry import registry

    codes = WatchService.get_watch_codes()
    if not codes:
        return jsonify({'success': True, 'prices': []})

    raw_prices = unified_stock_data_service.get_realtime_prices(codes)
    price_list = []
    for code, data in raw_prices.items():
        price_list.append({
            'code': code,
            'name': data.get('name', code),
            'price': data.get('current_price'),
            'change': data.get('change'),
            'change_pct': data.get('change_percent'),
            'volume': data.get('volume'),
            'market': data.get('market', ''),
        })

    analyses = WatchService.get_all_today_analyses()

    strategy = registry.get('watch_assistant')
    strategy_config = strategy.get_config() if strategy else {}
    cooldown_minutes = strategy_config.get('notification_cooldown_minutes', 30)
    default_threshold = strategy_config.get('default_volatility_threshold', 0.02)
    last_notified = getattr(strategy, '_last_notified', {}) if strategy else {}

    now = datetime.now()
    for item in price_list:
        code = item.get('code', '')
        analysis = analyses.get(code, {})

        cooldown_remaining = 0
        if code in last_notified:
            elapsed = (now - last_notified[code]).total_seconds()
            cooldown_remaining = max(0, int(cooldown_minutes * 60 - elapsed))

        item['notification'] = {
            'threshold': analysis.get('volatility_threshold', default_threshold),
            'cooldown_remaining': cooldown_remaining,
            'support_levels': analysis.get('support_levels', []),
            'resistance_levels': analysis.get('resistance_levels', []),
            'summary': analysis.get('summary', ''),
        }

    return jsonify({'success': True, 'prices': price_list})


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

    raw_prices = unified_stock_data_service.get_realtime_prices(uncalculated)
    prices_map = {}
    for code, price_data in raw_prices.items():
        prices_map[code] = {
            'code': code,
            'name': price_data.get('name', code),
            'price': price_data.get('current_price'),
            'change_pct': price_data.get('change_percent'),
        }

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
            # 清理可能的 markdown 代码块包裹
            cleaned = response.strip()
            if cleaned.startswith('```'):
                cleaned = cleaned.split('\n', 1)[-1].rsplit('```', 1)[0].strip()
            parsed = json.loads(cleaned)
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


@watch_bp.route('/market-status')
def market_status():
    from app.services.trading_calendar import TradingCalendarService

    MARKET_INFO = {
        'A':  {'name': 'A股', 'icon': '🇨🇳'},
        'US': {'name': '美股', 'icon': '🇺🇸'},
        'HK': {'name': '港股', 'icon': '🇭🇰'},
        'KR': {'name': '韩股', 'icon': '🇰🇷'},
        'TW': {'name': '台股', 'icon': '🇹🇼'},
        'JP': {'name': '日股', 'icon': '🇯🇵'},
    }

    # 动态获取用户盯盘列表中涉及的市场
    watched_markets = WatchService.get_watched_markets()
    markets = [
        {'key': m, **MARKET_INFO.get(m, {'name': m, 'icon': '🏳️'})}
        for m in watched_markets
        if m in MARKET_INFO
    ]

    from datetime import time as dtime

    # 午休窗口：(开始, 下午开盘)
    LUNCH_WINDOWS = {'A': (dtime(11, 30), dtime(13, 0)), 'JP': (dtime(11, 30), dtime(12, 30))}

    result = {}
    for m in markets:
        key = m['key']
        tz = TradingCalendarService.MARKET_TIMEZONES.get(key)
        now = TradingCalendarService.get_market_now(key)
        time_str = now.strftime('%H:%M')

        is_trading_day = TradingCalendarService.is_trading_day(key, now.date())
        is_open = TradingCalendarService.is_market_open(key)
        lunch = LUNCH_WINDOWS.get(key)
        is_lunch = (is_trading_day and not is_open
                    and lunch and lunch[0] <= now.time() < lunch[1])

        if not is_trading_day:
            status, status_text = 'holiday', '休市'
        elif is_open:
            status, status_text = 'trading', '交易中'
        elif is_lunch:
            status, status_text = 'lunch', '午休'
        elif TradingCalendarService.is_after_close(key, now):
            status, status_text = 'closed', '已收盘'
        else:
            status, status_text = 'pre_open', '未开盘'

        entry = {
            'name': m['name'],
            'icon': m['icon'],
            'timezone': str(tz),
            'time': time_str,
            'status': status,
            'status_text': status_text,
        }

        if is_lunch:
            now_secs = now.hour * 3600 + now.minute * 60 + now.second
            open_secs = lunch[1].hour * 3600 + lunch[1].minute * 60
            entry['seconds_to_open'] = max(0, open_secs - now_secs)

        result[key] = entry

    return jsonify({'success': True, 'data': result})


@watch_bp.route('/chart-data')
def chart_data():
    """获取图表数据"""
    from app.services.unified_stock_data import unified_stock_data_service

    code = request.args.get('code', '').strip()
    period = request.args.get('period', 'intraday')

    if not code:
        return jsonify({'success': False, 'message': '缺少股票代码'})

    result = {'success': True, 'code': code, 'period': period}

    if period == 'intraday':
        intraday = unified_stock_data_service.get_intraday_data([code])
        stocks = intraday.get('stocks', [])
        result['data'] = stocks[0]['data'] if stocks else []
        result['chart_type'] = 'line'
    else:
        days_map = {'7d': 7, '30d': 30, '90d': 90}
        days = days_map.get(period, 30)
        fetch_days = days + 20
        trend = unified_stock_data_service.get_trend_data([code], days=fetch_days)
        stocks = trend.get('stocks', [])
        ohlc_data = stocks[0]['data'] if stocks else []

        bollinger = []
        if len(ohlc_data) >= 20:
            closes = [d['close'] for d in ohlc_data]
            for i in range(len(closes)):
                if i < 19:
                    bollinger.append(None)
                    continue
                window = closes[i-19:i+1]
                ma = sum(window) / 20
                std = (sum((x - ma) ** 2 for x in window) / 20) ** 0.5
                bollinger.append({
                    'upper': round(ma + 2 * std, 2),
                    'middle': round(ma, 2),
                    'lower': round(ma - 2 * std, 2),
                })

        result['data'] = ohlc_data[-days:]
        result['bollinger'] = bollinger[-days:]
        result['chart_type'] = 'candlestick'

    analysis = WatchService.get_today_analysis(code)
    result['support_levels'] = analysis.get('support_levels', []) if analysis else []
    result['resistance_levels'] = analysis.get('resistance_levels', []) if analysis else []

    return jsonify(result)
