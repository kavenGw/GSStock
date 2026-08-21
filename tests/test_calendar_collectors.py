from datetime import date

import pandas as pd
import pytest


WATCH_STUB = [
    {'code': '002156', 'name': '通富微电', 'market': 'A'},
    {'code': '603986', 'name': '兆易创新', 'market': 'A'},
    {'code': '0700.HK', 'name': '腾讯控股', 'market': 'HK',
     'ah': {'code': '000001', 'market': 'A', 'name': '不应被采集'}},
    {'code': '000660.KS', 'name': 'SK海力士', 'market': 'KR'},
]


@pytest.fixture
def patched_watch(monkeypatch):
    from app.services import calendar_event as mod
    monkeypatch.setattr(mod, 'WATCH_CODES', WATCH_STUB)
    return mod


def test_collect_earnings_a_maps_disclosure_to_events(patched_watch, monkeypatch):
    mod = patched_watch
    monkeypatch.setattr(mod, 'period_keys_for_window',
                        lambda today=None: [('2026半年报', '2026H1')])
    monkeypatch.setattr(
        mod.EarningsService, 'fetch_disclosure_map',
        staticmethod(lambda period: {
            '002156': {'date': date(2026, 8, 29), 'status': 'changed',
                       'detail': '预约 2026-08-26 → 2026-08-29'},
            '603986': {'date': date(2026, 8, 19), 'status': 'confirmed', 'detail': None},
            '999999': {'date': date(2026, 8, 20), 'status': 'scheduled', 'detail': None},
        }))

    out = mod.collect_earnings_a(date(2026, 8, 21))

    codes = {e['stock_code'] for e in out}
    assert codes == {'002156', '603986'}, '非盯盘股不得进入日历'
    by_code = {e['stock_code']: e for e in out}
    assert by_code['002156']['event_date'] == date(2026, 8, 29)
    assert by_code['002156']['period_key'] == '2026H1'
    assert by_code['002156']['source'] == 'cninfo'
    assert by_code['002156']['event_type'] == 'earnings'
    assert by_code['002156']['priority'] == 'HIGH'
    assert by_code['002156']['title'] == '中报披露'


def test_collect_earnings_a_scheduled_is_medium_priority(patched_watch, monkeypatch):
    mod = patched_watch
    monkeypatch.setattr(mod, 'period_keys_for_window',
                        lambda today=None: [('2026半年报', '2026H1')])
    monkeypatch.setattr(
        mod.EarningsService, 'fetch_disclosure_map',
        staticmethod(lambda period: {
            '002156': {'date': date(2026, 8, 29), 'status': 'scheduled', 'detail': None},
        }))

    out = mod.collect_earnings_a(date(2026, 8, 21))
    assert out[0]['priority'] == 'MEDIUM'


def test_collect_earnings_a_skips_ah_subcodes(patched_watch, monkeypatch):
    """WATCH_CODES 条目内的 ah 子代码不展开，否则 A+H 同公司会重复两条。"""
    mod = patched_watch
    monkeypatch.setattr(mod, 'period_keys_for_window',
                        lambda today=None: [('2026半年报', '2026H1')])
    monkeypatch.setattr(
        mod.EarningsService, 'fetch_disclosure_map',
        staticmethod(lambda period: {
            '000001': {'date': date(2026, 8, 25), 'status': 'scheduled', 'detail': None},
        }))

    assert mod.collect_earnings_a(date(2026, 8, 21)) == []


class _FakeTicker:
    def __init__(self, cal):
        self._cal = cal

    @property
    def calendar(self):
        return self._cal


def test_collect_calendar_yf_yields_earnings_and_ex_dividend(patched_watch, monkeypatch):
    mod = patched_watch
    cals = {
        '0700.HK': {'Earnings Date': [date(2026, 11, 12)],
                    'Ex-Dividend Date': date(2026, 9, 10)},
        '000660.KS': {'Earnings Date': [date(2026, 10, 24)]},
    }
    monkeypatch.setattr(mod, '_yf_ticker', lambda code: _FakeTicker(cals[code]))
    monkeypatch.setattr(mod.circuit_breaker, 'is_available', lambda name: True)

    out = mod.collect_calendar_yf(date(2026, 8, 21))

    types = sorted((e['stock_code'], e['event_type']) for e in out)
    assert types == [('000660.KS', 'earnings'),
                     ('0700.HK', 'earnings'),
                     ('0700.HK', 'ex_dividend')]
    xd = [e for e in out if e['event_type'] == 'ex_dividend'][0]
    assert xd['priority'] == 'LOW'
    assert xd['period_key'] == 'XD202609'
    er = [e for e in out if e['stock_code'] == '0700.HK'
          and e['event_type'] == 'earnings'][0]
    assert er['period_key'] == '2026Q4'
    assert er['source'] == 'yfinance'


