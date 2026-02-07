from datetime import datetime, date
from app import db


class BankTransfer(db.Model):
    """银证转账记录"""
    __bind_key__ = 'private'
    __tablename__ = 'bank_transfers'

    id = db.Column(db.Integer, primary_key=True)
    transfer_date = db.Column(db.Date, nullable=False, index=True)
    transfer_type = db.Column(db.String(10), nullable=False)  # 'in' / 'out'
    amount = db.Column(db.Float, nullable=False)
    note = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'transfer_date': self.transfer_date.isoformat(),
            'transfer_type': self.transfer_type,
            'amount': self.amount,
            'note': self.note,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
