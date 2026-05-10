import pytest
from datetime import date, timedelta

from app.services.portfolio_shortlist.technical import compute_technical


def make_ohlc(closes: list[float], volumes: list[int] = None) -> list[dict]:
    """构造 N 行 OHLC，date 从 N 天前递增；high=close+1, low=close-1, open=close。"""
    if volumes is None:
        volumes = [10000] * len(closes)
    start = date.today() - timedelta(days=len(closes) - 1)
    rows = []
    for i, (c, v) in enumerate(zip(closes, volumes)):
        d = start + timedelta(days=i)
        rows.append({
            'date': d.isoformat(), 'open': c, 'high': c + 1,
            'low': c - 1, 'close': c, 'volume': v,
        })
    return rows


def test_uptrend_full_score():
    closes = [10 + i * 0.2 for i in range(30)]
    ohlc = make_ohlc(closes)
    result = compute_technical(ohlc)
    assert result['ma20_position'] == 1.0
    assert result['trend_direction'] == 1.0
    assert 0.8 <= result['support_ok'] <= 1.0


def test_downtrend_breaks_ma():
    closes = [20 - i * 0.3 for i in range(30)]
    ohlc = make_ohlc(closes)
    result = compute_technical(ohlc)
    assert result['ma20_position'] == 0.0
    assert result['trend_direction'] == 0.0


def test_volume_shrink():
    closes = [15.0] * 30
    volumes = [10000] * 25 + [3000] * 5
    ohlc = make_ohlc(closes, volumes)
    result = compute_technical(ohlc)
    assert result['volume_ratio'] < 0.5


def test_volume_normal():
    closes = [15.0] * 30
    volumes = [10000] * 30
    ohlc = make_ohlc(closes, volumes)
    result = compute_technical(ohlc)
    assert result['volume_ratio'] >= 0.8


def test_empty_ohlc_returns_neutral():
    result = compute_technical([])
    assert all(0.4 <= v <= 0.6 for v in result.values())


def test_returns_required_keys():
    result = compute_technical(make_ohlc([15.0] * 30))
    assert set(result.keys()) == {
        'ma20_position', 'volume_ratio', 'support_ok',
        'td_signal', 'trend_direction',
    }
