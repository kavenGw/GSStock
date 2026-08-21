from datetime import date

import pandas as pd
import pytest
from flask import Flask


WATCH_STUB = [
    {'code': '002156', 'name': '通富微电', 'market': 'A'},
    {'code': '0700.HK', 'name': '腾讯控股', 'market': 'HK'},
    {'code': '000660.KS', 'name': 'SK海力士', 'market': 'KR'},
]


@pytest.fixture
def app_ctx(tmp_path):
    from app import db
    import app.models.stock_event  # noqa: F401
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{tmp_path}/t.db'
    app.config['SQLALCHEMY_BINDS'] = {'private': f'sqlite:///{tmp_path}/tp.db'}
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()


def _ev(code, d, source, period_key, etype='earnings'):
    return {
        'event_date': d, 'event_type': etype, 'stock_code': code,
        'stock_name': code, 'market': 'A', 'title': 't', 'detail': None,
        'priority': 'MEDIUM', 'source': source, 'status': 'scheduled',
        'period_key': period_key, 'extra': None,
    }


def _silent_collectors(monkeypatch, mod, **overrides):
    """把四个 collector 都置成「成功但无事件」，再按需覆盖其中一个"""
    defaults = {
        'collect_earnings_a': lambda today: ([], True),
        'collect_calendar_yf': lambda today: ([], True),
        'collect_dividend_a': lambda today: ([], True),
        'collect_macro_range': lambda s, e: ([], True),
    }
    defaults.update(overrides)
    for name, fn in defaults.items():
        monkeypatch.setattr(mod, name, fn)


def test_window_spans_prev_month_to_two_months_ahead():
    from app.services.calendar_event import CalendarEventService
    start, end = CalendarEventService.window(date(2026, 8, 21))
    assert start == date(2026, 7, 1)
    assert end == date(2026, 10, 31)


def test_window_handles_year_boundary():
    from app.services.calendar_event import CalendarEventService
    start, end = CalendarEventService.window(date(2026, 12, 15))
    assert start == date(2026, 11, 1)
    assert end == date(2027, 2, 28)


def test_refresh_all_drops_events_outside_window(app_ctx, monkeypatch):
    from app.models.stock_event import StockEvent
    from app.services import calendar_event as mod

    _silent_collectors(monkeypatch, mod, collect_earnings_a=lambda today: ([
        _ev('002156', date(2026, 8, 29), 'cninfo', '2026H1'),
        _ev('300223', date(2027, 3, 1), 'cninfo', '2027A'),
    ], True))

    stats = mod.CalendarEventService.refresh_all(date(2026, 8, 21))

    assert stats['upserted'] == 1
    assert [r.stock_code for r in StockEvent.query.all()] == ['002156']


def test_refresh_all_one_collector_failure_does_not_block_others(app_ctx, monkeypatch):
    from app.models.stock_event import StockEvent
    from app.services import calendar_event as mod

    def _boom(today):
        raise RuntimeError('cninfo down')

    _silent_collectors(monkeypatch, mod, collect_earnings_a=_boom,
                       collect_calendar_yf=lambda today: ([
                           _ev('0700.HK', date(2026, 9, 3), 'yfinance', '2026Q3')], True))

    stats = mod.CalendarEventService.refresh_all(date(2026, 8, 21))

    assert stats['errors'] and 'cninfo down' in stats['errors'][0]
    assert [r.stock_code for r in StockEvent.query.all()] == ['0700.HK']


def test_refresh_all_failed_collector_does_not_prune_its_own_rows(app_ctx, monkeypatch):
    """cninfo 挂掉时，昨天采到的 cninfo 事件必须原样保留。"""
    from app.models.stock_event import StockEvent
    from app.services import calendar_event as mod

    mod.CalendarEventService.upsert_events([
        _ev('002156', date(2026, 8, 29), 'cninfo', '2026H1')])

    def _boom(today):
        raise RuntimeError('cninfo down')

    _silent_collectors(monkeypatch, mod, collect_earnings_a=_boom)

    mod.CalendarEventService.refresh_all(date(2026, 8, 21))

    assert StockEvent.query.count() == 1


