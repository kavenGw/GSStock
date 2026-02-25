"""价格预警策略 — 基于 SignalDetector 的4种信号"""
import logging
from app.strategies.base import Strategy, Signal

logger = logging.getLogger(__name__)


class PriceAlertStrategy(Strategy):
    name = "price_alert"
    description = "价格预警（缩量突破/新高/顶部巨量/MA5交叉）"
    schedule = "*/5 9-15 * * 1-5"

    def scan(self) -> list[Signal]:
        from app.services.position import PositionService
        from app.services.signal_cache import SignalCacheService
        from app.models.stock import Stock
        from app.utils.market_identifier import MarketIdentifier

        signals = []
        try:
            latest_date = PositionService.get_latest_date()
            if not latest_date:
                return signals

            positions = PositionService.get_snapshot(latest_date)
            a_share_codes = [p.stock_code for p in positions if MarketIdentifier.is_a_share(p.stock_code)]
            if not a_share_codes:
                return signals

            name_map = {}
            stocks = Stock.query.filter(Stock.stock_code.in_(a_share_codes)).all()
            for s in stocks:
                name_map[s.stock_code] = s.stock_name

            cached = SignalCacheService.get_cached_signals_with_names(a_share_codes, name_map)

            for sig_type in ['buy_signals', 'sell_signals']:
                for sig in cached.get(sig_type, []):
                    priority = "HIGH" if sig.get('type') == 'sell' else "MEDIUM"
                    signals.append(Signal(
                        strategy=self.name,
                        priority=priority,
                        title=f"{sig.get('stock_name', '')} - {sig.get('name', '')}",
                        detail=sig.get('description', ''),
                        data=sig,
                    ))
        except Exception as e:
            logger.error(f'[价格预警] 扫描失败: {e}')

        return signals
