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

    out, complete = mod.collect_earnings_a(date(2026, 8, 21))

    assert complete is True
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

    out, _ = mod.collect_earnings_a(date(2026, 8, 21))
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

    assert mod.collect_earnings_a(date(2026, 8, 21)) == ([], True)


def test_collect_earnings_a_no_period_is_incomplete(patched_watch, monkeypatch):
    """无报告期可取 ≠ 确认无财报——每年 11 月都是这种状态。

    这里若报 complete=True，refresh_all 会拿它当"本轮已重新采集"的凭据，
    把窗口内全部 cninfo 事件 prune 掉。
    """
    mod = patched_watch
    monkeypatch.setattr(mod, 'period_keys_for_window', lambda today=None: [])

    def _boom(period):
        raise AssertionError('无报告期时不应联网')

    monkeypatch.setattr(mod.EarningsService, 'fetch_disclosure_map', staticmethod(_boom))

    assert mod.collect_earnings_a(date(2026, 11, 10)) == ([], False)


def test_collect_earnings_a_period_failure_is_incomplete(patched_watch, monkeypatch):
    """一个报告期取数失败：已成功那期的事件照常返回，但不得为整个 source 背书。"""
    mod = patched_watch
    monkeypatch.setattr(mod, 'period_keys_for_window',
                        lambda today=None: [('2026半年报', '2026H1'),
                                            ('2026三季报', '2026Q3')])

    def _fetch(period):
        if period == '2026三季报':
            raise RuntimeError('cninfo timeout')
        return {'002156': {'date': date(2026, 8, 29), 'status': 'scheduled',
                           'detail': None}}

    monkeypatch.setattr(mod.EarningsService, 'fetch_disclosure_map',
                        staticmethod(_fetch))

    out, complete = mod.collect_earnings_a(date(2026, 8, 21))

    assert complete is False
    assert [e['stock_code'] for e in out] == ['002156']


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

    out, complete = mod.collect_calendar_yf(date(2026, 8, 21))

    assert complete is True
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

    assert mod.collect_calendar_yf(date(2026, 8, 21)) == ([], True)


def test_collect_calendar_yf_circuit_open_is_incomplete(patched_watch, monkeypatch):
    """熔断跳过是「一次都没试」，必须报 complete=False。

    早期版本只返回 []，refresh_all 无从分辨"确认无事件"与"根本没采"，
    一次 yfinance 限流就会把窗口内全部港/美/韩财报与除权事件清空。
    """
    mod = patched_watch

    def _boom(code):
        raise AssertionError('熔断时不应发起请求')

    monkeypatch.setattr(mod, '_yf_ticker', _boom)
    monkeypatch.setattr(mod.circuit_breaker, 'is_available', lambda name: False)

    assert mod.collect_calendar_yf(date(2026, 8, 21)) == ([], False)


def test_collect_calendar_yf_all_tickers_failing_is_incomplete(patched_watch, monkeypatch):
    """全部 ticker 重试耗尽 —— 空结果同样不得被当作"确认无事件"。"""
    mod = patched_watch

    def _tk(code):
        raise RuntimeError('rate limited')

    monkeypatch.setattr(mod, '_yf_ticker', _tk)
    monkeypatch.setattr(mod.circuit_breaker, 'is_available', lambda name: True)
    monkeypatch.setattr(mod.time, 'sleep', lambda s: None)

    assert mod.collect_calendar_yf(date(2026, 8, 21)) == ([], False)


def test_collect_calendar_yf_one_bad_ticker_does_not_kill_rest(patched_watch, monkeypatch):
    mod = patched_watch

    def _tk(code):
        if code == '0700.HK':
            # 必须是真实故障文案：'delisted'/'no data found' 现在被判为
            # 「该代码无数据」而非数据源故障，会走豁免路径、不置 complete=False。
            raise RuntimeError('429 Too Many Requests')
        return _FakeTicker({'Earnings Date': [date(2026, 10, 24)]})

    monkeypatch.setattr(mod, '_yf_ticker', _tk)
    monkeypatch.setattr(mod.circuit_breaker, 'is_available', lambda name: True)
    monkeypatch.setattr(mod.time, 'sleep', lambda s: None)

    out, complete = mod.collect_calendar_yf(date(2026, 8, 21))
    assert [e['stock_code'] for e in out] == ['000660.KS']
    assert complete is False, '部分失败也不足以为整个 source 背书'


def test_collect_calendar_yf_records_failure_per_exhausted_ticker(patched_watch, monkeypatch):
    """重试耗尽必须上报熔断器，否则一直失败也永远不熔断，同一场限流天天重演。"""
    mod = patched_watch
    calls = []

    def _tk(code):
        raise RuntimeError('rate limited')

    monkeypatch.setattr(mod, '_yf_ticker', _tk)
    monkeypatch.setattr(mod.circuit_breaker, 'is_available', lambda name: True)
    monkeypatch.setattr(mod.circuit_breaker, 'record_failure',
                        lambda name: calls.append(name))
    monkeypatch.setattr(mod.circuit_breaker, 'record_success',
                        lambda name: pytest.fail('全失败时不得报 success'))
    monkeypatch.setattr(mod.time, 'sleep', lambda s: None)

    mod.collect_calendar_yf(date(2026, 8, 21))

    assert calls == ['yfinance', 'yfinance'], 'WATCH_STUB 有两只非A股'


