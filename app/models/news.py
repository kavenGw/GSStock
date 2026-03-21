from datetime import datetime
from app import db


class NewsItem(db.Model):
    __tablename__ = 'news_item'
    __table_args__ = (
        db.UniqueConstraint('source_id', 'source_name', name='uq_news_source'),
    )

    id = db.Column(db.Integer, primary_key=True)
    source_id = db.Column(db.String(100), nullable=False)
    source_name = db.Column(db.String(50), default='wallstreetcn')
    content = db.Column(db.Text, nullable=False)
    display_time = db.Column(db.DateTime, nullable=False)
    score = db.Column(db.Integer, default=1)
    category = db.Column(db.String(20), default='other')
    importance = db.Column(db.Integer, default=0)
    is_interest = db.Column(db.Boolean, default=False)
    matched_keywords = db.Column(db.Text)
    matched_stocks = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.now)




class InterestKeyword(db.Model):
    __tablename__ = 'interest_keyword'

    id = db.Column(db.Integer, primary_key=True)
    keyword = db.Column(db.Text, nullable=False)
    source = db.Column(db.String(10), default='user')
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.now)


class CompanyKeyword(db.Model):
    __tablename__ = 'company_keyword'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Text, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    last_fetched_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now)


class IdentifiedCompany(db.Model):
    __tablename__ = 'identified_company'

    id = db.Column(db.Integer, primary_key=True)
    company_name = db.Column(db.String(100))
    stock_code = db.Column(db.String(20))
    news_content = db.Column(db.Text, nullable=False)
    reason = db.Column(db.Text)
    raw_result = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.now)
