from datetime import datetime
from app import db


class IndexTrendCache(db.Model):
    __tablename__ = 'index_trend_cache'
    __table_args__ = (
        db.UniqueConstraint('index_code', 'date', name='uq_index_date'),
        db.Index('idx_index_trend_cache_code_date', 'index_code', 'date'),
    )

    id = db.Column(db.Integer, primary_key=True)
    index_code = db.Column(db.String(20), nullable=False)
    date = db.Column(db.Date, nullable=False)
    price = db.Column(db.Float, nullable=False)
    volume = db.Column(db.BigInteger, nullable=True)  # 成交量
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