def test_collect_calendar_yf_partial_failure_does_not_record_success(patched_watch,
                                                                    monkeypatch):
    """部分成功时报 success 会把刚累计的 failure_count 清零，熔断器永远跳不起来。"""
    mod = patched_watch

    def _tk(code):
        if code == '0700.HK':
            raise RuntimeError('rate limited')
        return _FakeTicker({'Earnings Date': [date(2026, 10, 24)]})

    monkeypatch.setattr(mod, '_yf_ticker', _tk)
    monkeypatch.setattr(mod.circuit_breaker, 'is_available', lambda name: True)
    monkeypatch.setattr(mod.circuit_breaker, 'record_failure', lambda name: None)
    monkeypatch.setattr(mod.circuit_breaker, 'record_success',
                        lambda name: pytest.fail('部分失败时不得报 success'))
    monkeypatch.setattr(mod.time, 'sleep', lambda s: None)

    mod.collect_calendar_yf(date(2026, 8, 21))


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

    out, complete = mod.collect_dividend_a(date(2026, 8, 21))

    assert complete is True
    assert len(out) == 1
    e = out[0]
    assert e['stock_code'] == '002156'
    assert e['event_date'] == date(2026, 9, 5)
    assert e['event_type'] == 'ex_dividend'
    assert e['source'] == 'akshare'
    assert e['period_key'] == 'FH20251231'
    assert '实施方案' in e['detail']


def test_collect_dividend_a_partial_failure_is_incomplete(patched_watch, monkeypatch):
    """单个报告期失败不传染其它期的结果，但整轮必须报 complete=False——
    否则失败那期的既有除权除息行会被 prune_stale 当成「已撤销」删掉。"""
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

    out, complete = mod.collect_dividend_a(date(2026, 8, 21))

    assert [e['stock_code'] for e in out] == ['002156']
    assert complete is False


def test_collect_dividend_a_raises_when_all_periods_fail(patched_watch, monkeypatch):
    """全部报告期都取数失败时必须向上抛出，不能返回 []。

    refresh_all 只在 collector 自报 complete=True 时才 prune；抛异常与 complete=False
    效果一致，但抛出能进 stats['errors']，运维看得见"是 akshare 全站故障"。
    """
    mod = patched_watch

    def _boom(date):
        raise RuntimeError('akshare down')

    monkeypatch.setattr(mod, '_fhps_report_dates', lambda today: ['20251231', '20260930'])
    monkeypatch.setattr(mod.ak, 'stock_fhps_em', _boom)

    with pytest.raises(RuntimeError):
        mod.collect_dividend_a(date(2026, 8, 21))


def test_collect_macro_range_is_always_complete():
    """纯本地表，无 I/O，永远有资格为自己那两个 source 背书。"""
    from app.services import calendar_event as mod
    _, complete = mod.collect_macro_range(date(2026, 8, 1), date(2026, 10, 31))
    assert complete is True


def test_collect_calendar_yf_delisted_is_not_a_platform_failure(patched_watch, monkeypatch):
    """退市/代码有误是「该代码没有数据」，不是「数据源故障」。

    与 earnings.py 同一约定：不计平台失败。更关键的是也不能置 complete=False ——
    否则一只常年坏的代码会永久压制 yfinance 的 prune，日历再也删不掉已撤销的事件。
    """
    mod = patched_watch
    recorded = []

    def _tk(code):
        raise RuntimeError('%s: possibly delisted; no price data found' % code)

    monkeypatch.setattr(mod, '_yf_ticker', _tk)
    monkeypatch.setattr(mod.circuit_breaker, 'is_available', lambda name: True)
    monkeypatch.setattr(mod.circuit_breaker, 'record_failure',
                        lambda name: recorded.append(name))
    monkeypatch.setattr(mod.time, 'sleep', lambda s: None)

    events, complete = mod.collect_calendar_yf(date(2026, 8, 21))

    assert events == []
    assert recorded == [], '退市/无数据不得计入平台失败'
    assert complete is True, '坏代码不得永久冻结 prune'


def test_collect_calendar_yf_real_failure_still_counts(patched_watch, monkeypatch):
    """反向闸门：真实故障（限流等）仍必须计平台失败并置 complete=False。"""
    mod = patched_watch
    recorded = []

    def _tk(code):
        raise RuntimeError('429 Too Many Requests')

    monkeypatch.setattr(mod, '_yf_ticker', _tk)
    monkeypatch.setattr(mod.circuit_breaker, 'is_available', lambda name: True)
    monkeypatch.setattr(mod.circuit_breaker, 'record_failure',
                        lambda name: recorded.append(name))
    monkeypatch.setattr(mod.time, 'sleep', lambda s: None)

    events, complete = mod.collect_calendar_yf(date(2026, 8, 21))

    assert events == []
    assert recorded == ['yfinance', 'yfinance'], '每只重试耗尽的票各记一次'
    assert complete is False
