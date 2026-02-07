from datetime import datetime
from app import db


class MetalTrendCache(db.Model):
    __tablename__ = 'metal_trend_cache'
    __table_args__ = (
        db.UniqueConstraint('metal_code', 'date', name='uq_metal_date'),
        db.Index('idx_metal_trend_cache_code_date', 'metal_code', 'date'),
    )

    id = db.Column(db.Integer, primary_key=True)
    metal_code = db.Column(db.String(10), nullable=False)  # AU0, AG0, CU0, AL0
    date = db.Column(db.Date, nullable=False)
    price = db.Column(db.Float, nullable=False)  # 收盘价
    volume = db.Column(db.BigInteger, nullable=True)  # 成交量
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
