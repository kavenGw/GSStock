from datetime import date

import pytest


def test_macro_events_sorted_and_unique():
    from app.config.macro_calendar import MACRO_EVENTS
    dates = [(e['date'], e['type']) for e in MACRO_EVENTS]
    assert dates == sorted(dates), 'MACRO_EVENTS 必须按日期升序'
    assert len(dates) == len(set(dates)), '同日同类型不可重复'


def test_macro_events_all_real_dates():
    from app.config.macro_calendar import MACRO_EVENTS
    for e in MACRO_EVENTS:
        assert isinstance(e['date'], date)
        assert e['type'] in ('fomc', 'cpi', 'nfp')
        assert e['title']


def test_fomc_2026_matches_official_schedule():
    from app.config.macro_calendar import MACRO_EVENTS
    got = [e['date'] for e in MACRO_EVENTS
           if e['type'] == 'fomc' and e['date'].year == 2026]
    assert got == [date(2026, 1, 28), date(2026, 3, 18), date(2026, 4, 29),
                   date(2026, 6, 17), date(2026, 7, 29), date(2026, 9, 16),
                   date(2026, 10, 28), date(2026, 12, 9)]


def test_fomc_2027_matches_official_schedule():
    from app.config.macro_calendar import MACRO_EVENTS
    got = [e['date'] for e in MACRO_EVENTS
           if e['type'] == 'fomc' and e['date'].year == 2027]
    assert got == [date(2027, 1, 29), date(2027, 3, 19), date(2027, 5, 7),
                   date(2027, 6, 18), date(2027, 7, 30), date(2027, 9, 17),
                   date(2027, 10, 29), date(2027, 12, 10)]


def test_macro_no_partial_years():
    """若某 type 在某年出现，该年必须补满该 type 的全量条目数——
    防止有人只填三个月的 CPI 就误以为日程已完工。"""
    from app.config.macro_calendar import MACRO_EVENTS
    required = {'fomc': 8, 'cpi': 12, 'nfp': 12}
    counts = {}
    for e in MACRO_EVENTS:
        key = (e['type'], e['date'].year)
        counts[key] = counts.get(key, 0) + 1
    for (etype, year), n in counts.items():
        assert n == required[etype], (
            f'{etype} {year} 只有 {n} 条，应为 {required[etype]} 条（不允许半填年份）'
        )


def test_macro_events_cover_the_next_half_year():
    """日程表必须始终留出至少半年的前瞻量，否则会「静默过期」。

    宏观 collector 只是把本地表按窗口过滤；表一走完就无声地不再产出任何
    FOMC，日历页与每日推送里这一段直接消失，没有报错、没有告警。
    test_macro_no_partial_years 只约束「已存在的年份」要填满，某一年整体缺失
    时它平凡通过，拦不住这种过期。

    半年是刻意选的：当前表排到 2027-12-10，今天起还有 15 个月余量，绝不误报；
    而它会在表真正见底前约 7 个月就先红，留足按官方日程补录的时间。
    补表时把新一年的 8 次 FOMC 一次补齐，并同步更新按年断言的用例。
    """
    from datetime import timedelta

    from app.config.macro_calendar import MACRO_EVENTS

    horizon = date.today() + timedelta(days=183)
    latest = max(e['date'] for e in MACRO_EVENTS)
    assert latest >= horizon, (
        f'MACRO_EVENTS 最远只排到 {latest}，不足半年前瞻（需覆盖到 {horizon}）——'
        '请按 federalreserve.gov 官方日程补录下一年度 FOMC'
    )


def test_cpi_and_nfp_dates_deferred():
    """CPI / 非农发布日期待补——尚无可从本环境读到的可信数据源。

    已尝试且均失败：
    - bls.gov 直接请求返回 HTTP 403（含完整浏览器 UA 仍被拒）
    - akshare news_economic_baidu 无法获取所需 cookie
    - FRED 发布日历接口超时
    - federalreserve.gov 可访问，但不发布 BLS 的 CPI/非农日程

    一旦从可信源取得真实日期并补全 MACRO_EVENTS，本测试必须删除
    （而不是放宽断言凑过），删除本身就是"日程已补全"的信号。
    """
    from app.config.macro_calendar import MACRO_EVENTS
    assert not any(e['type'] == 'cpi' for e in MACRO_EVENTS)
    assert not any(e['type'] == 'nfp' for e in MACRO_EVENTS)


def test_collect_macro_filters_window_and_uses_empty_stock_code(monkeypatch):
    from app.services import calendar_event as mod
    monkeypatch.setattr(mod, 'MACRO_EVENTS', [
        {'date': date(2026, 7, 29), 'type': 'fomc', 'title': 'FOMC 议息'},
        {'date': date(2026, 9, 16), 'type': 'fomc', 'title': 'FOMC 议息'},
        {'date': date(2027, 1, 29), 'type': 'fomc', 'title': 'FOMC 议息'},
    ])

    out, complete = mod.collect_macro_range(date(2026, 8, 1), date(2026, 10, 31))

    assert complete is True
    assert len(out) == 1
    e = out[0]
    assert e['event_date'] == date(2026, 9, 16)
    assert e['stock_code'] == ''
    assert e['event_type'] == 'macro'
    assert e['priority'] == 'HIGH'
    assert e['period_key'] == '2026-09-16-fomc'
    assert e['source'] == 'fomc'


def test_collect_macro_source_per_type(monkeypatch):
    from app.services import calendar_event as mod
    monkeypatch.setattr(mod, 'MACRO_EVENTS', [
        {'date': date(2026, 9, 11), 'type': 'cpi', 'title': '美国 8 月 CPI'},
        {'date': date(2026, 9, 4), 'type': 'nfp', 'title': '美国 8 月非农'},
    ])

    out, _ = mod.collect_macro_range(date(2026, 9, 1), date(2026, 9, 30))

    assert {e['source'] for e in out} == {'bls'}


def test_collect_macro_same_date_different_type_no_period_key_collision(monkeypatch):
    """cpi 与 nfp 的 source 都是 'bls'，若 period_key 只用日期，同一天撞出相同的
    (event_type, stock_code, source, period_key) 业务键，upsert_events 会把后者
    当成前者的更新，静默覆盖丢掉一条——period_key 必须把 type 编进去以区分。"""
    from app.services import calendar_event as mod
    monkeypatch.setattr(mod, 'MACRO_EVENTS', [
        {'date': date(2026, 9, 4), 'type': 'cpi', 'title': '美国 8 月 CPI'},
        {'date': date(2026, 9, 4), 'type': 'nfp', 'title': '美国 8 月非农'},
    ])

    out, _ = mod.collect_macro_range(date(2026, 9, 1), date(2026, 9, 30))

    assert len(out) == 2
    keys = {e['period_key'] for e in out}
    assert len(keys) == 2
