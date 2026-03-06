"""推理服务 — 加载训练好的模型生成交易信号"""
import json
import logging
from pathlib import Path

import numpy as np
import torch

from app.ml.dataset import SIGNAL_NAMES
from app.ml.features import compute_features, FEATURE_DIM, WINDOW_SIZE
from app.ml.models.trend_transformer import TrendTransformer

logger = logging.getLogger(__name__)

MODEL_DIR = 'data/models'


class TrendPredictor:
    """缓存已加载模型，按 stock_code 推理"""
    _models: dict = {}

    def predict(self, stock_code: str, ohlcv: list[dict]) -> dict | None:
        """对单只股票生成交易信号

        Returns:
            {'signal': 'buy/sell/hold', 'confidence': 0.82, 'probabilities': {...}, 'model_date': '...'}
            模型不存在或数据不足时返回 None
        """
        model = self._load_model(stock_code)
        if model is None:
            return None

        features = compute_features(ohlcv)
        if features is None or len(features) < WINDOW_SIZE:
            return None

        window = features[-WINDOW_SIZE:]
        x = torch.tensor(window, dtype=torch.float32).unsqueeze(0)

        device = next(model.parameters()).device
        x = x.to(device)

        model.eval()
        with torch.no_grad():
            logits = model(x)
            probs = torch.softmax(logits, dim=1).cpu().numpy()[0]

        pred_idx = int(np.argmax(probs))
        model_path = Path(MODEL_DIR) / stock_code / 'model.pt'

        return {
            'signal': SIGNAL_NAMES[pred_idx],
            'confidence': round(float(probs[pred_idx]), 4),
            'probabilities': {SIGNAL_NAMES[i]: round(float(p), 4) for i, p in enumerate(probs)},
            'model_date': _get_model_date(model_path),
        }

    def _load_model(self, stock_code: str) -> TrendTransformer | None:
        if stock_code in self._models:
            return self._models[stock_code]

        model_path = Path(MODEL_DIR) / stock_code / 'model.pt'
        if not model_path.exists():
            return None

        device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        model = TrendTransformer(input_dim=FEATURE_DIM).to(device)
        model.load_state_dict(torch.load(model_path, map_location=device, weights_only=True))
        self._models[stock_code] = model
        logger.info(f'[推理] 加载模型 {stock_code}')
        return model

    def clear_cache(self, stock_code: str = None):
        if stock_code:
            self._models.pop(stock_code, None)
        else:
            self._models.clear()


def _get_model_date(model_path: Path) -> str:
    log_path = model_path.parent / 'train_log.json'
    if log_path.exists():
        with open(log_path, 'r') as f:
            data = json.load(f)
            return data.get('result', {}).get('trained_at', '')[:10]
    return ''
