"""估值汇总页测试"""
import pytest

from app.routes.valuations import compute_margin, _extract_price


def test_compute_margin_normal():
    assert compute_margin(7.78, 17.90) == pytest.approx(7.78 / 17.90 - 1)


def test_compute_margin_upside():
    assert compute_margin(20.0, 10.0) == pytest.approx(1.0)


def test_compute_margin_price_none():
    assert compute_margin(7.78, None) is None


def test_compute_margin_price_zero():
    assert compute_margin(7.78, 0) is None


def test_compute_margin_value_none():
    assert compute_margin(None, 17.90) is None


def test_extract_price_prefers_price_key():
    assert _extract_price({'price': 17.9, 'current_price': 99}) == 17.9


def test_extract_price_falls_back_to_current_price():
    assert _extract_price({'current_price': 12.3}) == 12.3


def test_extract_price_missing():
    assert _extract_price({}) is None


def test_extract_price_zero_is_none():
    assert _extract_price({'price': 0}) is None


def test_load_valuations_parses(tmp_path):
    from app.routes.valuations import load_valuations
    p = tmp_path / 'valuations.yaml'
    p.write_text(
        "- stock_code: '000878'\n"
        "  stock_name: 云南铜业\n"
        "  market: A\n"
        "  currency: CNY\n"
        "  rating: watch\n"
        "  bear: 6.50\n"
        "  base: 7.78\n"
        "  bull: 8.87\n"
        "  conviction_date: '2026-06-02'\n"
        "  source_doc: sectors/materials/nonferrous/2026-06-02-云南铜业-buffett分析.md\n",
        encoding='utf-8',
    )
    rows = load_valuations(p)
    assert len(rows) == 1
    assert rows[0]['stock_code'] == '000878'
    assert rows[0]['base'] == 7.78
    assert rows[0]['stock_name'] == '云南铜业'


def test_load_valuations_missing_returns_empty(tmp_path):
    from app.routes.valuations import load_valuations
    assert load_valuations(tmp_path / 'nope.yaml') == []


def test_load_valuations_empty_file_returns_empty(tmp_path):
    from app.routes.valuations import load_valuations
    p = tmp_path / 'empty.yaml'
    p.write_text('', encoding='utf-8')
    assert load_valuations(p) == []


@pytest.fixture
def app_client(monkeypatch):
    import os
    os.environ['SCHEDULER_ENABLED'] = '0'
    from app import create_app
    from app.services import unified_stock_data_service
    monkeypatch.setattr(unified_stock_data_service, 'get_realtime_prices',
                        lambda codes, force_refresh=False: {})
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


def test_index_route_smoke(app_client):
    resp = app_client.get('/valuations/')
    assert resp.status_code == 200
    assert '估值'.encode('utf-8') in resp.data
