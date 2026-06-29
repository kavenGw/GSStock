from flask import Flask
from app.routes import watch_bp


def _watch_client():
    app = Flask(__name__)
    app.register_blueprint(watch_bp)
    return app.test_client()


def test_watch_signals_returns_ohlc_per_code(monkeypatch):
    import app.services.unified_stock_data as usd

    def fake_get_trend_data(codes, days=60):
        assert days == 60
        return {'stocks': [
            {'stock_code': c, 'stock_name': c,
             'data': [{'date': '2026-06-01', 'open': 1, 'high': 2,
                       'low': 1, 'close': 1.5, 'volume': 100}]}
            for c in codes
        ]}

    monkeypatch.setattr(usd.unified_stock_data_service,
                        'get_trend_data', fake_get_trend_data)

    resp = _watch_client().get('/watch/signals')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['success'] is True
    codes = {s['stock_code'] for s in data['stocks']}
    assert '2631.HK' in codes and '300223' in codes
    assert all('data' in s and isinstance(s['data'], list) for s in data['stocks'])
