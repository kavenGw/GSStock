from datetime import date

import pytest
from flask import Flask


@pytest.fixture
def client(monkeypatch):
    """只注入 calendar_bp，避免 create_app 拉起 17 个调度任务 + crawl4ai。"""
    from app.routes import calendar_bp
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.register_blueprint(calendar_bp)
    with app.test_client() as c:
        yield c


def test_default_range_is_this_month_to_next_month_end():
    from app.routes.calendar import default_range
    start, end = default_range(date(2026, 8, 21))
    assert start == date(2026, 8, 1)
    assert end == date(2026, 9, 30)


def test_default_range_crosses_year():
    from app.routes.calendar import default_range
    start, end = default_range(date(2026, 12, 5))
    assert start == date(2026, 12, 1)
    assert end == date(2027, 1, 31)


def test_events_api_uses_default_range_when_no_params(client, monkeypatch):
    from app.services.calendar_event import CalendarEventService
    seen = {}

    def _fake(start, end):
        seen['range'] = (start, end)
        return []

    monkeypatch.setattr(CalendarEventService, 'get_events', staticmethod(_fake))
    monkeypatch.setattr(CalendarEventService, 'hours_since_refresh',
                        staticmethod(lambda: 1.5))

    r = client.get('/calendar/api/events')

    assert r.status_code == 200
    body = r.get_json()
    assert body['events'] == []
    assert body['stale_hours'] == 1.5
    assert seen['range'][0].day == 1


def test_events_api_honors_explicit_range(client, monkeypatch):
    from app.services.calendar_event import CalendarEventService
    seen = {}

    def _fake(start, end):
        seen['range'] = (start, end)
        return [{'event_date': '2026-09-16', 'title': 'FOMC 议息'}]

    monkeypatch.setattr(CalendarEventService, 'get_events', staticmethod(_fake))
    monkeypatch.setattr(CalendarEventService, 'hours_since_refresh',
                        staticmethod(lambda: None))

    r = client.get('/calendar/api/events?start=2026-09-01&end=2026-09-30')

    assert r.status_code == 200
    assert seen['range'] == (date(2026, 9, 1), date(2026, 9, 30))
    assert r.get_json()['events'][0]['title'] == 'FOMC 议息'


def test_events_api_falls_back_on_bad_date(client, monkeypatch):
    from app.services.calendar_event import CalendarEventService
    monkeypatch.setattr(CalendarEventService, 'get_events',
                        staticmethod(lambda start, end: []))
    monkeypatch.setattr(CalendarEventService, 'hours_since_refresh',
                        staticmethod(lambda: None))

    r = client.get('/calendar/api/events?start=not-a-date&end=2026-09-30')

    assert r.status_code == 200
    assert r.get_json()['start'].endswith('-01')


def test_events_api_rejects_oversized_range(client, monkeypatch):
    from app.services.calendar_event import CalendarEventService
    monkeypatch.setattr(CalendarEventService, 'get_events',
                        staticmethod(lambda start, end: []))
    monkeypatch.setattr(CalendarEventService, 'hours_since_refresh',
                        staticmethod(lambda: None))

    r = client.get('/calendar/api/events?start=2020-01-01&end=2030-01-01')

    assert r.status_code == 400


def test_refresh_api_returns_202(client, monkeypatch):
    r = client.post('/calendar/api/refresh')
    assert r.status_code == 202
    assert '刷新' in r.get_json()['message']
