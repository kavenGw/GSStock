from datetime import datetime
from app import db


class StockAlias(db.Model):
    """股票名称别名表

    用于处理同一股票在不同券商显示不同名称的情况
    例如：513850 在中信建投显示"美国50ETF易方达"，在东吴证券显示"美国50"
    """
    __tablename__ = 'stock_alias'

    id = db.Column(db.Integer, primary_key=True)
    alias_name = db.Column(db.String(50), nullable=False, unique=True, index=True)
    stock_code = db.Column(db.String(20), db.ForeignKey('stock.stock_code'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    stock = db.relationship('Stock', backref=db.backref('aliases', lazy='dynamic'))

    def to_dict(self):
        return {
            'id': self.id,
            'alias_name': self.alias_name,
            'stock_code': self.stock_code
        }
