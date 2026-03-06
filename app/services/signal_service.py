"""交易信号服务 — 对外统一接口"""
import logging
from pathlib import Path

from app.ml.predictor import TrendPredictor

logger = logging.getLogger(__name__)

_predictor = TrendPredictor()


class SignalService:

    @staticmethod
    def get_signal(stock_code: str, ohlcv: list[dict]) -> dict | None:
        return _predictor.predict(stock_code, ohlcv)

    @staticmethod
    def get_batch_signals(stock_data: dict[str, list[dict]]) -> dict[str, dict]:
        results = {}
        for code, ohlcv in stock_data.items():
            signal = _predictor.predict(code, ohlcv)
            if signal:
                results[code] = signal
        return results

    @staticmethod
    def has_model(stock_code: str) -> bool:
        return (Path('data/models') / stock_code / 'model.pt').exists()

    @staticmethod
    def clear_model_cache(stock_code: str = None):
        _predictor.clear_cache(stock_code)
