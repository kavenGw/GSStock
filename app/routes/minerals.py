import logging

from flask import render_template, jsonify, request

from app.routes import minerals_bp
from app.config.minerals import MINERAL_BOARDS

logger = logging.getLogger(__name__)

# 延迟绑定：由路由首次调用时从 minerals_data 注入，避免循环导入
# tests 通过 monkeypatch.setattr(mod, 'get_board_data', ...) 替换此名字
get_board_data = None


def _lazy_get_board_data(commodity, days=30, force_refresh=False):
    global get_board_data
    if get_board_data is None:
        from app.services.minerals_data import get_board_data as _gbd
        get_board_data = _gbd
    return get_board_data(commodity, days=days, force_refresh=force_refresh)


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
        data = _lazy_get_board_data(commodity, days=days, force_refresh=force)
    except Exception as e:
        logger.warning(f'[矿产] 板块 {commodity} 装配失败: {type(e).__name__}: {e}', exc_info=True)
        return jsonify({'commodity': commodity, 'name': MINERAL_BOARDS[commodity]['name'],
                        'futures': {'data': [], 'is_fallback': True, 'note': '数据获取失败'},
                        'stocks': []})
    return jsonify(data)
