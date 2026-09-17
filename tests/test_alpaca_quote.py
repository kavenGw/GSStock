"""Alpaca 夜盘报价：snapshot 解析、涨跌幅基准、纳秒时间戳、缺 key 降级、批量与缺席"""
import pytest

from app.services import alpaca_quote


@pytest.fixture(autouse=True)
def _keys(monkeypatch):
    monkeypatch.setattr(alpaca_quote, '_credentials', lambda: ('KEY', 'SEC'))
    yield


class _Resp:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status
        self.text = str(payload)

    def json(self):
        return self._payload


def _night(last_price, ts='2026-09-17T01:08:04.634777043Z', night_prev=999.0):
    """feed=overnight 的 snapshot。注意其 prevDailyBar 是前一个『夜盘时段』的收盘，
    不是前一常规交易日收盘——直接拿它当基准会算出假涨跌幅（实测 LITE 差 7.4 个百分点）。"""
    return {'latestTrade': {'p': last_price, 's': 142, 't': ts},
            'dailyBar': {'c': last_price, 't': '2026-09-17T00:00:00Z'},
            'prevDailyBar': {'c': night_prev, 't': '2026-09-16T00:00:00Z'}}


def _regular(close, date='2026-09-16', prev_close=800.0, prev_date='2026-09-15'):
    """feed=delayed_sip 的 snapshot，dailyBar 是官方常规时段日线"""
    return {'dailyBar': {'c': close, 't': f'{date}T00:00:00Z'},
            'prevDailyBar': {'c': prev_close, 't': f'{prev_date}T00:00:00Z'}}


class TestParseSnapshot:
    def test_baseline_is_regular_session_close(self):
        # 真实数据：LITE 夜盘 926.71，9/16 常规收盘 919.40 -> +0.80%
        # 若误用 overnight feed 的 prevDailyBar(856.61) 会算成 +8.18%，触发假告警
        q = alpaca_quote.parse_snapshot(_night(926.71, night_prev=856.61),
                                        _regular(919.40))
        assert q['session'] == 'overnight'
        assert q['price'] == 926.71
        assert q['change_pct'] == 0.8   # 误用夜盘 prevDailyBar(856.61) 会算成 +8.18%
        assert q['source'] == 'alpaca'

    def test_negative_change(self):
        q = alpaca_quote.parse_snapshot(_night(24.02), _regular(24.36))
        assert q['change_pct'] == -1.4    # 24.02/24.36-1 = -0.013957

    def test_falls_back_to_prev_when_regular_bar_already_rolled(self):
        # 防线：基准 bar 的日期须早于夜盘 bar 的日期，否则取 prevDailyBar
        q = alpaca_quote.parse_snapshot(
            _night(100.0),
            _regular(150.0, date='2026-09-17', prev_close=120.0, prev_date='2026-09-16'))
        assert q['change_pct'] == round((100.0 / 120.0 - 1) * 100, 2)

    def test_nanosecond_timestamp_parsed(self):
        # Alpaca 返回纳秒精度，datetime.fromisoformat 在 3.10 上会直接抛 ValueError
        q = alpaca_quote.parse_snapshot(_night(10.0, ts='2026-09-17T01:08:04.634777043Z'),
                                        _regular(10.0))
        assert q['time'].startswith('2026-09-17T01:08:04')

    def test_missing_pieces_return_none(self):
        assert alpaca_quote.parse_snapshot({**_night(10.0), 'latestTrade': None},
                                           _regular(9.0)) is None
        assert alpaca_quote.parse_snapshot(_night(10.0), None) is None
        assert alpaca_quote.parse_snapshot(_night(10.0), {}) is None
        assert alpaca_quote.parse_snapshot({}, _regular(9.0)) is None

    def test_zero_baseline_returns_none(self):
        # 基准为 0 会 ZeroDivisionError，须当作不可用而非崩溃
        assert alpaca_quote.parse_snapshot(_night(10.0), _regular(0)) is None

    def test_unverifiable_date_returns_none(self):
        """日期无法核验时宁可不给价 —— 错误基准会安静触发假告警，缺数据只是不显示"""
        night = _night(100.0)

        # 夜盘 dailyBar 缺席 -> 无从判断常规 bar 是否已翻篇
        assert alpaca_quote.parse_snapshot({**night, 'dailyBar': None}, _regular(120.0)) is None

        # 常规 bar 有价但缺日期 -> 不得当作「更早」而采信
        no_date = {'dailyBar': {'c': 120.0}, 'prevDailyBar': {'c': 110.0}}
        assert alpaca_quote.parse_snapshot(night, no_date) is None

        # 两个 bar 日期都不早于夜盘日 -> 无可用基准
        future = {'dailyBar': {'c': 120.0, 't': '2026-09-18T00:00:00Z'},
                  'prevDailyBar': {'c': 110.0, 't': '2026-09-17T00:00:00Z'}}
        assert alpaca_quote.parse_snapshot(night, future) is None

    def test_non_string_timestamp_does_not_raise(self):
        q = alpaca_quote.parse_snapshot({**_night(10.0), 'latestTrade': {'p': 10.0, 't': 12345}},
                                        _regular(10.0))
        assert q['time'] is None and q['price'] == 10.0


