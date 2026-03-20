"""交易信号服务 — 对外统一接口"""
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    from app.ml.predictor import TrendPredictor
    _predictor = TrendPredictor()
except ImportError:
    logger.warning('[SignalService] torch 未安装，AI信号功能不可用')
    _predictor = None


class SignalService:

    @staticmethod
    def get_signal(stock_code: str, ohlcv: list[dict]) -> dict | None:
        if not _predictor:
            return None
        return _predictor.predict(stock_code, ohlcv)

    @staticmethod
    def get_batch_signals(stock_data: dict[str, list[dict]]) -> dict[str, dict]:
        if not _predictor:
            return {}
        results = {}
        for code, ohlcv in stock_data.items():
            signal = _predictor.predict(code, ohlcv)
            if signal:
                results[code] = signal
        return results

    @staticmethod
    def has_model(stock_code: str) -> bool:
        if not _predictor:
            return False
        return (Path('data/models') / stock_code / 'model.pt').exists()

    @staticmethod
    def clear_model_cache(stock_code: str = None):
        if _predictor:
            _predictor.clear_cache(stock_code)
