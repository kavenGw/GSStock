import logging
import pandas as pd
from datetime import date
from app import db
from app.models.position import Position

logger = logging.getLogger(__name__)


class PositionService:
    @staticmethod
    def merge_positions(positions: list[dict]) -> list[dict]:
        """合并相同股票的持仓，总金额和数量相加

        - 若 stock_code 为空，从 Stock 表按名称查询补全
        - 若名称查询失败，从 StockAlias 表按别名查询
        - 合并key: stock_code 优先，若仍为空则使用 stock_name

        返回结构中每条记录包含:
        - merge_info: 合并信息追踪
            - merged_count: 被合并的记录数量
            - original_names: 原始名称列表
            - alias_matched: 是否通过别名匹配
            - matched_from: 'stock'/'alias'/None
        - unmatched: 是否未能匹配到股票代码
        """
        from app.models.stock import Stock
        from app.models.stock_alias import StockAlias

        logger.info(f"[merge] 开始合并持仓，输入{len(positions)}条记录")
        merged = {}

        for pos in positions:
            stock_code = pos.get('stock_code', '')
            stock_name = pos.get('stock_name', '')
            original_name = stock_name  # 保存原始名称用于 merge_info
            logger.info(f"[merge] 处理: code='{stock_code}', name='{stock_name}'")

            matched_from = None
            alias_matched = False

            # stock_code 为空时，从本地数据查询
            if not stock_code and stock_name:
                # 先按名称查询
                stock = Stock.query.filter_by(stock_name=stock_name).first()
                if stock:
                    stock_code = stock.stock_code
                    pos['stock_code'] = stock_code
                    matched_from = 'stock'
                    logger.info(f"[merge] 名称匹配成功: '{stock_name}' -> '{stock_code}'")
                else:
                    logger.info(f"[merge] 名称匹配失败: '{stock_name}', 尝试别名查询...")
                    # 再按别名查询
                    alias = StockAlias.query.filter_by(alias_name=stock_name).first()
                    if alias:
                        stock_code = alias.stock_code
                        pos['stock_code'] = stock_code
                        matched_from = 'alias'
                        alias_matched = True
                        # 获取标准名称并更新
                        standard_stock = Stock.query.filter_by(stock_code=stock_code).first()
                        if standard_stock:
                            pos['stock_name'] = standard_stock.stock_name
                            stock_name = standard_stock.stock_name
                            logger.info(f"[merge] 别名匹配成功: '{original_name}' -> '{stock_code}' (标准名称: '{stock_name}')")
                        else:
                            logger.info(f"[merge] 别名匹配成功: '{stock_name}' -> '{stock_code}'")
                    else:
                        logger.info(f"[merge] 别名匹配失败: '{stock_name}'")

            key = stock_code if stock_code else stock_name
            logger.info(f"[merge] 使用合并key: '{key}'")
            if not key:
                logger.warning(f"[merge] 跳过无效记录: code='{stock_code}', name='{stock_name}'")
                continue

            unmatched = not stock_code

            if key in merged:
                existing = merged[key]
                old_qty = existing['quantity']
                existing['quantity'] += pos['quantity']
                existing['total_amount'] += pos['total_amount']
                existing['merge_info']['merged_count'] += 1
                # 使用原始名称记录合并来源
                if original_name and original_name not in existing['merge_info']['original_names']:
                    existing['merge_info']['original_names'].append(original_name)
                if alias_matched:
                    existing['merge_info']['alias_matched'] = True
                    existing['merge_info']['matched_from'] = 'alias'
                logger.info(f"[merge] 合并到已有记录: key='{key}', qty: {old_qty} + {pos['quantity']} = {existing['quantity']}")
            else:
                merged_record = pos.copy()
                merged_record['merge_info'] = {
                    'merged_count': 1,
                    'original_names': [original_name] if original_name else [],
                    'alias_matched': alias_matched,
                    'matched_from': matched_from
                }
                merged_record['unmatched'] = unmatched
                merged[key] = merged_record
                logger.info(f"[merge] 新增记录: key='{key}', qty={pos['quantity']}")

        result = list(merged.values())

        # 计算加权平均价格：total_amount / quantity
        for record in result:
            if record['quantity'] > 0:
                record['current_price'] = round(record['total_amount'] / record['quantity'], 2)

        logger.info(f"[merge] 合并完成，输出{len(result)}条记录")
        return result

    @staticmethod
    def has_snapshot(target_date: date) -> bool:
        """检查指定日期是否有持仓快照"""
        return db.session.query(
            Position.query.filter_by(date=target_date).exists()
        ).scalar()

    @staticmethod
    def save_snapshot(target_date: date, positions: list[dict], overwrite: bool = True) -> bool:
        """保存持仓快照"""
        logger.info(f"保存持仓快照: date={target_date}, count={len(positions)}, overwrite={overwrite}")
        if overwrite:
            Position.query.filter_by(date=target_date).delete()
        else:
            # 合并模式：先获取现有数据
            existing = PositionService.get_snapshot(target_date)
            existing_data = [p.to_dict() for p in existing]
            positions = PositionService.merge_positions(existing_data + positions)
            Position.query.filter_by(date=target_date).delete()

        for pos in positions:
            if pos['quantity'] <= 0:
                continue
            position = Position(
                date=target_date,
                stock_code=pos['stock_code'],
                stock_name=pos['stock_name'],
                quantity=pos['quantity'],
                total_amount=pos['total_amount'],
                current_price=pos['current_price'],
            )
            db.session.add(position)

        db.session.commit()
        logger.info(f"持仓快照保存成功: date={target_date}")
        return True

    @staticmethod
    def get_snapshot(target_date: date) -> list[Position]:
        """获取指定日期的持仓快照"""
        return Position.query.filter_by(date=target_date).all()

    @staticmethod
    def get_latest_date() -> date | None:
        """获取最近一次持仓记录的日期"""
        result = db.session.query(db.func.max(Position.date)).scalar()
        return result

    @staticmethod
    def get_all_dates() -> list[date]:
        """获取所有有持仓记录的日期"""
        results = db.session.query(Position.date).distinct().order_by(Position.date.desc()).all()
        return [r[0] for r in results]

    @staticmethod
    def get_stock_history(stock_code: str, days: int = 7) -> dict:
        """获取指定股票的历史持仓数据和K线OHLC数据"""
        from app.services.unified_stock_data import unified_stock_data_service

        positions = Position.query.filter_by(stock_code=stock_code).order_by(Position.date.desc()).limit(days).all()
        positions = list(reversed(positions))

        if not positions:
            return {'stock_code': stock_code, 'stock_name': '', 'history': [], 'ohlc': []}

        stock_name = positions[-1].stock_name

        # 通过统一服务获取OHLC数据
        ohlc_data = []
        try:
            trend_result = unified_stock_data_service.get_trend_data([stock_code], days)
            stocks_data = trend_result.get('stocks', [])
            if stocks_data:
                stock_trend = stocks_data[0]
                for dp in stock_trend.get('data', []):
                    ohlc_data.append({
                        'date': dp['date'],
                        'open': dp['open'],
                        'high': dp['high'],
                        'low': dp['low'],
                        'close': dp['close']
                    })
        except Exception as e:
            logger.warning(f"获取股票 {stock_code} OHLC数据失败: {e}")

        history = []
        for p in positions:
            cost_price = p.total_amount / p.quantity if p.quantity > 0 else 0
            market_value = p.current_price * p.quantity
            profit = market_value - p.total_amount

            day_positions = Position.query.filter_by(date=p.date).all()
            day_total_market_value = sum(pos.current_price * pos.quantity for pos in day_positions)
            position_pct = (market_value / day_total_market_value * 100) if day_total_market_value > 0 else 0

            history.append({
                'date': p.date.isoformat(),
                'quantity': p.quantity,
                'cost_price': round(cost_price, 3),
                'current_price': p.current_price,
                'profit': round(profit, 2),
                'position_pct': round(position_pct, 1),
            })

        return {
            'stock_code': stock_code,
            'stock_name': stock_name,
            'history': history,
            'ohlc': ohlc_data
        }

    @staticmethod
    def calculate_daily_change(target_date: date) -> dict | None:
        """计算指定日期相比前一天的收益变化"""
        dates = PositionService.get_all_dates()
        if target_date not in dates:
            return None

        # 找到前一天
        dates_sorted = sorted(dates, reverse=True)
        prev_date = None
        for i, d in enumerate(dates_sorted):
            if d == target_date and i + 1 < len(dates_sorted):
                prev_date = dates_sorted[i + 1]
                break

        # 计算当天盈亏
        today_positions = PositionService.get_snapshot(target_date)
        today_market_value = sum(p.current_price * p.quantity for p in today_positions)
        today_cost = sum(p.total_amount for p in today_positions)
        today_profit = today_market_value - today_cost

        if prev_date is None:
            return {
                'daily_change': round(today_profit, 2),
                'prev_profit': 0
            }

        # 计算前一天盈亏
        prev_positions = PositionService.get_snapshot(prev_date)
        prev_market_value = sum(p.current_price * p.quantity for p in prev_positions)
        prev_cost = sum(p.total_amount for p in prev_positions)
        prev_profit = prev_market_value - prev_cost

        return {
            'daily_change': round(today_profit - prev_profit, 2),
            'prev_profit': round(prev_profit, 2)
        }

    @staticmethod
    def calculate_position_stats(positions: list[dict], total_capital: float | None = None) -> dict:
        """计算仓位统计，包括单股仓位百分比和总仓位统计"""
        # 计算总市值和总成本
        total_market_value = sum(p['current_price'] * p['quantity'] for p in positions)
        total_cost = sum(p['total_amount'] for p in positions)
        total_profit = total_market_value - total_cost
        total_profit_pct = (total_profit / total_cost * 100) if total_cost > 0 else 0

        # 计算每个持仓的仓位数据
        position_list = []
        for p in positions:
            market_value = p['current_price'] * p['quantity']
            position_pct = (market_value / total_market_value * 100) if total_market_value > 0 else 0

            # 单股仓位级别
            if position_pct > 30:
                position_level = 'danger'
            elif position_pct >= 20:
                position_level = 'warning'
            else:
                position_level = 'normal'

            position_list.append({
                **p,
                'market_value': market_value,
                'position_pct': round(position_pct, 1),
                'position_level': position_level,
            })

        # 总仓位计算
        total_position_pct = None
        risk_level = 'normal'
        if total_capital and total_capital > 0:
            total_position_pct = round(total_market_value / total_capital * 100, 1)
            if total_position_pct > 90:
                risk_level = 'danger'
            elif total_position_pct > 80:
                risk_level = 'high'

        return {
            'positions': position_list,
            'summary': {
                'total_market_value': round(total_market_value, 2),
                'total_cost': round(total_cost, 2),
                'total_profit': round(total_profit, 2),
                'total_profit_pct': round(total_profit_pct, 2),
                'total_capital': total_capital,
                'total_position_pct': total_position_pct,
                'risk_level': risk_level,
            }
        }

    @staticmethod
    def get_trend_data(stock_codes: list[str], end_date: date, days: int = 30) -> dict:
        """获取多只股票的历史价格并计算归一化涨跌幅

        委托给 UnifiedStockDataService 统一缓存服务
        """
        from app.services.unified_stock_data import unified_stock_data_service

        return unified_stock_data_service.get_trend_data(stock_codes, days)

    @staticmethod
    def calculate_category_profit(positions: list[dict], stock_categories: dict, category_tree: list) -> dict:
        """计算分类收益数据"""
        # 构建分类ID到名称的映射
        category_names = {}
        for parent in category_tree:
            category_names[parent['id']] = parent['name']
            for child in parent.get('children', []):
                category_names[child['id']] = child['name']

        # 按分类汇总收益
        category_profits = {}
        uncategorized_profit = 0

        for p in positions:
            stock_code = p.get('stock_code', '')
            cost_price = p.get('cost_price', 0)
            current_price = p.get('current_price', 0)
            quantity = p.get('quantity', 0)
            profit = (current_price - cost_price) * quantity

            sc = stock_categories.get(stock_code, {})
            cat_id = sc.get('category_id')

            if cat_id and cat_id in category_names:
                cat_name = category_names[cat_id]
                if cat_name not in category_profits:
                    category_profits[cat_name] = 0
                category_profits[cat_name] += profit
            else:
                uncategorized_profit += profit

        if uncategorized_profit != 0:
            category_profits['未分类'] = uncategorized_profit

        # 转换为列表格式
        result = []
        for name, profit in sorted(category_profits.items(), key=lambda x: abs(x[1]), reverse=True):
            result.append({
                'name': name,
                'profit': round(profit, 2)
            })

        return {'categories': result}
