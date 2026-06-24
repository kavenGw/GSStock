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
