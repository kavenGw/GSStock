from datetime import datetime, timedelta

import pytest
import requests

from app.services import market_cap_service as module
from app.services.market_cap_service import MarketCapService


def a_quote(symbol, cap='1587.04', when='20261030161445'):
    fields = [''] * 88
    fields[30], fields[45] = when, cap
    return f'v_{symbol}="{"~".join(fields)}";'


def hk_quote(symbol='r_hk02476', price='123.100', shares='982784813.00', when='2026/10/30 16:08:14'):
    fields = [''] * 78
    fields[3], fields[30], fields[69] = price, when, shares
    return f'v_{symbol}="{"~".join(fields)}";'


FX = 'v_whHKDCNY="310~港元人民币~HKDCNY~0.8480~0";'


class FakeCache:
    def __init__(self, entries=None):
        self.entries = entries or {}

    def get(self, code, cache_type):
        return self.entries.get(code)

    def set(self, code, cache_type, data, ttl=None):
        self.entries[code] = data

    def _calculate_ttl(self, code):
        return 1800


class FakeResponse:
    def __init__(self, text):
        self.text = text

    def raise_for_status(self):
        pass


@pytest.fixture
def cache(monkeypatch):
    fake = FakeCache()
    monkeypatch.setattr(module, 'memory_cache', fake)
    return fake


def respond_with(monkeypatch, *lines):
    calls = []

    def get(url, **kwargs):
        calls.append(url)
        return FakeResponse('\n'.join(lines))

    monkeypatch.setattr(module.requests, 'get', get)
    return calls


def fail_requests(monkeypatch):
    def get(url, **kwargs):
        raise requests.ConnectionError('down')

    monkeypatch.setattr(module.requests, 'get', get)


def cached_entry(expires_delta):
    return {
        'market_cap': 100.0, 'as_of': '2026-10-29 16:00', 'basis': 'A', 'fx': None,
        'expires_at': (datetime.now() + expires_delta).isoformat(),
    }


def test_a_and_hk_converted_to_cny_100m(monkeypatch, cache):
    calls = respond_with(monkeypatch, a_quote('sz002916'), hk_quote(), FX)
    result = MarketCapService.get_cny_market_caps(['002916', '02476'])
    assert 'r_hk02476' in calls[0] and 'whHKDCNY' in calls[0]
    assert result['market_caps']['002916']['market_cap'] == pytest.approx(1587.04)
    hk = result['market_caps']['02476']
    assert hk['market_cap'] == pytest.approx(123.1 * 982784813 / 1e8 * 0.848)
    assert (hk['basis'], hk['fx']) == ('H', 0.848)
    assert result['as_of'] == '2026-10-30 16:08'


def test_fx_failure_only_hides_hk(monkeypatch, cache):
    respond_with(monkeypatch, a_quote('sz002916'), hk_quote())
    caps = MarketCapService.get_cny_market_caps(['002916', '02476'])['market_caps']
    assert set(caps) == {'002916'}


def test_missing_single_quote_not_replaced_by_stale_cache(monkeypatch, cache):
    cache.entries['002463'] = cached_entry(timedelta(minutes=-1))
    respond_with(monkeypatch, a_quote('sz002916'), FX)
    caps = MarketCapService.get_cny_market_caps(['002916', '002463'])['market_caps']
    assert set(caps) == {'002916'}


def test_whole_failure_falls_back_to_stale_cache(monkeypatch, cache):
    cache.entries['002916'] = cached_entry(timedelta(minutes=-1))
    fail_requests(monkeypatch)
    result = MarketCapService.get_cny_market_caps(['002916', '002463'])
    assert result['market_caps']['002916']['market_cap'] == 100.0
    assert set(result['market_caps']) == {'002916'}
    assert result['as_of'] == '2026-10-29 16:00'


def test_whole_failure_without_cache_returns_empty(monkeypatch, cache):
    fail_requests(monkeypatch)
    assert MarketCapService.get_cny_market_caps(['002916']) == {'market_caps': {}, 'as_of': None}


def test_fresh_cache_skips_request(monkeypatch, cache):
    cache.entries['002916'] = cached_entry(timedelta(minutes=10))
    calls = respond_with(monkeypatch)
    assert MarketCapService.get_cny_market_caps(['002916'])['market_caps']['002916']['market_cap'] == 100.0
    assert calls == []


def test_fetched_entry_cached_with_retention_and_expiry(monkeypatch, cache):
    respond_with(monkeypatch, a_quote('sz002916'), FX)
    MarketCapService.get_cny_market_caps(['002916'])
    assert cache.entries['002916']['expires_at'] > datetime.now().isoformat()


def test_invalid_and_unsupported_values_are_skipped(monkeypatch, cache):
    respond_with(monkeypatch, a_quote('sz002916', cap='0'), hk_quote(shares=''), FX)
    assert MarketCapService.get_cny_market_caps(['002916', '02476', 'AAPL'])['market_caps'] == {}
