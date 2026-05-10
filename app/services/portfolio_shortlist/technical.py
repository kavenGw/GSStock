"""技术形态指标计算 — spec §5。

输入 30 日 OHLC（list of dict），输出 5 个 [0, 1] 子分给打分模块。
"""

from typing import Optional


def _ma(closes: list[float], window: int) -> Optional[float]:
    if len(closes) < window:
        return None
    return sum(closes[-window:]) / window


def _slope_sign(closes: list[float]) -> float:
    if len(closes) < 2:
        return 0.5
    return 1.0 if closes[-1] > closes[0] else 0.0


def _td_signal_from_ohlc(ohlc: list[dict]) -> float:
    """调用 TDSequentialService 计算 TD 九转信号。

    buy setup 完成（count=9, direction=buy）→ 1.0
    sell setup 完成（count=9, direction=sell）→ 0.0
    其余 → 0.5
    启发式兜底：连续 9 根收盘均 < 4 根前 → buy(1.0)，均 > 4 根前 → sell(0.0)
    """
    closes = [r['close'] for r in ohlc]
    if len(closes) < 13:
        return 0.5

    try:
        from app.services.td_sequential import TDSequentialService
        result = TDSequentialService.calculate(ohlc)
        if result.get('completed'):
            direction = result.get('direction')
            if direction == 'buy':
                return 1.0
            if direction == 'sell':
                return 0.0
        return 0.5
    except Exception:
        pass

    # 启发式兜底
    buy = sum(1 for i in range(-9, 0) if closes[i] < closes[i - 4]) >= 9
    sell = sum(1 for i in range(-9, 0) if closes[i] > closes[i - 4]) >= 9
    if buy:
        return 1.0
    if sell:
        return 0.0
    return 0.5


def compute_technical(ohlc: list[dict]) -> dict:
    """计算技术形态 5 指标，每项归一至 [0, 1]。"""
    if not ohlc:
        return {
            'ma20_position': 0.5, 'volume_ratio': 0.5, 'support_ok': 0.5,
            'td_signal': 0.5, 'trend_direction': 0.5,
        }

    closes = [r['close'] for r in ohlc]
    volumes = [r['volume'] for r in ohlc]
    cur = closes[-1]

    # MA20 位置
    ma20 = _ma(closes, 20)
    ma20_position = 1.0 if (ma20 is not None and cur >= ma20) else 0.0

    # 量比：5d 均量 / 30d 均量
    if len(volumes) >= 30:
        vol5 = sum(volumes[-5:]) / 5
        vol30 = sum(volumes[-30:]) / 30
        ratio = vol5 / vol30 if vol30 > 0 else 1.0
        if 0.8 <= ratio <= 1.5:
            volume_ratio = 1.0
        elif ratio > 1.5:
            volume_ratio = 0.8
        else:
            volume_ratio = max(0.0, ratio / 0.8 * 0.5)
    else:
        volume_ratio = 0.5

    # 支撑位置：当前价在 30d 高低区间的相对位置
    high30 = max(r['high'] for r in ohlc)
    low30 = min(r['low'] for r in ohlc)
    support_ok = (cur - low30) / (high30 - low30) if high30 > low30 else 0.5

    # TD 九转信号
    td_signal = _td_signal_from_ohlc(ohlc)

    # 趋势方向：30d 首尾收盘斜率
    trend_direction = _slope_sign(closes)

    return {
        'ma20_position': ma20_position,
        'volume_ratio': round(volume_ratio, 3),
        'support_ok': round(support_ok, 3),
        'td_signal': td_signal,
        'trend_direction': trend_direction,
    }
