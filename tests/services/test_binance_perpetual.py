from collections import deque

import httpx
import pytest

from app.services import binance_perpetual as module


@pytest.fixture
def env(monkeypatch):
    state = {'now': 10000, 'price': '100', 'status': 'TRADING',
             'type': 'TRADIFI_PERPETUAL', 'underlying': 'EQUITY', 'fail': False,
             'lag': 0, 'calls': []}
    monkeypatch.setattr(module.time, 'time', lambda: state['now'])
    service = module.BinancePerpetualService()
    monkeypatch.setattr(service, 'targets', lambda: [{
        'symbol': 'NVDAUSDT', 'source_code': 'NVDA', 'name': '英伟达',
        'kind': '股票/ETF永续', 'underlying_type': 'EQUITY', 'price_unit': 'USDT',
    }])

    def get(client, endpoint):
        state['calls'].append(endpoint)
        if state['fail']:
            raise httpx.ConnectError('offline')
        if endpoint == 'exchangeInfo':
            return {'symbols': [{'symbol': 'NVDAUSDT', 'status': state['status'],
                                 'contractType': state['type'], 'quoteAsset': 'USDT',
                                 'underlyingType': state['underlying']}]}
        timestamp = (state['now'] - state['lag']) * 1000
        if endpoint == 'ticker/24hr':
            return [{'symbol': 'NVDAUSDT', 'lastPrice': state['price'],
                     'priceChangePercent': '-2.1', 'closeTime': timestamp}]
        return [{'symbol': 'NVDAUSDT', 'markPrice': '100.1',
                 'lastFundingRate': '0.0001', 'time': timestamp,
                 'nextFundingTime': 20000000}]

    monkeypatch.setattr(service, '_get', get)
    state['service'] = service
    return state


def row(env):
    return env['service'].snapshot()['data'][0]


def test_tradfi_quote_and_cache_only_snapshot(env):
    env['service'].refresh()
    assert row(env)['available']
    assert row(env)['funding_rate_pct'] == pytest.approx(0.01)
    assert row(env)['change_15m_pct'] is None
    env['service'].refresh()
    env['service'].snapshot()
    assert len(env['calls']) == 3


@pytest.mark.parametrize('key,value', [
    ('status', 'SETTLING'), ('type', 'CURRENT_QUARTER'), ('underlying', 'COIN'),
    ('price', 'NaN'), ('price', '0'), ('price', '-1'), ('lag', 181), ('lag', -31),
])
def test_invalid_or_stale_quotes_cannot_alert(env, key, value):
    env[key] = value
    env['service'].refresh()
    assert not row(env)['available']
    assert row(env)['change_15m_pct'] is None


def test_complete_window_gap_failure_and_recovery(env):
    service = env['service']
    for minute in range(16):
        env['now'] = 10000 + minute * 60
        env['price'] = str(100 + minute)
        service.refresh()
    assert row(env)['change_15m_pct'] == pytest.approx(15)
    env['now'] += 60
    env['fail'] = True
    service.refresh()
    assert not row(env)['available']
    assert row(env)['updated_at'] == 10900
    assert not service._history
    env['fail'] = False
    env['now'] += 60
    service.refresh()
    assert row(env)['available']
    assert row(env)['change_15m_pct'] is None
    env['now'] += 181
    assert not row(env)['available']
    service.refresh()
    assert row(env)['change_15m_pct'] is None


def test_jittered_window_does_not_use_ancient_baseline(env):
    service = env['service']
    service.refresh()
    service._history['NVDAUSDT'] = deque([(9000, 10), (9940, 100), (10000, 104)])
    assert row(env)['change_15m_pct'] is None


def test_only_explicit_current_pool_mappings(monkeypatch):
    from app.config import stock_codes
    monkeypatch.setattr(stock_codes, 'WATCH_CODES', [
        {'code': 'NVDA', 'name': '英伟达'}, {'code': '603986', 'name': '兆易创新'},
        {'code': 'BTC', 'name': 'BTC'}, {'code': '1810.HK', 'name': '小米'},
    ])
    monkeypatch.setattr(stock_codes, 'BENCHMARK_CODES', [
        {'code': '^NDX', 'name': '纳指'}, {'code': 'CL=F', 'name': 'WTI原油期货'},
    ])
    rows = module.BinancePerpetualService.targets()
    assert {r['symbol'] for r in rows} == {'NVDAUSDT', 'HK1810USDT', 'CLUSDT'}
    assert rows[1]['price_unit'] == 'HKD（quanto）'
    assert rows[2]['kind'] == '商品永续'
