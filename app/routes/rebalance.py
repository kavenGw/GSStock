from flask import render_template, request, jsonify
from app.routes import rebalance_bp
from app.services.rebalance import RebalanceService


@rebalance_bp.route('/')
def index():
    """仓位管理页面"""
    return render_template('rebalance.html')


@rebalance_bp.route('/api/stocks')
def get_stocks():
    """获取股票列表（含权重、选中状态、当前持仓）"""
    stocks = RebalanceService.get_all_stocks_with_status()
    current_value = sum(s['market_value'] for s in stocks)
    return jsonify({
        'success': True,
        'current_value': round(current_value, 2),
        'stocks': stocks
    })


@rebalance_bp.route('/api/selection', methods=['POST'])
def save_selection():
    """保存股票选中状态"""
    data = request.get_json()
    stock_code = data.get('stock_code') if data else None
    selected = data.get('selected') if data else None

    if not stock_code:
        return jsonify({'success': False, 'error': '缺少股票代码'}), 400

    if selected is None:
        return jsonify({'success': False, 'error': '缺少选中状态'}), 400

    RebalanceService.save_selection(stock_code, selected)
    return jsonify({'success': True})


@rebalance_bp.route('/api/calculate', methods=['POST'])
def calculate():
    """计算操作建议并保存"""
    data = request.get_json()
    target_value = data.get('target_value') if data else None

    if target_value is None:
        return jsonify({'success': False, 'error': '缺少目标市值'}), 400

    try:
        target_value = float(target_value)
    except (ValueError, TypeError):
        return jsonify({'success': False, 'error': '目标市值必须是数字'}), 400

    result = RebalanceService.calculate_position_plan(target_value)
    if not result.get('success'):
        return jsonify(result), 400

    # 保存计算结果（只保存选中股票的操作建议，不包括清仓建议）
    RebalanceService.save_position_plan(result.get('items', []), target_value)

    return jsonify(result)


@rebalance_bp.route('/api/plans')
def get_plans():
    """获取已保存的仓位计划"""
    data = RebalanceService.get_position_plans()
    return jsonify({
        'success': True,
        'items': data['items'],
        'target_value': data['target_value'],
    })


@rebalance_bp.route('/api/weight', methods=['POST'])
def save_weight():
    """保存权重"""
    data = request.get_json()
    stock_code = data.get('stock_code') if data else None
    weight = data.get('weight') if data else None

    if not stock_code:
        return jsonify({'success': False, 'error': '缺少股票代码'}), 400

    if weight is None:
        return jsonify({'success': False, 'error': '缺少权重值'}), 400

    success, error = RebalanceService.save_weight(stock_code, weight)
    if not success:
        return jsonify({'success': False, 'error': error}), 400

    return jsonify({'success': True})
