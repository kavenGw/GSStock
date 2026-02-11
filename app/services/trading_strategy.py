"""交易策略服务"""
from datetime import date
from app import db
from app.models.trading_strategy import TradingStrategy, StrategyExecution


class TradingStrategyService:
    """交易策略服务类"""

    # 策略分类
    CATEGORIES = {
        'index_timing': '指数择时',
        'sector_rotation': '板块轮动',
        'arbitrage': '套利策略',
        'trend_follow': '趋势跟踪',
        'mean_reversion': '均值回归',
        'general': '通用策略',
    }

    # 操作类型
    ACTION_TYPES = {
        'buy': '买入',
        'sell': '卖出',
        'switch': '换仓',
        'hold': '持有观望',
    }

    # 市场类型
    MARKETS = {
        'A': 'A股',
        'US': '美股',
        'HK': '港股',
        'ALL': '全市场',
    }

    @staticmethod
    def get_all_strategies(include_inactive=False):
        """获取所有策略"""
        query = TradingStrategy.query
        if not include_inactive:
            query = query.filter_by(is_active=True)
        strategies = query.order_by(TradingStrategy.priority.desc(), TradingStrategy.id.desc()).all()
        return [s.to_dict() for s in strategies]

    @staticmethod
    def get_strategies_by_category(category, include_inactive=False):
        """按分类获取策略"""
        query = TradingStrategy.query.filter_by(category=category)
        if not include_inactive:
            query = query.filter_by(is_active=True)
        strategies = query.order_by(TradingStrategy.priority.desc(), TradingStrategy.id.desc()).all()
        return [s.to_dict() for s in strategies]

    @staticmethod
    def get_strategy(strategy_id):
        """获取单个策略"""
        strategy = TradingStrategy.query.get(strategy_id)
        return strategy.to_dict() if strategy else None

    @staticmethod
    def create_strategy(data):
        """创建新策略"""
        strategy = TradingStrategy(
            name=data.get('name'),
            category=data.get('category', 'general'),
            trigger_condition=data.get('trigger_condition'),
            trigger_market=data.get('trigger_market'),
            trigger_index=data.get('trigger_index'),
            action_type=data.get('action_type'),
            sell_target=data.get('sell_target'),
            buy_target=data.get('buy_target'),
            description=data.get('description'),
            notes=data.get('notes'),
            is_active=data.get('is_active', True),
            priority=data.get('priority', 0),
        )
        db.session.add(strategy)
        db.session.commit()
        return strategy.to_dict()

    @staticmethod
    def update_strategy(strategy_id, data):
        """更新策略"""
        strategy = TradingStrategy.query.get(strategy_id)
        if not strategy:
            return None

        if 'name' in data:
            strategy.name = data['name']
        if 'category' in data:
            strategy.category = data['category']
        if 'trigger_condition' in data:
            strategy.trigger_condition = data['trigger_condition']
        if 'trigger_market' in data:
            strategy.trigger_market = data['trigger_market']
        if 'trigger_index' in data:
            strategy.trigger_index = data['trigger_index']
        if 'action_type' in data:
            strategy.action_type = data['action_type']
        if 'sell_target' in data:
            strategy.sell_target = data['sell_target']
        if 'buy_target' in data:
            strategy.buy_target = data['buy_target']
        if 'description' in data:
            strategy.description = data['description']
        if 'notes' in data:
            strategy.notes = data['notes']
        if 'is_active' in data:
            strategy.is_active = data['is_active']
        if 'priority' in data:
            strategy.priority = data['priority']

        db.session.commit()
        return strategy.to_dict()

    @staticmethod
    def delete_strategy(strategy_id):
        """删除策略"""
        strategy = TradingStrategy.query.get(strategy_id)
        if not strategy:
            return False
        db.session.delete(strategy)
        db.session.commit()
        return True

    @staticmethod
    def toggle_strategy(strategy_id):
        """切换策略启用状态"""
        strategy = TradingStrategy.query.get(strategy_id)
        if not strategy:
            return None
        strategy.is_active = not strategy.is_active
        db.session.commit()
        return strategy.to_dict()

    # 执行记录相关方法

    @staticmethod
    def record_execution(strategy_id, data):
        """记录策略执行"""
        strategy = TradingStrategy.query.get(strategy_id)
        if not strategy:
            return None

        execution_date = data.get('execution_date')
        if isinstance(execution_date, str):
            execution_date = date.fromisoformat(execution_date)
        elif execution_date is None:
            execution_date = date.today()

        execution = StrategyExecution(
            strategy_id=strategy_id,
            execution_date=execution_date,
            triggered_by=data.get('triggered_by'),
            action_taken=data.get('action_taken'),
            result=data.get('result'),
            profit_loss=data.get('profit_loss'),
            notes=data.get('notes'),
        )
        db.session.add(execution)
        db.session.commit()
        return execution.to_dict()

    @staticmethod
    def get_executions(strategy_id=None, start_date=None, end_date=None, limit=50):
        """获取执行记录"""
        query = StrategyExecution.query

        if strategy_id:
            query = query.filter_by(strategy_id=strategy_id)

        if start_date:
            if isinstance(start_date, str):
                start_date = date.fromisoformat(start_date)
            query = query.filter(StrategyExecution.execution_date >= start_date)

        if end_date:
            if isinstance(end_date, str):
                end_date = date.fromisoformat(end_date)
            query = query.filter(StrategyExecution.execution_date <= end_date)

        executions = query.order_by(StrategyExecution.execution_date.desc()).limit(limit).all()
        return [e.to_dict() for e in executions]

    @staticmethod
    def delete_execution(execution_id):
        """删除执行记录"""
        execution = StrategyExecution.query.get(execution_id)
        if not execution:
            return False
        db.session.delete(execution)
        db.session.commit()
        return True

    @staticmethod
    def get_statistics():
        """获取策略统计信息"""
        total_strategies = TradingStrategy.query.count()
        active_strategies = TradingStrategy.query.filter_by(is_active=True).count()
        total_executions = StrategyExecution.query.count()

        # 按分类统计
        category_stats = {}
        for category, name in TradingStrategyService.CATEGORIES.items():
            count = TradingStrategy.query.filter_by(category=category).count()
            if count > 0:
                category_stats[category] = {
                    'name': name,
                    'count': count
                }

        # 按结果统计执行记录
        result_stats = {}
        for result in ['success', 'partial', 'skipped']:
            count = StrategyExecution.query.filter_by(result=result).count()
            result_stats[result] = count

        # 计算总盈亏
        total_profit = db.session.query(db.func.sum(StrategyExecution.profit_loss)).scalar() or 0

        return {
            'total_strategies': total_strategies,
            'active_strategies': active_strategies,
            'total_executions': total_executions,
            'category_stats': category_stats,
            'result_stats': result_stats,
            'total_profit': total_profit,
        }
