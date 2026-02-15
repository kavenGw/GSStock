"""股票详情抽屉 - 聚合数据API"""
import os
import logging
from datetime import date, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from flask import jsonify, request, current_app, send_file
from app.routes import stock_detail_bp

logger = logging.getLogger(__name__)


def _normalize_ohlc(raw):
    """将OHLC数据统一转为dict列表"""
    result = []
    for d in raw:
        if hasattr(d, 'to_dict'):
            d = d.to_dict()
        if isinstance(d, dict):
            result.append({
                'date': d.get('date', ''),
                'open': d.get('open', 0),
                'high': d.get('high', 0),
                'low': d.get('low', 0),
                'close': d.get('close', 0),
                'volume': d.get('volume', 0),
            })
        else:
            result.append({
                'date': getattr(d, 'date', ''),
                'open': getattr(d, 'open', 0),
                'high': getattr(d, 'high', 0),
                'low': getattr(d, 'low', 0),
                'close': getattr(d, 'close', 0),
                'volume': getattr(d, 'volume', 0),
            })
    return result


@stock_detail_bp.route('/<code>')
def get_detail(code):
    """聚合端点 - 并行获取所有数据"""
    from app.services.unified_stock_data import unified_stock_data_service
    from app.services.technical_indicators import TechnicalIndicatorService
    from app.services.ai_analyzer import AIAnalyzerService

    app = current_app._get_current_object()

    def fetch_basic():
        with app.app_context():
            result = unified_stock_data_service.get_realtime_prices([code])
            stocks = result.get('stocks', [])
            if stocks:
                p = stocks[0]
                return {
                    'code': code,
                    'name': p.get('name', ''),
                    'market': p.get('market', ''),
                    'price': p.get('price', 0),
                    'change': p.get('change', 0),
                    'change_pct': p.get('change_pct', 0),
                    'volume': p.get('volume', 0),
                }
            return {'code': code, 'name': '', 'market': '', 'price': 0, 'change': 0, 'change_pct': 0, 'volume': 0}

    def fetch_ohlc():
        with app.app_context():
            result = unified_stock_data_service.get_trend_data([code], days=60)
            stocks = result.get('stocks', [])
            if stocks:
                raw = stocks[0].get('data', [])
                return _normalize_ohlc(raw)
            return []

    def fetch_wyckoff():
        with app.app_context():
            from app.models.wyckoff import WyckoffAutoResult
            wyckoff = WyckoffAutoResult.query.filter_by(
                stock_code=code, status='success', timeframe='daily'
            ).order_by(WyckoffAutoResult.analysis_date.desc()).first()
            if not wyckoff:
                return None
            return {
                'phase': wyckoff.phase,
                'advice': wyckoff.advice,
                'support_price': wyckoff.support_price,
                'resistance_price': wyckoff.resistance_price,
                'events': wyckoff.to_dict().get('events', []),
                'score': wyckoff.score,
                'confidence': wyckoff.confidence,
                'composite_signal': wyckoff.composite_signal,
                'analysis_date': wyckoff.analysis_date.isoformat() if wyckoff.analysis_date else None,
            }

    def fetch_position():
        with app.app_context():
            from app.models.position import Position
            from app.services.position import PositionService
            latest_date = PositionService.get_latest_date()
            if not latest_date:
                return None
            pos = Position.query.filter_by(date=latest_date, stock_code=code).first()
            if not pos:
                return None
            return {
                'quantity': pos.quantity,
                'cost_price': round(pos.cost_price, 2),
                'total_amount': round(pos.total_amount, 2),
            }

    def fetch_advice():
        with app.app_context():
            from app.models.stock import Stock
            stock = Stock.query.filter_by(stock_code=code).first()
            if stock:
                return {'advice': stock.investment_advice, 'name': stock.stock_name}
            return {'advice': None, 'name': None}

    try:
        # ohlc 和其他独立数据并行获取
        parallel_tasks = {
            'basic': fetch_basic,
            'position': fetch_position,
            'ohlc': fetch_ohlc,
            'wyckoff': fetch_wyckoff,
            'advice_info': fetch_advice,
        }
        results = {}

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {executor.submit(fn): key for key, fn in parallel_tasks.items()}
            for future in as_completed(futures):
                key = futures[future]
                try:
                    results[key] = future.result()
                except Exception as e:
                    logger.error(f"获取 {key} 数据失败: {e}", exc_info=True)
                    results[key] = None

        basic = results.get('basic') or {'code': code, 'name': '', 'market': '', 'price': 0, 'change': 0, 'change_pct': 0, 'volume': 0}
        advice_info = results.get('advice_info') or {}
        ohlc = results.get('ohlc') or []

        # Stock模型的名称优先
        if advice_info.get('name'):
            basic['name'] = advice_info['name']

        # technical 依赖 ohlc 数据
        technical = None
        try:
            if ohlc:
                technical = TechnicalIndicatorService.calculate_all(ohlc)
                if technical:
                    technical = {
                        'score': technical.get('score'),
                        'signal': technical.get('signal'),
                        'signal_text': technical.get('signal_text'),
                        'macd_signal': technical.get('macd', {}).get('signal'),
                        'rsi_6': technical.get('rsi', {}).get('rsi_6'),
                        'trend_state': technical.get('trend', {}).get('state'),
                    }
        except Exception as e:
            logger.error(f"计算技术指标失败: {e}", exc_info=True)

        # 计算盈亏
        position = results.get('position')
        if position and basic.get('price') and position.get('cost_price'):
            cost = position['cost_price']
            price = basic['price']
            position['profit'] = round((price - cost) * position['quantity'], 2)
            position['profit_pct'] = round((price - cost) / cost * 100, 2) if cost > 0 else 0

        return jsonify({
            'basic': basic,
            'position': position,
            'ohlc': ohlc,
            'technical': technical,
            'wyckoff': results.get('wyckoff'),
            'advice': advice_info.get('advice'),
            'ai_enabled': AIAnalyzerService.is_available(),
        })
    except Exception as e:
        logger.error(f"获取股票详情失败: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@stock_detail_bp.route('/<code>/ohlc')
def get_ohlc(code):
    """单独走势数据（用于切换时间周期）"""
    from app.services.unified_stock_data import unified_stock_data_service

    days = request.args.get('days', 30, type=int)
    try:
        result = unified_stock_data_service.get_trend_data([code], days=days)
        stocks = result.get('stocks', [])
        ohlc = []
        if stocks:
            raw = stocks[0].get('data', [])
            ohlc = _normalize_ohlc(raw)
        return jsonify({'ohlc': ohlc})
    except Exception as e:
        logger.error(f"获取OHLC数据失败: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@stock_detail_bp.route('/ai/status')
def ai_status():
    """AI分析功能状态"""
    from app.services.ai_analyzer import AIAnalyzerService
    return jsonify({'enabled': AIAnalyzerService.is_available()})


@stock_detail_bp.route('/ai/history')
def ai_history():
    """获取股票AI分析历史"""
    from app.models.unified_cache import UnifiedStockCache

    stock_code = request.args.get('stock_code', '')
    if not stock_code:
        return jsonify({'error': '缺少 stock_code'}), 400

    try:
        today = date.today()
        history = []

        caches = UnifiedStockCache.query.filter(
            UnifiedStockCache.stock_code == stock_code,
            UnifiedStockCache.cache_type == 'ai_analysis',
            UnifiedStockCache.cache_date >= today - timedelta(days=30)
        ).order_by(UnifiedStockCache.cache_date.desc()).limit(10).all()

        for cache in caches:
            data = cache.get_data()
            if data and isinstance(data, dict) and 'error' not in data:
                history.append({
                    'date': cache.cache_date.strftime('%Y-%m-%d'),
                    'signal': data.get('signal'),
                    'score': data.get('score'),
                    'conclusion': data.get('conclusion'),
                    'confidence': data.get('confidence'),
                    'analysis': data.get('analysis'),
                    'action_plan': data.get('action_plan'),
                })

        return jsonify({'history': history})
    except Exception as e:
        logger.error(f"获取AI历史失败: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@stock_detail_bp.route('/ai/analyze', methods=['POST'])
def ai_analyze():
    """单只股票AI分析"""
    from app.services.ai_analyzer import AIAnalyzerService
    if not AIAnalyzerService.is_available():
        return jsonify({'error': 'AI分析未配置'}), 400

    data = request.get_json() or {}
    stock_code = data.get('stock_code', '')
    stock_name = data.get('stock_name', '')
    force = data.get('force', False)

    if not stock_code:
        return jsonify({'error': '缺少 stock_code'}), 400

    try:
        result = AIAnalyzerService.analyze_stock(stock_code, stock_name, force)
        return jsonify(result)
    except Exception as e:
        logger.error(f"AI分析 {stock_code} 失败: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@stock_detail_bp.route('/ai/batch', methods=['POST'])
def ai_batch():
    """批量AI分析"""
    from app.services.ai_analyzer import AIAnalyzerService
    if not AIAnalyzerService.is_available():
        return jsonify({'error': 'AI分析未配置'}), 400

    data = request.get_json() or {}
    stocks = data.get('stocks', [])
    if not stocks:
        return jsonify({'error': '缺少 stocks 列表'}), 400

    try:
        results = AIAnalyzerService.analyze_batch(stocks)
        return jsonify({'results': results})
    except Exception as e:
        logger.error(f"批量AI分析失败: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@stock_detail_bp.route('/<code>/wyckoff/analyze', methods=['POST'])
def wyckoff_analyze(code):
    from app.services.wyckoff import WyckoffAutoService
    from app.models.stock import Stock

    data = request.get_json() or {}
    timeframe = data.get('timeframe', 'daily')
    multi = data.get('multi_timeframe', False)

    try:
        stock = Stock.query.filter_by(stock_code=code).first()
        stock_name = stock.stock_name if stock else ''

        if multi:
            result = WyckoffAutoService.analyze_multi_timeframe(code, stock_name)
        else:
            result = WyckoffAutoService.analyze_single(code, stock_name, timeframe)
        return jsonify(result)
    except Exception as e:
        logger.error(f"威科夫分析 {code} 失败: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@stock_detail_bp.route('/<code>/wyckoff/backtest', methods=['POST'])
def wyckoff_backtest(code):
    """单股回测验证"""
    from app.services.backtest import BacktestService

    data = request.get_json() or {}
    days = data.get('days', 180)

    try:
        service = BacktestService()
        wyckoff_result = service.backtest_wyckoff(code, days)
        signal_result = service.backtest_signals(code, days)
        return jsonify({'wyckoff': wyckoff_result, 'signals': signal_result})
    except Exception as e:
        logger.error(f"威科夫回测 {code} 失败: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@stock_detail_bp.route('/<code>/wyckoff/reference/<phase>')
def wyckoff_reference(code, phase):
    """获取阶段参考图（直接返回图片文件）"""
    from app.models.wyckoff import WyckoffReference

    try:
        ref = WyckoffReference.query.filter_by(phase=phase)\
            .order_by(WyckoffReference.created_at.desc()).first()
        if not ref or not ref.image_path or not os.path.exists(ref.image_path):
            return jsonify({'error': '暂无参考图'}), 404
        return send_file(ref.image_path)
    except Exception as e:
        logger.error(f"获取参考图失败: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@stock_detail_bp.route('/<code>/wyckoff/history')
def wyckoff_history(code):
    from app.models.wyckoff import WyckoffAutoResult

    try:
        records = WyckoffAutoResult.query.filter_by(
            stock_code=code, status='success', timeframe='daily'
        ).order_by(WyckoffAutoResult.analysis_date.desc()).limit(20).all()
        return jsonify({'history': [r.to_dict() for r in records]})
    except Exception as e:
        logger.error(f"获取威科夫历史失败: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500
