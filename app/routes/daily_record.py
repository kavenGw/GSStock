import os
import json
import logging
from datetime import date
from flask import render_template, request, jsonify, current_app
from werkzeug.utils import secure_filename
from app.routes import daily_record_bp
from app.services.ocr import OcrService
from app.services.position import PositionService
from app.services.trade import TradeService
from app.services.stock import StockService
from app.services.daily_record import DailyRecordService
from app.services.bank_transfer import BankTransferService
from app.models.position import Position
from app.models.trade import Trade
from app.models.bank_transfer import BankTransfer
from app import db

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'bmp'}
MAX_FILES = 10


def allowed_file(filename: str) -> bool:
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@daily_record_bp.route('/')
def index():
    """每日记录上传页面"""
    today = date.today().isoformat()
    return render_template('daily_record.html', today=today)


@daily_record_bp.route('/upload-single', methods=['POST'])
def upload_single():
    """单文件上传识别"""
    file = request.files.get('file')
    upload_type = request.form.get('type')

    if not file or file.filename == '':
        return jsonify({'success': False, 'error': '请选择要上传的图片'})

    if not allowed_file(file.filename):
        return jsonify({'success': False, 'error': '仅支持 JPG/PNG/BMP 格式'})

    if upload_type not in ('position', 'trade'):
        return jsonify({'success': False, 'error': '无效的上传类型'})

    filename = secure_filename(file.filename)
    filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)

    try:
        if upload_type == 'position':
            ocr_result = OcrService.recognize(filepath)
            return jsonify({
                'success': True,
                'positions': ocr_result.get('positions', []),
                'account': ocr_result.get('account', {})
            })
        else:
            trades = OcrService.recognize_trade(filepath)
            StockService.fill_missing_codes(trades)
            return jsonify({'success': True, 'trades': trades})
    except Exception as e:
        logger.error(f"图片识别失败: {file.filename} - {e}")
        return jsonify({'success': False, 'error': f'识别失败: {str(e)}'})
    finally:
        if os.path.exists(filepath):
            os.remove(filepath)


@daily_record_bp.route('/merge', methods=['POST'])
def merge():
    """合并多张识别结果"""
    data = request.get_json()
    merge_type = data.get('type')
    items = data.get('data', [])

    if merge_type == 'position':
        all_positions = []
        account_data = {}
        for item in items:
            all_positions.extend(item.get('positions', []))
            account = item.get('account', {})
            if account:
                if 'total_asset' in account:
                    account_data['total_asset'] = account_data.get('total_asset', 0) + account['total_asset']

        merged = PositionService.merge_positions(all_positions) if all_positions else []
        return jsonify({'success': True, 'merged': merged, 'account': account_data})

    elif merge_type == 'trade':
        all_trades = []
        for item in items:
            all_trades.extend(item.get('trades', []))
        return jsonify({'success': True, 'trades': all_trades})

    return jsonify({'success': False, 'error': '无效的合并类型'})


