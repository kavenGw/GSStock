from datetime import datetime
from app import db


class Settlement(db.Model):
    __bind_key__ = 'private'
    __tablename__ = 'settlements'

    id = db.Column(db.Integer, primary_key=True)
    stock_code = db.Column(db.String(20), nullable=False, unique=True)
    stock_name = db.Column(db.String(50), nullable=False)
    total_buy_amount = db.Column(db.Float, nullable=False)
    total_sell_amount = db.Column(db.Float, nullable=False)
    profit = db.Column(db.Float, nullable=False)
    profit_pct = db.Column(db.Float, nullable=False)
    first_buy_date = db.Column(db.Date, nullable=False)
    last_sell_date = db.Column(db.Date, nullable=False)
    holding_days = db.Column(db.Integer, nullable=False)
    settled_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'stock_code': self.stock_code,
            'stock_name': self.stock_name,
            'total_buy_amount': self.total_buy_amount,
            'total_sell_amount': self.total_sell_amount,
            'profit': self.profit,
            'profit_pct': self.profit_pct,
            'first_buy_date': self.first_buy_date.isoformat(),
            'last_sell_date': self.last_sell_date.isoformat(),
            'holding_days': self.holding_days,
        }
