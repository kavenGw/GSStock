from datetime import datetime
from app import db


class Advice(db.Model):
    __bind_key__ = 'private'
    __tablename__ = 'advices'
    __table_args__ = (
        db.UniqueConstraint('date', 'stock_code', name='uq_advice_date_stock'),
        db.Index('idx_advice_date', 'date'),
    )

    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    stock_code = db.Column(db.String(20), nullable=False)
    support_price = db.Column(db.Float, nullable=True)
    resistance_price = db.Column(db.Float, nullable=True)
    strategy = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'date': self.date.isoformat(),
            'stock_code': self.stock_code,
            'support_price': self.support_price,
            'resistance_price': self.resistance_price,
            'strategy': self.strategy,
        }
