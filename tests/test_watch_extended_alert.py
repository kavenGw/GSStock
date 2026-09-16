"""美股暗盘异动推送：阈值、首推/复推、时段外重置、合并一条消息、缓存为空不推"""
import pytest

from app.services.notification import NotificationService
from app.services.trading_calendar import TradingCalendarService
from app.services.watch_service import WatchService
from app.strategies.watch_extended_alert import WatchExtendedAlertStrategy


@pytest.fixture
def env(monkeypatch):
    from app.services import unified_stock_data as usd
    state = {'session': 'pre', 'cached': {}, 'sent': []}
    monkeypatch.setattr(WatchService, 'get_watch_list', staticmethod(lambda: [
        {'stock_code': 'NVDA', 'stock_name': '英伟达', 'market': 'US'},
        {'stock_code': 'LITE', 'stock_name': 'Lumentum', 'market': 'US'},
        {'stock_code': '0700.HK', 'stock_name': '腾讯控股', 'market': 'HK'},
    ]))
    monkeypatch.setattr(TradingCalendarService, 'get_us_session',
                        classmethod(lambda cls, dt=None: state['session']))
    monkeypatch.setattr(usd.unified_stock_data_service, 'get_us_extended_cached',
                        lambda codes: {c: q for c, q in state['cached'].items() if c in codes})
    monkeypatch.setattr(NotificationService, 'send_slack',
                        staticmethod(lambda text, channel='news', blocks=None: state['sent'].append((text, channel)) or True))
    strat = WatchExtendedAlertStrategy()
    strat._pushed = {}
    state['strat'] = strat
    return state


def _q(session, price, pct):
    return {'session': session, 'price': price, 'change_pct': pct, 'time': None}


def test_config_defaults():
    s = WatchExtendedAlertStrategy()
    assert s.schedule == 'interval_minutes:1'
    assert s.needs_llm is False
    assert s._threshold() == 3.0
    assert s._restep() == 2.0


def test_below_threshold_not_pushed(env):
    env['cached'] = {'NVDA': _q('pre', 212.0, -2.79), 'LITE': _q('pre', 900.0, 1.5)}
    env['strat'].scan()
    assert env['sent'] == []


def test_triggered_merged_into_one_message(env):
    env['cached'] = {'NVDA': _q('pre', 212.21, -3.2), 'LITE': _q('pre', 857.1, -7.54)}
    env['strat'].scan()
    assert len(env['sent']) == 1
    text, channel = env['sent'][0]
    assert channel == 'news_watch'
    assert text.splitlines()[0] == '🌙 *美股盘前异动*'
    assert '  · *Lumentum(LITE)* $857.10 🟢-7.54%' in text
    assert '  · *英伟达(NVDA)* $212.21 🟢-3.20%' in text
    assert text.index('LITE') < text.index('NVDA')


def test_post_session_title(env):
    env['session'] = 'post'
    env['cached'] = {'NVDA': _q('post', 220.0, 4.0)}
    env['strat'].scan()
    assert env['sent'][0][0].startswith('🌙 *美股盘后异动*')
    assert '🔴+4.00%' in env['sent'][0][0]


def test_repush_only_after_restep(env):
    env['cached'] = {'NVDA': _q('pre', 212.0, -3.2)}
    env['strat'].scan()
    env['cached'] = {'NVDA': _q('pre', 210.0, -4.5)}
    env['strat'].scan()
    assert len(env['sent']) == 1
    env['cached'] = {'NVDA': _q('pre', 205.0, -5.3)}
    env['strat'].scan()
    assert len(env['sent']) == 2
    assert '-5.30%' in env['sent'][1][0]


def test_state_reset_outside_session(env):
    env['cached'] = {'NVDA': _q('pre', 212.0, -3.2)}
    env['strat'].scan()
    env['session'] = None
    env['strat'].scan()
    assert env['strat']._pushed == {}
    env['session'] = 'post'
    env['cached'] = {'NVDA': _q('post', 212.0, -3.2)}
    env['strat'].scan()
    assert len(env['sent']) == 2


def test_session_switch_resets_state(env):
    env['cached'] = {'NVDA': _q('pre', 212.0, -3.2)}
    env['strat'].scan()
    env['session'] = 'post'
    env['cached'] = {'NVDA': _q('post', 212.0, -3.2)}
    env['strat'].scan()
    assert len(env['sent']) == 2


def test_empty_cache_not_pushed(env):
    env['cached'] = {}
    assert env['strat'].scan() == []
    assert env['sent'] == []


def test_non_us_codes_ignored(env):
    env['cached'] = {'0700.HK': _q('pre', 500.0, -9.0)}
    env['strat'].scan()
    assert env['sent'] == []


def test_overnight_session_not_pushed(env):
    # get_us_session 的 'overnight' 不在白名单内，须视同无时段，不推送
    env['session'] = 'overnight'
    env['cached'] = {'NVDA': _q('overnight', 212.0, -5.0)}
    env['strat'].scan()
    assert env['sent'] == []
