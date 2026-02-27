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


@news_bp.route('/poll')
def poll():
    items, count = NewsService.poll_news()
    return jsonify({'success': True, 'new_items': items, 'new_count': count})


@news_bp.route('/summarize', methods=['POST'])
def summarize():
    data = request.get_json()
    item_ids = data.get('item_ids', [])
    if not item_ids:
        return jsonify({'success': False, 'error': 'missing item_ids'})
    summary = NewsService.summarize_items(item_ids)
    if not summary:
        return jsonify({'success': False, 'error': 'summarize failed'})
    return jsonify({'success': True, 'summary': summary})
