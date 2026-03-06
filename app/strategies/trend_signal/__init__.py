"""AI 走势信号策略 — 基于 Transformer 模型的交易信号"""
import logging
from app.strategies.base import Strategy, Signal

logger = logging.getLogger(__name__)


class TrendSignalStrategy(Strategy):
    name = "trend_signal"
    description = "AI 走势信号 — Transformer 模型交易信号"
    schedule = "interval_minutes:30"
    enabled = True

    def scan(self) -> list[Signal]:
        from app.models.stock import Stock
        from app.services.signal_service import SignalService
        from app.services.unified_stock_data import UnifiedStockDataService

        stocks = Stock.query.all()
        if not stocks:
            return []

        data_svc = UnifiedStockDataService()
        codes = [s.code for s in stocks if SignalService.has_model(s.code)]
        if not codes:
            return []

        signals = []
        trend_data = data_svc.get_trend_data(codes, days=120)

        for code in codes:
            stock_trend = trend_data.get(code)
            if not stock_trend or not stock_trend.get('data'):
                continue

            result = SignalService.get_signal(code, stock_trend['data'])
            if not result or result['signal'] == 'hold':
                continue
            if result['confidence'] < 0.6:
                continue

            stock = next((s for s in stocks if s.code == code), None)
            name = stock.name if stock else code
            action = '买入' if result['signal'] == 'buy' else '卖出'
            probs = result['probabilities']

            signals.append(Signal(
                strategy=self.name,
                priority='HIGH' if result['confidence'] >= 0.8 else 'MEDIUM',
                title=f'{name}({code}) AI {action}信号',
                detail=f"置信度 {result['confidence']:.0%} | 买入:{probs['buy']:.0%} 卖出:{probs['sell']:.0%} 持有:{probs['hold']:.0%}",
                data={'stock_code': code, **result},
            ))

        logger.info(f'[AI信号] 扫描 {len(codes)} 只, 产出 {len(signals)} 个信号')
        return signals
