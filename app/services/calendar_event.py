"""事件日历服务 — 采集并物化盯盘股/宏观重要事件"""
import json
import logging
from datetime import date, datetime

from app import db
from app.models.stock_event import StockEvent

logger = logging.getLogger(__name__)

PRIORITY_ORDER = {'HIGH': 0, 'MEDIUM': 1, 'LOW': 2}

_WRITABLE_FIELDS = ('event_date', 'stock_name', 'market', 'title',
                    'detail', 'priority', 'status')


class CalendarEventService:
    """事件日历服务"""

    @staticmethod
    def upsert_events(events: list[dict]) -> list[int]:
        """按业务键 (event_type, stock_code, source, period_key) upsert，返回命中行 id"""
        ids = []
        for e in events:
            key = {
                'event_type': e['event_type'],
                'stock_code': e.get('stock_code') or '',
                'source': e['source'],
                'period_key': e['period_key'],
            }
            row = StockEvent.query.filter_by(**key).first()
            if row is None:
                row = StockEvent(**key)
                db.session.add(row)

            for f in _WRITABLE_FIELDS:
                if f in e:
                    setattr(row, f, e[f])
            extra = e.get('extra')
            row.extra = json.dumps(extra, ensure_ascii=False) if extra else None
            row.updated_at = datetime.now()

            db.session.flush()
            ids.append(row.id)

        db.session.commit()
        return ids

    @staticmethod
    def prune_stale(start: date, end: date, keep_ids: list[int],
                    sources: list[str]) -> int:
        """删除窗口内、属于 sources、且本轮未命中的行。manual 永不删除。"""
        if not sources:
            return 0

        q = StockEvent.query.filter(
            StockEvent.source.in_(sources),
            StockEvent.source != 'manual',
            StockEvent.event_date >= start,
            StockEvent.event_date <= end,
        )
        if keep_ids:
            q = q.filter(~StockEvent.id.in_(keep_ids))

        n = q.delete(synchronize_session=False)
        db.session.commit()
        return n

    @staticmethod
    def get_events(start: date, end: date) -> list[dict]:
        rows = StockEvent.query.filter(
            StockEvent.event_date >= start,
            StockEvent.event_date <= end,
        ).all()
        rows.sort(key=lambda r: (r.event_date,
                                 PRIORITY_ORDER.get(r.priority, 1),
                                 r.stock_code or ''))
        return [r.to_dict() for r in rows]

    @staticmethod
    def hours_since_refresh() -> float | None:
        """距最近一次采集的小时数；表为空返回 None"""
        latest = db.session.query(db.func.max(StockEvent.updated_at)).scalar()
        if not latest:
            return None
        return (datetime.now() - latest).total_seconds() / 3600
