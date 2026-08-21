from datetime import datetime

from app import db


class StockEvent(db.Model):
    """盯盘股/宏观重要事件 — 由 calendar_event 策略每日物化"""
    __tablename__ = 'stock_event'
    __table_args__ = (
        db.UniqueConstraint('event_type', 'stock_code', 'source', 'period_key',
                            name='uq_stock_event_business_key'),
        db.Index('idx_stock_event_date', 'event_date'),
    )

    id = db.Column(db.Integer, primary_key=True)
    event_date = db.Column(db.Date, nullable=False)
    event_type = db.Column(db.String(20), nullable=False)
    # 宏观事件存空串而非 NULL：SQLite 唯一索引中 NULL 互不相等，会导致去重失效
    stock_code = db.Column(db.String(20), nullable=False, default='')
    stock_name = db.Column(db.String(50))
    market = db.Column(db.String(10))
    title = db.Column(db.String(200), nullable=False)
    detail = db.Column(db.String(500))
    priority = db.Column(db.String(10), nullable=False, default='MEDIUM')
    source = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='scheduled')
    period_key = db.Column(db.String(20), nullable=False)
    extra = db.Column(db.Text)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    def to_dict(self):
        return {
            'id': self.id,
            'event_date': self.event_date.isoformat() if self.event_date else None,
            'event_type': self.event_type,
            'stock_code': self.stock_code,
            'stock_name': self.stock_name,
            'market': self.market,
            'title': self.title,
            'detail': self.detail,
            'priority': self.priority,
            'source': self.source,
            'status': self.status,
        }
