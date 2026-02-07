from datetime import datetime
from app import db


class Trade(db.Model):
    __bind_key__ = 'private'
    __tablename__ = 'trades'
    __table_args__ = (
        db.Index('idx_trade_stock_code', 'stock_code'),
        db.Index('idx_trade_date', 'trade_date'),
    )

    id = db.Column(db.Integer, primary_key=True)
    trade_date = db.Column(db.Date, nullable=False)
    trade_time = db.Column(db.Time, nullable=True)
    stock_code = db.Column(db.String(6), nullable=False)
    stock_name = db.Column(db.String(50), nullable=False)
    trade_type = db.Column(db.String(4), nullable=False)  # 'buy' 或 'sell'
    quantity = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Float, nullable=False)
    amount = db.Column(db.Float, nullable=False)
    fee = db.Column(db.Float, nullable=True, default=0)  # 手续费（佣金+印花税+过户费）
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'trade_date': self.trade_date.isoformat(),
            'trade_time': self.trade_time.isoformat() if self.trade_time else None,
            'stock_code': self.stock_code,
            'stock_name': self.stock_name,
            'trade_type': self.trade_type,
            'quantity': self.quantity,
            'price': self.price,
            'amount': self.amount,
            'fee': self.fee or 0,
        }
