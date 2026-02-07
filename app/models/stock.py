from datetime import datetime
from app import db


class Stock(db.Model):
    """股票代码与名称映射表"""
    __tablename__ = 'stock'

    stock_code = db.Column(db.String(20), primary_key=True)
    stock_name = db.Column(db.String(50), nullable=False)
    investment_advice = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'stock_code': self.stock_code,
            'stock_name': self.stock_name,
            'investment_advice': self.investment_advice
        }