@daily_record_bp.route('/save', methods=['POST'])
def save():
    """保存全部数据（持仓和交易），默认累加模式"""
    from app.models.daily_snapshot import DailySnapshot

    data = request.get_json()
    target_date_str = data.get('date')
    positions = data.get('positions', [])
    trades = data.get('trades', [])
    account = data.get('account', {})
    transfer = data.get('transfer')
    overwrite = data.get('overwrite', False)
    overwrite_stocks = data.get('overwrite_stocks', False)

    if not target_date_str:
        return jsonify({'success': False, 'error': '日期不能为空'})

    has_account = account and account.get('total_asset')
    if not positions and not trades and not transfer and not has_account:
        return jsonify({'success': False, 'error': '没有数据需要保存'})

    # 合并持仓和交易的股票信息用于检测冲突
    all_stocks = list(positions)
    for t in trades:
        all_stocks.append({'stock_code': t.get('stock_code'), 'stock_name': t.get('stock_name')})

    # 检测股票名称冲突
    conflicts = StockService.detect_conflicts(all_stocks)
    if conflicts and not overwrite_stocks:
        return jsonify({
            'success': False,
            'has_conflicts': True,
            'conflicts': conflicts
        })

    target_date = date.fromisoformat(target_date_str)
    errors = {}

    logger.info(f"保存每日记录: date={target_date_str}, "
                f"positions={len(positions)}, trades={len(trades)}, "
                f"account={account}, transfer={transfer}")

    # 保存持仓数据（PositionService.save_snapshot 内部处理合并逻辑）
    if positions:
        try:
            PositionService.save_snapshot(target_date, positions, overwrite=overwrite)
        except Exception as e:
            logger.error(f"保存持仓数据失败: {e}")
            errors['positions'] = str(e)

    # 保存交易数据
    if trades:
        try:
            if overwrite:
                Trade.query.filter_by(trade_date=target_date).delete()
                db.session.commit()

            for trade_data in trades:
                trade_data['trade_date'] = target_date_str
                logger.info(f"保存交易: {trade_data.get('stock_code')} "
                            f"{trade_data.get('trade_type')} "
                            f"qty={trade_data.get('quantity')} "
                            f"price={trade_data.get('price')} "
                            f"fee={trade_data.get('fee')}")
                TradeService.save_trade(trade_data)
        except Exception as e:
            logger.error(f"保存交易数据失败: {e}")
            errors['trades'] = str(e)

    # 保存银证转账数据
    if transfer and transfer.get('type') and transfer.get('amount'):
        try:
            BankTransferService.save_transfer(
                transfer_date=target_date,
                transfer_type=transfer['type'],
                amount=float(transfer['amount']),
                note=transfer.get('note')
            )
            logger.info(f"保存银证转账: {transfer}")
        except Exception as e:
            logger.error(f"保存银证转账失败: {e}")
            errors['transfer'] = str(e)

    # 保存账户快照数据（总资产、当日盈亏、手续费）
    if account:
        try:
            DailySnapshot.save_snapshot(
                target_date,
                total_asset=account.get('total_asset'),
                daily_profit=account.get('daily_profit'),
                daily_profit_pct=account.get('daily_profit_pct'),
            )
            logger.info(f"保存账户快照: {account}")
        except Exception as e:
            logger.error(f"保存账户快照失败: {e}")
            errors['account'] = str(e)

    if errors:
        return jsonify({
            'success': False,
            'error': '保存部分失败',
            'details': errors
        })

    # 保存股票代码到本地
    if all_stocks:
        StockService.save_from_positions(all_stocks, overwrite=overwrite_stocks)

    return jsonify({
        'success': True,
        'redirect': f'/daily-record/stats/{target_date_str}'
    })


@daily_record_bp.route('/stats/<date_str>')
def stats(date_str: str):
    """每日统计页面"""
    target_date = date.fromisoformat(date_str)
    stats_data = DailyRecordService.calculate_daily_stats(target_date)
    return render_template('daily_stats.html', stats=stats_data, date=date_str)


@daily_record_bp.route('/api/stats/<date_str>')
def api_stats(date_str: str):
    """每日统计数据 API"""
    target_date = date.fromisoformat(date_str)
    stats_data = DailyRecordService.calculate_daily_stats(target_date)
    return jsonify({'success': True, 'data': stats_data})


