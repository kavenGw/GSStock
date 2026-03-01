from datetime import datetime
from app import db


class DramPrice(db.Model):
    __tablename__ = 'dram_price'
    __table_args__ = (
        db.UniqueConstraint('date', 'spec', name='uq_dram_price_date_spec'),
        db.Index('idx_dram_price_date', 'date'),
    )

    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    spec = db.Column(db.String(50), nullable=False)  # DDR5_16Gb, DDR4_8Gb, DDR4_16Gb
    avg_price = db.Column(db.Float, nullable=False)
    high_price = db.Column(db.Float, nullable=True)
    low_price = db.Column(db.Float, nullable=True)
    change_pct = db.Column(db.Float, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
