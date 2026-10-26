from app import db


class OilAlert(db.Model):
    __tablename__ = 'oil_alert'

    key = db.Column(db.String(160), primary_key=True)
    target_band = db.Column(db.Integer, nullable=False)
    sent_band = db.Column(db.Integer, nullable=False, default=0)
    message = db.Column(db.Text, nullable=False)
    channel = db.Column(db.String(80), nullable=False)
    source = db.Column(db.String(20), nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    lease_until = db.Column(db.DateTime, nullable=True)
    sent_at = db.Column(db.DateTime, nullable=True)
