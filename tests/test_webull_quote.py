"""Webull 扩展时段报价：tickerId 解析与缓存、字段映射、session 由调用方给定、失败跳过"""
import pytest

from app.services import webull_quote


@pytest.fixture(autouse=True)
def _clear_ids():
    webull_quote._ticker_ids.clear()
    yield
    webull_quote._ticker_ids.clear()


class _Resp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


SEARCH_PAYLOAD = {'data': [
    {'symbol': 'NVDA', 'regionId': 1, 'tickerId': 111},
    {'symbol': 'NVDAX', 'regionId': 6, 'tickerId': 222},
    {'symbol': 'NVDA', 'regionId': 6, 'tickerId': 913257561},
]}


class TestResolveTickerId:
    def test_picks_us_region_exact_symbol(self, monkeypatch):
        monkeypatch.setattr(webull_quote.requests, 'get',
                            lambda url, **kw: _Resp(SEARCH_PAYLOAD))
        assert webull_quote.resolve_ticker_id('NVDA') == 913257561

    def test_caches_result(self, monkeypatch):
        calls = []

        def fake_get(url, **kw):
            calls.append(url)
            return _Resp(SEARCH_PAYLOAD)

        monkeypatch.setattr(webull_quote.requests, 'get', fake_get)
        webull_quote.resolve_ticker_id('NVDA')
        webull_quote.resolve_ticker_id('NVDA')
        assert len(calls) == 1

    def test_no_match_returns_none(self, monkeypatch):
        monkeypatch.setattr(webull_quote.requests, 'get',
                            lambda url, **kw: _Resp({'data': []}))
        assert webull_quote.resolve_ticker_id('NOPE') is None

    def test_http_failure_returns_none(self, monkeypatch):
        def boom(url, **kw):
            raise RuntimeError('network down')

        monkeypatch.setattr(webull_quote.requests, 'get', boom)
        assert webull_quote.resolve_ticker_id('NVDA') is None

    def test_no_match_caches_negative_result(self, monkeypatch):
        calls = []

        def fake_get(url, **kw):
            calls.append(url)
            return _Resp({'data': []})

        monkeypatch.setattr(webull_quote.requests, 'get', fake_get)
        assert webull_quote.resolve_ticker_id('NOPE') is None
        assert webull_quote.resolve_ticker_id('NOPE') is None
        assert len(calls) == 1

    def test_exception_not_cached_retries_next_call(self, monkeypatch):
        calls = []

        def boom(url, **kw):
            calls.append(url)
            raise RuntimeError('network down')

        monkeypatch.setattr(webull_quote.requests, 'get', boom)
        assert webull_quote.resolve_ticker_id('NVDA') is None
        assert webull_quote.resolve_ticker_id('NVDA') is None
        assert len(calls) == 2


class TestParseQuote:
    def test_ratio_converted_to_percent(self):
        raw = {'pPrice': '213.4712', 'pChRatio': '0.0061',
               'tradeTime': '2026-09-16T11:46:40.516+0000', 'overnight': 0}
        q = webull_quote.parse_quote(raw, 'pre')
        assert q == {'session': 'pre', 'price': 213.47, 'change_pct': 0.61,
                     'time': '2026-09-16T11:46:40.516+0000', 'source': 'webull'}

    def test_negative_ratio(self):
        q = webull_quote.parse_quote({'pPrice': '10', 'pChRatio': '-0.0234'}, 'post')
        assert q['change_pct'] == -2.34 and q['session'] == 'post'

    def test_session_comes_from_caller_not_overnight_flag(self):
        # Webull 说 overnight=0，调用方按时钟给 overnight，以调用方为准
        q = webull_quote.parse_quote({'pPrice': '10', 'pChRatio': '0', 'overnight': 0}, 'overnight')
        assert q['session'] == 'overnight'

    def test_missing_price_returns_none(self):
        assert webull_quote.parse_quote({'pPrice': None, 'pChRatio': '0.01'}, 'pre') is None
        assert webull_quote.parse_quote({'pPrice': '', 'pChRatio': '0.01'}, 'pre') is None
        assert webull_quote.parse_quote({}, 'pre') is None

    def test_missing_ratio_defaults_zero(self):
        assert webull_quote.parse_quote({'pPrice': '10'}, 'pre')['change_pct'] == 0.0