def test_collect_calendar_yf_drops_past_ex_dividend(patched_watch, monkeypatch):
    """yfinance 的 Ex-Dividend Date 是「最近一次」，常常已是过去日期。"""
    mod = patched_watch
    cals = {
        '0700.HK': {'Ex-Dividend Date': date(2026, 5, 15)},
        '000660.KS': {},
    }
    monkeypatch.setattr(mod, '_yf_ticker', lambda code: _FakeTicker(cals[code]))
    monkeypatch.setattr(mod.circuit_breaker, 'is_available', lambda name: True)

    assert mod.collect_calendar_yf(date(2026, 8, 21)) == []


def test_collect_calendar_yf_returns_empty_when_circuit_open(patched_watch, monkeypatch):
    mod = patched_watch

    def _boom(code):
        raise AssertionError('熔断时不应发起请求')

    monkeypatch.setattr(mod, '_yf_ticker', _boom)
    monkeypatch.setattr(mod.circuit_breaker, 'is_available', lambda name: False)

    assert mod.collect_calendar_yf(date(2026, 8, 21)) == []


def test_collect_calendar_yf_one_bad_ticker_does_not_kill_rest(patched_watch, monkeypatch):
    mod = patched_watch

    def _tk(code):
        if code == '0700.HK':
            raise RuntimeError('delisted')
        return _FakeTicker({'Earnings Date': [date(2026, 10, 24)]})

    monkeypatch.setattr(mod, '_yf_ticker', _tk)
    monkeypatch.setattr(mod.circuit_breaker, 'is_available', lambda name: True)
    monkeypatch.setattr(mod.time, 'sleep', lambda s: None)

    out = mod.collect_calendar_yf(date(2026, 8, 21))
    assert [e['stock_code'] for e in out] == ['000660.KS']


def test_collect_dividend_a_maps_ex_date(patched_watch, monkeypatch):
    mod = patched_watch
    df = pd.DataFrame([
        {'代码': '002156', '名称': '通富微电', '除权除息日': pd.Timestamp('2026-09-05'),
         '现金分红-现金分红比例': 1.5, '方案进度': '实施方案'},
        {'代码': '603986', '名称': '兆易创新', '除权除息日': pd.NaT,
         '现金分红-现金分红比例': 2.0, '方案进度': '预披露'},
        {'代码': '999999', '名称': '别人家', '除权除息日': pd.Timestamp('2026-09-06'),
         '现金分红-现金分红比例': 1.0, '方案进度': '实施方案'},
    ])
    monkeypatch.setattr(mod, '_fhps_report_dates', lambda today: ['20251231'])
    monkeypatch.setattr(mod.ak, 'stock_fhps_em', lambda date: df)

    out = mod.collect_dividend_a(date(2026, 8, 21))

    assert len(out) == 1
    e = out[0]
    assert e['stock_code'] == '002156'
    assert e['event_date'] == date(2026, 9, 5)
    assert e['event_type'] == 'ex_dividend'
    assert e['source'] == 'akshare'
    assert e['period_key'] == 'FH20251231'
    assert '实施方案' in e['detail']


def test_collect_dividend_a_tolerates_one_bad_period(patched_watch, monkeypatch):
    """单个报告期取数失败不应传染其它已成功报告期——只有全军覆没才是真故障。"""
    mod = patched_watch
    ok_df = pd.DataFrame([
        {'代码': '002156', '名称': '通富微电', '除权除息日': pd.Timestamp('2026-09-05'),
         '现金分红-现金分红比例': 1.5, '方案进度': '实施方案'},
    ])

    def _fhps(date):
        if date == '20251231':
            raise RuntimeError('akshare down')
        return ok_df

    monkeypatch.setattr(mod, '_fhps_report_dates', lambda today: ['20251231', '20260930'])
    monkeypatch.setattr(mod.ak, 'stock_fhps_em', _fhps)

    out = mod.collect_dividend_a(date(2026, 8, 21))
    assert [e['stock_code'] for e in out] == ['002156']


def test_collect_dividend_a_raises_when_all_periods_fail(patched_watch, monkeypatch):
    """全部报告期都取数失败时必须向上抛出，不能返回 []。

    refresh_all 把「collector 正常返回」等同于「本轮已重新采集」，据此用
    prune_stale 删除本轮未命中的既有 akshare 行；若这里吞掉全灭异常返回 []，
    一次 akshare 全站故障就会被误判为"确认无分红"，把历史除权除息事件整体清空。
    """
    mod = patched_watch

    def _boom(date):
        raise RuntimeError('akshare down')

    monkeypatch.setattr(mod, '_fhps_report_dates', lambda today: ['20251231', '20260930'])
    monkeypatch.setattr(mod.ak, 'stock_fhps_em', _boom)

    with pytest.raises(RuntimeError):
        mod.collect_dividend_a(date(2026, 8, 21))
