from flask import Flask

from app.routes import watch_bp
from app.services.binance_perpetual import binance_perpetual_service


def test_perpetual_route_never_fetches_or_sends(monkeypatch):
    def unexpected():
        raise AssertionError('cache-only endpoint must not fetch')

    monkeypatch.setattr(binance_perpetual_service, 'refresh', unexpected)
    monkeypatch.setattr(binance_perpetual_service, 'snapshot', lambda: {
        'data': [{'symbol': 'NVDAUSDT', 'available': False}], 'error': '行情不可用',
    })
    app = Flask(__name__)
    app.register_blueprint(watch_bp)
    payload = app.test_client().get('/watch/perpetuals').get_json()
    assert payload['success']
    assert payload['data'][0]['available'] is False
    assert payload['error'] == '行情不可用'
