"""独立于股票交易日历的币安永续行情与推送。"""
import time
from datetime import datetime, timedelta, timezone

from app.config.binance_config import BINANCE_ALERT_THRESHOLD_PCT, BINANCE_ALERT_COOLDOWN_MINUTES
from app.config.notification_config import CHANNEL_WATCH
from app.services.binance_perpetual import binance_perpetual_service
from app.strategies.base import Strategy

CST = timezone(timedelta(hours=8))


def format_rows(rows, *, alert=False):
    lines = []
    for row in rows:
        label = f"*{row['name']} · {row['symbol']}*"
        if not row['available']:
            updated = row.get('updated_at')
            last = datetime.fromtimestamp(updated, CST).strftime('%m-%d %H:%M') if updated else '暂无'
            lines.append(f'{label}\n行情不可用（最后更新 {last}）')
            continue
        change = row.get('change_15m_pct')
        heading = ''
        if alert and change is not None:
            direction = '上涨' if change > 0 else '下跌'
            heading = f'*币安永续 · 15分钟{direction} {change:+.2f}%*\n'
        lines.append(
            f"{heading}{label}\n"
            f"最新价 {row['price']:g} {row['price_unit']} ｜24小时 {row['change_pct']:+.2f}%")
    return '\n\n'.join(lines)


def send_summary(rows, local):
    from app.services.notification import NotificationService
    from app.services.notification_tables import format_binance_summary

    title = f'币安永续 · 行情摘要 {local:%Y-%m-%d %H:%M} 北京时间'
    for message in format_binance_summary(rows, title):
        if NotificationService.send_slack(message['text'], CHANNEL_WATCH, blocks=message['blocks']):
            continue
        if not NotificationService.send_slack(message['text'], CHANNEL_WATCH):
            return False
    return True


class BinanceWatchStrategy(Strategy):
    name = 'binance_watch'
    description = '币安永续全天行情、十五分钟异动和北京时间早晚摘要'
    schedule = 'interval_minutes:1'

    def __init__(self):
        super().__init__()
        self._pushed = {}
        self._summary_slot = None

    def scan(self):
        from app.services.notification import NotificationService

        binance_perpetual_service.refresh()
        rows = binance_perpetual_service.snapshot()['data']
        if not rows:
            return []
        now = time.time()
        alerts = [r for r in rows if r['available'] and r['change_15m_pct'] is not None
                  and abs(r['change_15m_pct']) >= BINANCE_ALERT_THRESHOLD_PCT
                  and now - self._pushed.get(r['symbol'], 0) >= BINANCE_ALERT_COOLDOWN_MINUTES * 60]
        if alerts and NotificationService.send_slack(
                format_rows(alerts, alert=True), CHANNEL_WATCH):
            for row in alerts:
                self._pushed[row['symbol']] = now

        local = datetime.fromtimestamp(now, CST)
        slot = local.strftime('%Y-%m-%d %H')
        if local.hour in (9, 21) and local.minute < 5 and self._summary_slot != slot:
            if send_summary(rows, local):
                self._summary_slot = slot
        return []
