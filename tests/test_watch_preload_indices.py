from app.strategies.watch_preload import WatchPreloadStrategy


def test_index_codes_for_open_markets():
    s = WatchPreloadStrategy()
    got = s._index_codes_for_markets({'A'})
    assert got == {'A': ['000001.SS', '399006.SZ', '000688.SS']}


def test_index_codes_kr_open():
    s = WatchPreloadStrategy()
    got = s._index_codes_for_markets({'A', 'KR'})
    assert got['KR'] == ['^KS11']


def test_index_codes_none_open():
    s = WatchPreloadStrategy()
    assert s._index_codes_for_markets({'US', 'HK'}) == {}
