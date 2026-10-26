"""盯盘区间统计纯函数单测"""
import pytest

from app.services.watch_range_stats import compute_range_stats, fmt_price, format_range_stats


def _row(d, high, low, close, volume=100):
    return {'date': f'2026-10-{d:02d}', 'high': high, 'low': low, 'close': close, 'volume': volume}


def test_basic_stats():
    rows = [_row(20, 12, 9, 10), _row(21, 13, 10, 12), _row(22, 11, 8, 9)]
    s = compute_range_stats(rows, 7)
    assert s['high'] == 13 and s['low'] == 8 and s['current'] == 9
    assert s['days'] == 3 and s['end_date'] == '2026-10-22'
    assert s['position'] == pytest.approx(20)


def test_takes_last_window_rows_sorted_by_date():
    rows = [_row(d, 10 + d, 9, 10 + d) for d in (5, 3, 4, 2, 1)]
    s = compute_range_stats(rows, 3)
    assert s['days'] == 3 and s['end_date'] == '2026-10-05'
    assert s['low'] == 9 and s['high'] == 15 and s['current'] == 15


def test_vwap_weights_by_volume():
    rows = [_row(20, 12, 6, 9, volume=100), _row(21, 21, 15, 18, volume=300)]
    s = compute_range_stats(rows, 7)
    assert s['vwap'] == pytest.approx((9 * 100 + 18 * 300) / 400)


def test_vwap_skips_days_without_volume():
    rows = [_row(20, 12, 6, 9, volume=0), _row(21, 21, 15, 18, volume=None), _row(22, 33, 27, 30)]
    s = compute_range_stats(rows, 7)
    assert s['vwap'] == pytest.approx(30)


def test_vwap_none_when_all_volume_missing():
    rows = [_row(20, 12, 6, 9, volume=0), _row(21, 21, 15, 18, volume=None)]
    assert compute_range_stats(rows, 7)['vwap'] is None


def test_position_none_when_flat():
    rows = [_row(20, 10, 10, 10), _row(21, 10, 10, 10)]
    assert compute_range_stats(rows, 7)['position'] is None


def test_empty_rows():
    assert compute_range_stats([], 7) is None
    assert compute_range_stats([{'date': '2026-10-20', 'close': None}], 7) is None


def test_fmt_price():
    assert fmt_price(128.5) == '128.50'
    assert fmt_price(285000) == '285,000'
    assert fmt_price(None) == '—'


def _entry(code, name, market, rows_7, rows_30, expected='2026-10-22'):
    return {'code': code, 'name': name, 'market': market, 'expected_date': expected,
            'stats': {'7d': compute_range_stats(rows_7, 7), '30d': compute_range_stats(rows_30, 30)}}


def test_format_splits_windows_and_marks_short_window():
    full_7 = [_row(d, 12, 8, 10) for d in range(14, 23) if d not in (18, 19)]
    full_30 = [{**_row(1, 12, 8, 10), 'date': f'2026-09-{d:02d}'} for d in range(1, 30)] + full_7
    entries = [
        _entry('NVDA', '英伟达', 'US', full_7, full_30),
        _entry('603986', '兆易创新', 'A', full_7, full_7),
    ]
    short, long = format_range_stats(entries)
    assert short.startswith('📊 *盯盘区间统计 · 7 天*（最近 7 个交易日，截至 2026-10-22）')
    assert long.startswith('📊 *盯盘区间统计 · 30 天*（最近 30 个交易日，截至 2026-10-22）')
    assert '30d' not in short and '7d' not in long
    assert short.index('NVDA') < short.index('603986')
    lines = long.split('\n')
    assert '*兆易创新(603986)* [A股] 当前 10.00' in lines
    assert '  · 30d(7日) 高 12.00 | 低 8.00 | 均 10.00 | 位置 50%' in lines
    assert '  · 30d 高 12.00 | 低 8.00 | 均 10.00 | 位置 50%' in lines
    assert '  · 7d 高 12.00 | 低 8.00 | 均 10.00 | 位置 50%' in short


def test_windows_sort_independently_across_markets_with_missing_positions_last():
    low = [_row(22, 20, 10, 11)]
    high = [_row(22, 20, 10, 19)]
    flat = [_row(22, 10, 10, 10)]
    entries = [
        _entry('FLAT', 'Flat', 'US', flat, flat),
        _entry('A', 'Alpha', 'A', high, low),
        _entry('B', 'Beta', 'HK', low, high),
        _entry('C', 'Gamma', 'KR', low, high),
    ]
    short, long = format_range_stats(entries)
    assert short.index('*Beta') < short.index('*Gamma') < short.index('*Alpha') < short.index('*Flat')
    assert long.index('*Alpha') < long.index('*Beta') < long.index('*Gamma') < long.index('*Flat')
    assert '[港股]' in short and '[韩股]' in short and '[美股]' in short


def test_format_marks_stale_and_dash_values():
    rows = [_row(20, 10, 10, 10, volume=0)]
    messages = format_range_stats([_entry('0100.HK', 'MiniMax', 'HK', rows, rows)])
    for text in messages:
        assert '*MiniMax(0100.HK)* [港股] (截至 10-20) 当前 10.00' in text
        assert '均 — | 位置 —' in text


