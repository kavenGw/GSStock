"""每日简报路由"""
import logging
from flask import render_template, jsonify
from app.routes import briefing_bp
from app.services.briefing import BriefingService

logger = logging.getLogger(__name__)


@briefing_bp.route('/')
def index():
    """每日简报页面"""
    return render_template('briefing.html')


@briefing_bp.route('/api/data')
def get_data():
    """获取简报数据 API"""
    try:
        data = BriefingService.get_briefing_data(force_refresh=False)
        # 添加财报预警数据
        earnings_alert_data = BriefingService.get_earnings_alert_data()
        data['earnings_alerts'] = earnings_alert_data.get('earnings_alerts', [])
        data['has_earnings_alerts'] = earnings_alert_data.get('has_alerts', False)
        return jsonify(data)
    except Exception as e:
        logger.error(f"获取简报数据失败: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@briefing_bp.route('/api/refresh', methods=['POST'])
def refresh_data():
    """强制刷新简报数据 API"""
    try:
        data = BriefingService.get_briefing_data(force_refresh=True)
        # 添加财报预警数据
        earnings_alert_data = BriefingService.get_earnings_alert_data()
        data['earnings_alerts'] = earnings_alert_data.get('earnings_alerts', [])
        data['has_earnings_alerts'] = earnings_alert_data.get('has_alerts', False)
        return jsonify(data)
    except Exception as e:
        logger.error(f"刷新简报数据失败: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500
