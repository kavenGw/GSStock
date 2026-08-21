import pytest


def test_calendar_page_renders_two_months(app_client, monkeypatch):
    """渲染 HTML 必须走 create_app —— base.html 跨 blueprint url_for 会 BuildError。"""
    r = app_client.get('/calendar/')
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert html.count('cal-month') >= 2
    assert 'calendar.js' in html
    assert 'calendar.css' in html


def test_nav_has_calendar_entry(app_client):
    r = app_client.get('/calendar/')
    html = r.get_data(as_text=True)
    assert '/calendar/' in html
    assert '日历' in html
