"""数据集构建 — OHLCV 数据转换为训练样本"""
import numpy as np
import torch
from torch.utils.data import Dataset
from app.ml.features import compute_features, WINDOW_SIZE


LABEL_BUY = 0
LABEL_SELL = 1
LABEL_HOLD = 2
SIGNAL_NAMES = {LABEL_BUY: 'buy', LABEL_SELL: 'sell', LABEL_HOLD: 'hold'}

DEFAULT_FUTURE_DAYS = 5
DEFAULT_THRESHOLD = 0.02


def generate_labels(closes: list[float], future_days: int = DEFAULT_FUTURE_DAYS,
                    threshold: float = DEFAULT_THRESHOLD) -> np.ndarray:
    """基于未来 N 日收益率生成标签"""
    closes = np.array(closes, dtype=np.float64)
    labels = []
    for i in range(len(closes) - future_days):
        future_return = (closes[i + future_days] - closes[i]) / closes[i]
        if future_return > threshold:
            labels.append(LABEL_BUY)
        elif future_return < -threshold:
            labels.append(LABEL_SELL)
        else:
            labels.append(LABEL_HOLD)
    return np.array(labels)


class TrendDataset(Dataset):
    """滑动窗口数据集"""

    def __init__(self, ohlcv: list[dict], future_days: int = DEFAULT_FUTURE_DAYS,
                 threshold: float = DEFAULT_THRESHOLD):
        features = compute_features(ohlcv)
        if features is None:
            self.samples = []
            return

        closes = [d['close'] for d in ohlcv]
        labels = generate_labels(closes, future_days, threshold)

        self.samples = []
        max_start = min(len(features) - WINDOW_SIZE, len(labels) - 1)
        for i in range(max_start + 1):
            window = features[i:i + WINDOW_SIZE]
            label_idx = i + WINDOW_SIZE - 1
            if label_idx < len(labels):
                self.samples.append((
                    torch.tensor(window, dtype=torch.float32),
                    torch.tensor(labels[label_idx], dtype=torch.long),
                ))

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        return self.samples[idx]
