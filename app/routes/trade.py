from datetime import date
from flask import request, jsonify, render_template
from app.routes import trade_bp
from app.services.trade import TradeService
from app.services.bank_transfer import BankTransferService


@trade_bp.route('/')
def index():
    stock_code = request.args.get('stock_code', '')
    trade_type = request.args.get('trade_type', '')

    trades = TradeService.get_trades(
        stock_code=stock_code if stock_code else None,
        trade_type=trade_type if trade_type else None
    )

    stock_codes = TradeService.get_stock_codes()
    stock_codes_with_names = TradeService.get_stock_codes_with_names()

    # 计算每只股票的可结算状态
    settleable_stocks = {}
    for code in stock_codes:
        check = TradeService.check_settlement(code)
        if check['can_settle']:
            settleable_stocks[code] = True

    return render_template(
        'trade_list.html',
        trades=trades,
        stock_codes=stock_codes,
        stock_codes_with_names=stock_codes_with_names,
        current_stock_code=stock_code,
        current_trade_type=trade_type,
        settleable_stocks=settleable_stocks,
    )


@trade_bp.route('/save', methods=['POST'])
def save():
    data = request.get_json()
    if not data or 'trades' not in data:
        return jsonify({'error': '无效的数据'}), 400

    trades_data = data['trades']
    saved_count = 0

    for trade_data in trades_data:
        # 验证必填字段
        if not trade_data.get('stock_code'):
            continue
        if not trade_data.get('trade_type'):
            continue
        if not trade_data.get('quantity') or trade_data['quantity'] <= 0:
            continue
        if not trade_data.get('price') or trade_data['price'] <= 0:
            continue

        # 设置默认日期
        if not trade_data.get('trade_date'):
            trade_data['trade_date'] = date.today().isoformat()

        # 验证日期不能晚于今天
        trade_date = date.fromisoformat(trade_data['trade_date'])
        if trade_date > date.today():
            return jsonify({'error': f'交易日期不能晚于今天: {trade_data["trade_date"]}'}), 400

        TradeService.save_trade(trade_data)
        saved_count += 1

    return jsonify({'success': True, 'count': saved_count})


@trade_bp.route('/<int:trade_id>', methods=['DELETE'])
def delete(trade_id):
    if TradeService.delete_trade(trade_id):
        return jsonify({'success': True})
    return jsonify({'error': '交易记录不存在'}), 404


@trade_bp.route('/<int:trade_id>', methods=['PUT'])
def update(trade_id):
    data = request.get_json()
    if not data:
        return jsonify({'error': '无效的数据'}), 400

    # 验证数据
    if 'quantity' in data and data['quantity'] <= 0:
        return jsonify({'error': '数量必须大于0'}), 400
    if 'price' in data and data['price'] <= 0:
        return jsonify({'error': '价格必须大于0'}), 400
    if 'trade_date' in data:
        trade_date = date.fromisoformat(data['trade_date'])
        if trade_date > date.today():
            return jsonify({'error': '交易日期不能晚于今天'}), 400

    trade = TradeService.update_trade(trade_id, data)
    if trade:
        return jsonify({'success': True, 'trade': trade.to_dict()})
    return jsonify({'error': '交易记录不存在'}), 404


@trade_bp.route('/settle/<stock_code>', methods=['POST'])
def settle(stock_code):
    check = TradeService.check_settlement(stock_code)
    if not check['can_settle']:
        return jsonify({'error': check['reason']}), 400

    settlement = TradeService.settle_stock(stock_code)
    if settlement:
        return jsonify({'success': True, 'settlement': settlement.to_dict()})
    return jsonify({'error': '结算失败'}), 500


@trade_bp.route('/stats')
def stats():
    settlements = TradeService.get_settlements()
    chart_data = TradeService.get_chart_data()
    return render_template(
        'trade_stats.html',
        settlements=settlements,
        chart_data=chart_data,
    )


@trade_bp.route('/api/chart-data')
def chart_data():
    data = TradeService.get_chart_data()
    return jsonify(data)


