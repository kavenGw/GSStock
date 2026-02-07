from datetime import date, datetime
from flask import request, jsonify, render_template, send_file
from app.routes import wyckoff_bp
from app.services.wyckoff import WyckoffService, WyckoffAutoService
from app.services.position import PositionService


# 参考图路由
@wyckoff_bp.route('/reference')
def reference_list():
    phase = request.args.get('phase')
    references = WyckoffService.get_references(phase)
    return render_template('wyckoff_reference.html', references=references, current_phase=phase)


@wyckoff_bp.route('/reference/upload', methods=['POST'])
def reference_upload():
    if 'file' not in request.files:
        return jsonify({'error': '未选择文件'}), 400

    file = request.files['file']
    phase = request.form.get('phase')
    description = request.form.get('description')

    if not phase:
        return jsonify({'error': '请选择阶段'}), 400

    ref, error = WyckoffService.save_reference(file, phase, description)
    if error:
        return jsonify({'error': error}), 400

    return jsonify({'success': True, 'reference': ref.to_dict()})


@wyckoff_bp.route('/reference/<int:ref_id>', methods=['DELETE'])
def reference_delete(ref_id):
    success, error = WyckoffService.delete_reference(ref_id)
    if not success:
        return jsonify({'error': error}), 404
    return jsonify({'success': True})


# 分析记录路由
@wyckoff_bp.route('/analysis')
def analysis_list():
    stock_code = request.args.get('stock_code')
    analyses = WyckoffService.get_analyses(stock_code)
    return render_template('wyckoff_analysis.html', analyses=analyses, stock_code=stock_code)


@wyckoff_bp.route('/analysis/<stock_code>')
def analysis_detail(stock_code):
    analyses = WyckoffService.get_analyses(stock_code)
    return render_template('wyckoff_analysis.html', analyses=analyses, stock_code=stock_code, detail_view=True)


@wyckoff_bp.route('/analysis/save', methods=['POST'])
def analysis_save():
    if 'file' not in request.files:
        return jsonify({'error': '未选择文件'}), 400

    file = request.files['file']
    stock_code = request.form.get('stock_code')
    analysis_date = request.form.get('analysis_date')
    phase = request.form.get('phase')
    event = request.form.get('event') or None
    notes = request.form.get('notes') or None

    if not stock_code or not analysis_date or not phase:
        return jsonify({'error': '请填写必要信息'}), 400

    analysis, error = WyckoffService.save_analysis(
        stock_code, analysis_date, file, phase, event, notes
    )
    if error:
        return jsonify({'error': error}), 400

    return jsonify({'success': True, 'analysis': analysis.to_dict()})


@wyckoff_bp.route('/analysis/<int:analysis_id>', methods=['DELETE'])
def analysis_delete(analysis_id):
    success, error = WyckoffService.delete_analysis(analysis_id)
    if not success:
        return jsonify({'error': error}), 404
    return jsonify({'success': True})


# API 路由
@wyckoff_bp.route('/api/latest/<stock_code>')
def api_latest(stock_code):
    analysis = WyckoffService.get_latest_analysis(stock_code)
    if not analysis:
        return jsonify({'phase': None, 'event': None, 'date': None})
    return jsonify({
        'phase': analysis.phase,
        'event': analysis.event,
        'date': analysis.analysis_date.isoformat() if analysis.analysis_date else None,
    })


@wyckoff_bp.route('/api/batch-latest', methods=['POST'])
def api_batch_latest():
    data = request.get_json()
    stock_codes = data.get('stock_codes', [])
    result = WyckoffService.get_batch_latest(stock_codes)

    # 添加PE数据
    if stock_codes:
        try:
            from app.services.earnings import EarningsService
            pe_data_map = EarningsService.get_pe_ratios(stock_codes)
            for code in result:
                if code in pe_data_map:
                    result[code]['pe_data'] = pe_data_map[code]
                else:
                    result[code]['pe_data'] = {'pe_ttm': None, 'pe_status': 'na', 'pe_display': '暂无数据'}
        except Exception as e:
            import logging
            logging.warning(f"获取PE数据失败: {e}")

    return jsonify(result)


# 图片访问路由
@wyckoff_bp.route('/image/<path:filepath>')
def serve_image(filepath):
    return send_file(filepath)


@wyckoff_bp.route('/auto/analyze', methods=['POST'])
def auto_analyze():
    """批量分析 API"""
    data = request.get_json()
    stock_list = data.get('stock_list', [])

    if not stock_list:
        return jsonify({'success': False, 'error': '未提供股票列表'}), 400

    results = WyckoffAutoService.analyze_batch(stock_list)
    failed_count = sum(1 for r in results if r.get('status') != 'success')

    return jsonify({
        'success': True,
        'results': results,
        'failed_count': failed_count,
    })


@wyckoff_bp.route('/auto/history')
def auto_history():
    """历史查询 API"""
    stock_code = request.args.get('stock_code')
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')

    start_date = None
    end_date = None
    if start_date_str:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
    if end_date_str:
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()

    records = WyckoffAutoService.get_auto_history(stock_code, start_date, end_date)
    return jsonify({'success': True, 'records': records})
