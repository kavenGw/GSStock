"""push_realtime_analysis：cache_only 取价 + 无新鲜价的股整块不推"""
from datetime import datetime, timedelta

from app.services.notification import NotificationService
from app.services.watch_service import WatchService
from app.services.unified_stock_data import unified_stock_data_service

ANALYSES = {
    '600519': {'realtime': {'signal': 'buy', 'summary': 'sum-fresh',
                            'support_levels': [10.0], 'resistance_levels': [20.0]}},
    '0700.HK': {'realtime': {'signal': 'sell', 'summary': 'sum-stale',
                             'support_levels': [1.0], 'resistance_levels': [2.0]}},
}
WATCH_LIST = [
    {'stock_code': '600519', 'stock_name': '茅台', 'market': 'A'},
    {'stock_code': '0700.HK', 'stock_name': '腾讯', 'market': 'HK'},
]


def _setup(monkeypatch, prices):
    NotificationService._realtime_push_state = {'date': None, 'stocks': {}}
    monkeypatch.setattr(WatchService, 'get_watch_list', staticmethod(lambda: WATCH_LIST))
    calls = {}

    def fake_prices(codes, **kwargs):
        calls['kwargs'] = kwargs
        return prices

    monkeypatch.setattr(unified_stock_data_service, 'get_realtime_prices', fake_prices)
    sent = []
    monkeypatch.setattr(NotificationService, 'send_slack',
                        staticmethod(lambda msg, channel=None, blocks=None:
                                     sent.append(msg) or True))
    return calls, sent


def test_stale_stock_block_not_pushed(monkeypatch):
    prices = {
        '600519': {'current_price': 1800.0, 'change_percent': 1.2,
                   'last_fetch_time': datetime.now().isoformat()},
        '0700.HK': {'current_price': 500.0, 'change_percent': -0.5,
                    'last_fetch_time': (datetime.now() - timedelta(minutes=10)).isoformat()},
    }
    calls, sent = _setup(monkeypatch, prices)
    NotificationService.push_realtime_analysis(ANALYSES)
    joined = '\n'.join(sent)
    assert '600519' in joined and '1800.0' in joined
    assert '0700.HK' not in joined and 'sum-stale' not in joined


def test_uses_cache_only_read(monkeypatch):
    prices = {'600519': {'current_price': 1800.0, 'change_percent': 1.2,
                         'last_fetch_time': datetime.now().isoformat()}}
    calls, sent = _setup(monkeypatch, prices)
    NotificationService.push_realtime_analysis(ANALYSES)
    assert calls['kwargs'].get('cache_only') is True


def test_all_stale_pushes_nothing(monkeypatch):
    old = (datetime.now() - timedelta(minutes=30)).isoformat()
    prices = {
        '600519': {'current_price': 1800.0, 'last_fetch_time': old},
        '0700.HK': {'current_price': 500.0, 'last_fetch_time': old},
    }
    calls, sent = _setup(monkeypatch, prices)
    result = NotificationService.push_realtime_analysis(ANALYSES)
    assert sent == []
    assert result is False


def test_stale_gate_precedes_state_write(monkeypatch):
    """闸门必须在 _realtime_push_state 写入之前拦截 —— 否则停更期间被静默的股，
    恢复新鲜后会被误判成"已推送过"而走增量路径，丢失首推的完整支撑/压力信息"""
    single = {'600519': ANALYSES['600519']}
    stale = (datetime.now() - timedelta(minutes=10)).isoformat()
    calls, sent = _setup(monkeypatch, {
        '600519': {'current_price': 1800.0, 'change_percent': 1.2, 'last_fetch_time': stale},
    })
    NotificationService.push_realtime_analysis(single)
    assert sent == []
    assert '600519' not in NotificationService._realtime_push_state['stocks']

    fresh = datetime.now().isoformat()
    monkeypatch.setattr(unified_stock_data_service, 'get_realtime_prices',
                         lambda codes, **kwargs: {
                             '600519': {'current_price': 1800.0, 'change_percent': 1.2,
                                        'last_fetch_time': fresh},
                         })
    NotificationService.push_realtime_analysis(single)
    joined = '\n'.join(sent)
    assert '📊 盯盘实时分析' in joined
    assert '支撑' in joined and '压力' in joined
    assert '🔄 盯盘更新' not in joined
