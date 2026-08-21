from datetime import date

import pytest
from flask import Flask


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

    monkeypatch.setattr(mod, 'collect_earnings_a', lambda today: [
        _ev('002156', date(2026, 8, 29), 'cninfo', '2026H1'),
        _ev('300223', date(2027, 3, 1), 'cninfo', '2027A'),
    ])
    monkeypatch.setattr(mod, 'collect_calendar_yf', lambda today: [])
    monkeypatch.setattr(mod, 'collect_dividend_a', lambda today: [])
    monkeypatch.setattr(mod, 'collect_macro_range', lambda s, e: [])

    stats = mod.CalendarEventService.refresh_all(date(2026, 8, 21))

    assert stats['upserted'] == 1
    assert [r.stock_code for r in StockEvent.query.all()] == ['002156']


def test_refresh_all_one_collector_failure_does_not_block_others(app_ctx, monkeypatch):
    from app.models.stock_event import StockEvent
    from app.services import calendar_event as mod

    def _boom(today):
        raise RuntimeError('cninfo down')

    monkeypatch.setattr(mod, 'collect_earnings_a', _boom)
    monkeypatch.setattr(mod, 'collect_calendar_yf', lambda today: [
        _ev('0700.HK', date(2026, 9, 3), 'yfinance', '2026Q3')])
    monkeypatch.setattr(mod, 'collect_dividend_a', lambda today: [])
    monkeypatch.setattr(mod, 'collect_macro_range', lambda s, e: [])

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

    monkeypatch.setattr(mod, 'collect_earnings_a', _boom)
    monkeypatch.setattr(mod, 'collect_calendar_yf', lambda today: [])
    monkeypatch.setattr(mod, 'collect_dividend_a', lambda today: [])
    monkeypatch.setattr(mod, 'collect_macro_range', lambda s, e: [])

    mod.CalendarEventService.refresh_all(date(2026, 8, 21))

    assert StockEvent.query.count() == 1


def test_refresh_all_prunes_withdrawn_event(app_ctx, monkeypatch):
    from app.models.stock_event import StockEvent
    from app.services import calendar_event as mod

    mod.CalendarEventService.upsert_events([
        _ev('002156', date(2026, 8, 29), 'cninfo', '2026H1'),
        _ev('300223', date(2026, 8, 28), 'cninfo', '2026H1'),
    ])

    monkeypatch.setattr(mod, 'collect_earnings_a', lambda today: [
        _ev('002156', date(2026, 8, 29), 'cninfo', '2026H1')])
    monkeypatch.setattr(mod, 'collect_calendar_yf', lambda today: [])
    monkeypatch.setattr(mod, 'collect_dividend_a', lambda today: [])
    monkeypatch.setattr(mod, 'collect_macro_range', lambda s, e: [])

    stats = mod.CalendarEventService.refresh_all(date(2026, 8, 21))

    assert stats['removed'] == 1
    assert [r.stock_code for r in StockEvent.query.all()] == ['002156']


def test_strategy_schedule_is_before_daily_briefing():
    from app.strategies.calendar_event import CalendarEventStrategy
    s = CalendarEventStrategy()
    assert s.name == 'calendar_event'
    assert s.schedule == '30 7 * * *'
    assert s.needs_llm is False
