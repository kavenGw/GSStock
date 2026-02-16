from datetime import datetime
from app import db


class StockWeight(db.Model):
    """股票目标权重表"""
    __bind_key__ = 'private'
    __tablename__ = 'stock_weights'

    stock_code = db.Column(db.String(20), primary_key=True)
    weight = db.Column(db.Numeric(5, 2), nullable=False, default=1.0)
    selected = db.Column(db.Boolean, default=False)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    def to_dict(self):
        return {
            'stock_code': self.stock_code,
            'weight': float(self.weight),
            'selected': self.selected,
        }
