from app.config.stock_codes import WATCH_CODES
from app.services.watch_service import WatchService


def test_get_watch_codes_matches_config_order():
    codes = WatchService.get_watch_codes()
    assert codes == [e['code'] for e in WATCH_CODES]
    assert len(codes) == len(WATCH_CODES)
    assert '2631.HK' in codes and '2577.HK' in codes


def test_get_watch_list_fields():
    items = WatchService.get_watch_list()
    assert len(items) == len(WATCH_CODES)
    first = items[0]
    assert set(first.keys()) >= {'id', 'stock_code', 'stock_name', 'market', 'added_at'}
    assert first['added_at'] is None
    by_code = {i['stock_code']: i for i in items}
    assert by_code['000660.KS']['stock_name'] == 'SK海力士'
    assert by_code['000660.KS']['market'] == 'KR'


def test_get_watched_markets_priority_order():
    markets = WatchService.get_watched_markets()
    assert markets == ['A', 'HK', 'KR']


def test_get_market_map():
    mm = WatchService.get_market_map()
    assert mm['000660.KS'] == 'KR'
    assert mm['2631.HK'] == 'HK'
    assert mm['300223'] == 'A'
    assert len(mm) == len(WATCH_CODES)


def _watch_client():
    from flask import Flask
    from app.routes import watch_bp
    app = Flask(__name__)
    app.register_blueprint(watch_bp)
    return app.test_client()


def test_add_remove_search_routes_removed():
    c = _watch_client()
    assert c.post('/watch/add', json={'stock_code': 'X'}).status_code == 404
    assert c.delete('/watch/remove/300223').status_code == 404
    assert c.get('/watch/stocks/search?q=x').status_code == 404
