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
