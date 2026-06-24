import os

import pytest


@pytest.fixture(scope='session')
def app_client():
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
