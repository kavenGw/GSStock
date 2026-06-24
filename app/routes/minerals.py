import logging

from flask import render_template, jsonify, request

from app.routes import minerals_bp
from app.config.minerals import MINERAL_BOARDS
from app.services.minerals_data import get_board_data

logger = logging.getLogger(__name__)


@minerals_bp.route('/')
def index():
    boards = [{'commodity': k, 'name': v['name'], 'futures_name': v['futures_name']}
              for k, v in MINERAL_BOARDS.items()]
    return render_template('minerals.html', boards=boards)


@minerals_bp.route('/api/board/<commodity>')
def api_board(commodity):
    if commodity not in MINERAL_BOARDS:
        return jsonify({'error': f'unknown commodity: {commodity}'}), 404
    days = request.args.get('days', '30')
    days = int(days) if days.isdigit() else 30
    force = request.args.get('force', '0') == '1'
    try:
        data = get_board_data(commodity, days=days, force_refresh=force)
    except Exception as e:
        logger.warning(f'[矿产] 板块 {commodity} 装配失败: {type(e).__name__}: {e}', exc_info=True)
        return jsonify({'commodity': commodity, 'name': MINERAL_BOARDS[commodity]['name'],
                        'futures': {'data': [], 'is_fallback': True, 'note': '数据获取失败'},
                        'stocks': []})
    return jsonify(data)
