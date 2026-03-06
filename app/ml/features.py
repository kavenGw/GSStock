"""特征工程 — OHLCV 数据转换为模型输入特征"""
import numpy as np


# 特征维度：OHLCV(5) + MA(4) + RSI(1) + MACD(3) + 布林带(3) + ATR(1) + 量变化率(1) + OBV(1) = 19
FEATURE_DIM = 19
WINDOW_SIZE = 60


def compute_features(ohlcv: list[dict]) -> np.ndarray | None:
    """将 OHLCV 数据列表转换为特征矩阵

    Args:
        ohlcv: OHLCV 数据列表，每项包含 open, high, low, close, volume

    Returns:
        (seq_len, FEATURE_DIM) 的 numpy 数组，MinMax 归一化到 [0,1]
        数据不足时返回 None
    """
    if len(ohlcv) < WINDOW_SIZE:
        return None

    opens = np.array([d['open'] for d in ohlcv], dtype=np.float64)
    highs = np.array([d['high'] for d in ohlcv], dtype=np.float64)
    lows = np.array([d['low'] for d in ohlcv], dtype=np.float64)
    closes = np.array([d['close'] for d in ohlcv], dtype=np.float64)
    volumes = np.array([d['volume'] for d in ohlcv], dtype=np.float64)

    ma5 = _moving_average(closes, 5)
    ma10 = _moving_average(closes, 10)
    ma20 = _moving_average(closes, 20)
    ma60 = _moving_average(closes, 60)

    rsi = _rsi(closes, 14)
    macd_line, signal_line, histogram = _macd(closes)
    upper, middle, lower = _bollinger(closes, 20, 2)
    atr = _atr(highs, lows, closes, 14)
    vol_change = _volume_change_rate(volumes)
    obv = _obv(closes, volumes)

    features = np.column_stack([
        opens, highs, lows, closes, volumes,
        ma5, ma10, ma20, ma60,
        rsi,
        macd_line, signal_line, histogram,
        upper, middle, lower,
        atr,
        vol_change,
        obv,
    ])

    feat_min = features.min(axis=0)
    feat_max = features.max(axis=0)
    feat_range = feat_max - feat_min
    feat_range[feat_range == 0] = 1.0
    features = (features - feat_min) / feat_range

    return features.astype(np.float32)


def _moving_average(data: np.ndarray, window: int) -> np.ndarray:
    result = np.full_like(data, np.nan)
    cumsum = np.cumsum(data)
    result[window - 1:] = (cumsum[window - 1:] - np.concatenate([[0], cumsum[:-window]])) / window
    result[:window - 1] = result[window - 1]
    return result


def _rsi(closes: np.ndarray, period: int) -> np.ndarray:
    deltas = np.diff(closes, prepend=closes[0])
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)
    avg_gain = np.full_like(closes, np.nan)
    avg_loss = np.full_like(closes, np.nan)
    avg_gain[period] = gains[1:period + 1].mean()
    avg_loss[period] = losses[1:period + 1].mean()
    for i in range(period + 1, len(closes)):
        avg_gain[i] = (avg_gain[i - 1] * (period - 1) + gains[i]) / period
        avg_loss[i] = (avg_loss[i - 1] * (period - 1) + losses[i]) / period
    rs = avg_gain / np.where(avg_loss == 0, 1e-10, avg_loss)
    rsi = 100 - 100 / (1 + rs)
    rsi[:period] = 50.0
    return rsi


def _macd(closes: np.ndarray, fast=12, slow=26, signal=9):
    ema_fast = _ema(closes, fast)
    ema_slow = _ema(closes, slow)
    macd_line = ema_fast - ema_slow
    signal_line = _ema(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def _ema(data: np.ndarray, period: int) -> np.ndarray:
    result = np.empty_like(data)
    multiplier = 2.0 / (period + 1)
    result[0] = data[0]
    for i in range(1, len(data)):
        result[i] = (data[i] - result[i - 1]) * multiplier + result[i - 1]
    return result


def _bollinger(closes: np.ndarray, period: int, num_std: float):
    middle = _moving_average(closes, period)
    rolling_std = np.full_like(closes, np.nan)
    for i in range(period - 1, len(closes)):
        rolling_std[i] = closes[i - period + 1:i + 1].std()
    rolling_std[:period - 1] = rolling_std[period - 1]
    upper = middle + num_std * rolling_std
    lower = middle - num_std * rolling_std
    return upper, middle, lower


def _atr(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int) -> np.ndarray:
    tr = np.maximum(highs - lows,
                    np.maximum(np.abs(highs - np.roll(closes, 1)),
                               np.abs(lows - np.roll(closes, 1))))
    tr[0] = highs[0] - lows[0]
    atr = np.full_like(tr, np.nan)
    atr[period - 1] = tr[:period].mean()
    for i in range(period, len(tr)):
        atr[i] = (atr[i - 1] * (period - 1) + tr[i]) / period
    atr[:period - 1] = atr[period - 1]
    return atr


def _volume_change_rate(volumes: np.ndarray) -> np.ndarray:
    prev = np.roll(volumes, 1)
    prev[0] = volumes[0]
    rate = (volumes - prev) / np.where(prev == 0, 1, prev)
    return rate


def _obv(closes: np.ndarray, volumes: np.ndarray) -> np.ndarray:
    direction = np.sign(np.diff(closes, prepend=closes[0]))
    obv = np.cumsum(direction * volumes)
    return obv
