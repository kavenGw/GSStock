from datetime import datetime, date
import json
from app import db


class WyckoffAutoResult(db.Model):
    """威科夫自动分析结果模型"""
    __tablename__ = 'wyckoff_auto_result'
    __table_args__ = (
        db.UniqueConstraint('analysis_date', 'stock_code', name='uq_wyckoff_auto_date_stock'),
        db.Index('idx_wyckoff_auto_date', 'analysis_date'),
    )

    id = db.Column(db.Integer, primary_key=True)
    analysis_date = db.Column(db.Date, nullable=False)
    stock_code = db.Column(db.String(6), nullable=False)
    phase = db.Column(db.String(20), nullable=False)  # accumulation/markup/distribution/markdown
    events = db.Column(db.Text, nullable=True)  # JSON 数组
    advice = db.Column(db.String(20), nullable=False)  # buy/hold/sell/watch
    support_price = db.Column(db.Float, nullable=True)
    resistance_price = db.Column(db.Float, nullable=True)
    current_price = db.Column(db.Float, nullable=True)
    details = db.Column(db.Text, nullable=True)  # JSON 详情
    status = db.Column(db.String(20), default='success')  # success/failed/insufficient
    error_msg = db.Column(db.String(200), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        events_list = []
        if self.events:
            events_list = json.loads(self.events)
        details_dict = {}
        if self.details:
            details_dict = json.loads(self.details)
        return {
            'id': self.id,
            'analysis_date': self.analysis_date.isoformat() if self.analysis_date else None,
            'stock_code': self.stock_code,
            'phase': self.phase,
            'events': events_list,
            'advice': self.advice,
            'support_price': self.support_price,
            'resistance_price': self.resistance_price,
            'current_price': self.current_price,
            'details': details_dict,
            'status': self.status,
            'error_msg': self.error_msg,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class WyckoffReference(db.Model):
    """威科夫参考图模型"""
    __tablename__ = 'wyckoff_reference'

    id = db.Column(db.Integer, primary_key=True)
    phase = db.Column(db.String(20), nullable=False)  # accumulation/markup/distribution/markdown
    description = db.Column(db.Text, nullable=True)
    image_path = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'phase': self.phase,
            'description': self.description,
            'image_path': self.image_path,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class WyckoffAnalysis(db.Model):
    """威科夫分析记录模型"""
    __bind_key__ = 'private'
    __tablename__ = 'wyckoff_analysis'

    id = db.Column(db.Integer, primary_key=True)
    stock_code = db.Column(db.String(6), nullable=False, index=True)
    analysis_date = db.Column(db.Date, nullable=False)
    phase = db.Column(db.String(20), nullable=False)  # accumulation/markup/distribution/markdown
    event = db.Column(db.String(20), nullable=True)  # spring/shakeout/breakout/utad
    notes = db.Column(db.Text, nullable=True)
    image_path = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'stock_code': self.stock_code,
            'analysis_date': self.analysis_date.isoformat() if self.analysis_date else None,
            'phase': self.phase,
            'event': self.event,
            'notes': self.notes,
            'image_path': self.image_path,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
