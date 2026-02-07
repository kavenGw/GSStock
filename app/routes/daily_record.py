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


@daily_record_bp.route('/upload-position', methods=['POST'])
def upload_position():
    """上传持仓图片（支持多张）"""
    files = request.files.getlist('files')
    # 获取前端传来的已有数据（用于累加合并）
    existing_json = request.form.get('existing', '[]')
    existing_positions = json.loads(existing_json) if existing_json else []
    logger.info(f"[上传持仓] 收到existing数据: {len(existing_positions)}条")
    for i, pos in enumerate(existing_positions):
        logger.info(f"  existing[{i+1}] code={pos.get('stock_code')}, name={pos.get('stock_name')}, qty={pos.get('quantity')}")

    if not files or len(files) == 0:
        return jsonify({'success': False, 'error': '请选择要上传的图片'})

    if len(files) > MAX_FILES:
        return jsonify({'success': False, 'error': f'最多支持{MAX_FILES}张图片'})

    results = []
    all_positions = list(existing_positions)  # 从已有数据开始
    account_data = {}  # 账户概览数据

    for file in files:
        if not file or file.filename == '':
            continue

        if not allowed_file(file.filename):
            results.append({
                'filename': file.filename,
                'success': False,
                'error': '仅支持 JPG/PNG/BMP 格式'
            })
            continue

        filename = secure_filename(file.filename)
        filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        try:
            ocr_result = OcrService.recognize(filepath)
            positions = ocr_result.get('positions', [])
            account = ocr_result.get('account', {})

            results.append({
                'filename': file.filename,
                'success': True,
                'positions': positions,
                'account': account
            })
            all_positions.extend(positions)

            # 叠加账户数据（多账户总资产和盈亏相加）
            if account:
                if 'total_asset' in account:
                    account_data['total_asset'] = account_data.get('total_asset', 0) + account['total_asset']
                if 'daily_profit' in account:
                    account_data['daily_profit'] = account_data.get('daily_profit', 0) + account['daily_profit']
                if 'daily_profit_pct' in account:
                    account_data['daily_profit_pct'] = account.get('daily_profit_pct')
        except Exception as e:
            logger.error(f"持仓图片识别失败: {file.filename} - {e}")
            results.append({
                'filename': file.filename,
                'success': False,
                'error': f'识别失败: {str(e)}'
            })
        finally:
            if os.path.exists(filepath):
                os.remove(filepath)

    # 合并相同股票的持仓
    logger.info(f"[上传持仓] OCR识别结果: {len(all_positions)}条")
    for i, pos in enumerate(all_positions):
        logger.info(f"  [{i+1}] code={pos.get('stock_code')}, name={pos.get('stock_name')}, qty={pos.get('quantity')}")

    merged = PositionService.merge_positions(all_positions) if all_positions else []

    logger.info(f"[上传持仓] 合并后: {len(merged)}条")
    for i, pos in enumerate(merged):
        logger.info(f"  [{i+1}] code={pos.get('stock_code')}, name={pos.get('stock_name')}, qty={pos.get('quantity')}")

    return jsonify({
        'success': True,
        'results': results,
        'merged': merged,
        'account': account_data
    })


@daily_record_bp.route('/upload-trade', methods=['POST'])
def upload_trade():
    """上传交易图片（支持多张）"""
    files = request.files.getlist('files')
    # 获取前端传来的已有数据（用于累加合并）
    existing_json = request.form.get('existing', '[]')
    existing_trades = json.loads(existing_json) if existing_json else []

    if not files or len(files) == 0:
        return jsonify({'success': False, 'error': '请选择要上传的图片'})

    if len(files) > MAX_FILES:
        return jsonify({'success': False, 'error': f'最多支持{MAX_FILES}张图片'})

    results = []
    all_trades = list(existing_trades)  # 从已有数据开始

    for file in files:
        if not file or file.filename == '':
            continue

        if not allowed_file(file.filename):
            results.append({
                'filename': file.filename,
                'success': False,
                'error': '仅支持 JPG/PNG/BMP 格式'
            })
            continue

        filename = secure_filename(file.filename)
        filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        try:
            trades = OcrService.recognize_trade(filepath)
            # 根据股票名称补全缺失的股票代码
            StockService.fill_missing_codes(trades)
            results.append({
                'filename': file.filename,
                'success': True,
                'trades': trades
            })
            all_trades.extend(trades)
        except Exception as e:
            logger.error(f"交易图片识别失败: {file.filename} - {e}")
            results.append({
                'filename': file.filename,
                'success': False,
                'error': f'识别失败: {str(e)}'
            })
        finally:
            if os.path.exists(filepath):
                os.remove(filepath)

    return jsonify({
        'success': True,
        'results': results,
        'all_trades': all_trades
    })


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

    if not positions and not trades and not transfer:
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

    # 保存账户快照数据（总资产、当日盈亏）
    if account:
        try:
            DailySnapshot.save_snapshot(
                target_date,
                total_asset=account.get('total_asset'),
                daily_profit=account.get('daily_profit'),
                daily_profit_pct=account.get('daily_profit_pct')
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
