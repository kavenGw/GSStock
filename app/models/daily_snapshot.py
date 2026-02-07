from datetime import datetime, date
from app import db


class DailySnapshot(db.Model):
    """每日账户快照，保存从截图识别的总资产和当日盈亏"""
    __bind_key__ = 'private'
    __tablename__ = 'daily_snapshots'

    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False, unique=True)
    total_asset = db.Column(db.Float, nullable=True)  # 总资产
    daily_profit = db.Column(db.Float, nullable=True)  # 当日参考盈亏
    daily_profit_pct = db.Column(db.Float, nullable=True)  # 当日盈亏百分比
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'date': self.date.isoformat(),
            'total_asset': self.total_asset,
            'daily_profit': self.daily_profit,
            'daily_profit_pct': self.daily_profit_pct,
        }

    @classmethod
    def save_snapshot(cls, target_date: date, total_asset: float = None,
                      daily_profit: float = None, daily_profit_pct: float = None):
        """保存或更新每日快照"""
        snapshot = cls.query.filter_by(date=target_date).first()
        if snapshot:
            if total_asset is not None:
                snapshot.total_asset = total_asset
            if daily_profit is not None:
                snapshot.daily_profit = daily_profit
            if daily_profit_pct is not None:
                snapshot.daily_profit_pct = daily_profit_pct
        else:
            snapshot = cls(
                date=target_date,
                total_asset=total_asset,
                daily_profit=daily_profit,
                daily_profit_pct=daily_profit_pct,
            )
            db.session.add(snapshot)
        db.session.commit()
        return snapshot

    @classmethod
    def get_snapshot(cls, target_date: date):
        """获取指定日期的快照"""
        return cls.query.filter_by(date=target_date).first()

    @classmethod
    def get_all_snapshots(cls) -> list:
        """获取所有快照，按日期降序"""
        return cls.query.order_by(cls.date.desc()).all()
