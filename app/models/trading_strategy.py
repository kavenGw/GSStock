"""交易策略模型"""
from datetime import datetime
from app import db


class TradingStrategy(db.Model):
    """交易策略模型

    用于存储和管理交易策略规则，例如：
    - 当纳指提前透支晚上涨幅，可以先卖出，买入达链或者谷歌链
    """
    __bind_key__ = 'private'
    __tablename__ = 'trading_strategies'
    __table_args__ = (
        db.Index('idx_strategy_active', 'is_active'),
        db.Index('idx_strategy_category', 'category'),
    )

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)  # 策略名称
    category = db.Column(db.String(50), nullable=False, default='general')  # 策略分类

    # 触发条件
    trigger_condition = db.Column(db.Text, nullable=False)  # 触发条件描述
    trigger_market = db.Column(db.String(20), nullable=True)  # 触发市场: A股/美股/港股
    trigger_index = db.Column(db.String(50), nullable=True)  # 触发指数代码

    # 操作建议
    action_type = db.Column(db.String(20), nullable=False)  # 操作类型: buy/sell/switch
    sell_target = db.Column(db.String(200), nullable=True)  # 卖出标的（多个用逗号分隔）
    buy_target = db.Column(db.String(200), nullable=True)  # 买入标的（多个用逗号分隔）

    # 详细描述
    description = db.Column(db.Text, nullable=True)  # 策略详细说明
    notes = db.Column(db.Text, nullable=True)  # 备注

    # 状态
    is_active = db.Column(db.Boolean, default=True)  # 是否启用
    priority = db.Column(db.Integer, default=0)  # 优先级，数值越大优先级越高

    # 时间戳
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'category': self.category,
            'trigger_condition': self.trigger_condition,
            'trigger_market': self.trigger_market,
            'trigger_index': self.trigger_index,
            'action_type': self.action_type,
            'sell_target': self.sell_target,
            'buy_target': self.buy_target,
            'description': self.description,
            'notes': self.notes,
            'is_active': self.is_active,
            'priority': self.priority,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class StrategyExecution(db.Model):
    """策略执行记录"""
    __bind_key__ = 'private'
    __tablename__ = 'strategy_executions'
    __table_args__ = (
        db.Index('idx_execution_date', 'execution_date'),
        db.Index('idx_execution_strategy', 'strategy_id'),
    )

    id = db.Column(db.Integer, primary_key=True)
    strategy_id = db.Column(db.Integer, db.ForeignKey('trading_strategies.id'), nullable=False)
    execution_date = db.Column(db.Date, nullable=False)

    # 执行详情
    triggered_by = db.Column(db.String(200), nullable=True)  # 触发原因
    action_taken = db.Column(db.Text, nullable=True)  # 实际执行的操作
    result = db.Column(db.String(20), nullable=True)  # 执行结果: success/partial/skipped
    profit_loss = db.Column(db.Float, nullable=True)  # 盈亏金额
    notes = db.Column(db.Text, nullable=True)  # 执行备注

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # 关联
    strategy = db.relationship('TradingStrategy', backref=db.backref('executions', lazy='dynamic'))

    def to_dict(self):
        return {
            'id': self.id,
            'strategy_id': self.strategy_id,
            'strategy_name': self.strategy.name if self.strategy else None,
            'execution_date': self.execution_date.isoformat() if self.execution_date else None,
            'triggered_by': self.triggered_by,
            'action_taken': self.action_taken,
            'result': self.result,
            'profit_loss': self.profit_loss,
            'notes': self.notes,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
