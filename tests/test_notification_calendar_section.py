from datetime import date

import pytest


def test_format_calendar_events_empty_returns_blank(monkeypatch):
    from app.services import notification as mod
    from app.services.calendar_event import CalendarEventService

    monkeypatch.setattr(CalendarEventService, 'get_events',
                        staticmethod(lambda start, end: []))
    monkeypatch.setattr(CalendarEventService, 'hours_since_refresh',
                        staticmethod(lambda: 1.0))

    assert mod.NotificationService.format_calendar_events() == ''


def test_format_calendar_events_db_error_returns_blank(monkeypatch):
    from app.services import notification as mod
    from app.services.calendar_event import CalendarEventService

    def _boom(start, end):
        raise RuntimeError('no such table')

    monkeypatch.setattr(CalendarEventService, 'get_events', staticmethod(_boom))
    assert mod.NotificationService.format_calendar_events() == ''


def test_format_calendar_events_groups_by_date(monkeypatch):
    from app.services import notification as mod
    from app.services.calendar_event import CalendarEventService

    today = date.today()
    monkeypatch.setattr(CalendarEventService, 'get_events', staticmethod(lambda s, e: [
        {'event_date': today.isoformat(), 'event_type': 'earnings',
         'stock_code': '603986', 'stock_name': '兆易创新', 'title': '中报披露',
         'detail': None, 'priority': 'HIGH', 'status': 'confirmed'},
        {'event_date': today.isoformat(), 'event_type': 'ex_dividend',
         'stock_code': '0700.HK', 'stock_name': '腾讯控股', 'title': '除权除息',
         'detail': None, 'priority': 'LOW', 'status': 'scheduled'},
        {'event_date': '2026-09-16', 'event_type': 'macro', 'stock_code': '',
         'stock_name': None, 'title': 'FOMC 议息', 'detail': None,
         'priority': 'HIGH', 'status': 'scheduled'},
    ]))
    monkeypatch.setattr(CalendarEventService, 'hours_since_refresh',
                        staticmethod(lambda: 2.0))

    text = mod.NotificationService.format_calendar_events()

    assert '📅 未来7天事件' in text
    assert '今天' in text
    assert '兆易创新(603986)' in text
    assert '腾讯控股(0700.HK)' in text
    assert 'FOMC 议息' in text
    assert '未更新' not in text


def test_format_calendar_events_flags_stale_data(monkeypatch):
    from app.services import notification as mod
    from app.services.calendar_event import CalendarEventService

    monkeypatch.setattr(CalendarEventService, 'get_events', staticmethod(lambda s, e: [
        {'event_date': date.today().isoformat(), 'event_type': 'macro',
         'stock_code': '', 'stock_name': None, 'title': 'FOMC 议息',
         'detail': None, 'priority': 'HIGH', 'status': 'scheduled'},
    ]))
    monkeypatch.setattr(CalendarEventService, 'hours_since_refresh',
                        staticmethod(lambda: 30.0))

    text = mod.NotificationService.format_calendar_events()
    assert '⚠️ 事件数据 30 小时未更新' in text


def test_daily_briefing_prompt_includes_calendar_label():
    from app.llm.prompts.daily_briefing import build_daily_briefing_prompt

    prompt = build_daily_briefing_prompt({
        'calendar_events': '📅 未来7天事件\n  今天  兆易创新(603986) 中报披露',
        'watch_analysis': '盯盘：兆易创新 HOLD',
    })

    assert '【近期事件日历】' in prompt
    assert prompt.index('【近期事件日历】') < prompt.index('【盯盘分析】')
    assert '财报提醒' not in prompt


def test_build_market_blocks_accepts_calendar_text():
    from app.services.notification import NotificationService

    blocks = NotificationService.build_market_blocks(
        indices_text='', futures_text='', etf_text='', sectors_text='',
        technical_text='', dram_text='', ai_text='',
        adr_text='', calendar_text='📅 未来7天事件\n  今天  兆易创新(603986) 中报披露')

    dumped = str(blocks)
    assert '未来7天事件' in dumped


def test_format_calendar_events_caps_slack_section_length(monkeypatch):
    """Slack 的 section text 超 3000 字会整条 chat.postMessage 被拒——
    不是这一段变短，而是整条推送消失。事件多时必须按行截断并标注省略数量。"""
    from app.services import notification as mod
    from app.services.calendar_event import CalendarEventService

    events = [{
        'event_date': '2026-08-%02d' % (21 + i % 7),
        'event_type': 'earnings',
        'stock_code': 'CODE%03d' % i,
        'stock_name': '很长的公司名称示例股份有限公司%03d' % i,
        'title': '财报披露',
        'detail': '预约 2026-08-26 → 2026-08-29，业绩预告已出',
        'status': 'scheduled',
    } for i in range(200)]

    monkeypatch.setattr(CalendarEventService, 'get_events',
                        staticmethod(lambda start, end: events))
    monkeypatch.setattr(CalendarEventService, 'hours_since_refresh',
                        staticmethod(lambda: 1.0))

    text = mod.NotificationService.format_calendar_events()

    assert len(text) <= mod.CALENDAR_SECTION_MAX_CHARS
    lines = text.split(chr(10))
    assert lines[0].startswith('📅')
    assert '另有' in lines[-1] and '条事件未显示' in lines[-1]
    assert len(lines) > 2, '截断后仍应保留最早的若干条事件'
    assert 'CODE000' in text, '保留的是最早的事件而非任意一段'


def test_format_calendar_events_short_list_not_truncated(monkeypatch):
    from app.services import notification as mod
    from app.services.calendar_event import CalendarEventService

    events = [{
        'event_date': '2026-08-21', 'event_type': 'macro', 'stock_code': '',
        'stock_name': None, 'title': 'FOMC 议息', 'detail': None,
        'status': 'scheduled',
    }]
    monkeypatch.setattr(CalendarEventService, 'get_events',
                        staticmethod(lambda start, end: events))
    monkeypatch.setattr(CalendarEventService, 'hours_since_refresh',
                        staticmethod(lambda: 1.0))

    text = mod.NotificationService.format_calendar_events()

    assert '另有' not in text
    assert 'FOMC 议息' in text