class TestGetOvernightQuotes:
    def _two_feeds(self, monkeypatch, night, regular, calls=None):
        def fake_get(url, **kw):
            prm = kw.get('params', {})
            if calls is not None:
                calls.append(prm)
            return _Resp(night if prm.get('feed') == 'overnight' else regular)

        monkeypatch.setattr(alpaca_quote.requests, 'get', fake_get)

    def test_batch_two_requests_one_per_feed(self, monkeypatch):
        calls = []
        self._two_feeds(monkeypatch,
                        {'NVDA': _night(215.51), 'WOLF': _night(24.02)},
                        {'NVDA': _regular(213.90), 'WOLF': _regular(24.36)},
                        calls)
        out = alpaca_quote.get_overnight_quotes(['NVDA', 'WOLF'])
        assert set(out) == {'NVDA', 'WOLF'}
        assert out['NVDA']['change_pct'] == 0.75   # 215.51/213.90-1
        assert len(calls) == 2, '两个 feed 各一次批量请求，不得每票一次'
        assert {c['feed'] for c in calls} == {'overnight', 'delayed_sip'}
        assert all(c['symbols'] == 'NVDA,WOLF' for c in calls)

    def test_symbol_missing_in_either_feed_absent(self, monkeypatch):
        self._two_feeds(monkeypatch,
                        {'NVDA': _night(10.0), 'AMD': _night(20.0)},
                        {'NVDA': _regular(9.0)})   # AMD 缺基准
        assert set(alpaca_quote.get_overnight_quotes(['NVDA', 'AMD'])) == {'NVDA'}

    def test_regular_feed_failure_yields_no_quotes(self, monkeypatch):
        # 夜盘 feed 成功但基准 feed 挂了：不得只凭半边数据出价
        def fake_get(url, **kw):
            if kw.get('params', {}).get('feed') == 'overnight':
                return _Resp({'NVDA': _night(215.51)})
            return _Resp({'message': 'forbidden'}, status=403)

        monkeypatch.setattr(alpaca_quote.requests, 'get', fake_get)
        assert alpaca_quote.get_overnight_quotes(['NVDA']) == {}

    def test_bad_symbol_does_not_kill_batch(self, monkeypatch):
        # 单只票脏数据（价格是非数值）不得拖垮整批，否则上层会误判为「预取失败」进退避
        self._two_feeds(monkeypatch,
                        {'NVDA': _night(215.51),
                         'AMD': {**_night(1.0), 'latestTrade': {'p': 'N/A', 't': 'x'}}},
                        {'NVDA': _regular(213.90), 'AMD': _regular(500.0)})
        out = alpaca_quote.get_overnight_quotes(['NVDA', 'AMD'])
        assert set(out) == {'NVDA'}

    def test_no_credentials_returns_empty(self, monkeypatch):
        monkeypatch.setattr(alpaca_quote, '_credentials', lambda: (None, None))
        monkeypatch.setattr(alpaca_quote.requests, 'get',
                            lambda url, **kw: pytest.fail('无 key 时不应发请求'))
        assert alpaca_quote.get_overnight_quotes(['NVDA']) == {}

    def test_http_error_returns_empty(self, monkeypatch):
        monkeypatch.setattr(alpaca_quote.requests, 'get',
                            lambda url, **kw: _Resp({'message': 'forbidden'}, status=403))
        assert alpaca_quote.get_overnight_quotes(['NVDA']) == {}

    def test_network_failure_returns_empty(self, monkeypatch):
        def boom(url, **kw):
            raise RuntimeError('network down')

        monkeypatch.setattr(alpaca_quote.requests, 'get', boom)
        assert alpaca_quote.get_overnight_quotes(['NVDA']) == {}

    def test_empty_symbols(self, monkeypatch):
        monkeypatch.setattr(alpaca_quote.requests, 'get',
                            lambda url, **kw: pytest.fail('空入参不应发请求'))
        assert alpaca_quote.get_overnight_quotes([]) == {}
