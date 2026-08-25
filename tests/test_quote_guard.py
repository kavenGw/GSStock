"""行情取数守卫：拒绝集合竞价参考价、零成交、字段错位的报价。

L24（2026-08-25 建滔积层板轮）：控制者 09:00:20 读到 hk01888 报 40.360/+14.99%、
成交仅 95 手，据此把「中报超预期导致跳涨」写进三路 A 的派发；而 09:20 开盘后
实为 35.320/+0.63%，因果完全反了。三路 subagent 全被污染、两轮校准。
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.quote_guard import QuoteRejected, guard, in_session, infer_market, main

SHARES = 3_151_450_000


def _quote(price, volume, ts, *, code='hk01888', shares=SHARES, market_cap=None):
    return {
        'code': code,
        'price': price,
        'volume': volume,
        'timestamp': ts,
        'shares': shares,
        'market_cap': market_cap if market_cap is not None else price * shares,
    }


def test_infer_market():
    assert infer_market('hk01888') == 'HK'
    assert infer_market('sh600183') == 'A'
    assert infer_market('sz300757') == 'A'
    assert infer_market('NVDA') == 'US'
    assert infer_market('1888.HK') == 'HK'
    assert infer_market('1888.hk') == 'HK'
    assert infer_market('600183.SS') == 'A'
    assert infer_market('300757.SZ') == 'A'


def test_in_session_hk():
    assert in_session('HK', datetime(2026, 8, 25, 10, 13)) is True
    assert in_session('HK', datetime(2026, 8, 25, 9, 0)) is False
    assert in_session('HK', datetime(2026, 8, 25, 9, 20)) is False
    assert in_session('HK', datetime(2026, 8, 25, 12, 30)) is False


def test_rejects_preopen_auction_price():
    """本条就是 L24 的原始现场：09:00:20、成交 95 手、报 40.360。"""
    q = _quote(40.360, 95, datetime(2026, 8, 25, 9, 0, 20))
    with pytest.raises(QuoteRejected) as exc:
        guard(q)
    assert '竞价' in str(exc.value)


def test_rejects_zero_volume():
    q = _quote(35.320, 0, datetime(2026, 8, 25, 10, 13))
    with pytest.raises(QuoteRejected) as exc:
        guard(q)
    assert '成交' in str(exc.value)


def test_rejects_market_cap_mismatch():
    """市值与 价×股本 不符 = 字段错位；旧档曾把振幅字段当 PB 用。"""
    q = _quote(35.320, 5_000_000, datetime(2026, 8, 25, 10, 13),
               market_cap=35.320 * SHARES * 1.5)
    with pytest.raises(QuoteRejected) as exc:
        guard(q)
    assert '自洽' in str(exc.value)


def test_accepts_valid_intraday_quote():
    q = _quote(35.320, 5_000_000, datetime(2026, 8, 25, 10, 13))
    assert guard(q) is q


def test_allow_preopen_passes_but_marks_warning():
    """豁免的只是"非交易时段"一条：成交量与市值仍须过，过了才带警告放行。"""
    q = _quote(40.360, 5_000_000, datetime(2026, 8, 25, 9, 0, 20))
    out = guard(q, allow_preopen=True)
    assert '不可作行情锚' in out['preopen_warning']


def test_allow_preopen_still_checks_volume():
    """L24 原始现场（95 手）即便带 --allow-preopen 也过不了成交量断言。"""
    q = _quote(40.360, 95, datetime(2026, 8, 25, 9, 0, 20))
    with pytest.raises(QuoteRejected) as exc:
        guard(q, allow_preopen=True)
    assert '成交' in str(exc.value)


def test_suffix_style_hk_code_still_rejects_lunch_break():
    """1888.HK 若被误判成 US，港股午休快照会被美股时段放行 —— 本条锁住它。"""
    q = _quote(35.320, 5_000_000, datetime(2026, 8, 25, 12, 30), code='1888.HK')
    with pytest.raises(QuoteRejected):
        guard(q)


def test_rejects_missing_market_cap():
    """市值缺失 = 自洽校验无法进行；无法验证不等于验证通过。"""
    q = _quote(35.320, 5_000_000, datetime(2026, 8, 25, 10, 13), market_cap=0)
    with pytest.raises(QuoteRejected) as exc:
        guard(q)
    assert '市值' in str(exc.value)


def test_us_intraday_naive_ts_passes():
    """naive 时戳按市场本地时间解释：美股 10:30 即 ET 10:30，盘中放行。"""
    q = _quote(180.0, 5_000_000, datetime(2026, 8, 25, 10, 30), code='NVDA')
    assert guard(q) is q


def test_us_premarket_rejected():
    """美股盘前 08:00 ET —— 本机时区是 Asia/Shanghai，此前用本地 naive 比较会把
    每个美股报价都判成非交易时段；现在按 ET 解释，只有真盘前才被拒。"""
    q = _quote(180.0, 5_000_000, datetime(2026, 8, 25, 8, 0), code='NVDA')
    with pytest.raises(QuoteRejected) as exc:
        guard(q)
    assert '交易时段' in str(exc.value)


def test_us_tz_aware_ts_converted_to_et():
    """北京时间 22:30（UTC+8）= ET 10:30，tz-aware 时戳须换算后判定。"""
    cst = timezone(timedelta(hours=8))
    q = _quote(180.0, 5_000_000, datetime(2026, 8, 25, 22, 30, tzinfo=cst), code='NVDA')
    assert guard(q) is q


def test_allow_preopen_still_checks_market_cap():
    """--allow-preopen 只豁免"非交易时段"；字段错位不该带着竞价标签混过去。"""
    q = _quote(40.360, 5_000_000, datetime(2026, 8, 25, 9, 0, 20),
               market_cap=40.360 * SHARES * 1.5)
    with pytest.raises(QuoteRejected) as exc:
        guard(q, allow_preopen=True)
    assert '自洽' in str(exc.value)


def test_rejects_a_share_closing_auction():
    """A 股 14:57-15:00 是收盘集合竞价，与开盘竞价同类失败模式。"""
    q = _quote(12.0, 5_000_000, datetime(2026, 8, 25, 14, 58), code='sh600183')
    with pytest.raises(QuoteRejected) as exc:
        guard(q)
    assert '竞价' in str(exc.value)


def test_rejects_weekend_snapshot():
    """周六 10:13 的陈旧快照能过成交量与市值两条断言，必须靠交易日判定拦住。"""
    q = _quote(35.320, 5_000_000, datetime(2026, 8, 29, 10, 13))
    with pytest.raises(QuoteRejected) as exc:
        guard(q)
    assert '周末' in str(exc.value)


def test_cli_rejects_l24_original_scene(capsys):
    """CLI 跑 L24 原始现场：09:00:20、95 手、40.360 —— 非零退出。"""
    rc = main(['--code', 'hk01888', '--price', '40.360', '--volume', '95',
               '--ts', '2026-08-25 09:00:20', '--shares', '3151450000',
               '--market-cap', '127192520000'])
    err = capsys.readouterr().err
    assert rc == 1
    assert '取数被拒' in err


def test_cli_accepts_corrected_quote(capsys):
    """同一只股开盘后的真实报价 —— exit 0。"""
    rc = main(['--code', 'hk01888', '--price', '35.320', '--volume', '5000000',
               '--ts', '2026-08-25 10:13:25', '--shares', '3151450000',
               '--market-cap', '111309214000'])
    out = capsys.readouterr().out
    assert rc == 0
    assert '通过' in out
