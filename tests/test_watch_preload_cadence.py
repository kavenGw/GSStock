from app.strategies.watch_preload import WatchPreloadStrategy


def test_a_share_refreshes_every_tick():
    assert all(WatchPreloadStrategy._should_refresh_market('A', t) for t in range(6))


def test_hk_refreshes_every_tick():
    assert all(WatchPreloadStrategy._should_refresh_market('HK', t) for t in range(6))


def test_us_refreshes_every_third_tick():
    assert WatchPreloadStrategy._should_refresh_market('US', 0) is True
    assert WatchPreloadStrategy._should_refresh_market('US', 1) is False
    assert WatchPreloadStrategy._should_refresh_market('US', 2) is False
    assert WatchPreloadStrategy._should_refresh_market('US', 3) is True


def test_schedule_is_one_minute():
    assert WatchPreloadStrategy.schedule == 'interval_minutes:1'


def test_oil_refreshes_without_watched_stocks(monkeypatch):
    from app.services.watch_service import WatchService
    from app.services.unified_stock_data import unified_stock_data_service

    calls = []

    def fetch(codes, force_refresh=False):
        calls.append((codes, force_refresh))
        return {code: {'current_price': 80.0} for code in codes}

    monkeypatch.setattr(WatchService, 'get_watch_codes', staticmethod(lambda: []))
    monkeypatch.setattr(unified_stock_data_service, 'get_realtime_prices', fetch)
    strategy = WatchPreloadStrategy()
    strategy._backoff = {}
    for _ in range(4):
        assert strategy.scan() == []
    assert calls == [(['CL=F', 'BZ=F'], True)] * 2
