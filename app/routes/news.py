from flask import render_template, jsonify, request
from app.routes import news_bp
from app.services.news_service import NewsService
from app.models.news import InterestKeyword, CompanyKeyword, NewsDerivation
from app import db


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



@news_bp.route('/latest')
def latest():
    since_id = request.args.get('since_id', 0, type=int)
    items, count = NewsService.get_latest_count(since_id)
    return jsonify({'success': True, 'new_items': items, 'new_count': count})


@news_bp.route('/summarize', methods=['POST'])
def summarize():
    data = request.get_json()
    item_ids = [int(i) for i in data.get('item_ids', [])]
    if not item_ids:
        return jsonify({'success': False, 'error': 'missing item_ids'})
    summary = NewsService.summarize_items(item_ids)
    if not summary:
        return jsonify({'success': False, 'error': 'summarize failed'})
    return jsonify({'success': True, 'summary': summary})


@news_bp.route('/keywords')
def get_keywords():
    keywords = InterestKeyword.query.order_by(InterestKeyword.created_at.desc()).all()
    return jsonify({
        'success': True,
        'keywords': [{
            'id': str(kw.id),
            'keyword': kw.keyword,
            'source': kw.source,
            'is_active': kw.is_active,
        } for kw in keywords]
    })


@news_bp.route('/keywords', methods=['POST'])
def add_keyword():
    data = request.get_json()
    keyword = data.get('keyword', '').strip()
    if not keyword:
        return jsonify({'success': False, 'error': 'keyword required'})
    existing = InterestKeyword.query.filter_by(keyword=keyword).first()
    if existing:
        existing.is_active = True
        existing.source = 'user'
        db.session.commit()
        return jsonify({'success': True, 'id': str(existing.id)})
    kw = InterestKeyword(keyword=keyword, source='user')
    db.session.add(kw)
    db.session.commit()
    return jsonify({'success': True, 'id': str(kw.id)})


@news_bp.route('/keywords/<int:kw_id>', methods=['DELETE'])
def delete_keyword(kw_id):
    kw = db.session.get(InterestKeyword, kw_id)
    if not kw:
        return jsonify({'success': False, 'error': 'not found'})
    db.session.delete(kw)
    db.session.commit()
    return jsonify({'success': True})


@news_bp.route('/keywords/<int:kw_id>/accept', methods=['POST'])
def accept_keyword(kw_id):
    kw = db.session.get(InterestKeyword, kw_id)
    if kw:
        kw.is_active = True
        kw.source = 'user'
        db.session.commit()
    return jsonify({'success': True})


@news_bp.route('/companies')
def get_companies():
    companies = CompanyKeyword.query.filter_by(is_active=True).order_by(CompanyKeyword.created_at.desc()).all()
    return jsonify({
        'success': True,
        'companies': [{'id': str(c.id), 'name': c.name} for c in companies]
    })


@news_bp.route('/companies', methods=['POST'])
def add_company():
    data = request.get_json()
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'success': False, 'error': 'name required'})
    existing = CompanyKeyword.query.filter_by(name=name).first()
    if existing:
        existing.is_active = True
        db.session.commit()
        return jsonify({'success': True, 'id': str(existing.id)})
    c = CompanyKeyword(name=name)
    db.session.add(c)
    db.session.commit()
    return jsonify({'success': True, 'id': str(c.id)})


@news_bp.route('/companies/<int:company_id>', methods=['DELETE'])
def delete_company(company_id):
    c = db.session.get(CompanyKeyword, company_id)
    if not c:
        return jsonify({'success': False, 'error': 'not found'})
    db.session.delete(c)
    db.session.commit()
    return jsonify({'success': True})


@news_bp.route('/derivations/<int:news_id>')
def get_derivation(news_id):
    d = NewsDerivation.query.filter_by(news_item_id=news_id).first()
    if not d:
        return jsonify({'success': False})
    return jsonify({
        'success': True,
        'derivation': {
            'summary': d.summary,
            'sources': d.sources or [],
            'importance': d.importance,
            'search_query': d.search_query,
        }
    })
