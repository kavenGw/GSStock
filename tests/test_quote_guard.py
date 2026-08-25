"""行情取数守卫：拒绝集合竞价参考价、零成交、字段错位的报价。

L24（2026-08-25 建滔积层板轮）：控制者 09:00:20 读到 hk01888 报 40.360/+14.99%、
成交仅 95 手，据此把「中报超预期导致跳涨」写进三路 A 的派发；而 09:20 开盘后
实为 35.320/+0.63%，因果完全反了。三路 subagent 全被污染、两轮校准。
"""
import sys
from datetime import datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.quote_guard import QuoteRejected, guard, in_session, infer_market

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
    q = _quote(40.360, 95, datetime(2026, 8, 25, 9, 0, 20))
    out = guard(q, allow_preopen=True)
    assert '不可作行情锚' in out['preopen_warning']
