from datetime import date, timedelta

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
        {'event_date': (today + timedelta(days=5)).isoformat(),
         'event_type': 'macro', 'stock_code': '',
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


def test_format_calendar_events_repeats_date_on_every_line(monkeypatch):
    """Slack 比例字体下缩进对不齐，同日第二条起若省略日期就像没有日期。"""
    from datetime import timedelta
    from app.services import notification as mod
    from app.services.calendar_event import CalendarEventService

    day = date.today() + timedelta(days=4)
    monkeypatch.setattr(CalendarEventService, 'get_events', staticmethod(lambda s, e: [
        {'event_date': day.isoformat(), 'event_type': 'earnings',
         'stock_code': '002156', 'stock_name': '通富微电', 'title': '中报披露',
         'detail': None, 'priority': 'HIGH', 'status': 'scheduled'},
        {'event_date': day.isoformat(), 'event_type': 'earnings',
         'stock_code': '000725', 'stock_name': '京东方A', 'title': '中报披露',
         'detail': None, 'priority': 'HIGH', 'status': 'scheduled'},
    ]))
    monkeypatch.setattr(CalendarEventService, 'hours_since_refresh',
                        staticmethod(lambda: 1.0))

    lines = mod.NotificationService.format_calendar_events().split(chr(10))[1:]

    assert len(lines) == 2
    md = day.isoformat()[5:]
    weekday = '周' + '一二三四五六日'[day.weekday()]
    for line in lines:
        assert line.startswith('`%s %s` ' % (md, weekday)), line


def test_calendar_date_label_today_and_tomorrow():
    from datetime import timedelta
    from app.services.notification import NotificationService

    today = date(2026, 8, 25)
    label = NotificationService._calendar_date_label
    assert label('2026-08-25', today) == '08-25 今天'
    assert label('2026-08-26', today) == '08-26 明天'
    assert label('2026-08-29', today) == '08-29 周六'
    assert label('not-a-date', today) == 'not-a-date'


def _stub_last_trading_day(monkeypatch):
    """交易日历用纯工作日近似，避免测试依赖 exchange-calendars 的节假日数据"""
    from app.services.trading_calendar import TradingCalendarService

    def _prev(cls, market, before=None):
        d = before - timedelta(days=1)
        while d.weekday() >= 5:
            d -= timedelta(days=1)
        return d

    monkeypatch.setattr(TradingCalendarService, 'get_last_trading_day',
                        classmethod(_prev))


def test_a_share_earnings_shifted_to_previous_session_after_close(monkeypatch):
    """A股预约披露日 T 指见报日，公告 T-1 交易日盘后就已挂网——推送按盘后落位。"""
    from app.services import notification as mod
    from app.services.calendar_event import CalendarEventService

    _stub_last_trading_day(monkeypatch)
    today = date.today()
    disclose = today + timedelta(days=3)
    monkeypatch.setattr(CalendarEventService, 'get_events', staticmethod(lambda s, e: [
        {'event_date': disclose.isoformat(), 'event_type': 'earnings',
         'stock_code': '603986', 'stock_name': '兆易创新', 'market': 'A',
         'title': '中报披露', 'detail': None, 'priority': 'HIGH',
         'status': 'scheduled'},
    ]))
    monkeypatch.setattr(CalendarEventService, 'hours_since_refresh',
                        staticmethod(lambda: 1.0))

    line = mod.NotificationService.format_calendar_events().split(chr(10))[1]

    from app.services.trading_calendar import TradingCalendarService
    eff = TradingCalendarService.get_last_trading_day('A', before=disclose)
    assert line.startswith('`%s ' % eff.isoformat()[5:])
    assert '盘后`' in line
    assert disclose.isoformat()[5:] not in line


def test_non_a_share_and_ex_dividend_keep_original_date(monkeypatch):
    """除权除息是真实当日事件，港美股财报按各自日历——都不前移。"""
    from app.services import notification as mod
    from app.services.calendar_event import CalendarEventService

    _stub_last_trading_day(monkeypatch)
    day = date.today() + timedelta(days=2)
    monkeypatch.setattr(CalendarEventService, 'get_events', staticmethod(lambda s, e: [
        {'event_date': day.isoformat(), 'event_type': 'ex_dividend',
         'stock_code': '600519', 'stock_name': '贵州茅台', 'market': 'A',
         'title': '除权除息', 'detail': None, 'priority': 'LOW',
         'status': 'scheduled'},
        {'event_date': day.isoformat(), 'event_type': 'earnings',
         'stock_code': '0700.HK', 'stock_name': '腾讯控股', 'market': 'HK',
         'title': '财报披露', 'detail': None, 'priority': 'MEDIUM',
         'status': 'scheduled'},
    ]))
    monkeypatch.setattr(CalendarEventService, 'hours_since_refresh',
                        staticmethod(lambda: 1.0))

    lines = mod.NotificationService.format_calendar_events().split(chr(10))[1:]

    assert len(lines) == 2
    for line in lines:
        assert line.startswith('`%s ' % day.isoformat()[5:]), line
        assert '盘后' not in line


def test_a_share_earnings_on_window_edge_shifts_into_window(monkeypatch):
    """窗口末日之后一天的披露，其盘后时点落在窗口内，必须仍然出现。"""
    from app.services import notification as mod
    from app.services.calendar_event import CalendarEventService

    _stub_last_trading_day(monkeypatch)
    today = date.today()
    captured = {}

    def _get_events(start, end):
        captured['end'] = end
        return [{'event_date': (today + timedelta(days=8)).isoformat(),
                 'event_type': 'earnings', 'stock_code': '000725',
                 'stock_name': '京东方A', 'market': 'A', 'title': '中报披露',
                 'detail': None, 'priority': 'HIGH', 'status': 'scheduled'},
                {'event_date': (today + timedelta(days=8)).isoformat(),
                 'event_type': 'macro', 'stock_code': '', 'stock_name': None,
                 'market': 'US', 'title': 'FOMC 议息', 'detail': None,
                 'priority': 'HIGH', 'status': 'scheduled'}]

    monkeypatch.setattr(CalendarEventService, 'get_events', staticmethod(_get_events))
    monkeypatch.setattr(CalendarEventService, 'hours_since_refresh',
                        staticmethod(lambda: 1.0))

    text = mod.NotificationService.format_calendar_events()

    assert captured['end'] == today + timedelta(days=8), '需多取一天兜住前移的A股财报'
    assert '京东方A' in text
    assert 'FOMC' not in text, '未前移的事件超出7天窗口应被剔除'


def test_calendar_date_label_yesterday_for_shifted_release():
    from app.services.notification import NotificationService

    label = NotificationService._calendar_date_label
    assert label('2026-08-24', date(2026, 8, 25)) == '08-24 昨天'
