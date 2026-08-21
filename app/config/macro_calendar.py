"""宏观事件日程 — 事件日历模块专用

FOMC 日期取自 federalreserve.gov/monetarypolicy/fomccalendars.htm，
会议为两天，此处记决议日（第二天）。2026-08-21 取，已用测试锁定。

CPI / 非农日期暂缺：本环境内已尝试 bls.gov（直连 403）、akshare
news_economic_baidu（无法取 cookie）、FRED 发布日历（超时）、
federalreserve.gov（可访问但不发布 BLS 日程），均未能取得可信源。
不得凭"每月固定几号"之类规律推算——节假日会挪期，编造的日期比
缺失更危险。待有可用数据源时再补，届时删除
tests/test_macro_calendar.py::test_cpi_and_nfp_dates_deferred。

注意：app/services/fed_rate.py 的 FOMC_MEETINGS 是利率概率服务自用的历史决议表，
与本文件各自独立维护，不要互相引用。
"""
from datetime import date

MACRO_EVENTS = [
    {'date': date(2026, 1, 28), 'type': 'fomc', 'title': 'FOMC 议息'},
    {'date': date(2026, 3, 18), 'type': 'fomc', 'title': 'FOMC 议息'},
    {'date': date(2026, 4, 29), 'type': 'fomc', 'title': 'FOMC 议息'},
    {'date': date(2026, 6, 17), 'type': 'fomc', 'title': 'FOMC 议息'},
    {'date': date(2026, 7, 29), 'type': 'fomc', 'title': 'FOMC 议息'},
    {'date': date(2026, 9, 16), 'type': 'fomc', 'title': 'FOMC 议息'},
    {'date': date(2026, 10, 28), 'type': 'fomc', 'title': 'FOMC 议息'},
    {'date': date(2026, 12, 9), 'type': 'fomc', 'title': 'FOMC 议息'},
    {'date': date(2027, 1, 29), 'type': 'fomc', 'title': 'FOMC 议息'},
    {'date': date(2027, 3, 19), 'type': 'fomc', 'title': 'FOMC 议息'},
    {'date': date(2027, 5, 7), 'type': 'fomc', 'title': 'FOMC 议息'},
    {'date': date(2027, 6, 18), 'type': 'fomc', 'title': 'FOMC 议息'},
    {'date': date(2027, 7, 30), 'type': 'fomc', 'title': 'FOMC 议息'},
    {'date': date(2027, 9, 17), 'type': 'fomc', 'title': 'FOMC 议息'},
    {'date': date(2027, 10, 29), 'type': 'fomc', 'title': 'FOMC 议息'},
    {'date': date(2027, 12, 10), 'type': 'fomc', 'title': 'FOMC 议息'},
    # ↓ CPI / 非农：DEFERRED —— 无可信数据源，见上方模块 docstring。
    #   禁止按经验规律（"CPI 约每月 10 号左右""非农是每月第一个周五"）
    #   臆造日期填入此处。补全时 title 格式为
    #   '美国 {统计月} CPI' / '美国 {统计月} 非农'，'type' 分别为 'cpi' / 'nfp'。
]

MACRO_EVENTS.sort(key=lambda e: (e['date'], e['type']))
