from datetime import datetime
from app import db


class Category(db.Model):
    __tablename__ = 'categories'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(20), nullable=False)
    description = db.Column(db.Text, nullable=True)
    parent_id = db.Column(db.Integer, db.ForeignKey('categories.id', ondelete='CASCADE'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    parent = db.relationship('Category', remote_side=[id], backref='children')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'parent_id': self.parent_id,
            'full_name': f"{self.parent.name} - {self.name}" if self.parent else self.name
        }


class StockCategory(db.Model):
    __tablename__ = 'stock_categories'
    __table_args__ = (
        db.UniqueConstraint('stock_code', name='uq_stock_category'),
        db.Index('idx_stock_category_code', 'stock_code'),
    )

    id = db.Column(db.Integer, primary_key=True)
    stock_code = db.Column(db.String(6), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id', ondelete='SET NULL'), nullable=True)

    category = db.relationship('Category', backref='stocks')

    def to_dict(self):
        cat = self.category
        return {
            'stock_code': self.stock_code,
            'category_id': self.category_id,
            'category_name': cat.to_dict()['full_name'] if cat else None,
            'parent_id': cat.parent_id if cat else None
        }
