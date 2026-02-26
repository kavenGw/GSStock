from flask import render_template, jsonify, request
from app.routes import news_bp
from app.services.news_service import NewsService


@news_bp.route('/')
def index():
    return render_template('news.html')


@news_bp.route('/items')
def items():
    tab = request.args.get('tab', 'all')
    limit = request.args.get('limit', 30, type=int)
    before_id = request.args.get('before_id', type=int)
    data = NewsService.get_news_items(tab=tab, limit=limit, before_id=before_id)
    return jsonify({'success': True, 'items': data})


@news_bp.route('/briefing')
def briefing():
    data = NewsService.get_latest_briefing()
    return jsonify({'success': True, 'briefing': data})


@news_bp.route('/refresh', methods=['POST'])
def refresh():
    from app.strategies.registry import registry
    strategy = registry.get('news_monitor')
    if strategy:
        strategy.scan()
    return jsonify({'success': True})
