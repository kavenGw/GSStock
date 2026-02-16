import logging
from datetime import date, timedelta
from collections import defaultdict
from sqlalchemy import func
from app import db
from app.models.trade import Trade
from app.models.settlement import Settlement
from app.models.category import StockCategory
from app.services.unified_stock_data import UnifiedStockDataService

logger = logging.getLogger(__name__)


class TradeService:
    @staticmethod
    def save_trade(data: dict) -> Trade:
        """保存单条交易记录"""
        logger.debug(f"[交易] 保存交易记录: {data.get('stock_code')} {data.get('trade_type')}")
        trade = Trade(
            trade_date=date.fromisoformat(data['trade_date']) if isinstance(data['trade_date'], str) else data['trade_date'],
            trade_time=data.get('trade_time'),
            stock_code=data['stock_code'],
            stock_name=data['stock_name'],
            trade_type=data['trade_type'],
            quantity=data['quantity'],
            price=data['price'],
            amount=data['quantity'] * data['price'],
            fee=data.get('fee', 0),
        )
        db.session.add(trade)
        db.session.commit()
        logger.debug(f"[交易] 交易记录保存成功: id={trade.id}")
        return trade

    @staticmethod
    def get_trades(stock_code: str = None, trade_type: str = None) -> list[Trade]:
        """获取交易列表，支持筛选"""
        query = Trade.query
        if stock_code:
            query = query.filter(Trade.stock_code == stock_code)
        if trade_type:
            query = query.filter(Trade.trade_type == trade_type)
        return query.order_by(Trade.trade_date.desc(), Trade.id.desc()).all()

    @staticmethod
    def get_trade(trade_id: int) -> Trade | None:
        """获取单条交易记录"""
        return Trade.query.get(trade_id)

    @staticmethod
    def delete_trade(trade_id: int) -> bool:
        """删除交易记录并清除相关结算"""
        trade = Trade.query.get(trade_id)
        if not trade:
            return False

        stock_code = trade.stock_code
        logger.debug(f"[交易] 删除交易记录: id={trade_id}, stock={stock_code}")

        db.session.delete(trade)

        # 删除该股票的结算记录
        settlement = Settlement.query.filter_by(stock_code=stock_code).first()
        if settlement:
            logger.debug(f"[交易] 同步删除结算记录: stock={stock_code}")
            db.session.delete(settlement)

        db.session.commit()
        return True

    @staticmethod
    def update_trade(trade_id: int, data: dict) -> Trade | None:
        """更新交易记录"""
        trade = Trade.query.get(trade_id)
        if not trade:
            return None

        logger.debug(f"[交易] 更新交易记录: id={trade_id}")
        stock_code = trade.stock_code

        if 'trade_date' in data:
            trade.trade_date = date.fromisoformat(data['trade_date']) if isinstance(data['trade_date'], str) else data['trade_date']
        if 'trade_type' in data:
            trade.trade_type = data['trade_type']
        if 'quantity' in data:
            trade.quantity = data['quantity']
        if 'price' in data:
            trade.price = data['price']
        if 'fee' in data:
            trade.fee = data['fee']

        trade.amount = trade.quantity * trade.price

        # 删除该股票的结算记录
        settlement = Settlement.query.filter_by(stock_code=stock_code).first()
        if settlement:
            logger.debug(f"[交易] 因交易更新删除结算记录: stock={stock_code}")
            db.session.delete(settlement)

        db.session.commit()
        return trade

    @staticmethod
    def check_settlement(stock_code: str) -> dict:
        """检查股票是否可结算（买入总量==卖出总量）"""
        trades = Trade.query.filter_by(stock_code=stock_code).all()
        if not trades:
            return {'can_settle': False, 'reason': '无交易记录'}

        buy_qty = sum(t.quantity for t in trades if t.trade_type == 'buy')
        sell_qty = sum(t.quantity for t in trades if t.trade_type == 'sell')

        if buy_qty == 0:
            return {'can_settle': False, 'reason': '无买入记录'}
        if sell_qty == 0:
            return {'can_settle': False, 'reason': '无卖出记录'}
        if buy_qty != sell_qty:
            return {
                'can_settle': False,
                'reason': f'持仓未清零（买入{buy_qty}股，卖出{sell_qty}股）',
                'remaining': buy_qty - sell_qty
            }

        return {'can_settle': True}

    @staticmethod
    def settle_stock(stock_code: str) -> Settlement | None:
        """结算股票"""
        check = TradeService.check_settlement(stock_code)
        if not check['can_settle']:
            logger.warning(f"[交易.结算] 结算失败: {stock_code} - {check['reason']}")
            return None

        trades = Trade.query.filter_by(stock_code=stock_code).all()
        buy_trades = [t for t in trades if t.trade_type == 'buy']
        sell_trades = [t for t in trades if t.trade_type == 'sell']

        total_buy_amount = sum(t.amount for t in buy_trades)
        total_sell_amount = sum(t.amount for t in sell_trades)
        total_fee = sum(t.fee or 0 for t in trades)
        profit = total_sell_amount - total_buy_amount - total_fee
        profit_pct = (profit / total_buy_amount * 100) if total_buy_amount > 0 else 0

        first_buy_date = min(t.trade_date for t in buy_trades)
        last_sell_date = max(t.trade_date for t in sell_trades)
        holding_days = (last_sell_date - first_buy_date).days

        stock_name = trades[0].stock_name

        # 删除已有的结算记录
        existing = Settlement.query.filter_by(stock_code=stock_code).first()
        if existing:
            db.session.delete(existing)

        settlement = Settlement(
            stock_code=stock_code,
            stock_name=stock_name,
            total_buy_amount=total_buy_amount,
            total_sell_amount=total_sell_amount,
            profit=profit,
            profit_pct=profit_pct,
            first_buy_date=first_buy_date,
            last_sell_date=last_sell_date,
            holding_days=holding_days,
        )
        db.session.add(settlement)
        db.session.commit()

        logger.info(f"[交易.结算] 结算成功: {stock_code}, 盈亏={profit:.2f}")
        return settlement

    @staticmethod
    def get_settlements() -> list[Settlement]:
        """获取所有已结算记录"""
        return Settlement.query.order_by(Settlement.settled_at.desc()).all()

    @staticmethod
    def get_chart_data() -> dict:
        """获取图表数据"""
        settlements = Settlement.query.order_by(Settlement.last_sell_date.asc()).all()

        # 获取股票分类映射
        stock_categories = {sc.stock_code: sc.category for sc in StockCategory.query.all()}

        # 盈亏分布（按股票）
        profit_distribution = [
            {
                'stock_code': s.stock_code,
                'stock_name': s.stock_name,
                'profit': s.profit,
            }
            for s in settlements
        ]

        # 按分类汇总
        category_profits = {}
        for s in settlements:
            category = stock_categories.get(s.stock_code)
            if category:
                cat_name = f"{category.parent.name} - {category.name}" if category.parent else category.name
            else:
                cat_name = '未分类'

            if cat_name not in category_profits:
                category_profits[cat_name] = 0
            category_profits[cat_name] += s.profit

        by_category = [
            {'category': name, 'total_profit': round(profit, 2)}
            for name, profit in category_profits.items()
        ]
        by_category.sort(key=lambda x: x['total_profit'], reverse=True)

        # 累计盈亏
        cumulative_profit = []
        cumulative = 0
        for s in settlements:
            cumulative += s.profit
            cumulative_profit.append({
                'date': s.last_sell_date.isoformat(),
                'cumulative': cumulative,
                'stock_name': s.stock_name,
            })

        # 统计摘要
        total_trades = Trade.query.count()
        total_settlements = len(settlements)
        total_profit = sum(s.profit for s in settlements)
        win_count = sum(1 for s in settlements if s.profit > 0)
        win_rate = (win_count / total_settlements * 100) if total_settlements > 0 else 0

        return {
            'profit_distribution': profit_distribution,
            'by_category': by_category,
            'cumulative_profit': cumulative_profit,
            'summary': {
                'total_trades': total_trades,
                'total_settlements': total_settlements,
                'total_profit': total_profit,
                'win_rate': win_rate,
            }
        }

    @staticmethod
    def get_stock_codes() -> list[str]:
        """获取所有有交易记录的股票代码"""
        results = db.session.query(Trade.stock_code).distinct().all()
        return [r[0] for r in results]

    @staticmethod
    def get_stock_codes_with_names() -> list[dict]:
        """获取所有有交易记录的股票代码和名称"""
        results = db.session.query(Trade.stock_code, Trade.stock_name).distinct().all()
        return [{'code': r[0], 'name': r[1] or ''} for r in results]

    @staticmethod
    def get_list_charts_data(days: int = None, stock_code: str = None) -> dict:
        """获取列表页图表数据"""
        query = Trade.query

        if days:
            start_date = date.today() - timedelta(days=days)
            query = query.filter(Trade.trade_date >= start_date)
        if stock_code:
            query = query.filter(Trade.stock_code == stock_code)

        trades = query.order_by(Trade.trade_date.asc()).all()

        if not trades:
            return {'amount_distribution': [], 'buy_sell_compare': [], 'trade_frequency': []}

        # 交易金额分布（按股票）
        stock_amounts = defaultdict(float)
        for t in trades:
            stock_amounts[t.stock_name or t.stock_code] += t.amount

        amount_distribution = [
            {'name': name, 'value': round(amount, 2)}
            for name, amount in sorted(stock_amounts.items(), key=lambda x: x[1], reverse=True)
        ]

        # 买卖对比（按股票）
        buy_amounts = defaultdict(float)
        sell_amounts = defaultdict(float)
        for t in trades:
            key = t.stock_name or t.stock_code
            if t.trade_type == 'buy':
                buy_amounts[key] += t.amount
            else:
                sell_amounts[key] += t.amount

        all_stocks = set(buy_amounts.keys()) | set(sell_amounts.keys())
        buy_sell_compare = [
            {
                'name': name,
                'buy': round(buy_amounts.get(name, 0), 2),
                'sell': round(sell_amounts.get(name, 0), 2)
            }
            for name in sorted(all_stocks)
        ]

        # 交易频率（按日期）
        date_counts = defaultdict(lambda: {'buy': 0, 'sell': 0, 'amount': 0})
        for t in trades:
            d = t.trade_date.isoformat()
            date_counts[d][t.trade_type] += 1
            date_counts[d]['amount'] += t.amount

        trade_frequency = [
            {
                'date': d,
                'buy_count': data['buy'],
                'sell_count': data['sell'],
                'total_amount': round(data['amount'], 2)
            }
            for d, data in sorted(date_counts.items())
        ]

        return {
            'amount_distribution': amount_distribution,
            'buy_sell_compare': buy_sell_compare,
            'trade_frequency': trade_frequency,
        }

    @staticmethod
    def get_timeline_data(stock_code: str, days: int = 60) -> dict:
        """获取单股交易时间线（含K线数据）"""
        start_date = date.today() - timedelta(days=days)
        trades = Trade.query.filter(
            Trade.stock_code == stock_code,
            Trade.trade_date >= start_date
        ).order_by(Trade.trade_date.asc()).all()

        if not trades:
            return {'stock_code': stock_code, 'stock_name': '', 'trades': [], 'ohlc': []}

        stock_name = trades[0].stock_name

        trade_list = [
            {
                'date': t.trade_date.isoformat(),
                'type': t.trade_type,
                'quantity': t.quantity,
                'price': t.price,
                'amount': round(t.amount, 2)
            }
            for t in trades
        ]

        # 获取OHLC K线数据
        ohlc_data = []
        try:
            unified_service = UnifiedStockDataService()
            trend_result = unified_service.get_trend_data([stock_code], days)
            if trend_result.get('stocks'):
                stock_trend = trend_result['stocks'][0]
                ohlc_data = stock_trend.get('data', [])
        except Exception as e:
            logger.warning(f"[交易] 获取K线数据失败: {stock_code}, {e}")

        return {
            'stock_code': stock_code,
            'stock_name': stock_name,
            'trades': trade_list,
            'ohlc': ohlc_data
        }

    @staticmethod
    def get_category_profit() -> dict:
        """获取分类收益数据"""
        settlements = Settlement.query.all()
        stock_categories = {sc.stock_code: sc.category for sc in StockCategory.query.all()}

        # 按分类层级组织数据
        category_data = defaultdict(lambda: {'value': 0, 'children': defaultdict(float)})

        for s in settlements:
            category = stock_categories.get(s.stock_code)
            if category:
                if category.parent:
                    parent_name = category.parent.name
                    child_name = category.name
                else:
                    parent_name = category.name
                    child_name = None
            else:
                parent_name = '未分类'
                child_name = None

            category_data[parent_name]['value'] += s.profit
            if child_name:
                category_data[parent_name]['children'][child_name] += s.profit

        # 转换为旭日图数据格式
        sunburst_data = []
        for parent_name, data in category_data.items():
            item = {
                'name': parent_name,
                'value': round(data['value'], 2)
            }
            if data['children']:
                item['children'] = [
                    {'name': name, 'value': round(value, 2)}
                    for name, value in data['children'].items()
                ]
            sunburst_data.append(item)

        return {'sunburst': sunburst_data}

    @staticmethod
    def get_period_trend(period: str = 'month') -> dict:
        """获取月度/季度趋势"""
        settlements = Settlement.query.order_by(Settlement.last_sell_date.asc()).all()
        trades = Trade.query.all()

        if not settlements and not trades:
            return {'labels': [], 'profits': [], 'trade_counts': [], 'win_rates': []}

        # 按周期汇总
        period_data = defaultdict(lambda: {'profit': 0, 'trade_count': 0, 'win_count': 0, 'total_count': 0})

        for s in settlements:
            if period == 'month':
                key = s.last_sell_date.strftime('%Y-%m')
            else:  # quarter
                q = (s.last_sell_date.month - 1) // 3 + 1
                key = f"{s.last_sell_date.year}-Q{q}"

            period_data[key]['profit'] += s.profit
            period_data[key]['total_count'] += 1
            if s.profit > 0:
                period_data[key]['win_count'] += 1

        for t in trades:
            if period == 'month':
                key = t.trade_date.strftime('%Y-%m')
            else:
                q = (t.trade_date.month - 1) // 3 + 1
                key = f"{t.trade_date.year}-Q{q}"
            period_data[key]['trade_count'] += 1

        sorted_keys = sorted(period_data.keys())

        return {
            'labels': sorted_keys,
            'profits': [round(period_data[k]['profit'], 2) for k in sorted_keys],
            'trade_counts': [period_data[k]['trade_count'] for k in sorted_keys],
            'win_rates': [
                round(period_data[k]['win_count'] / period_data[k]['total_count'] * 100, 1)
                if period_data[k]['total_count'] > 0 else 0
                for k in sorted_keys
            ]
        }

    @staticmethod
    def get_holding_analysis() -> dict:
        """获取持仓周期分析数据（散点图）"""
        settlements = Settlement.query.all()

        scatter_data = [
            {
                'name': s.stock_name or s.stock_code,
                'holding_days': s.holding_days,
                'profit_pct': round(s.profit_pct, 2),
                'profit': round(s.profit, 2)
            }
            for s in settlements
        ]

        return {'scatter': scatter_data}
