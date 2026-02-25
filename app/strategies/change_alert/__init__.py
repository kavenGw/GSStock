"""涨跌幅预警策略 — 基于实时价格的涨跌幅检测"""
import logging
from app.strategies.base import Strategy, Signal

logger = logging.getLogger(__name__)


class ChangeAlertStrategy(Strategy):
    name = "change_alert"
    description = "涨跌幅预警（超阈值触发）"
    schedule = "*/10 9-15 * * 1-5"

    def scan(self) -> list[Signal]:
        from app.services.unified_stock_data import unified_stock_data_service
        from app.services.position import PositionService

        signals = []
        try:
            latest_date = PositionService.get_latest_date()
            if not latest_date:
                return signals

            positions = PositionService.get_snapshot(latest_date)
            codes = [p.stock_code for p in positions]
            if not codes:
                return signals

            config = self.get_config()
            high_threshold = config.get('high_threshold', 5.0)
            low_threshold = config.get('low_threshold', -5.0)
            medium_threshold = config.get('medium_threshold', 3.0)

            result = unified_stock_data_service.get_realtime_prices(codes)
            prices = result.get('prices', [])

            for p in prices:
                change_pct = p.get('change_pct', 0)
                if not change_pct:
                    continue

                abs_change = abs(change_pct)
                if abs_change < medium_threshold:
                    continue

                if change_pct >= high_threshold or change_pct <= low_threshold:
                    priority = "HIGH"
                else:
                    priority = "MEDIUM"

                direction = "涨" if change_pct > 0 else "跌"
                signals.append(Signal(
                    strategy=self.name,
                    priority=priority,
                    title=f"{p.get('name', '')} 大幅{direction} {change_pct:+.2f}%",
                    detail=f"当前价: {p.get('price', 0)} | 成交量: {p.get('volume', 0):,}",
                    data=p,
                ))
        except Exception as e:
            logger.error(f'[涨跌幅预警] 扫描失败: {e}')

        return signals
