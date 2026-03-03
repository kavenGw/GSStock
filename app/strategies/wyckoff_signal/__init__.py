"""威科夫信号策略 — 基于多周期分析的强信号检测"""
import logging
from app.strategies.base import Strategy, Signal

logger = logging.getLogger(__name__)


class WyckoffSignalStrategy(Strategy):
    name = "wyckoff_signal"
    description = "威科夫多周期信号（strong_buy/strong_sell）"
    schedule = "*/30 9-15 * * 1-5"
    needs_llm = True

    def scan(self) -> list[Signal]:
        from app.services.wyckoff import WyckoffAutoService
        from app.services.position import PositionService

        signals = []
        try:
            latest_date = PositionService.get_latest_date()
            if not latest_date:
                return signals

            positions = PositionService.get_snapshot(latest_date)
            stock_list = [{'code': p.stock_code, 'name': p.stock_name} for p in positions]
            if not stock_list:
                return signals

            config = self.get_config()
            strong_signals = config.get('strong_signals', ['strong_buy', 'strong_sell'])

            service = WyckoffAutoService()
            results = service.analyze_batch(stock_list)

            for r in results:
                if r.get('status') != 'success':
                    continue
                composite = r.get('composite_signal', '')
                if composite not in strong_signals:
                    continue

                is_sell = 'sell' in composite
                signals.append(Signal(
                    strategy=self.name,
                    priority="HIGH",
                    title=f"{r.get('stock_name', '')} 威科夫{('卖出' if is_sell else '买入')}信号",
                    detail=f"阶段: {r.get('phase', '')} | 信号: {composite} | 置信度: {r.get('confidence', 0):.0%}",
                    data=r,
                ))
        except Exception as e:
            logger.error(f'[威科夫信号] 扫描失败: {e}')

        return signals
