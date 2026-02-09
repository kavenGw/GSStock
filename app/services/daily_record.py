import logging
from datetime import date
from app import db
from app.models.position import Position
from app.models.trade import Trade
from app.models.category import StockCategory, Category
from app.models.daily_snapshot import DailySnapshot
from app.models.bank_transfer import BankTransfer

logger = logging.getLogger(__name__)


class DailyRecordService:
    @staticmethod
    def get_previous_trading_date(target_date: date) -> date | None:
        """获取前一个有持仓数据的日期"""
        result = db.session.query(Position.date)\
            .filter(Position.date < target_date)\
            .distinct()\
            .order_by(Position.date.desc())\
            .first()
        return result[0] if result else None

    @staticmethod
    def get_daily_profit(target_date: date, prev_date: date | None) -> dict:
        """计算当日盈亏
        当日盈亏 = 当日总资产 - 前日总资产 - 净转入（转入 - 转出）
        手续费 = 理论盈亏（各股票市值变动+交易净额） - 实际盈亏（资产差值）
        """
        today_positions = Position.query.filter_by(date=target_date).all()
        today_market_value = sum(p.current_price * p.quantity for p in today_positions)
        today_cost = sum(p.total_amount for p in today_positions)

        today_snapshot = DailySnapshot.get_snapshot(target_date)
        today_total_asset = today_snapshot.total_asset if today_snapshot and today_snapshot.total_asset else today_market_value

        transfers = BankTransfer.query.filter_by(transfer_date=target_date).all()
        transfer_in = sum(t.amount for t in transfers if t.transfer_type == 'in')
        transfer_out = sum(t.amount for t in transfers if t.transfer_type == 'out')
        net_transfer = transfer_in - transfer_out

        result = {
            'today_market_value': round(today_market_value, 2),
            'today_total_asset': round(today_total_asset, 2),
            'today_cost': round(today_cost, 2),
            'prev_total_asset': None,
            'daily_profit': None,
            'daily_profit_pct': None,
            'total_profit': round(today_market_value - today_cost, 2),
            'total_profit_pct': round((today_market_value - today_cost) / today_cost * 100 if today_cost > 0 else 0, 2),
            'transfer_in': round(transfer_in, 2),
            'transfer_out': round(transfer_out, 2),
            'net_transfer': round(net_transfer, 2),
            'daily_fee': 0,
        }

        if prev_date:
            prev_snapshot = DailySnapshot.get_snapshot(prev_date)
            prev_positions = Position.query.filter_by(date=prev_date).all()
            prev_pos_map = {p.stock_code: p for p in prev_positions}

            prev_total_asset = prev_snapshot.total_asset if prev_snapshot and prev_snapshot.total_asset else \
                sum(p.current_price * p.quantity for p in prev_positions)

            daily_profit = today_total_asset - prev_total_asset - net_transfer
            daily_profit_pct = (daily_profit / prev_total_asset * 100) if prev_total_asset > 0 else 0

            result['prev_total_asset'] = round(prev_total_asset, 2)
            result['daily_profit'] = round(daily_profit, 2)
            result['daily_profit_pct'] = round(daily_profit_pct, 2)

            # 手续费 = 理论盈亏 - 实际盈亏
            today_pos_dict = {p.stock_code: p for p in today_positions}
            trades = Trade.query.filter_by(trade_date=target_date).all()
            trade_by_stock = {}
            for t in trades:
                if t.stock_code not in trade_by_stock:
                    trade_by_stock[t.stock_code] = {'buy': 0, 'sell': 0}
                if t.trade_type == 'buy':
                    trade_by_stock[t.stock_code]['buy'] += t.amount
                else:
                    trade_by_stock[t.stock_code]['sell'] += t.amount

            all_stocks = set(today_pos_dict.keys()) | set(prev_pos_map.keys())
            theoretical_profit = 0
            for code in all_stocks:
                today_p = today_pos_dict.get(code)
                prev_p = prev_pos_map.get(code)
                today_mv = today_p.current_price * today_p.quantity if today_p else 0
                prev_mv = prev_p.current_price * prev_p.quantity if prev_p else 0
                td = trade_by_stock.get(code, {'buy': 0, 'sell': 0})
                theoretical_profit += today_mv - prev_mv + td['sell'] - td['buy']

            daily_fee = theoretical_profit - daily_profit
            result['daily_fee'] = round(max(0, daily_fee), 2)

        return result

    @staticmethod
    def get_profit_breakdown(target_date: date, prev_date: date | None) -> list:
        """获取盈亏组成明细，遍历所有股票计算每只股票的当日盈亏"""
        # 获取当日和前日持仓
        today_positions = {p.stock_code: p for p in Position.query.filter_by(date=target_date).all()}
        prev_positions = {}
        if prev_date:
            prev_positions = {p.stock_code: p for p in Position.query.filter_by(date=prev_date).all()}

        # 获取当日交易
        trades = Trade.query.filter_by(trade_date=target_date).all()
        trade_by_stock = {}
        for t in trades:
            if t.stock_code not in trade_by_stock:
                trade_by_stock[t.stock_code] = {'buy': 0, 'sell': 0, 'fee': 0}
            if t.trade_type == 'buy':
                trade_by_stock[t.stock_code]['buy'] += t.amount
            else:
                trade_by_stock[t.stock_code]['sell'] += t.amount
            trade_by_stock[t.stock_code]['fee'] += t.fee or 0

        # 汇总所有相关股票代码
        all_stocks = set(today_positions.keys()) | set(prev_positions.keys())

        breakdown = []
        for code in all_stocks:
            today_pos = today_positions.get(code)
            prev_pos = prev_positions.get(code)
            trade_data = trade_by_stock.get(code, {'buy': 0, 'sell': 0, 'fee': 0})

            today_market_value = today_pos.current_price * today_pos.quantity if today_pos else 0
            prev_market_value = prev_pos.current_price * prev_pos.quantity if prev_pos else 0
            today_cost = today_pos.total_amount if today_pos else 0
            prev_cost = prev_pos.total_amount if prev_pos else 0

            # 判断股票状态
            if today_pos and prev_pos:
                status = 'holding'
            elif today_pos and not prev_pos:
                status = 'new'
            else:
                status = 'closed'

            # 统一公式：当日盈亏 = 今日市值 - 昨日市值 + 卖出金额 - 买入金额 - 手续费
            daily_profit = today_market_value - prev_market_value + trade_data['sell'] - trade_data['buy'] - trade_data['fee']
            # 交易净额 = 卖出金额 - 买入金额（注意：对于已清仓股票，这等于卖出收入，而非实际盈亏）
            trade_net = trade_data['sell'] - trade_data['buy']

            stock_name = today_pos.stock_name if today_pos else (prev_pos.stock_name if prev_pos else '')

            breakdown.append({
                'stock_code': code,
                'stock_name': stock_name,
                'status': status,
                'prev_market_value': round(prev_market_value, 2),
                'today_market_value': round(today_market_value, 2),
                'trade_profit': round(trade_net, 2),
                'daily_profit': round(daily_profit, 2),
                'fee': round(trade_data['fee'], 2),
            })

        # 按盈亏绝对值从大到小排序
        breakdown.sort(key=lambda x: abs(x['daily_profit']), reverse=True)
        return breakdown

    @staticmethod
    def get_light_positions(target_date: date, threshold: float = 5.0) -> list:
        """获取轻仓股票列表（仓位百分比低于阈值）"""
        positions = Position.query.filter_by(date=target_date).all()
        if not positions:
            return []

        # 计算总市值
        total_market_value = sum(p.current_price * p.quantity for p in positions)
        if total_market_value <= 0:
            return []

        light_positions = []
        for p in positions:
            market_value = p.current_price * p.quantity
            position_pct = (market_value / total_market_value) * 100

            if position_pct < threshold:
                light_positions.append({
                    'stock_code': p.stock_code,
                    'stock_name': p.stock_name,
                    'market_value': round(market_value, 2),
                    'position_pct': round(position_pct, 2),
                })

        # 按仓位从低到高排序
        light_positions.sort(key=lambda x: x['position_pct'])
        return light_positions

    @staticmethod
    def calculate_daily_stats(target_date: date) -> dict:
        """计算当日统计数据汇总"""
        prev_date = DailyRecordService.get_previous_trading_date(target_date)

        # 计算当日盈亏
        summary = DailyRecordService.get_daily_profit(target_date, prev_date)

        # 获取盈亏组成明细
        profit_breakdown = DailyRecordService.get_profit_breakdown(target_date, prev_date)

        # 获取轻仓股票
        light_positions = DailyRecordService.get_light_positions(target_date)

        return {
            'date': target_date.isoformat(),
            'prev_date': prev_date.isoformat() if prev_date else None,
            'summary': summary,
            'profit_breakdown': profit_breakdown,
            'light_positions': light_positions,
        }

    @staticmethod
    def get_all_trading_dates() -> list[date]:
        """获取所有有持仓数据的日期，按日期升序"""
        results = db.session.query(Position.date)\
            .distinct()\
            .order_by(Position.date.asc())\
            .all()
        return [r[0] for r in results]

    @staticmethod
    def get_daily_profit_history() -> dict:
        """获取每日收益历史数据，用于图表展示"""
        dates = DailyRecordService.get_all_trading_dates()
        if not dates:
            return {'daily_profits': [], 'cumulative_profits': [], 'summary': {}}

        daily_profits = []
        cumulative_profit = 0
        cumulative_profits = []
        prev_date = None

        for target_date in dates:
            profit_data = DailyRecordService.get_daily_profit(target_date, prev_date)

            daily_profit = profit_data['daily_profit']
            if daily_profit is not None:
                cumulative_profit += daily_profit
                daily_profits.append({
                    'date': target_date.isoformat(),
                    'daily_profit': daily_profit,
                    'daily_profit_pct': profit_data['daily_profit_pct'],
                    'market_value': profit_data['today_market_value'],
                    'net_transfer': profit_data.get('net_transfer', 0),
                    'daily_fee': profit_data.get('daily_fee', 0),
                })
                cumulative_profits.append({
                    'date': target_date.isoformat(),
                    'cumulative': round(cumulative_profit, 2),
                })

            prev_date = target_date

        # 计算统计摘要
        if daily_profits:
            profits = [d['daily_profit'] for d in daily_profits]
            fees = [d.get('daily_fee', 0) for d in daily_profits]
            win_days = sum(1 for p in profits if p > 0)
            loss_days = sum(1 for p in profits if p < 0)
            max_profit = max(profits) if profits else 0
            max_loss = min(profits) if profits else 0
            avg_profit = sum(profits) / len(profits) if profits else 0
            total_fee = sum(fees)

            summary = {
                'total_days': len(daily_profits),
                'win_days': win_days,
                'loss_days': loss_days,
                'win_rate': round(win_days / len(daily_profits) * 100, 2) if daily_profits else 0,
                'total_profit': round(cumulative_profit, 2),
                'max_profit': round(max_profit, 2),
                'max_loss': round(max_loss, 2),
                'avg_profit': round(avg_profit, 2),
                'total_fee': round(total_fee, 2),
            }
        else:
            summary = {}

        return {
            'daily_profits': daily_profits,
            'cumulative_profits': cumulative_profits,
            'summary': summary,
        }

    @staticmethod
    def get_profit_by_stock() -> dict:
        """按股票统计累计收益"""
        dates = DailyRecordService.get_all_trading_dates()
        if len(dates) < 2:
            return {'by_stock': []}

        stock_profits = {}
        prev_date = None

        for target_date in dates:
            if prev_date is None:
                prev_date = target_date
                continue

            breakdown = DailyRecordService.get_profit_breakdown(target_date, prev_date)
            for item in breakdown:
                code = item['stock_code']
                if code not in stock_profits:
                    stock_profits[code] = {
                        'stock_code': code,
                        'stock_name': item['stock_name'],
                        'total_profit': 0,
                    }
                stock_profits[code]['total_profit'] += item['daily_profit']
            prev_date = target_date

        # 转为列表并排序
        by_stock = list(stock_profits.values())
        for item in by_stock:
            item['total_profit'] = round(item['total_profit'], 2)
        by_stock.sort(key=lambda x: x['total_profit'], reverse=True)

        return {'by_stock': by_stock}

    @staticmethod
    def get_profit_by_category() -> dict:
        """按分类统计累计收益"""
        dates = DailyRecordService.get_all_trading_dates()
        if len(dates) < 2:
            return {'by_category': []}

        # 获取所有股票的分类映射
        stock_categories = {sc.stock_code: sc.category for sc in StockCategory.query.all()}

        category_profits = {}
        prev_date = None

        for target_date in dates:
            if prev_date is None:
                prev_date = target_date
                continue

            breakdown = DailyRecordService.get_profit_breakdown(target_date, prev_date)
            for item in breakdown:
                code = item['stock_code']
                category = stock_categories.get(code)

                if category:
                    cat_name = f"{category.parent.name} - {category.name}" if category.parent else category.name
                else:
                    cat_name = '未分类'

                if cat_name not in category_profits:
                    category_profits[cat_name] = 0
                category_profits[cat_name] += item['daily_profit']
            prev_date = target_date

        # 转为列表并排序
        by_category = [
            {'category': name, 'total_profit': round(profit, 2)}
            for name, profit in category_profits.items()
        ]
        by_category.sort(key=lambda x: x['total_profit'], reverse=True)

        return {'by_category': by_category}
