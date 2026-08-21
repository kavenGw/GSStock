"""港股 ETF 溢价（Yahoo T-1 净值源）—— 3431.HK 南方港韩科技"""
import pandas as pd

from app.services.briefing import BriefingService
from app.services.notification import NotificationService

HK_CODE = '3431.HK'


def _row(price, iopv):
    return pd.Series({'最新价': price, 'IOPV实时估值': iopv})


def _patch_eastmoney(monkeypatch, etf_map):
    """返回非 None 的快照，避免真实 fund_etf_spot_em 网络调用"""
    monkeypatch.setattr(
        'app.services.unified_stock_data.unified_stock_data_service._get_source_snapshot',
        lambda key: etf_map if key == 'eastmoney_etf' else None,
    )


def test_yahoo_source_computes_premium_without_signal(monkeypatch):
    _patch_eastmoney(monkeypatch, {})
    monkeypatch.setattr(
        BriefingService, '_fetch_yahoo_etf_quote',
        staticmethod(lambda code: {'price': 10.42, 'nav': 10.5704}),
    )

    etfs = {e['code']: e for e in BriefingService.get_etf_premium_data()['etfs']}
    hk = etfs[HK_CODE]
    assert hk['premium_rate'] == -1.42
    assert hk['signal'] is None
    assert hk['error'] is None


def test_yahoo_failure_degrades_only_that_etf(monkeypatch):
    _patch_eastmoney(monkeypatch, {'159941': _row(1.55, 1.50), '513850': _row(2.04, 2.00)})
    monkeypatch.setattr(BriefingService, '_fetch_yahoo_etf_quote', staticmethod(lambda code: None))

    data = BriefingService.get_etf_premium_data()
    etfs = {e['code']: e for e in data['etfs']}
    assert etfs['159941']['premium_rate'] == 3.33
    assert etfs['159941']['signal'] == 'normal'
    assert etfs['513850']['signal'] == 'buy'
    assert etfs[HK_CODE]['premium_rate'] is None
    assert etfs[HK_CODE]['error']
    assert data['partial'] is True


def test_push_line_shows_hk_etf_without_signal_label(monkeypatch):
    _patch_eastmoney(monkeypatch, {})
    monkeypatch.setattr(
        BriefingService, '_fetch_yahoo_etf_quote',
        staticmethod(lambda code: {'price': 10.42, 'nav': 10.5704}),
    )

    text = NotificationService.format_etf_premium_summary()
    assert '南方港韩科技(T-1) -1.42%' in text
    assert '适合买入' not in text
    assert '溢价过高' not in text


class _FakeTicker:
    def __init__(self, info):
        self._info = info

    def __call__(self, code):
        return self

    @property
    def info(self):
        return self._info


def _patch_snapshot_passthrough(monkeypatch):
    store = {}
    monkeypatch.setattr(
        'app.services.unified_stock_data.unified_stock_data_service._get_source_snapshot',
        lambda key: store.get(key),
    )
    monkeypatch.setattr(
        'app.services.unified_stock_data.unified_stock_data_service._set_source_snapshot',
        lambda key, value: store.__setitem__(key, value),
    )
    return store


def test_fetch_yahoo_etf_quote_returns_price_and_nav(monkeypatch):
    _patch_snapshot_passthrough(monkeypatch)
    monkeypatch.setattr(
        'yfinance.Ticker',
        _FakeTicker({'regularMarketPrice': 10.42, 'navPrice': 10.5704}),
    )

    assert BriefingService._fetch_yahoo_etf_quote(HK_CODE) == {'price': 10.42, 'nav': 10.5704}


def test_fetch_yahoo_etf_quote_falls_back_to_previous_close(monkeypatch):
    _patch_snapshot_passthrough(monkeypatch)
    monkeypatch.setattr(
        'yfinance.Ticker',
        _FakeTicker({'previousClose': 10.40, 'navPrice': 10.5704}),
    )

    assert BriefingService._fetch_yahoo_etf_quote(HK_CODE) == {'price': 10.40, 'nav': 10.5704}


def test_fetch_yahoo_etf_quote_returns_none_when_nav_missing(monkeypatch):
    _patch_snapshot_passthrough(monkeypatch)
    monkeypatch.setattr('yfinance.Ticker', _FakeTicker({'regularMarketPrice': 10.42}))

    assert BriefingService._fetch_yahoo_etf_quote(HK_CODE) is None


def test_fetch_yahoo_etf_quote_caches_within_snapshot(monkeypatch):
    store = _patch_snapshot_passthrough(monkeypatch)
    calls = []

    class _Counting(_FakeTicker):
        def __call__(self, code):
            calls.append(code)
            return self

    monkeypatch.setattr('yfinance.Ticker', _Counting({'regularMarketPrice': 10.42, 'navPrice': 10.5704}))

    BriefingService._fetch_yahoo_etf_quote(HK_CODE)
    BriefingService._fetch_yahoo_etf_quote(HK_CODE)
    assert calls == [HK_CODE]
    assert store['yahoo_etf_nav'][HK_CODE] == {'price': 10.42, 'nav': 10.5704}
