from datetime import datetime
from app import db


class PositionPlan(db.Model):
    """仓位计划表 - 保存仓位管理的计算结果"""
    __bind_key__ = 'private'
    __tablename__ = 'position_plans'

    id = db.Column(db.Integer, primary_key=True)
    stock_code = db.Column(db.String(20), nullable=False, index=True)
    stock_name = db.Column(db.String(20), nullable=True)
    target_value = db.Column(db.Float, nullable=False)
    current_value = db.Column(db.Float, nullable=False, default=0)
    diff = db.Column(db.Float, nullable=False, default=0)
    operation = db.Column(db.String(10), nullable=False)  # buy/sell/hold
    shares = db.Column(db.Integer, nullable=False, default=0)
    weight = db.Column(db.Float, nullable=False, default=1.0)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    def to_dict(self):
        return {
            'stock_code': self.stock_code,
            'stock_name': self.stock_name,
            'target_value': self.target_value,
            'current_value': self.current_value,
            'diff': self.diff,
            'operation': self.operation,
            'shares': self.shares,
            'weight': self.weight,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
