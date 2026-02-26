from datetime import datetime
from app import db


class NewsItem(db.Model):
    __tablename__ = 'news_item'

    id = db.Column(db.Integer, primary_key=True)
    source_id = db.Column(db.BigInteger, unique=True, nullable=False)
    content = db.Column(db.Text, nullable=False)
    display_time = db.Column(db.DateTime, nullable=False)
    score = db.Column(db.Integer, default=1)
    category = db.Column(db.String(20), default='other')
    created_at = db.Column(db.DateTime, default=datetime.now)


class NewsBriefing(db.Model):
    __tablename__ = 'news_briefing'

    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    news_count = db.Column(db.Integer, default=0)
    period_start = db.Column(db.DateTime)
    period_end = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.now)
