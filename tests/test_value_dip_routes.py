from flask import Flask
from app.routes import value_dip_bp
from app.services.value_dip import ValueDipService


def _client(monkeypatch):
    monkeypatch.setattr(ValueDipService, 'get_watch_performance',
                        staticmethod(lambda: [{'code': '300223', 'name': '北京君正',
                                               'market': 'A', 'price': 30.0,
                                               'change_7d': 1.0, 'change_30d': 2.0,
                                               'change_90d': 3.0, 'high_90d': 40.0,
                                               'pullback_90d': -25.0}]))
    monkeypatch.setattr(ValueDipService, 'get_pullback_ranking',
                        staticmethod(lambda days=90: [{'code': '300223', 'name': '北京君正',
                                                       'market': 'A', 'price': 30.0,
                                                       'high': 40.0, 'pullback_pct': -25.0}]))
    app = Flask(__name__)
    app.register_blueprint(value_dip_bp)
    return app.test_client()


def test_api_stocks_flat(monkeypatch):
    c = _client(monkeypatch)
    resp = c.get('/value-dip/api/stocks')
    assert resp.status_code == 200
    body = resp.get_json()
    assert 'stocks' in body
    assert body['stocks'][0]['market'] == 'A'


def test_api_sectors_route_removed(monkeypatch):
    c = _client(monkeypatch)
    assert c.get('/value-dip/api/sectors').status_code == 404


def test_api_pullback_still_works(monkeypatch):
    c = _client(monkeypatch)
    body = c.get('/value-dip/api/pullback?days=90').get_json()
    assert body['stocks'][0]['pullback_pct'] == -25.0
