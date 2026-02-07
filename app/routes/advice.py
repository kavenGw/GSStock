from datetime import date
from flask import request, jsonify
from app import db
from app.routes import advice_bp
from app.models.advice import Advice


@advice_bp.route('/save', methods=['POST'])
def save():
    data = request.get_json()
    if not data:
        return jsonify({'error': '无效的数据'}), 400

    stock_code = data.get('stock_code')
    target_date = date.fromisoformat(data['date']) if 'date' in data else date.today()

    advice = Advice.query.filter_by(date=target_date, stock_code=stock_code).first()
    if not advice:
        advice = Advice(date=target_date, stock_code=stock_code)
        db.session.add(advice)

    advice.support_price = data.get('support_price')
    advice.resistance_price = data.get('resistance_price')
    advice.strategy = data.get('strategy')

    db.session.commit()
    return jsonify({'success': True, 'advice': advice.to_dict()})


@advice_bp.route('/api/<target_date>')
def get_by_date(target_date):
    target = date.fromisoformat(target_date)
    advices = Advice.query.filter_by(date=target).all()
    return jsonify({
        'advices': {a.stock_code: a.to_dict() for a in advices}
    })
