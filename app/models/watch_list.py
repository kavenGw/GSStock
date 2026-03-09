from datetime import datetime
from app import db


class WatchList(db.Model):
    """盯盘列表"""
    __tablename__ = 'watch_list'

    id = db.Column(db.Integer, primary_key=True)
    stock_code = db.Column(db.String(20), nullable=False, unique=True)
    stock_name = db.Column(db.String(50))
    market = db.Column(db.String(10))  # 'A', 'US', 'HK'
    added_at = db.Column(db.DateTime, default=datetime.utcnow)


class WatchAnalysis(db.Model):
    """盯盘AI分析结果"""
    __tablename__ = 'watch_analysis'
    __table_args__ = (
        db.UniqueConstraint('stock_code', 'analysis_date', 'period', name='uq_watch_analysis_code_date_period'),
    )

    id = db.Column(db.Integer, primary_key=True)
    stock_code = db.Column(db.String(20), nullable=False)
    analysis_date = db.Column(db.Date, nullable=False)
    period = db.Column(db.String(10), nullable=False, default='30d')
    support_levels = db.Column(db.Text)
    resistance_levels = db.Column(db.Text)
    analysis_summary = db.Column(db.Text)
    signal = db.Column(db.String(10))  # buy/sell/hold/watch
    analysis_detail = db.Column(db.Text)  # JSON: {signal_text, ma_levels, price_range}
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
