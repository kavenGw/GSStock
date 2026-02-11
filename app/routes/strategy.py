"""交易策略路由"""
from flask import request, jsonify, render_template
from app.routes import strategy_bp
from app.services.trading_strategy import TradingStrategyService


@strategy_bp.route('/')
def index():
    """交易策略主页"""
    strategies = TradingStrategyService.get_all_strategies(include_inactive=True)
    statistics = TradingStrategyService.get_statistics()
    return render_template(
        'trading_strategy.html',
        strategies=strategies,
        statistics=statistics,
        categories=TradingStrategyService.CATEGORIES,
        action_types=TradingStrategyService.ACTION_TYPES,
        markets=TradingStrategyService.MARKETS,
    )


@strategy_bp.route('/api/list')
def api_list():
    """获取策略列表API"""
    include_inactive = request.args.get('include_inactive', 'false').lower() == 'true'
    category = request.args.get('category')

    if category:
        strategies = TradingStrategyService.get_strategies_by_category(category, include_inactive)
    else:
        strategies = TradingStrategyService.get_all_strategies(include_inactive)

    return jsonify({
        'success': True,
        'strategies': strategies
    })


@strategy_bp.route('/api/<int:strategy_id>')
def api_get(strategy_id):
    """获取单个策略API"""
    strategy = TradingStrategyService.get_strategy(strategy_id)
    if not strategy:
        return jsonify({'error': '策略不存在'}), 404
    return jsonify({'success': True, 'strategy': strategy})


@strategy_bp.route('/api/create', methods=['POST'])
def api_create():
    """创建策略API"""
    data = request.get_json()
    if not data:
        return jsonify({'error': '无效的请求数据'}), 400

    # 验证必填字段
    if not data.get('name'):
        return jsonify({'error': '策略名称不能为空'}), 400
    if not data.get('trigger_condition'):
        return jsonify({'error': '触发条件不能为空'}), 400
    if not data.get('action_type'):
        return jsonify({'error': '操作类型不能为空'}), 400

    try:
        strategy = TradingStrategyService.create_strategy(data)
        return jsonify({'success': True, 'strategy': strategy})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@strategy_bp.route('/api/<int:strategy_id>', methods=['PUT'])
def api_update(strategy_id):
    """更新策略API"""
    data = request.get_json()
    if not data:
        return jsonify({'error': '无效的请求数据'}), 400

    strategy = TradingStrategyService.update_strategy(strategy_id, data)
    if not strategy:
        return jsonify({'error': '策略不存在'}), 404

    return jsonify({'success': True, 'strategy': strategy})


@strategy_bp.route('/api/<int:strategy_id>', methods=['DELETE'])
def api_delete(strategy_id):
    """删除策略API"""
    if TradingStrategyService.delete_strategy(strategy_id):
        return jsonify({'success': True})
    return jsonify({'error': '策略不存在'}), 404


@strategy_bp.route('/api/<int:strategy_id>/toggle', methods=['POST'])
def api_toggle(strategy_id):
    """切换策略启用状态API"""
    strategy = TradingStrategyService.toggle_strategy(strategy_id)
    if not strategy:
        return jsonify({'error': '策略不存在'}), 404
    return jsonify({'success': True, 'strategy': strategy})


# 执行记录相关API

@strategy_bp.route('/api/executions')
def api_executions():
    """获取执行记录列表API"""
    strategy_id = request.args.get('strategy_id', type=int)
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    limit = request.args.get('limit', 50, type=int)

    executions = TradingStrategyService.get_executions(
        strategy_id=strategy_id,
        start_date=start_date,
        end_date=end_date,
        limit=limit
    )
    return jsonify({'success': True, 'executions': executions})


@strategy_bp.route('/api/executions/create', methods=['POST'])
def api_create_execution():
    """记录策略执行API"""
    data = request.get_json()
    if not data:
        return jsonify({'error': '无效的请求数据'}), 400

    strategy_id = data.get('strategy_id')
    if not strategy_id:
        return jsonify({'error': '策略ID不能为空'}), 400

    try:
        execution = TradingStrategyService.record_execution(strategy_id, data)
        if not execution:
            return jsonify({'error': '策略不存在'}), 404
        return jsonify({'success': True, 'execution': execution})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@strategy_bp.route('/api/executions/<int:execution_id>', methods=['DELETE'])
def api_delete_execution(execution_id):
    """删除执行记录API"""
    if TradingStrategyService.delete_execution(execution_id):
        return jsonify({'success': True})
    return jsonify({'error': '记录不存在'}), 404


@strategy_bp.route('/api/statistics')
def api_statistics():
    """获取统计信息API"""
    statistics = TradingStrategyService.get_statistics()
    return jsonify({'success': True, 'statistics': statistics})
