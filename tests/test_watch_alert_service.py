from datetime import datetime, timedelta
from app.services.watch_alert_service import WatchAlertService


def _fresh_service():
    # 重置单例状态，避免测试间污染
    svc = WatchAlertService()
    svc._price_ring = {}
    svc._momentum_cooldown = {}
    svc._fired = {}
    svc._last_trading_date = datetime.now().strftime('%Y-%m-%d')
    return svc


def test_momentum_fires_on_fast_rise():
    svc = _fresh_service()
    now = datetime.now()
    # 手动灌入 3 分钟前的旧价
    from collections import deque
    svc._price_ring['603626'] = deque([(now - timedelta(minutes=3), 30.0)], maxlen=5)
    sigs = svc._check_intraday_momentum('603626', '科森科技', {'current_price': 30.6})  # +2%
    assert len(sigs) == 1
    assert sigs[0].data['alert_type'] == 'intraday_momentum'
    assert sigs[0].data['direction'] == 'up'


def test_momentum_silent_below_threshold():
    svc = _fresh_service()
    now = datetime.now()
    from collections import deque
    svc._price_ring['603626'] = deque([(now - timedelta(minutes=3), 30.0)], maxlen=5)
    sigs = svc._check_intraday_momentum('603626', '科森科技', {'current_price': 30.2})  # +0.67%
    assert sigs == []


def test_momentum_cooldown_dedup():
    svc = _fresh_service()
    now = datetime.now()
    from collections import deque
    svc._price_ring['603626'] = deque([(now - timedelta(minutes=3), 30.0)], maxlen=5)
    first = svc._check_intraday_momentum('603626', '科森科技', {'current_price': 30.6})
    second = svc._check_intraday_momentum('603626', '科森科技', {'current_price': 30.7})
    assert len(first) == 1 and second == []  # cooldown 内不重复


def test_momentum_ring_maxlen():
    svc = _fresh_service()
    for i in range(8):
        svc._check_intraday_momentum('603626', '科森科技', {'current_price': 30.0 + i * 0.01})
    assert len(svc._price_ring['603626']) == 5


def _sr_params():
    return {'support_levels': [59.54, 55.0], 'resistance_levels': [63.75]}


def test_support_break_requires_crossing_from_above():
    # 通富微电场景：盘前分析给的"支撑"高于开盘价，股价一路上涨靠近该位，不应报跌破
    svc = _fresh_service()
    svc._prev_prices = {'002156': 58.9}
    sigs = svc._check_support_resistance('002156', '通富微电', 59.26, _sr_params())
    assert sigs == []


def test_support_break_fires_when_falling_through():
    svc = _fresh_service()
    svc._prev_prices = {'002156': 59.8}
    sigs = svc._check_support_resistance('002156', '通富微电', 59.26, _sr_params())
    assert len(sigs) == 1
    assert sigs[0].data['direction'] == 'support_break'


def test_resistance_break_requires_crossing_from_below():
    svc = _fresh_service()
    svc._prev_prices = {'002156': 64.5}
    sigs = svc._check_support_resistance('002156', '通富微电', 63.9, _sr_params())
    assert sigs == []


def test_support_test_from_above_still_fires():
    svc = _fresh_service()
    svc._prev_prices = {'002156': 60.5}
    sigs = svc._check_support_resistance('002156', '通富微电', 59.7, _sr_params())
    assert len(sigs) == 1
    assert sigs[0].data['direction'] == 'support_hold'


def test_no_break_without_prev_price():
    svc = _fresh_service()
    svc._prev_prices = {}
    sigs = svc._check_support_resistance('002156', '通富微电', 59.26, _sr_params())
    assert sigs == []
