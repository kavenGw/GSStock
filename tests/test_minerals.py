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
