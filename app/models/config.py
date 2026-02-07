from datetime import datetime
from app import db


class Config(db.Model):
    __tablename__ = 'configs'
    __bind_key__ = 'private'

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True, nullable=False)
    value = db.Column(db.String(200), nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

    @staticmethod
    def get_value(key: str, default=None):
        """获取配置值"""
        config = Config.query.filter_by(key=key).first()
        return config.value if config else default

    @staticmethod
    def set_value(key: str, value: str):
        """设置配置值"""
        config = Config.query.filter_by(key=key).first()
        if config:
            config.value = value
            config.updated_at = datetime.utcnow()
        else:
            config = Config(key=key, value=value)
            db.session.add(config)
        db.session.commit()
