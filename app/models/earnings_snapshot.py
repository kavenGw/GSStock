from datetime import datetime, date
from app import db


class EarningsSnapshot(db.Model):
    """财报估值快照 — 每日预计算"""
    __tablename__ = 'earnings_snapshot'
    __table_args__ = (
        db.UniqueConstraint('stock_code', 'snapshot_date', name='uq_earnings_snapshot'),
        db.Index('idx_earnings_snapshot_date', 'snapshot_date'),
    )

    id = db.Column(db.Integer, primary_key=True)
    stock_code = db.Column(db.String(20), nullable=False)
    stock_name = db.Column(db.String(50))
    market_cap = db.Column(db.Float)

    q1_revenue = db.Column(db.Float)
    q2_revenue = db.Column(db.Float)
    q3_revenue = db.Column(db.Float)
    q4_revenue = db.Column(db.Float)
    q1_profit = db.Column(db.Float)
    q2_profit = db.Column(db.Float)
    q3_profit = db.Column(db.Float)
    q4_profit = db.Column(db.Float)

    q1_label = db.Column(db.String(10))
    q2_label = db.Column(db.String(10))
    q3_label = db.Column(db.String(10))
    q4_label = db.Column(db.String(10))

    pe_dynamic = db.Column(db.Float)
    ps_dynamic = db.Column(db.Float)

    snapshot_date = db.Column(db.Date, nullable=False, default=date.today)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'stock_code': self.stock_code,
            'stock_name': self.stock_name,
            'market_cap': self.market_cap,
            'quarters': [self.q1_label, self.q2_label, self.q3_label, self.q4_label],
            'revenue': [self.q1_revenue, self.q2_revenue, self.q3_revenue, self.q4_revenue],
            'profit': [self.q1_profit, self.q2_profit, self.q3_profit, self.q4_profit],
            'pe_dynamic': self.pe_dynamic,
            'ps_dynamic': self.ps_dynamic,
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M') if self.updated_at else None,
        }
