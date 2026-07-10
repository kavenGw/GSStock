"""watch_preload 取价间隔降频至 3 分钟"""
from app.strategies.watch_preload import WatchPreloadStrategy


def test_preload_schedule_is_3_minutes():
    assert WatchPreloadStrategy.schedule == 'interval_minutes:3'
