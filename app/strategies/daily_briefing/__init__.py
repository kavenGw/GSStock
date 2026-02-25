"""每日简报策略 — 汇总市场数据生成日报"""
import logging
from app.strategies.base import Strategy, Signal

logger = logging.getLogger(__name__)


class DailyBriefingStrategy(Strategy):
    name = "daily_briefing"
    description = "每日简报（市场概况+持仓+预警）"
    schedule = "30 8 * * 1-5"
    needs_llm = True

    def scan(self) -> list[Signal]:
        from app.services.notification import NotificationService

        signals = []
        try:
            briefing = NotificationService.format_briefing_summary()
            alerts = NotificationService.format_alert_signals()

            parts = [briefing.get('text', '')]
            if alerts.get('text'):
                parts.append(alerts['text'])

            detail = '\n---\n'.join(parts)

            signals.append(Signal(
                strategy=self.name,
                priority="MEDIUM",
                title="每日简报",
                detail=detail,
                data={
                    'briefing_html': briefing.get('html', ''),
                    'alerts_html': alerts.get('html', ''),
                },
            ))
        except Exception as e:
            logger.error(f'[每日简报] 生成失败: {e}')

        return signals
