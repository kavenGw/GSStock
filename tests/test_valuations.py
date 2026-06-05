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


@pytest.fixture(scope='module')
def app_client():
    import os
    os.environ['SCHEDULER_ENABLED'] = '0'
    from app import create_app
    from app.services import unified_stock_data_service
    _orig = unified_stock_data_service.get_realtime_prices
    unified_stock_data_service.get_realtime_prices = lambda codes, force_refresh=False: {}
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client
    unified_stock_data_service.get_realtime_prices = _orig


def test_index_route_smoke(app_client):
    resp = app_client.get('/valuations/')
    assert resp.status_code == 200
    assert '估值'.encode('utf-8') in resp.data


def test_api_prices_structure(app_client, monkeypatch):
    from app.services import unified_stock_data_service

    def fake_prices(codes, force_refresh=False):
        assert force_refresh is True  # ?force=1 必须透传
        return {'000878': {'price': 17.90, 'name': '云南铜业'}}

    monkeypatch.setattr(unified_stock_data_service, 'get_realtime_prices', fake_prices)
    resp = app_client.get('/valuations/api/prices?force=1')
    assert resp.status_code == 200
    body = resp.get_json()
    assert '000878' in body
    row = body['000878']
    assert row['current_price'] == 17.90
    assert row['margin_base'] == pytest.approx(7.78 / 17.90 - 1)


def test_api_prices_missing_price_yields_none(app_client, monkeypatch):
    from app.services import unified_stock_data_service
    monkeypatch.setattr(unified_stock_data_service, 'get_realtime_prices',
                        lambda codes, force_refresh=False: {'000878': {'price': 0}})
    resp = app_client.get('/valuations/api/prices?force=1')
    row = resp.get_json()['000878']
    assert row['current_price'] is None
    assert row['margin_base'] is None


def test_index_has_table_headers_and_refresh(app_client):
    resp = app_client.get('/valuations/')
    html = resp.data.decode('utf-8')
    for col in ('Bear', 'Base', 'Bull', '当前价', '安全边际'):
        assert col in html, f'缺列头 {col}'
    assert 'id="refresh-btn"' in html


def test_load_valuations_filters_rows_without_code(tmp_path):
    from app.routes.valuations import load_valuations
    p = tmp_path / 'v.yaml'
    p.write_text(
        "- stock_code: '000001'\n  base: 1.0\n"
        "- note: 没有 stock_code 的脏行\n"
        "- stock_code: '000002'\n  base: 2.0\n",
        encoding='utf-8',
    )
    rows = load_valuations(p)
    assert [r['stock_code'] for r in rows] == ['000001', '000002']


def test_index_degrades_when_price_fetch_raises(app_client, monkeypatch):
    from app.services import unified_stock_data_service
    def boom(codes, force_refresh=False):
        raise RuntimeError('network down')
    monkeypatch.setattr(unified_stock_data_service, 'get_realtime_prices', boom)
    resp = app_client.get('/valuations/')
    assert resp.status_code == 200  # 降级渲染而非 500


def test_index_renders_market_tabs_with_counts(app_client):
    html = app_client.get('/valuations/').data.decode('utf-8')
    for label in ('全部', 'A股', '港股', '美股'):
        assert label in html, f'缺 tab 文案 {label}'
    from collections import Counter
    from app.routes.valuations import load_valuations
    rows = load_valuations()
    counts = Counter(r.get('market') for r in rows)
    assert f'全部 ({len(rows)})' in html
    assert f"A股 ({counts.get('A', 0)})" in html
    assert f"港股 ({counts.get('HK', 0)})" in html
    assert f"美股 ({counts.get('US', 0)})" in html


def test_index_has_currency_column_and_data_market(app_client):
    html = app_client.get('/valuations/').data.decode('utf-8')
    assert '币种' in html, '缺币种列头'
    assert 'data-market=' in html, '缺行 data-market 属性'
    assert 'switchTab' in html, '缺 switchTab JS'


def test_group_by_sector_orders_groups_by_count_desc():
    from app.routes.valuations import group_by_sector
    rows = [
        {'stock_code': 'a', 'sector': 'electronics', 'margin_base': 0.1},
        {'stock_code': 'b', 'sector': 'semiconductor', 'margin_base': 0.2},
        {'stock_code': 'c', 'sector': 'semiconductor', 'margin_base': 0.3},
        {'stock_code': 'd', 'sector': 'semiconductor', 'margin_base': 0.1},
    ]
    groups = group_by_sector(rows)
    assert [g['sector'] for g in groups] == ['semiconductor', 'electronics']
    assert groups[0]['count'] == 3
    assert groups[0]['label'] == '半导体'
    assert groups[1]['label'] == '电子'


def test_group_by_sector_sorts_rows_within_group_by_base_margin_desc():
    from app.routes.valuations import group_by_sector
    rows = [
        {'stock_code': 'lo', 'sector': 'materials', 'margin_base': 0.05},
        {'stock_code': 'hi', 'sector': 'materials', 'margin_base': 0.50},
        {'stock_code': 'none', 'sector': 'materials', 'margin_base': None},
        {'stock_code': 'mid', 'sector': 'materials', 'margin_base': 0.20},
    ]
    [grp] = group_by_sector(rows)
    assert [r['stock_code'] for r in grp['rows']] == ['hi', 'mid', 'lo', 'none']


def test_group_by_sector_unknown_sector_falls_back_to_raw():
    from app.routes.valuations import group_by_sector
    [grp] = group_by_sector([{'stock_code': 'x', 'sector': 'weird-thing', 'margin_base': 0.1}])
    assert grp['sector'] == 'weird-thing'
    assert grp['label'] == 'weird-thing'


def test_group_by_sector_none_sector_grouped_as_unclassified():
    from app.routes.valuations import group_by_sector
    [grp] = group_by_sector([{'stock_code': 'x', 'sector': None, 'margin_base': 0.1}])
    assert grp['label'] == '未分类'


def test_group_by_sector_empty_returns_empty():
    from app.routes.valuations import group_by_sector
    assert group_by_sector([]) == []
