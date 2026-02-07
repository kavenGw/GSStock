from flask import render_template, jsonify
from app.routes import profit_bp
from app.services.daily_record import DailyRecordService
from app.services.trade import TradeService


@profit_bp.route('/daily')
def daily():
    """每日收益页面"""
    data = DailyRecordService.get_daily_profit_history()
    by_stock = DailyRecordService.get_profit_by_stock()
    by_category = DailyRecordService.get_profit_by_category()
    return render_template(
        'daily_profit.html',
        data=data,
        by_stock=by_stock,
        by_category=by_category,
    )


@profit_bp.route('/overall')
def overall():
    """整体收益页面"""
    daily_data = DailyRecordService.get_daily_profit_history()
    by_stock = DailyRecordService.get_profit_by_stock()
    by_category = DailyRecordService.get_profit_by_category()
    trade_data = TradeService.get_chart_data()
    settlements = TradeService.get_settlements()
    return render_template(
        'overall_profit.html',
        daily_data=daily_data,
        by_stock=by_stock,
        by_category=by_category,
        trade_data=trade_data,
        settlements=settlements,
    )


@profit_bp.route('/api/daily')
def api_daily():
    """每日收益 API"""
    data = DailyRecordService.get_daily_profit_history()
    return jsonify({'success': True, 'data': data})


@profit_bp.route('/api/overall')
def api_overall():
    """整体收益 API"""
    daily_data = DailyRecordService.get_daily_profit_history()
    trade_data = TradeService.get_chart_data()
    return jsonify({
        'success': True,
        'daily': daily_data,
        'trade': trade_data,
    })
