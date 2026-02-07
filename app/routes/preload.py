from datetime import date
from flask import jsonify
from app.routes import preload_bp
from app.services.preload import PreloadService


@preload_bp.route('/api/preload/status')
def preload_status():
    """获取当日预加载状态"""
    today = date.today()
    status = PreloadService.check_preload_status(today)
    return jsonify(status)


@preload_bp.route('/api/preload/start', methods=['POST'])
def preload_start():
    """启动预加载"""
    today = date.today()
    result = PreloadService.start_preload(today)
    return jsonify(result)


@preload_bp.route('/api/preload/progress')
def preload_progress():
    """获取预加载进度"""
    today = date.today()
    progress = PreloadService.get_preload_progress(today)
    return jsonify(progress)


@preload_bp.route('/api/preload/results')
def preload_results():
    """获取预加载的分析结果"""
    today = date.today()
    results = PreloadService.get_cached_results(today)
    return jsonify({'success': True, 'results': results})