@daily_record_bp.route('/api/calc-fee', methods=['POST'])
def api_calc_fee():
    """根据当前输入数据和前一交易日数据计算手续费"""
    from app.models.daily_snapshot import DailySnapshot

    data = request.get_json()
    target_date_str = data.get('date')
    positions = data.get('positions', [])
    trades = data.get('trades', [])
    total_asset = data.get('total_asset')
    new_transfer = data.get('transfer')

    if not target_date_str or not total_asset:
        return jsonify({'success': False, 'error': '缺少日期或总资产数据'})

    target_date = date.fromisoformat(target_date_str)
    prev_date = DailyRecordService.get_previous_trading_date(target_date)

    if not prev_date:
        return jsonify({'success': False, 'error': '无前一交易日数据，无法计算'})

    # 前日数据：必须有快照（含现金的总资产）才能准确推算手续费
    prev_snapshot = DailySnapshot.get_snapshot(prev_date)
    prev_positions = Position.query.filter_by(date=prev_date).all()
    prev_pos_map = {p.stock_code: p for p in prev_positions}

    if not (prev_snapshot and prev_snapshot.total_asset):
        # 无前日快照，回退到已记录的 Trade.fee 累加
        existing_trades = Trade.query.filter_by(trade_date=target_date).all()
        trade_fee = round(sum(t.fee or 0 for t in existing_trades), 2)
        return jsonify({
            'success': True,
            'fee': trade_fee,
            'detail': {
                'theoretical_profit': None,
                'actual_profit': None,
                'prev_date': prev_date.isoformat(),
                'prev_total_asset': None,
                'note': '前日无总资产快照，使用交易记录手续费累加',
            }
        })

    prev_total_asset = prev_snapshot.total_asset

    # 净转入（已有 + 新输入）
    existing_transfers = BankTransfer.query.filter_by(transfer_date=target_date).all()
    net_transfer = sum(t.amount if t.transfer_type == 'in' else -t.amount for t in existing_transfers)
    if new_transfer and new_transfer.get('type') and new_transfer.get('amount'):
        net_transfer += new_transfer['amount'] if new_transfer['type'] == 'in' else -new_transfer['amount']

    # 实际盈亏
    actual_profit = total_asset - prev_total_asset - net_transfer

    # 理论盈亏：遍历所有股票计算 市值变动 + 交易净额
    today_pos_map = {}
    for p in positions:
        code = p.get('stock_code')
        if code:
            today_pos_map[code] = {
                'market_value': (p.get('current_price', 0) or 0) * (p.get('quantity', 0) or 0)
            }

    trade_by_stock = {}
    for t in trades:
        code = t.get('stock_code')
        if not code:
            continue
        if code not in trade_by_stock:
            trade_by_stock[code] = {'buy': 0, 'sell': 0}
        amount = (t.get('quantity', 0) or 0) * (t.get('price', 0) or 0)
        if t.get('trade_type') == 'buy':
            trade_by_stock[code]['buy'] += amount
        else:
            trade_by_stock[code]['sell'] += amount

    # 合并所有相关股票（持仓 + 交易），避免遗漏仅有交易但无持仓的股票
    all_stocks = set(today_pos_map.keys()) | set(prev_pos_map.keys()) | set(trade_by_stock.keys())
    theoretical_profit = 0
    stock_details = []
    for code in sorted(all_stocks):
        today_mv = today_pos_map.get(code, {}).get('market_value', 0)
        prev_p = prev_pos_map.get(code)
        prev_mv = prev_p.current_price * prev_p.quantity if prev_p else 0
        td = trade_by_stock.get(code, {'buy': 0, 'sell': 0})
        stock_profit = today_mv - prev_mv + td['sell'] - td['buy']
        theoretical_profit += stock_profit
        stock_details.append({
            'code': code,
            'today_mv': round(today_mv, 2),
            'prev_mv': round(prev_mv, 2),
            'buy': round(td['buy'], 2),
            'sell': round(td['sell'], 2),
            'profit': round(stock_profit, 2),
        })

    fee = round(theoretical_profit - actual_profit, 2)
    # 负值表示数据异常（实际盈亏 > 理论盈亏）
    is_abnormal = fee < 0

    return jsonify({
        'success': True,
        'fee': fee,
        'is_abnormal': is_abnormal,
        'detail': {
            'theoretical_profit': round(theoretical_profit, 2),
            'actual_profit': round(actual_profit, 2),
            'prev_date': prev_date.isoformat(),
            'prev_total_asset': round(prev_total_asset, 2),
            'net_transfer': round(net_transfer, 2),
            'today_total_asset': round(total_asset, 2),
            'stock_details': stock_details,
        }
    })


@daily_record_bp.route('/api/prev-asset/<date_str>')
def api_prev_asset(date_str: str):
    """获取前一交易日的总资产和当日转账信息，用于计算当日盈亏"""
    from app.models.daily_snapshot import DailySnapshot

    target_date = date.fromisoformat(date_str)
    prev_date = DailyRecordService.get_previous_trading_date(target_date)

    # 获取当日已有的转账记录
    daily_transfer = BankTransferService.get_daily_transfer(target_date)

    if not prev_date:
        return jsonify({
            'success': True,
            'has_prev': False,
            'prev_date': None,
            'prev_total_asset': None,
            'transfer': daily_transfer
        })

    prev_snapshot = DailySnapshot.get_snapshot(prev_date)
    if prev_snapshot and prev_snapshot.total_asset:
        prev_total_asset = prev_snapshot.total_asset
    else:
        prev_positions = Position.query.filter_by(date=prev_date).all()
        prev_total_asset = sum(p.current_price * p.quantity for p in prev_positions)

    return jsonify({
        'success': True,
        'has_prev': True,
        'prev_date': prev_date.isoformat(),
        'prev_total_asset': round(prev_total_asset, 2),
        'transfer': daily_transfer
    })
