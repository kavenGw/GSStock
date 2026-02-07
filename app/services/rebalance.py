from app import db
from app.models.stock_weight import StockWeight
from app.models.stock import Stock
from app.models.position_plan import PositionPlan
from app.models.rebalance_config import RebalanceConfig
from app.services.position import PositionService


class RebalanceService:
    @staticmethod
    def get_all_stocks_with_status():
        """获取所有股票及其权重、选中状态、当前持仓市值"""
        # 获取所有股票代码和名称
        stocks = Stock.query.all()
        stock_map = {s.stock_code: s.stock_name for s in stocks}

        # 获取所有权重记录
        weights = StockWeight.query.all()
        weight_map = {w.stock_code: w for w in weights}

        # 获取最新持仓
        latest_date = PositionService.get_latest_date()
        position_map = {}
        if latest_date:
            positions = PositionService.get_snapshot(latest_date)
            for p in positions:
                market_value = p.current_price * p.quantity
                position_map[p.stock_code] = {
                    'market_value': market_value,
                    'current_price': p.current_price,
                    'quantity': p.quantity,
                }
                # 如果持仓中的股票不在 Stock 表中，也加入列表
                if p.stock_code not in stock_map:
                    stock_map[p.stock_code] = p.stock_name

        # 合并数据
        result = []
        for stock_code, stock_name in stock_map.items():
            weight_record = weight_map.get(stock_code)
            position = position_map.get(stock_code, {})

            result.append({
                'stock_code': stock_code,
                'stock_name': stock_name,
                'weight': float(weight_record.weight) if weight_record else 1.0,
                'selected': weight_record.selected if weight_record else False,
                'market_value': round(position.get('market_value', 0), 2),
                'current_price': position.get('current_price', 0),
                'quantity': position.get('quantity', 0),
            })

        # 按选中状态和市值排序
        result.sort(key=lambda x: (-x['selected'], -x['market_value']))
        return result

    @staticmethod
    def get_weights(stock_codes):
        """批量获取权重，未设置的返回默认值 1.0"""
        if not stock_codes:
            return {}
        weights = StockWeight.query.filter(StockWeight.stock_code.in_(stock_codes)).all()
        result = {w.stock_code: float(w.weight) for w in weights}
        for code in stock_codes:
            if code not in result:
                result[code] = 1.0
        return result

    @staticmethod
    def save_weight(stock_code, weight):
        """保存权重（upsert），返回 (success, message)"""
        if not isinstance(weight, (int, float)):
            return False, '权重必须是数字'
        if weight <= 0:
            return False, '权重必须大于 0'
        if weight > 99.99:
            return False, '权重不能超过 99.99'

        weight = round(weight, 2)

        existing = StockWeight.query.get(stock_code)
        if existing:
            existing.weight = weight
        else:
            existing = StockWeight(stock_code=stock_code, weight=weight)
            db.session.add(existing)

        db.session.commit()
        return True, None

    @staticmethod
    def save_selection(stock_code, selected):
        """保存股票选中状态"""
        existing = StockWeight.query.get(stock_code)
        if existing:
            existing.selected = selected
        else:
            existing = StockWeight(stock_code=stock_code, weight=1.0, selected=selected)
            db.session.add(existing)

        db.session.commit()
        return True, None

    @staticmethod
    def calculate_position_plan(target_value):
        """计算仓位管理建议

        target_value: 目标总市值
        返回: {success, target_value, current_value, items, sell_all}
        """
        if not target_value or target_value <= 0:
            return {'success': False, 'error': '请输入有效的目标市值'}

        # 获取选中的股票
        selected_weights = StockWeight.query.filter_by(selected=True).all()
        if not selected_weights:
            return {'success': False, 'error': '请至少选择一只股票'}

        selected_codes = [w.stock_code for w in selected_weights]
        weight_map = {w.stock_code: float(w.weight) for w in selected_weights}

        # 获取股票名称
        stocks = Stock.query.filter(Stock.stock_code.in_(selected_codes)).all()
        name_map = {s.stock_code: s.stock_name for s in stocks}

        # 获取当前持仓
        latest_date = PositionService.get_latest_date()
        position_map = {}
        held_codes = set()
        current_total_value = 0

        if latest_date:
            positions = PositionService.get_snapshot(latest_date)
            for p in positions:
                market_value = p.current_price * p.quantity
                position_map[p.stock_code] = {
                    'stock_name': p.stock_name,
                    'market_value': market_value,
                    'current_price': p.current_price,
                    'quantity': p.quantity,
                }
                held_codes.add(p.stock_code)
                current_total_value += market_value
                # 补充名称
                if p.stock_code not in name_map:
                    name_map[p.stock_code] = p.stock_name

        # 计算权重总和
        total_weight = sum(weight_map.values())
        if total_weight <= 0:
            return {'success': False, 'error': '权重总和必须大于 0'}

        # 计算选中股票的操作建议
        items = []
        for code in selected_codes:
            weight = weight_map[code]
            target_stock_value = target_value * (weight / total_weight)

            pos = position_map.get(code, {})
            current_value = pos.get('market_value', 0)
            current_price = pos.get('current_price', 0)
            current_quantity = pos.get('quantity', 0)

            diff = target_stock_value - current_value

            # 判断操作类型（差额在目标市值的2%以内视为持有）
            threshold = target_stock_value * 0.02
            if abs(diff) <= threshold:
                operation = 'hold'
                shares = 0
            elif diff > 0:
                operation = 'buy'
                shares = int(diff / current_price / 100) * 100 if current_price > 0 else 0
            else:
                operation = 'sell'
                shares = int(abs(diff) / current_price / 100) * 100 if current_price > 0 else 0

            items.append({
                'stock_code': code,
                'stock_name': name_map.get(code, code),
                'weight': weight,
                'target_value': round(target_stock_value, 2),
                'current_value': round(current_value, 2),
                'current_quantity': current_quantity,
                'current_price': current_price,
                'diff': round(diff, 2),
                'operation': operation,
                'shares': shares,
            })

        # 按操作优先级和差额排序
        order = {'sell': 0, 'buy': 1, 'hold': 2}
        items.sort(key=lambda x: (order.get(x['operation'], 3), -abs(x['diff'])))

        return {
            'success': True,
            'target_value': target_value,
            'current_value': round(current_total_value, 2),
            'items': items,
        }

    @staticmethod
    def calculate_rebalance(positions):
        """计算配平建议（供其他页面使用）"""
        if not positions:
            return []

        stock_codes = [p.get('stock_code') or p.stock_code for p in positions]
        weights = RebalanceService.get_weights(stock_codes)

        total_market_value = 0
        total_weight = 0
        items = []

        for p in positions:
            stock_code = p.get('stock_code') if isinstance(p, dict) else p.stock_code
            stock_name = p.get('stock_name') if isinstance(p, dict) else p.stock_name
            quantity = p.get('quantity') if isinstance(p, dict) else p.quantity
            current_price = p.get('current_price') if isinstance(p, dict) else p.current_price

            market_value = current_price * quantity
            weight = weights.get(stock_code, 1.0)

            total_market_value += market_value
            total_weight += weight

            items.append({
                'stock_code': stock_code,
                'stock_name': stock_name,
                'market_value': market_value,
                'weight': weight,
                'current_price': current_price,
            })

        if total_market_value <= 0:
            return []

        result = []
        for item in items:
            actual_pct = item['market_value'] / total_market_value * 100
            target_pct = item['weight'] / total_weight * 100
            deviation = target_pct - actual_pct
            shares = int(abs(deviation / 100 * total_market_value) / item['current_price'] / 100) * 100 if item['current_price'] > 0 else 0

            if abs(deviation) <= 2:
                operation = 'hold'
            elif deviation > 0:
                operation = 'buy'
            else:
                operation = 'sell'

            result.append({
                'stock_code': item['stock_code'],
                'stock_name': item['stock_name'],
                'market_value': round(item['market_value'], 2),
                'actual_pct': round(actual_pct, 2),
                'weight': item['weight'],
                'target_pct': round(target_pct, 2),
                'deviation': round(deviation, 2),
                'operation': operation,
                'shares': shares,
            })

        result.sort(key=lambda x: abs(x['deviation']), reverse=True)
        return result

    @staticmethod
    def save_position_plan(items, target_value=0):
        """保存仓位计划到数据库"""
        # 清除旧数据
        PositionPlan.query.delete()

        # 保存目标总市值
        RebalanceConfig.save_target_value(target_value)

        # 保存新数据
        for item in items:
            plan = PositionPlan(
                stock_code=item['stock_code'],
                stock_name=item.get('stock_name'),
                target_value=item['target_value'],
                current_value=item.get('current_value', 0),
                diff=item.get('diff', 0),
                operation=item['operation'],
                shares=item.get('shares', 0),
                weight=item.get('weight', 1.0),
            )
            db.session.add(plan)

        db.session.commit()

    @staticmethod
    def get_position_plans():
        """获取所有仓位计划及配置"""
        plans = PositionPlan.query.all()
        config = RebalanceConfig.get_config()
        return {
            'items': [p.to_dict() for p in plans],
            'target_value': config.target_value,
        }

    @staticmethod
    def get_position_plan_by_code(stock_code):
        """获取指定股票的仓位计划"""
        plan = PositionPlan.query.filter_by(stock_code=stock_code).first()
        return plan.to_dict() if plan else None