def test_refresh_all_prunes_withdrawn_event(app_ctx, monkeypatch):
    from app.models.stock_event import StockEvent
    from app.services import calendar_event as mod

    mod.CalendarEventService.upsert_events([
        _ev('002156', date(2026, 8, 29), 'cninfo', '2026H1'),
        _ev('300223', date(2026, 8, 28), 'cninfo', '2026H1'),
    ])

    _silent_collectors(monkeypatch, mod, collect_earnings_a=lambda today: ([
        _ev('002156', date(2026, 8, 29), 'cninfo', '2026H1')], True))

    stats = mod.CalendarEventService.refresh_all(date(2026, 8, 21))

    assert stats['removed'] == 1
    assert stats['incomplete'] == []
    assert [r.stock_code for r in StockEvent.query.all()] == ['002156']


def test_refresh_all_incomplete_collector_does_not_prune(app_ctx, monkeypatch):
    """collector 正常返回但自报未采全时，prune 授权同样不发放。"""
    from app.models.stock_event import StockEvent
    from app.services import calendar_event as mod

    mod.CalendarEventService.upsert_events([
        _ev('002156', date(2026, 8, 29), 'cninfo', '2026H1')])

    _silent_collectors(monkeypatch, mod,
                       collect_earnings_a=lambda today: ([], False))

    stats = mod.CalendarEventService.refresh_all(date(2026, 8, 21))

    assert stats['removed'] == 0
    assert stats['incomplete'] == ['earnings_a']
    assert StockEvent.query.count() == 1


class _FakeTicker:
    def __init__(self, cal):
        self._cal = cal

    @property
    def calendar(self):
        return self._cal


def _seed_yf(mod):
    mod.CalendarEventService.upsert_events([
        _ev('0700.HK', date(2026, 9, 3), 'yfinance', '2026Q3'),
        _ev('000660.KS', date(2026, 10, 24), 'yfinance', '2026Q4'),
        _ev('0700.HK', date(2026, 9, 10), 'yfinance', 'XD202609',
            etype='ex_dividend'),
    ])


def test_refresh_all_yfinance_circuit_open_does_not_wipe_rows(app_ctx, monkeypatch):
    """熔断当天不得清空 yfinance 事件。

    这是本模块最贵的一个洞：yfinance 一次限流触发熔断 → collect_calendar_yf 正常
    返回 [] → refresh_all 误认为"确认无事件" → 窗口内全部港/美/韩财报与除权被删，
    且 errors 为空、无任何告警。当天 07:30 之后的推送里，盯盘池财报覆盖归零
    （财报段已把盯盘池整体排除，指望日历段覆盖）。
    """
    from app.models.stock_event import StockEvent
    from app.services import calendar_event as mod

    _seed_yf(mod)
    monkeypatch.setattr(mod, 'WATCH_CODES', WATCH_STUB)
    monkeypatch.setattr(mod.circuit_breaker, 'is_available', lambda name: False)
    _silent_collectors(monkeypatch, mod, collect_calendar_yf=mod.collect_calendar_yf)

    stats = mod.CalendarEventService.refresh_all(date(2026, 8, 21))

    assert stats['removed'] == 0
    assert stats['incomplete'] == ['calendar_yf']
    assert StockEvent.query.filter_by(source='yfinance').count() == 3


def test_refresh_all_all_yf_tickers_failing_does_not_wipe_rows(app_ctx, monkeypatch):
    """每只 ticker 都重试耗尽（限流的典型表现）时同样不得清空。"""
    from app.models.stock_event import StockEvent
    from app.services import calendar_event as mod

    _seed_yf(mod)
    monkeypatch.setattr(mod, 'WATCH_CODES', WATCH_STUB)
    monkeypatch.setattr(mod.circuit_breaker, 'is_available', lambda name: True)
    monkeypatch.setattr(mod.circuit_breaker, 'record_failure', lambda name: None)
    monkeypatch.setattr(mod.time, 'sleep', lambda s: None)

    def _tk(code):
        raise RuntimeError('YFRateLimitError')

    monkeypatch.setattr(mod, '_yf_ticker', _tk)
    _silent_collectors(monkeypatch, mod, collect_calendar_yf=mod.collect_calendar_yf)

    stats = mod.CalendarEventService.refresh_all(date(2026, 8, 21))

    assert stats['removed'] == 0
    assert stats['incomplete'] == ['calendar_yf']
    assert StockEvent.query.filter_by(source='yfinance').count() == 3


