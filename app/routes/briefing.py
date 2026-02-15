"""每日简报路由 - 渐进式加载"""
import logging
from flask import render_template, jsonify, request
from app.routes import briefing_bp
from app.services.briefing import BriefingService
from app.services.notification import NotificationService

logger = logging.getLogger(__name__)


@briefing_bp.route('/')
def index():
    """每日简报页面"""
    return render_template('briefing.html')


@briefing_bp.route('/api/stocks')
def get_stocks():
    """基础股票数据（价格+投资建议）"""
    try:
        force = request.args.get('force', 'false') == 'true'
        data = BriefingService.get_stocks_basic_data(force)
        return jsonify(data)
    except Exception as e:
        logger.error(f"获取股票数据失败: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@briefing_bp.route('/api/stocks/pe')
def get_stocks_pe():
    """股票PE数据"""
    try:
        force = request.args.get('force', 'false') == 'true'
        data = BriefingService.get_stocks_pe_data(force)
        return jsonify(data)
    except Exception as e:
        logger.error(f"获取PE数据失败: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@briefing_bp.route('/api/stocks/earnings')
def get_stocks_earnings():
    """股票财报日期"""
    try:
        force = request.args.get('force', 'false') == 'true'
        data = BriefingService.get_stocks_earnings_data(force)
        return jsonify(data)
    except Exception as e:
        logger.error(f"获取财报日期失败: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@briefing_bp.route('/api/indices')
def get_indices():
    """指数数据"""
    try:
        force = request.args.get('force', 'false') == 'true'
        data = BriefingService.get_indices_data(force)
        return jsonify(data)
    except Exception as e:
        logger.error(f"获取指数数据失败: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@briefing_bp.route('/api/futures')
def get_futures():
    """期货数据"""
    try:
        force = request.args.get('force', 'false') == 'true'
        data = BriefingService.get_futures_data(force)
        return jsonify(data)
    except Exception as e:
        logger.error(f"获取期货数据失败: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@briefing_bp.route('/api/etf')
def get_etf():
    """ETF溢价数据"""
    try:
        force = request.args.get('force', 'false') == 'true'
        data = BriefingService.get_etf_premium_data(force)
        return jsonify(data)
    except Exception as e:
        logger.error(f"获取ETF数据失败: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@briefing_bp.route('/api/sectors')
def get_sectors():
    """板块数据（涨幅+评级）"""
    try:
        force = request.args.get('force', 'false') == 'true'
        cn = BriefingService.get_cn_sectors_data(force)
        us = BriefingService.get_us_sectors_data(force)
        ratings = BriefingService.get_sector_ratings(None, force)
        return jsonify({
            'cn_sectors': cn,
            'us_sectors': us,
            'sector_ratings': ratings
        })
    except Exception as e:
        logger.error(f"获取板块数据失败: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@briefing_bp.route('/api/stocks/technical')
def get_stocks_technical():
    """股票技术指标数据（评分+MACD信号）"""
    try:
        force = request.args.get('force', 'false') == 'true'
        data = BriefingService.get_stocks_technical_data(force)
        return jsonify(data)
    except Exception as e:
        logger.error(f"获取技术指标失败: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@briefing_bp.route('/api/earnings-alerts')
def get_earnings_alerts():
    """财报预警数据"""
    try:
        data = BriefingService.get_earnings_alert_data()
        return jsonify(data)
    except Exception as e:
        logger.error(f"获取财报预警失败: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@briefing_bp.route('/api/notification/status')
def notification_status():
    """推送配置状态"""
    return jsonify(NotificationService.get_status())


@briefing_bp.route('/api/notification/push', methods=['POST'])
def notification_push():
    """推送每日报告"""
    data = request.get_json() or {}
    include_ai = data.get('include_ai', False)

    try:
        results = NotificationService.push_daily_report(include_ai=include_ai)
        return jsonify(results)
    except Exception as e:
        logger.error(f"推送报告失败: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@briefing_bp.route('/api/notification/test', methods=['POST'])
def notification_test():
    """测试推送"""
    data = request.get_json() or {}
    channel = data.get('channel', 'all')

    try:
        test_msg = '测试消息 - 股票分析系统推送配置验证'
        test_html = '<h3>测试消息</h3><p>股票分析系统推送配置验证成功</p>'
        results = {}

        if channel in ('slack', 'all'):
            results['slack'] = NotificationService.send_slack(test_msg)
        if channel in ('email', 'all'):
            results['email'] = NotificationService.send_email('推送测试', test_html)

        return jsonify(results)
    except Exception as e:
        logger.error(f"测试推送失败: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500
