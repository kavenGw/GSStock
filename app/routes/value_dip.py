import logging
from flask import render_template, jsonify
from app.routes import value_dip_bp
from app.services.value_dip import ValueDipService

logger = logging.getLogger(__name__)


@value_dip_bp.route('/')
def index():
    return render_template('value_dip.html')


@value_dip_bp.route('/api/sectors')
def sectors():
    try:
        data = ValueDipService.get_sector_performance()
        return jsonify(data)
    except Exception as e:
        logger.error(f'[价值洼地] API 错误: {e}')
        return jsonify({'error': str(e)}), 500
