from datetime import datetime, date
from app import db


class Position(db.Model):
    __bind_key__ = 'private'
    __tablename__ = 'positions'
    __table_args__ = (
        db.UniqueConstraint('date', 'stock_code', name='uq_position_date_stock'),
        db.Index('idx_position_date', 'date'),
    )

    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    stock_code = db.Column(db.String(6), nullable=False)
    stock_name = db.Column(db.String(50), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    total_amount = db.Column(db.Float, nullable=False)  # 总金额
    current_price = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def cost_price(self) -> float:
        """成本价 = 总金额 / 持股数"""
        if self.quantity and self.quantity > 0:
            return self.total_amount / self.quantity
        return 0.0

    def to_dict(self):
        return {
            'id': self.id,
            'date': self.date.isoformat(),
            'stock_code': self.stock_code,
            'stock_name': self.stock_name,
            'quantity': self.quantity,
            'total_amount': self.total_amount,
            'cost_price': self.cost_price,
            'current_price': self.current_price,
        }
