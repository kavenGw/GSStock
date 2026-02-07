from datetime import datetime, date
from app import db


class PreloadStatus(db.Model):
    """预加载状态模型"""
    __tablename__ = 'preload_status'

    id = db.Column(db.Integer, primary_key=True)
    preload_date = db.Column(db.Date, nullable=False, unique=True, index=True)
    status = db.Column(db.String(20), default='pending')  # pending/running/completed/failed
    total_count = db.Column(db.Integer, default=0)
    success_count = db.Column(db.Integer, default=0)
    failed_count = db.Column(db.Integer, default=0)
    current_stock = db.Column(db.String(50), nullable=True)  # 当前处理的股票
    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)

    def to_dict(self):
        return {
            'id': self.id,
            'preload_date': self.preload_date.isoformat() if self.preload_date else None,
            'status': self.status,
            'total_count': self.total_count,
            'success_count': self.success_count,
            'failed_count': self.failed_count,
            'current_stock': self.current_stock,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
        }