def test_refresh_all_successful_yf_run_still_prunes(app_ctx, monkeypatch):
    """反向闸门：全员成功时撤销的事件仍要被清掉，不能因为怕误删而永不 prune。"""
    from app.models.stock_event import StockEvent
    from app.services import calendar_event as mod

    _seed_yf(mod)
    monkeypatch.setattr(mod, 'WATCH_CODES', WATCH_STUB)
    monkeypatch.setattr(mod.circuit_breaker, 'is_available', lambda name: True)
    monkeypatch.setattr(mod.circuit_breaker, 'record_success', lambda name: None)
    cals = {
        '0700.HK': {'Earnings Date': [date(2026, 9, 3)]},
        '000660.KS': {'Earnings Date': [date(2026, 10, 24)]},
    }
    monkeypatch.setattr(mod, '_yf_ticker', lambda code: _FakeTicker(cals[code]))
    _silent_collectors(monkeypatch, mod, collect_calendar_yf=mod.collect_calendar_yf)

    stats = mod.CalendarEventService.refresh_all(date(2026, 8, 21))

    assert stats['incomplete'] == []
    assert stats['removed'] == 1, '撤销的除权除息行应被清理'
    kinds = {r.event_type for r in StockEvent.query.filter_by(source='yfinance').all()}
    assert kinds == {'earnings'}


def test_refresh_all_empty_period_list_does_not_wipe_cninfo_rows(app_ctx, monkeypatch):
    """11 月每天都没有报告期可采——不能因此把 cninfo 事件整体清空。"""
    from app.models.stock_event import StockEvent
    from app.services import calendar_event as mod

    mod.CalendarEventService.upsert_events([
        _ev('002156', date(2026, 11, 20), 'cninfo', '2026Q3')])

    monkeypatch.setattr(mod, 'WATCH_CODES', WATCH_STUB)
    monkeypatch.setattr(mod, 'period_keys_for_window', lambda today=None: [])
    _silent_collectors(monkeypatch, mod, collect_earnings_a=mod.collect_earnings_a)

    stats = mod.CalendarEventService.refresh_all(date(2026, 11, 10))

    assert stats['removed'] == 0
    assert stats['incomplete'] == ['earnings_a']
    assert StockEvent.query.filter_by(source='cninfo').count() == 1


def test_refresh_all_partial_dividend_failure_does_not_wipe_akshare_rows(app_ctx,
                                                                        monkeypatch):
    """一个报告期失败时，那期对应的既有除权除息行不得被当成「已撤销」删掉。"""
    from app.models.stock_event import StockEvent
    from app.services import calendar_event as mod

    mod.CalendarEventService.upsert_events([
        _ev('002156', date(2026, 8, 25), 'akshare', 'FH20251231',
            etype='ex_dividend')])

    ok_df = pd.DataFrame([
        {'代码': '002156', '名称': '通富微电', '除权除息日': pd.Timestamp('2026-09-05'),
         '现金分红-现金分红比例': 1.5, '方案进度': '实施方案'},
    ])

    def _fhps(date):
        if date == '20251231':
            raise RuntimeError('akshare down')
        return ok_df

    monkeypatch.setattr(mod, 'WATCH_CODES', WATCH_STUB)
    monkeypatch.setattr(mod, '_fhps_report_dates',
                        lambda today: ['20251231', '20260930'])
    monkeypatch.setattr(mod.ak, 'stock_fhps_em', _fhps)
    _silent_collectors(monkeypatch, mod, collect_dividend_a=mod.collect_dividend_a)

    stats = mod.CalendarEventService.refresh_all(date(2026, 8, 21))

    assert stats['removed'] == 0
    assert stats['incomplete'] == ['dividend_a']
    assert StockEvent.query.filter_by(period_key='FH20251231').count() == 1


def test_strategy_schedule_is_before_daily_briefing():
    from app.strategies.calendar_event import CalendarEventStrategy
    s = CalendarEventStrategy()
    assert s.name == 'calendar_event'
    assert s.schedule == '30 7 * * *'
    assert s.needs_llm is False
