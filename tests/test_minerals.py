import pytest


def test_mineral_boards_has_copper_and_lithium():
    from app.config.minerals import MINERAL_BOARDS
    assert set(MINERAL_BOARDS) == {'copper', 'lithium'}
    cu = MINERAL_BOARDS['copper']
    assert cu['futures_code'] == 'HG=F'
    assert cu['futures_source'] == 'yfinance'
    li = MINERAL_BOARDS['lithium']
    assert li['futures_code'] == 'LC0'
    assert li['futures_source'] == 'akshare'
    for b in MINERAL_BOARDS.values():
        assert {'name', 'futures_code', 'futures_name', 'futures_source', 'futures_fallback_code'} <= set(b)


def test_fetch_lithium_trend_parses_akshare(monkeypatch):
    import pandas as pd
    from app.services import minerals_data as md
    fake = pd.DataFrame({
        '日期': ['2026-06-20', '2026-06-23', '2026-06-24'],
        '开盘价': [68000, 68200, 68500],
        '最高价': [68600, 68700, 69000],
        '最低价': [67800, 68000, 68300],
        '收盘价': [68200, 68500, 68900],
    })
    monkeypatch.setattr(md, '_fetch_lithium_raw', lambda symbol='LC0': fake)
    out = md.fetch_lithium_futures_trend(days=30)
    assert out['stock_code'] == 'LC0'
    assert out['data'][-1] == {'date': '2026-06-24', 'close': 68900.0}


def test_fetch_lithium_trend_returns_none_on_error(monkeypatch):
    from app.services import minerals_data as md
    def boom(symbol='LC0'):
        raise RuntimeError('akshare down')
    monkeypatch.setattr(md, '_fetch_lithium_raw', boom)
    assert md.fetch_lithium_futures_trend() is None


def test_get_board_futures_copper_uses_futures_service(monkeypatch):
    from app.services import minerals_data as md
    monkeypatch.setattr(md.FuturesService, 'get_custom_trend_data',
                        staticmethod(lambda codes, days=30, cached_only=False: {
                            'stocks': [{'stock_code': 'HG=F', 'stock_name': 'COMEX铜',
                                        'data': [{'date': '2026-06-24', 'close': 4.82}]}],
                            'date_range': {}}))
    out = md.get_board_futures('copper', days=30)
    assert out['stock_code'] == 'HG=F'
    assert out['is_fallback'] is False
    assert out['data'][-1]['close'] == 4.82


def test_get_board_futures_lithium_degrades_when_akshare_fails(monkeypatch):
    from app.services import minerals_data as md
    monkeypatch.setattr(md, 'fetch_lithium_futures_trend', lambda days=30: None)
    out = md.get_board_futures('lithium', days=30)
    assert out['is_fallback'] is True
    assert out['data'] == []
    assert '暂缺' in out['note']


def test_load_board_stocks_filters_by_commodity(tmp_path):
    from app.services.minerals_data import load_board_stocks
    p = tmp_path / 'v.yaml'
    p.write_text(
        "- stock_code: '601899'\n  stock_name: 紫金矿业\n  market: A\n  commodity: copper\n  commodity_impact: positive\n  base: 9.7\n"
        "- stock_code: '002460'\n  stock_name: 赣锋锂业\n  market: A\n  commodity: lithium\n  commodity_impact: positive\n  base: 25.37\n"
        "- stock_code: '600519'\n  stock_name: 贵州茅台\n  market: A\n  base: 1.0\n",
        encoding='utf-8')
    rows = load_board_stocks('copper', path=p)
    assert [r['stock_code'] for r in rows] == ['601899']


def test_get_board_data_sorts_positive_first_then_margin(monkeypatch, tmp_path):
    from app.services import minerals_data as md
    p = tmp_path / 'v.yaml'
    p.write_text(
        "- stock_code: '601899'\n  stock_name: 紫金矿业\n  market: A\n  commodity: copper\n  commodity_impact: positive\n  base: 12.0\n"
        "- stock_code: '000630'\n  stock_name: 铜陵有色\n  market: A\n  commodity: copper\n  commodity_impact: positive\n  base: 20.0\n"
        "- stock_code: '301217'\n  stock_name: 铜冠铜箔\n  market: A\n  commodity: copper\n  commodity_impact: negative\n  base: 30.0\n",
        encoding='utf-8')
    monkeypatch.setattr(md, 'VALUATIONS_PATH', p)
    monkeypatch.setattr(md, 'get_board_futures', lambda commodity, days=30: {'data': [], 'is_fallback': False})
    monkeypatch.setattr(md.FuturesService, 'get_custom_trend_data',
                        staticmethod(lambda codes, days=30, cached_only=False: {'stocks': []}))
    monkeypatch.setattr(md.unified_stock_data_service, 'get_realtime_prices',
                        lambda codes, cache_only=False: {c: {'price': 10.0} for c in codes})
    out = md.get_board_data('copper', days=30)
    # 正面在前，正面组内 base 安全边际(=base/price-1)降序：000630(20/10-1=1.0) > 601899(0.2)，负面 301217 垫底
    assert [s['stock_code'] for s in out['stocks']] == ['000630', '601899', '301217']
    assert out['name'] == '铜'


