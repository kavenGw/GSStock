from datetime import datetime
from app import db


class RebalanceConfig(db.Model):
    """仓位管理配置表 - 保存目标总市值等配置"""
    __bind_key__ = 'private'
    __tablename__ = 'rebalance_config'

    id = db.Column(db.Integer, primary_key=True)
    target_value = db.Column(db.Float, nullable=False, default=0)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    @staticmethod
    def get_config():
        """获取配置，不存在则创建"""
        config = RebalanceConfig.query.first()
        if not config:
            config = RebalanceConfig(target_value=0)
            db.session.add(config)
            db.session.commit()
        return config

    @staticmethod
    def save_target_value(value):
        """保存目标总市值"""
        config = RebalanceConfig.get_config()
        config.target_value = value
        db.session.commit()
        return config