def test_notification_wiring_uses_watch_codes(monkeypatch):
    from app.config import stock_codes
    from app.services.notification import NotificationService as N
    from app.services.unified_stock_data import unified_stock_data_service as svc

    monkeypatch.setattr(stock_codes, 'WATCH_CODES', [
        {'code': '603986', 'name': '兆易创新', 'market': 'A'},
        {'code': '0981.HK', 'name': '中芯国际', 'market': 'HK',
         'ah': {'code': '688981', 'market': 'A', 'name': '中芯国际'}},
    ])
    calls = []

    def fake_trend(codes, days=60, force_refresh=False):
        calls.append((tuple(codes), days))
        return {'stocks': [{'stock_code': '603986', 'stock_name': '兆易创新',
                            'data': [_row(22, 11, 9, 10)]}]}

    monkeypatch.setattr(svc, 'get_trend_data', fake_trend)
    monkeypatch.setattr(N, '_expected_last_trading_date', staticmethod(lambda m: '2026-10-22'))

    messages = N.format_watch_range_stats()
    assert calls == [(('603986', '0981.HK'), 60)]
    assert len(messages) == 2
    for text in messages:
        assert '*兆易创新(603986)* [A股] 当前 10.00' in text and '中芯国际' not in text


def test_notification_wiring_swallows_errors(monkeypatch):
    from app.services.notification import NotificationService as N
    from app.services.unified_stock_data import unified_stock_data_service as svc

    def boom(*a, **k):
        raise RuntimeError('api down')

    monkeypatch.setattr(svc, 'get_trend_data', boom)
    assert N.format_watch_range_stats() == []


def test_format_skips_stocks_without_data():
    entries = [_entry('NVDA', '英伟达', 'US', [], []),
               _entry('AMD', 'AMD', 'US', [_row(22, 11, 9, 10)], [_row(22, 11, 9, 10)])]
    for text in format_range_stats(entries):
        assert '英伟达' not in text and '*AMD(AMD)*' in text
    assert format_range_stats([_entry('NVDA', '英伟达', 'US', [], [])]) == []
    assert format_range_stats([]) == []


def test_format_skips_empty_window_and_uses_its_own_dates():
    entries = [_entry('AMD', 'AMD', 'US', [], [_row(20, 11, 9, 10)])]
    messages = format_range_stats(entries)
    assert len(messages) == 1
    assert '30 天*（最近 30 个交易日，截至 2026-10-20）' in messages[0]
    assert '(截至 10-20)' in messages[0]


@pytest.mark.parametrize('range_results', [(True, True), (False, True)])
def test_daily_report_sends_each_window_and_counts_results(monkeypatch, range_results):
    from app.services.notification import NotificationService as N, CHANNEL_WATCH
    from app.services.watch_analysis_service import WatchAnalysisService
    from app.services.watch_service import WatchService
    from app.services.briefing import BriefingService
    from app.llm.router import llm_router

    monkeypatch.setattr(N, 'has_daily_push', lambda *a: False)
    monkeypatch.setattr(N, '_mark_daily_push', lambda *a: None)
    monkeypatch.setattr(N, 'format_briefing_summary', lambda: {'text': 'briefing'})
    for method in ('format_indices_summary', 'format_futures_summary',
                   'format_etf_premium_summary', 'format_adr_premium_summary',
                   'format_sectors_summary', 'format_dram_summary',
                   'format_technical_summary', 'format_calendar_events'):
        monkeypatch.setattr(N, method, lambda: '')
    monkeypatch.setattr(N, 'format_github_release_updates', lambda: ([], []))
    monkeypatch.setattr(N, 'build_briefing_blocks', lambda *a: [])
    monkeypatch.setattr(N, 'build_market_blocks', lambda **kw: [])
    monkeypatch.setattr(N, 'format_watch_analysis', lambda *a: {'text': ''})
    monkeypatch.setattr(WatchAnalysisService, 'analyze_stocks', lambda *a: None)
    monkeypatch.setattr(WatchService, 'get_all_today_analyses', lambda: [])
    monkeypatch.setattr(BriefingService, 'save_adr_premium_snapshot', lambda: None)
    monkeypatch.setattr(llm_router, 'route', lambda *a: None)
    messages = format_range_stats([
        _entry('AMD', 'AMD', 'US', [_row(22, 11, 9, 10)], [_row(22, 11, 9, 10)]),
    ])
    monkeypatch.setattr(N, 'format_watch_range_stats', lambda: messages)
    sent = []
    outcomes = iter(range_results)

    def fake_send(text, channel, **kwargs):
        sent.append((text, channel))
        return next(outcomes) if channel == CHANNEL_WATCH else True

    monkeypatch.setattr(N, 'send_slack', fake_send)
    result = N.push_daily_report()
    assert [text for text, channel in sent if channel == CHANNEL_WATCH] == messages
    assert result['messages_total'] == 3
    assert result['messages_sent'] == 1 + sum(range_results)