@trade_bp.route('/api/list-charts')
def list_charts():
    """列表页图表数据"""
    days = request.args.get('days', type=int)
    stock_code = request.args.get('stock_code')
    data = TradeService.get_list_charts_data(days=days, stock_code=stock_code)
    return jsonify(data)


@trade_bp.route('/api/timeline/<stock_code>')
def timeline(stock_code):
    """单股交易时间线"""
    days = request.args.get('days', 60, type=int)
    data = TradeService.get_timeline_data(stock_code, days=days)
    return jsonify(data)


@trade_bp.route('/api/category-profit')
def category_profit():
    """分类收益数据"""
    data = TradeService.get_category_profit()
    return jsonify(data)


@trade_bp.route('/api/period-trend')
def period_trend():
    """月度/季度趋势"""
    period = request.args.get('period', 'month')
    data = TradeService.get_period_trend(period=period)
    return jsonify(data)


@trade_bp.route('/api/holding-analysis')
def holding_analysis():
    """持仓周期分析"""
    data = TradeService.get_holding_analysis()
    return jsonify(data)


@trade_bp.route('/transfers')
def get_transfers():
    """获取转账列表"""
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')

    start_date = date.fromisoformat(start_date_str) if start_date_str else None
    end_date = date.fromisoformat(end_date_str) if end_date_str else None

    transfers = BankTransferService.get_transfers(start_date, end_date)
    return jsonify({
        'success': True,
        'transfers': [t.to_dict() for t in transfers]
    })


@trade_bp.route('/transfers', methods=['POST'])
def create_transfer():
    """新增转账"""
    data = request.get_json()
    if not data:
        return jsonify({'error': '无效的数据'}), 400

    transfer_date_str = data.get('transfer_date')
    transfer_type = data.get('transfer_type')
    amount = data.get('amount')

    if not transfer_date_str or not transfer_type or not amount:
        return jsonify({'error': '缺少必填字段'}), 400

    if transfer_type not in ['in', 'out']:
        return jsonify({'error': '无效的转账类型'}), 400

    if amount <= 0:
        return jsonify({'error': '金额必须大于0'}), 400

    transfer_date = date.fromisoformat(transfer_date_str)
    if transfer_date > date.today():
        return jsonify({'error': '转账日期不能晚于今天'}), 400

    transfer = BankTransferService.save_transfer(
        transfer_date=transfer_date,
        transfer_type=transfer_type,
        amount=float(amount),
        note=data.get('note')
    )
    return jsonify({'success': True, 'transfer': transfer.to_dict()})


@trade_bp.route('/transfers/<int:transfer_id>', methods=['PUT'])
def update_transfer(transfer_id):
    """更新转账"""
    data = request.get_json()
    if not data:
        return jsonify({'error': '无效的数据'}), 400

    if 'amount' in data and data['amount'] <= 0:
        return jsonify({'error': '金额必须大于0'}), 400

    if 'transfer_type' in data and data['transfer_type'] not in ['in', 'out']:
        return jsonify({'error': '无效的转账类型'}), 400

    if 'transfer_date' in data:
        transfer_date = date.fromisoformat(data['transfer_date'])
        if transfer_date > date.today():
            return jsonify({'error': '转账日期不能晚于今天'}), 400

    transfer = BankTransferService.update_transfer(transfer_id, data)
    if transfer:
        return jsonify({'success': True, 'transfer': transfer.to_dict()})
    return jsonify({'error': '转账记录不存在'}), 404


@trade_bp.route('/transfers/<int:transfer_id>', methods=['DELETE'])
def delete_transfer(transfer_id):
    """删除转账"""
    if BankTransferService.delete_transfer(transfer_id):
        return jsonify({'success': True})
    return jsonify({'error': '转账记录不存在'}), 404


@trade_bp.route('/api/transfer-stats')
def transfer_stats():
    """转账统计数据"""
    data = BankTransferService.get_transfer_stats()
    return jsonify(data)
