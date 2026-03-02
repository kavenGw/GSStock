import json
import logging
from flask import render_template, request, jsonify

from app import db
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
    from app.config.stock_codes import BENCHMARK_CODES

    codes = WatchService.get_watch_codes()
    cache_only = request.args.get('cache_only', 'false').lower() == 'true'

    # 盯盘股票报价
    price_list = []
    if codes:
        raw_prices = unified_stock_data_service.get_realtime_prices(codes, cache_only=cache_only)
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

    # 基准标的报价
    bench_codes = [b['code'] for b in BENCHMARK_CODES]
    bench_raw = unified_stock_data_service.get_realtime_prices(bench_codes, cache_only=cache_only)
    benchmark_list = []
    for b in BENCHMARK_CODES:
        data = bench_raw.get(b['code'], {})
        benchmark_list.append({
            'code': b['code'],
            'name': b['name'],
            'market': b['market'],
            'price': data.get('current_price'),
            'change': data.get('change'),
            'change_pct': data.get('change_percent'),
        })

    return jsonify({'success': True, 'prices': price_list, 'benchmarks': benchmark_list})


@watch_bp.route('/analyze', methods=['POST'])
def analyze():
    from app.services.unified_stock_data import unified_stock_data_service
    from app.llm.router import llm_router
    from app.llm.prompts.watch_analysis import (
        SYSTEM_PROMPT, build_realtime_analysis_prompt,
        build_7d_analysis_prompt, build_30d_analysis_prompt,
    )

    data = request.get_json() or {}
    period = data.get('period', '30d')
    force = data.get('force', False)

    codes = WatchService.get_watch_codes()
    if not codes:
        return jsonify({'success': True, 'data': {}, 'message': '盯盘列表为空'})

    if period != 'realtime' and not force:
        existing = WatchService.get_all_today_analyses()
        all_cached = all(existing.get(c, {}).get(period) for c in codes)
        if all_cached:
            return jsonify({'success': True, 'data': existing, 'message': f'{period} 使用今日缓存'})

    intraday_map = {}
    trend_map = {}
    if period == 'realtime':
        intraday = unified_stock_data_service.get_intraday_data(codes)
        intraday_map = {s['stock_code']: s for s in intraday.get('stocks', [])}

    if period in ('7d', '30d'):
        days = 7 if period == '7d' else 30
        trend = unified_stock_data_service.get_trend_data(codes, days=days)
        trend_map = {s['stock_code']: s for s in trend.get('stocks', [])}

    raw_prices = unified_stock_data_service.get_realtime_prices(codes)

    provider = llm_router.route('watch_analysis')
    if not provider:
        return jsonify({'success': False, 'message': 'LLM 不可用'})

    for code in codes:
        price_data = raw_prices.get(code, {})
        current_price = price_data.get('current_price', 0)
        stock_name = price_data.get('name', code)
        if not current_price:
            continue

        if period != 'realtime' and not force:
            existing_analysis = WatchService.get_today_analysis(code, period)
            if existing_analysis:
                continue

        try:
            if period == 'realtime':
                intraday_stock = intraday_map.get(code, {})
                intraday_data = intraday_stock.get('data', [])
                if not intraday_data:
                    continue
                prompt = build_realtime_analysis_prompt(stock_name, code, intraday_data, current_price)
            elif period == '7d':
                trend_stock = trend_map.get(code, {})
                ohlc = trend_stock.get('data', [])
                if not ohlc:
                    continue
                prompt = build_7d_analysis_prompt(stock_name, code, ohlc, current_price)
            else:
                trend_stock = trend_map.get(code, {})
                ohlc = trend_stock.get('data', [])
                if not ohlc:
                    continue
                prompt = build_30d_analysis_prompt(stock_name, code, ohlc, current_price)

            response = provider.chat([
                {'role': 'system', 'content': SYSTEM_PROMPT},
                {'role': 'user', 'content': prompt},
            ])
            cleaned = response.strip()
            if cleaned.startswith('```'):
                cleaned = cleaned.split('\n', 1)[-1].rsplit('```', 1)[0].strip()
            parsed = json.loads(cleaned)
            WatchService.save_analysis(
                stock_code=code,
                period=period,
                support_levels=parsed.get('support_levels', []),
                resistance_levels=parsed.get('resistance_levels', []),
                summary=parsed.get('summary', ''),
            )
        except Exception as e:
            db.session.rollback()
            logger.error(f"[盯盘AI] {code} {period}分析失败: {e}")

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
    from app.services.unified_stock_data import unified_stock_data_service
    from app.services.trading_calendar import TradingCalendarService
    from app.utils.market_identifier import MarketIdentifier

    code = request.args.get('code', '').strip()
    period = request.args.get('period', 'intraday')
    last_timestamp = request.args.get('last_timestamp', '').strip()

    if not code:
        return jsonify({'success': False, 'message': '缺少股票代码'})

    result = {'success': True, 'code': code, 'period': period}

    if period == 'intraday':
        market = MarketIdentifier.identify(code) or 'A'
        is_open = TradingCalendarService.is_market_open(market)

        intraday = unified_stock_data_service.get_intraday_data([code])
        stocks = intraday.get('stocks', [])
        stock_data = stocks[0] if stocks else {}
        all_data = stock_data.get('data', [])

        # 优先使用数据自带的 trading_date，兜底用 effective_cache_date
        trading_date = stock_data.get('trading_date', '')
        if not trading_date:
            from app.services.market_session import SmartCacheStrategy
            effective_date = SmartCacheStrategy.get_effective_cache_date(code)
            trading_date = effective_date.strftime('%Y-%m-%d')

        if last_timestamp and all_data:
            all_data = [d for d in all_data if d.get('time', '') > last_timestamp]

        result['data'] = all_data
        result['chart_type'] = 'line'
        result['is_open'] = is_open
        result['is_trading'] = is_open
        result['trading_date'] = trading_date
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

    analysis_data = WatchService.get_today_analysis(code)
    if analysis_data and isinstance(analysis_data, dict):
        all_supports = []
        all_resistances = []
        for p_data in analysis_data.values():
            if isinstance(p_data, dict):
                all_supports.extend(p_data.get('support_levels', []))
                all_resistances.extend(p_data.get('resistance_levels', []))
        result['support_levels'] = sorted(set(all_supports))
        result['resistance_levels'] = sorted(set(all_resistances))
    else:
        result['support_levels'] = []
        result['resistance_levels'] = []

    return jsonify(result)
