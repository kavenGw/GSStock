"""盯盘助手策略 — 实时监控关注股票的价格波动"""
import logging
from datetime import datetime

from app.strategies.base import Strategy, Signal
from app.services.trading_calendar import TradingCalendarService
from app.utils.market_identifier import MarketIdentifier

logger = logging.getLogger(__name__)


class WatchAssistantStrategy(Strategy):
    name = "watch_assistant"
    description = "盯盘助手 — 实时监控关注股票的价格波动"
    schedule = ""
    needs_llm = True
    enabled = True

    def __init__(self):
        super().__init__()
        self._last_prices = {}
        self._last_notified = {}

    def scan(self) -> list[Signal]:
        from app.services.watch_service import WatchService
        from app.services.unified_stock_data import unified_stock_data_service

        watch_codes = WatchService.get_watch_codes()
        if not watch_codes:
            return []

        # 按市场分组，仅获取当前交易中的市场
        active_codes = []
        for code in watch_codes:
            market = MarketIdentifier.identify(code) or 'A'
            if TradingCalendarService.is_market_open(market):
                active_codes.append(code)

        if not active_codes:
            return []

        result = unified_stock_data_service.get_realtime_prices(active_codes)
        prices = result.get('prices', [])

        analyses = WatchService.get_all_today_analyses()
        config = self.get_config()
        default_threshold = config.get('default_volatility_threshold', 0.02)
        cooldown = config.get('notification_cooldown_minutes', 30)

        signals = []
        for p in prices:
            code = p.get('code', '')
            current_price = p.get('price', 0)
            if not code or not current_price:
                continue

            last_price = self._last_prices.get(code)
            self._last_prices[code] = current_price

            if last_price is None:
                continue

            change_pct = abs(current_price - last_price) / last_price
            analysis = analyses.get(code, {})
            threshold = analysis.get('volatility_threshold') or default_threshold

            if change_pct < threshold:
                continue

            # 通知冷却检查
            last_notify = self._last_notified.get(code)
            if last_notify and (datetime.now() - last_notify).total_seconds() < cooldown * 60:
                continue

            self._last_notified[code] = datetime.now()

            direction = "上涨" if current_price > last_price else "下跌"
            pct_display = (current_price - last_price) / last_price * 100
            detail_parts = [f"当前价: {current_price:.2f} | 变动: {pct_display:+.2f}%"]

            support = analysis.get('support_levels', [])
            resistance = analysis.get('resistance_levels', [])
            if support:
                nearest_support = min(support, key=lambda x: abs(x - current_price))
                dist = (current_price - nearest_support) / nearest_support * 100
                detail_parts.append(f"距支撑位 {nearest_support}: {dist:+.2f}%")
            if resistance:
                nearest_resist = min(resistance, key=lambda x: abs(x - current_price))
                dist = (current_price - nearest_resist) / nearest_resist * 100
                detail_parts.append(f"距阻力位 {nearest_resist}: {dist:+.2f}%")

            summary = analysis.get('summary', '')
            if summary:
                detail_parts.append(f"AI: {summary}")

            signals.append(Signal(
                strategy=self.name,
                priority="HIGH" if change_pct >= threshold * 2 else "MEDIUM",
                title=f"盯盘提醒 | {p.get('name', code)}({code}) {direction} {pct_display:+.2f}%",
                detail="\n".join(detail_parts),
                data={'stock_code': code, 'price': current_price, 'change_pct': pct_display},
            ))

        return signals