from pathlib import Path


def test_schema_accepts_valid_commodity_fields():
    import scripts._docs_schema as s
    fm = {'doc_type': 'buffett', 'stock_code': '601899', 'stock_name': '紫金矿业',
          'sector': 'materials', 'subsector': 'nonferrous', 'themes': ['copper'],
          'rating': 'core', 'conviction_date': '2026-04-24', 'thesis': 'x',
          'commodity': 'copper', 'commodity_impact': 'positive'}
    out = s.validate_frontmatter(fm, Path('x.md'))
    assert not [v for v in out if 'commodity' in v]


def test_schema_rejects_bad_commodity():
    import scripts._docs_schema as s
    fm = {'doc_type': 'buffett', 'stock_code': '601899', 'stock_name': '紫金矿业',
          'sector': 'materials', 'subsector': 'nonferrous', 'themes': ['copper'],
          'rating': 'core', 'conviction_date': '2026-04-24', 'thesis': 'x',
          'commodity': 'gold-typo', 'commodity_impact': 'up'}
    out = s.validate_frontmatter(fm, Path('x.md'))
    assert any("commodity 'gold-typo'" in v for v in out)
    assert any("commodity_impact 'up'" in v for v in out)


def test_schema_accepts_neutral_impact():
    import scripts._docs_schema as s
    fm = {'doc_type': 'buffett', 'stock_code': '000878', 'stock_name': '云南铜业',
          'sector': 'materials', 'subsector': 'nonferrous', 'themes': ['copper'],
          'rating': 'watch', 'watch_reason': 'x', 'conviction_date': '2026-06-02', 'thesis': 'x',
          'commodity': 'copper', 'commodity_impact': 'neutral'}
    out = s.validate_frontmatter(fm, Path('x.md'))
    assert not [v for v in out if 'commodity_impact' in v]


def test_get_board_data_neutral_sorts_between(monkeypatch, tmp_path):
    from app.services import minerals_data as md
    p = tmp_path / 'v.yaml'
    p.write_text(
        "- stock_code: '601899'\n  stock_name: 紫金\n  market: A\n  commodity: copper\n  commodity_impact: positive\n  base: 12.0\n"
        "- stock_code: '000878'\n  stock_name: 云南铜业\n  market: A\n  commodity: copper\n  commodity_impact: neutral\n  base: 50.0\n"
        "- stock_code: '301217'\n  stock_name: 铜冠铜箔\n  market: A\n  commodity: copper\n  commodity_impact: negative\n  base: 99.0\n",
        encoding='utf-8')
    monkeypatch.setattr(md, 'VALUATIONS_PATH', p)
    monkeypatch.setattr(md, 'get_board_futures', lambda commodity, days=30: {'data': [], 'is_fallback': False})
    monkeypatch.setattr(md.FuturesService, 'get_custom_trend_data',
                        staticmethod(lambda codes, days=30, cached_only=False: {'stocks': []}))
    monkeypatch.setattr(md.unified_stock_data_service, 'get_realtime_prices',
                        lambda codes, cache_only=False: {c: {'price': 10.0} for c in codes})
    out = md.get_board_data('copper', days=30)
    assert [s['stock_code'] for s in out['stocks']] == ['601899', '000878', '301217']


@pytest.fixture(scope='module')
def app_client():
    import os
    os.environ['SCHEDULER_ENABLED'] = '0'
    from app import create_app
    from app.services import unified_stock_data_service
    _orig = unified_stock_data_service.get_realtime_prices
    unified_stock_data_service.get_realtime_prices = lambda codes, force_refresh=False, cache_only=False: {}
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client
    unified_stock_data_service.get_realtime_prices = _orig


def test_minerals_index_smoke(app_client):
    resp = app_client.get('/minerals/')
    assert resp.status_code == 200
    html = resp.data.decode('utf-8')
    assert '矿产' in html
    assert '铜' in html and '锂' in html


def test_minerals_api_board_returns_json(app_client, monkeypatch):
    from app.routes import minerals as mod
    monkeypatch.setattr(mod, 'get_board_data', lambda commodity, days=30, force_refresh=False: {
        'commodity': commodity, 'name': '铜',
        'futures': {'stock_code': 'HG=F', 'data': [{'date': '2026-06-24', 'close': 4.82}],
                    'is_fallback': False, 'note': None, 'futures_name': 'COMEX铜'},
        'stocks': [{'stock_code': '601899', 'stock_name': '紫金矿业', 'impact': 'positive',
                    'current_price': 18.2, 'margin_base': -0.46, 'trend': []}]})
    resp = app_client.get('/minerals/api/board/copper')
    assert resp.status_code == 200
    body = resp.get_json()
    assert body['futures']['stock_code'] == 'HG=F'
    assert body['stocks'][0]['impact'] == 'positive'


def test_minerals_api_board_unknown_404(app_client):
    resp = app_client.get('/minerals/api/board/uranium')
    assert resp.status_code == 404