class TestGetExtendedQuotes:
    def _patch(self, monkeypatch, quotes):
        monkeypatch.setattr(webull_quote, 'resolve_ticker_id',
                            lambda symbol: {'NVDA': 1, 'AMD': 2, 'WOLF': 3}.get(symbol))
        monkeypatch.setattr(webull_quote, '_fetch_quote',
                            lambda ticker_id: quotes[ticker_id])

    def test_batch(self, monkeypatch):
        self._patch(monkeypatch, {1: {'pPrice': '10', 'pChRatio': '0.01'},
                                  2: {'pPrice': '20', 'pChRatio': '-0.02'}})
        out = webull_quote.get_extended_quotes(['NVDA', 'AMD'], 'pre')
        assert out['NVDA']['price'] == 10.0 and out['AMD']['change_pct'] == -2.0
        assert all(q['session'] == 'pre' for q in out.values())

    def test_unresolvable_symbol_skipped(self, monkeypatch):
        self._patch(monkeypatch, {1: {'pPrice': '10', 'pChRatio': '0.01'}})
        out = webull_quote.get_extended_quotes(['NVDA', 'UNKNOWN'], 'pre')
        assert set(out) == {'NVDA'}

    def test_fetch_failure_skipped(self, monkeypatch):
        def fetch(ticker_id):
            if ticker_id == 3:
                raise RuntimeError('boom')
            return {'pPrice': '10', 'pChRatio': '0.01'}

        monkeypatch.setattr(webull_quote, 'resolve_ticker_id',
                            lambda symbol: {'NVDA': 1, 'WOLF': 3}.get(symbol))
        monkeypatch.setattr(webull_quote, '_fetch_quote', fetch)
        assert set(webull_quote.get_extended_quotes(['NVDA', 'WOLF'], 'post')) == {'NVDA'}

    def test_empty_inputs(self, monkeypatch):
        assert webull_quote.get_extended_quotes([], 'pre') == {}
        assert webull_quote.get_extended_quotes(['NVDA'], None) == {}

    def test_overnight_requires_webull_flag(self, monkeypatch):
        # 2026-09-17 实测：ET 20:35 夜盘窗口内 Webull 仍报 overnight=0、status=A，
        # pPrice 是冻结的盘后价，pChRatio 以 ET 20:00 收盘价为基准。不给价而非标成暗盘。
        monkeypatch.setattr(webull_quote, 'resolve_ticker_id', lambda symbol: 1)
        monkeypatch.setattr(webull_quote, '_fetch_quote',
                            lambda ticker_id: {'pPrice': '215.68', 'pChRatio': '0.0083',
                                               'overnight': 0})
        assert webull_quote.get_extended_quotes(['NVDA'], 'overnight') == {}

    def test_overnight_served_when_flag_set(self, monkeypatch):
        # 降级须自动恢复：Webull 一旦真供夜盘数据（overnight=1），价格照常流出
        monkeypatch.setattr(webull_quote, 'resolve_ticker_id', lambda symbol: 1)
        monkeypatch.setattr(webull_quote, '_fetch_quote',
                            lambda ticker_id: {'pPrice': '215.68', 'pChRatio': '0.0083',
                                               'overnight': 1})
        out = webull_quote.get_extended_quotes(['NVDA'], 'overnight')
        assert out['NVDA']['price'] == 215.68 and out['NVDA']['session'] == 'overnight'

    def test_pre_post_unaffected_by_flag(self, monkeypatch):
        # overnight 标志只管夜盘，不得波及盘前/盘后
        monkeypatch.setattr(webull_quote, 'resolve_ticker_id', lambda symbol: 1)
        monkeypatch.setattr(webull_quote, '_fetch_quote',
                            lambda ticker_id: {'pPrice': '10', 'pChRatio': '0.01', 'overnight': 0})
        assert webull_quote.get_extended_quotes(['NVDA'], 'pre')['NVDA']['price'] == 10.0
        assert webull_quote.get_extended_quotes(['NVDA'], 'post')['NVDA']['price'] == 10.0
