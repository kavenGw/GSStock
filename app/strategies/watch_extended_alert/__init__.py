"""美股暗盘异动推送 — 盘前/盘后涨跌超阈值合并一条推 Slack（只读缓存，不触发 API）"""
import logging

from app.strategies.base import Strategy, Signal

logger = logging.getLogger(__name__)


class WatchExtendedAlertStrategy(Strategy):
    name = "watch_extended_alert"
    description = "美股盘前/盘后暗盘异动推送"
    schedule = "interval_minutes:1"
    needs_llm = False

    # {code: 上次推送的 change_pct}，时段切换/结束即清空；进程内状态，重启可能重推一次
    _pushed = {}
    _session = None

    def _threshold(self) -> float:
        return float(self._config.get('threshold_pct', 3))

    def _restep(self) -> float:
        return float(self._config.get('restep_pct', 2))

    def scan(self) -> list[Signal]:
        from app.services.notification import NotificationService
        from app.services.trading_calendar import TradingCalendarService
        from app.services.unified_stock_data import unified_stock_data_service
        from app.services.watch_service import WatchService

        session = TradingCalendarService.get_us_session()
        if session == 'regular':
            session = None
        if session != self._session:
            self._pushed = {}
            self._session = session
        if not session:
            return []

        us = [e for e in WatchService.get_watch_list() if e['market'] == 'US']
        if not us:
            return []
        names = {e['stock_code']: e['stock_name'] for e in us}
        quotes = unified_stock_data_service.get_us_extended_cached(list(names))

        threshold, restep = self._threshold(), self._restep()
        rows = []
        for code, q in quotes.items():
            pct = q.get('change_pct')
            if pct is None or abs(pct) < threshold:
                continue
            last = self._pushed.get(code)
            if last is not None and abs(pct - last) < restep:
                continue
            rows.append({'code': code, 'name': names.get(code, code),
                         'price': q.get('price'), 'change_pct': pct})

        if not rows:
            return []
        rows.sort(key=lambda r: -abs(r['change_pct']))
        if NotificationService.push_extended_alerts(session, rows):
            for r in rows:
                self._pushed[r['code']] = r['change_pct']
        return []
