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
    from app.config.stock_codes import BENCHMARK_CODES
    from app.services.trading_calendar import TradingCalendarService
    from app.utils.market_identifier import MarketIdentifier

    codes = WatchService.get_watch_codes()

    def _fetch_prices_with_cache(target_codes: list) -> dict:
        if not target_codes:
            return {}

        cached, missing = unified_stock_data_service.get_prices_cached_only(target_codes)
        stale = [code for code, data in cached.items()
                 if isinstance(data, dict) and data.get('_is_degraded')]
        refresh_candidates = set(missing) | set(stale)

        # If market is open and cache is missing or degraded, force a refresh once.
        if refresh_candidates:
            refresh_codes = []
            for code in refresh_candidates:
                market = MarketIdentifier.identify(code) or 'A'
                if TradingCalendarService.is_market_open(market):
                    refresh_codes.append(code)
            if refresh_codes:
                fetched = unified_stock_data_service.get_realtime_prices(refresh_codes, force_refresh=True)
                cached.update(fetched)
        return cached

    price_list = []
    if codes:
        raw_prices = _fetch_prices_with_cache(codes)
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

    bench_codes = [b['code'] for b in BENCHMARK_CODES]
    bench_raw = _fetch_prices_with_cache(bench_codes)
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
    from app.services.watch_analysis_service import WatchAnalysisService

    data = request.get_json() or {}
    period = data.get('period', '30d')
    force = data.get('force', False)

    all_analyses = WatchAnalysisService.analyze_stocks(period, force)
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

        TRADING_SESSIONS = {
            'A': [['09:30', '11:30'], ['13:00', '15:00']],
            'KR': [['09:00', '15:30']],
            'US': [['09:30', '16:00']],
            'HK': [['09:30', '16:00']],
            'JP': [['09:00', '11:30'], ['12:30', '15:00']],
            'TW': [['09:00', '13:30']],
        }
        result['trading_sessions'] = TRADING_SESSIONS.get(market, [['09:30', '16:00']])

        prev_day_data = []
        try:
            from datetime import datetime as dt_cls
            trading_date_obj = dt_cls.strptime(trading_date, '%Y-%m-%d').date() if trading_date else None
            if trading_date_obj:
                prev_date = TradingCalendarService.get_last_trading_day(market, trading_date_obj)
                from app.models.unified_cache import UnifiedStockCache
                cached = UnifiedStockCache.get_cache_with_status([code], 'intraday_1m', prev_date).get(code)
                if cached and cached.get('data'):
                    prev_day_data = cached['data'].get('data', [])
        except Exception as e:
            import logging
            logging.getLogger(__name__).debug(f"[盯盘] 前日分时缓存读取失败 {code}: {e}")
        result['prev_day_data'] = prev_day_data

        prev_close = None
        if prev_day_data:
            prev_close = prev_day_data[-1].get('close')
        if prev_close is None:
            try:
                trend_2d = unified_stock_data_service.get_trend_data([code], days=5)
                trend_stocks = trend_2d.get('stocks', [])
                if trend_stocks and len(trend_stocks[0].get('data', [])) >= 2:
                    prev_close = trend_stocks[0]['data'][-2].get('close')
            except Exception:
                pass
        result['prev_close'] = prev_close

        # 分钟级九转信号
        from app.services.td_sequential import TDSequentialService
        td_intraday = {'direction': None, 'count': 0, 'completed': False, 'history': []}
        try:
            intraday_ohlc = stock_data.get('data', [])
            if len(intraday_ohlc) >= 5:
                td_intraday = TDSequentialService.calculate(intraday_ohlc)
        except Exception as e:
            logger.debug(f"[盯盘] 分钟级九转信号计算失败 {code}: {e}")
        result['td_sequential_intraday'] = td_intraday
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

    # 算法支撑/压力（基于60日OHLC）
    from app.utils.support_resistance import calculate_support_resistance
    algo_sr = {'support': [], 'resistance': []}
    stocks_60d = []
    try:
        trend_60d = unified_stock_data_service.get_trend_data([code], days=60)
        stocks_60d = trend_60d.get('stocks', [])
        if stocks_60d and stocks_60d[0].get('data') and len(stocks_60d[0]['data']) >= 20:
            ohlc = stocks_60d[0]['data']
            highs = [d['high'] for d in ohlc]
            lows = [d['low'] for d in ohlc]
            closes = [d['close'] for d in ohlc]
            algo_sr = calculate_support_resistance(highs, lows, closes)
    except Exception as e:
        logger.debug(f"[盯盘] 算法支撑/压力计算失败 {code}: {e}")

    # AI分析的支撑/压力
    ai_supports = []
    ai_resistances = []
    analysis_data = WatchService.get_today_analysis(code)
    if analysis_data and isinstance(analysis_data, dict):
        for p_data in analysis_data.values():
            if isinstance(p_data, dict):
                ai_supports.extend(p_data.get('support_levels', []))
                ai_resistances.extend(p_data.get('resistance_levels', []))

    # 合并去重
    result['support_levels'] = sorted(set(algo_sr['support'] + ai_supports))
    result['resistance_levels'] = sorted(set(algo_sr['resistance'] + ai_resistances))

    # 九转序列信号（复用60日趋势数据）
    from app.services.td_sequential import TDSequentialService
    td_result = {'direction': None, 'count': 0, 'completed': False, 'history': []}
    try:
        if stocks_60d and stocks_60d[0].get('data'):
            td_result = TDSequentialService.calculate(stocks_60d[0]['data'])
    except Exception as e:
        logger.debug(f"[盯盘] 九转信号计算失败 {code}: {e}")
    result['td_sequential'] = td_result

    return jsonify(result)


@watch_bp.route('/earnings')
def earnings():
    from app.services.earnings_service import QuarterlyEarningsService

    code = request.args.get('code', '').strip()
    if not code:
        return jsonify({'success': False, 'message': '缺少股票代码'})

    data = QuarterlyEarningsService.get_earnings(code)
    return jsonify({'success': True, 'data': data})
