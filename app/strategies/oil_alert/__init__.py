import logging
from datetime import datetime, timedelta, timezone

from app.strategies.base import Strategy

logger = logging.getLogger(__name__)


class OilAlertStrategy(Strategy):
    name = 'oil_alert'
    description = '原油行情档位与重要新闻提醒'
    schedule = 'interval_minutes:1'
    needs_llm = False

    def scan(self):
        from app import db
        from app.models.news import NewsItem
        from app.services.oil_alert_service import OilAlertService, OIL_CODES, LOCAL_ZONE
        from app.services.unified_stock_data import unified_stock_data_service

        now = datetime.now(timezone.utc)
        local_cutoff = (now - timedelta(hours=2)).astimezone(LOCAL_ZONE).replace(tzinfo=None)
        try:
            items = NewsItem.query.filter(NewsItem.display_time >= local_cutoff).all()
            OilAlertService.process_news(items, now.replace(tzinfo=None))
        except Exception:
            db.session.rollback()
            logger.exception('[原油提醒] 新闻扫描失败')
        try:
            prices = unified_stock_data_service.get_realtime_prices(list(OIL_CODES), cache_only=True)
            OilAlertService.process_quotes(prices, now.replace(tzinfo=None))
        except Exception:
            db.session.rollback()
            logger.exception('[原油提醒] 行情扫描失败')
        return []
