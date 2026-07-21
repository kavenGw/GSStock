from flask import Flask
from app.routes import watch_bp


def _make_app():
    app = Flask(__name__)
    app.register_blueprint(watch_bp, url_prefix='/watch')
    return app


def test_prices_returns_indices(monkeypatch):
    from app.services import unified_stock_data as usd

    def fake_cached_only(codes):
        cached = {c: {'current_price': 2500.0, 'change_percent': 0.3,
                      'name': 'KOSPI', 'market': 'KR'} for c in codes}
        return cached, []

    def fake_a_index(codes, force_refresh=False, cache_only=False):
        return {c: {'close': 3400.0, 'change_percent': 0.5, 'name': c}
                for c in codes}

    monkeypatch.setattr(usd.unified_stock_data_service,
                        'get_prices_cached_only', fake_cached_only)
    monkeypatch.setattr(usd.unified_stock_data_service,
                        'get_a_share_index_quotes', fake_a_index)

    client = _make_app().test_client()
    resp = client.get('/watch/prices').get_json()

    assert 'indices' in resp
    assert set(resp['indices'].keys()) == {'A', 'KR'}
    a = resp['indices']['A']
    assert [i['code'] for i in a] == ['000001.SS', '399006.SZ', '000688.SS']
    assert a[0]['price'] == 3400.0 and a[0]['change_pct'] == 0.5
    assert a[0]['name'] == '上证'
    kr = resp['indices']['KR']
    assert kr[0]['code'] == '^KS11' and kr[0]['price'] == 2500.0
