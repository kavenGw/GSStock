import sqlite3
from datetime import date
from unittest.mock import Mock

import pytest
from flask import Flask
from sqlalchemy.exc import OperationalError

from app import db
from app.models.unified_cache import UnifiedStockCache


@pytest.fixture
def cache_db(tmp_path):
    path = tmp_path / 'cache.db'
    app = Flask(__name__)
    app.config.update(SQLALCHEMY_DATABASE_URI=f'sqlite:///{path.as_posix()}',
                      SQLALCHEMY_ENGINE_OPTIONS={'connect_args': {'timeout': 0.01}})
    db.init_app(app)
    with app.app_context():
        UnifiedStockCache.__table__.create(db.engine)
        UnifiedStockCache.set_cached_data('688766', 'ohlc_60', {'old': True})
        locker = sqlite3.connect(path)
        locker.execute('BEGIN IMMEDIATE')
        try:
            yield locker
        finally:
            locker.rollback()
            locker.close()
            db.session.remove()
            db.engine.dispose()


@pytest.mark.parametrize('code', ['688766', '600519'])
def test_write_retries_after_writer_releases_lock(cache_db, monkeypatch, code):
    import time
    sleep = Mock(side_effect=lambda _: cache_db.rollback())
    monkeypatch.setattr(time, 'sleep', sleep)
    UnifiedStockCache.set_cached_data(code, 'ohlc_60', {'new': True})
    assert sleep.call_count == 1
    assert UnifiedStockCache.get_cached_data(code, 'ohlc_60') == {'new': True}


def test_exhausted_lock_rolls_back_and_session_remains_usable(cache_db, monkeypatch):
    import time
    sleep = Mock()
    monkeypatch.setattr(time, 'sleep', sleep)
    with pytest.raises(OperationalError, match='database is locked'):
        UnifiedStockCache.set_cached_data('688766', 'ohlc_60', {'new': True})
    assert sleep.call_count == 3
    cache_db.rollback()
    assert UnifiedStockCache.get_cached_data('688766', 'ohlc_60') == {'old': True}


def test_other_database_errors_are_not_retried_or_hidden(cache_db, monkeypatch):
    import time
    from app.services.unified_stock_data import UnifiedStockDataService

    cache_db.rollback()
    UnifiedStockCache.__table__.drop(db.engine)
    sleep = Mock()
    monkeypatch.setattr(time, 'sleep', sleep)
    with pytest.raises(OperationalError, match='no such table'):
        UnifiedStockDataService._save_trend_cache('688766', 'ohlc_60', {'new': True})
    sleep.assert_not_called()
    assert db.session.is_active


def test_incremental_trend_survives_exhausted_cache_lock(cache_db, monkeypatch):
    import time
    from app.services import unified_stock_data as module

    monkeypatch.setattr(time, 'sleep', lambda _: None)
    service = module.UnifiedStockDataService()
    old = {'stock_code': '688766', 'data': [{'date': '2026-10-27', 'close': 260}]}
    new = {'data': [{'date': '2026-10-28', 'close': 270}]}
    monkeypatch.setattr(module.memory_cache, 'get_batch', lambda *a: {})
    memory_set = Mock()
    monkeypatch.setattr(module.memory_cache, 'set', memory_set)
    monkeypatch.setattr(module, 'is_readonly_mode', lambda: False)
    monkeypatch.setattr(module.BatchCacheStrategy, 'filter_by_trading_status',
                        lambda codes: {'use_cache': []})
    monkeypatch.setattr(service, '_get_effective_cache_dates',
                        lambda codes: {'688766': date.today()})
    monkeypatch.setattr(UnifiedStockCache, 'get_cache_with_status',
                        lambda *a: {'688766': {'data': old, 'is_complete': False}})
    monkeypatch.setattr(UnifiedStockCache, 'get_data_end_dates',
                        lambda *a: {'688766': date(2026, 10, 27)})
    monkeypatch.setattr(module.TradingCalendarService, 'get_trading_days', lambda *a: [date.today()])
    monkeypatch.setattr(module.TradingCalendarService, 'is_after_close', lambda *a: False)
    monkeypatch.setattr(service, '_get_stock_name', lambda *a: 'test')
    monkeypatch.setattr(service, '_fetch_incremental_trend_data', lambda *a: new)
    result = service.get_trend_data(['688766'])
    assert result['stocks'][0]['data'][-1]['close'] == 270
    assert memory_set.call_args.args[2]['data'][-1]['close'] == 270
    cache_db.rollback()
    assert UnifiedStockCache.get_cached_data('688766', 'ohlc_60') == {'old': True}
