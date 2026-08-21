from datetime import date

import pandas as pd
import pytest


def _df(rows):
    return pd.DataFrame(rows, columns=[
        '股票代码', '股票简称', '首次预约', '初次变更', '二次变更', '三次变更', '实际披露'])


def test_period_keys_for_window_august_covers_h1():
    from app.services.earnings import period_keys_for_window
    out = period_keys_for_window(date(2026, 8, 21))
    assert ('2026半年报', '2026H1') in out


def test_period_keys_for_window_september_covers_h1_and_q3():
    from app.services.earnings import period_keys_for_window
    out = period_keys_for_window(date(2026, 9, 10))
    keys = [k for _, k in out]
    assert '2026H1' in keys and '2026Q3' in keys


def test_period_keys_for_window_deduplicates():
    from app.services.earnings import period_keys_for_window
    out = period_keys_for_window(date(2026, 7, 1))
    assert len(out) == len(set(out))


def test_fetch_disclosure_map_picks_actual_over_scheduled(monkeypatch):
    from app.services import earnings as mod

    monkeypatch.setattr(mod, '_disclosure_cache', {})
    monkeypatch.setattr(mod.ak, 'stock_report_disclosure', lambda market, period: _df([
        ['603986', '兆易创新', pd.Timestamp('2026-08-19'), pd.NaT, pd.NaT, pd.NaT,
         pd.Timestamp('2026-08-19')],
    ]))

    out = mod.EarningsService.fetch_disclosure_map('2026半年报')

    assert out['603986']['date'] == date(2026, 8, 19)
    assert out['603986']['status'] == 'confirmed'


def test_fetch_disclosure_map_marks_changed_and_records_original(monkeypatch):
    from app.services import earnings as mod

    monkeypatch.setattr(mod, '_disclosure_cache', {})
    monkeypatch.setattr(mod.ak, 'stock_report_disclosure', lambda market, period: _df([
        ['002156', '通富微电', pd.Timestamp('2026-08-26'), pd.Timestamp('2026-08-29'),
         pd.NaT, pd.NaT, pd.NaT],
    ]))

    out = mod.EarningsService.fetch_disclosure_map('2026半年报')

    assert out['002156']['date'] == date(2026, 8, 29)
    assert out['002156']['status'] == 'changed'
    assert '2026-08-26' in out['002156']['detail']
    assert '2026-08-29' in out['002156']['detail']


def test_fetch_disclosure_map_swallows_unpublished_period(monkeypatch):
    """未发布期次时 akshare 内部抛 ValueError，必须吞掉返回空 dict。"""
    from app.services import earnings as mod

    def _boom(market, period):
        raise ValueError('Length mismatch: Expected axis has 0 elements, '
                         'new values have 10 elements')

    monkeypatch.setattr(mod, '_disclosure_cache', {})
    monkeypatch.setattr(mod.ak, 'stock_report_disclosure', _boom)

    assert mod.EarningsService.fetch_disclosure_map('2026三季') == {}


def test_fetch_disclosure_map_caches_per_period(monkeypatch):
    from app.services import earnings as mod

    calls = []

    def _spy(market, period):
        calls.append(period)
        return _df([['603986', '兆易创新', pd.Timestamp('2026-08-19'),
                     pd.NaT, pd.NaT, pd.NaT, pd.NaT]])

    monkeypatch.setattr(mod, '_disclosure_cache', {})
    monkeypatch.setattr(mod.ak, 'stock_report_disclosure', _spy)

    mod.EarningsService.fetch_disclosure_map('2026半年报')
    mod.EarningsService.fetch_disclosure_map('2026半年报')

    assert calls == ['2026半年报'], '同一期次同一天只应取一次'


def test_fetch_disclosure_map_propagates_network_failure(monkeypatch):
    """网络故障等非"未发布"异常必须原样抛出，不能被吞成 {}，
    否则下游会把失败误判为"当期无数据"进而清空日历事件。"""
    from app.services import earnings as mod

    def _boom(market, period):
        raise ConnectionError('boom')

    monkeypatch.setattr(mod, '_disclosure_cache', {})
    monkeypatch.setattr(mod.ak, 'stock_report_disclosure', _boom)

    with pytest.raises(ConnectionError):
        mod.EarningsService.fetch_disclosure_map('2026半年报')

    assert mod._disclosure_cache == {}, '失败不应写入缓存，需允许当天重试'


def test_fetch_disclosure_map_propagates_other_valueerror(monkeypatch):
    """非"Length mismatch"的 ValueError（如格式错误的响应体）也必须抛出，
    不能被误判为期次未发布。"""
    from app.services import earnings as mod

    def _boom(market, period):
        raise ValueError('unexpected token')

    monkeypatch.setattr(mod, '_disclosure_cache', {})
    monkeypatch.setattr(mod.ak, 'stock_report_disclosure', _boom)

    with pytest.raises(ValueError):
        mod.EarningsService.fetch_disclosure_map('2026半年报')

    assert mod._disclosure_cache == {}


def test_fetch_earnings_akshare_now_returns_real_dates(monkeypatch):
    """回归：该函数曾是空壳，A股财报预警长期失效。"""
    from app.services import earnings as mod

    monkeypatch.setattr(
        mod.EarningsService, 'fetch_disclosure_map',
        staticmethod(lambda period: {
            '000725': {'date': date(2026, 8, 29), 'status': 'scheduled', 'detail': None}
        }))
    monkeypatch.setattr(mod, '_today', lambda: date(2026, 8, 21))

    out = mod.EarningsService._fetch_earnings_akshare('000725')

    assert out['next_earnings_date'] == '2026-08-29'
    assert out['market'] == 'A'


def test_fetch_earnings_akshare_past_date_goes_to_last(monkeypatch):
    from app.services import earnings as mod

    monkeypatch.setattr(
        mod.EarningsService, 'fetch_disclosure_map',
        staticmethod(lambda period: {
            '603986': {'date': date(2026, 8, 19), 'status': 'confirmed', 'detail': None}
        }))
    monkeypatch.setattr(mod, '_today', lambda: date(2026, 8, 21))

    out = mod.EarningsService._fetch_earnings_akshare('603986')

    assert out['last_earnings_date'] == '2026-08-19'
    assert out['next_earnings_date'] is None
