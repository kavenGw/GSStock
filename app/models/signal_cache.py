from datetime import datetime
from app import db


class SignalCache(db.Model):
    """买卖点信号缓存模型"""
    __tablename__ = 'signal_cache'
    __table_args__ = (
        db.Index('idx_signal_cache_code_date', 'stock_code', 'signal_date'),
    )

    id = db.Column(db.Integer, primary_key=True)
    stock_code = db.Column(db.String(20), nullable=False)  # 股票/期货代码
    signal_date = db.Column(db.Date, nullable=False)  # 信号发生日期
    signal_type = db.Column(db.String(10), nullable=False)  # buy / sell
    signal_name = db.Column(db.String(50), nullable=False)  # 信号名称
    description = db.Column(db.String(200), nullable=True)  # 信号描述
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'stock_code': self.stock_code,
            'date': self.signal_date.isoformat() if self.signal_date else None,
            'type': self.signal_type,
            'name': self.signal_name,
            'description': self.description,
        }
