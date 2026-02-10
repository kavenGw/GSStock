"""
回测验证服务 - 验证威科夫阶段判断和买卖信号的历史准确率
"""
import logging
from datetime import date, timedelta
from collections import defaultdict

from app import db
from app.models.wyckoff import WyckoffAutoResult
from app.models.signal_cache import SignalCache

logger = logging.getLogger(__name__)

# 威科夫阶段的预期方向
PHASE_EXPECTED_DIRECTION = {
    'accumulation': 'up',      # 吸筹 → 预期上涨
    'markup': 'up',            # 上升 → 预期继续上涨
    'distribution': 'down',    # 派发 → 预期下跌
    'markdown': 'down',        # 下降 → 预期继续下跌
}

# 回测评估周期（天）
EVAL_PERIODS = [5, 10, 20]


class BacktestService:
    """回测验证服务"""

    def __init__(self):
        from app.services.unified_stock_data import UnifiedStockDataService
        self.data_service = UnifiedStockDataService()

    def backtest_wyckoff(self, stock_code: str, lookback_days: int = 180) -> dict:
        """回测威科夫阶段判断

        1. 获取历史自动分析记录（WyckoffAutoResult表）
        2. 获取对应时段的实际走势
        3. 验证阶段判断后N天的走势是否符合预期
        4. 输出：方向准确率、平均收益率
        """
        start_date = date.today() - timedelta(days=lookback_days)

        records = WyckoffAutoResult.query.filter(
            WyckoffAutoResult.stock_code == stock_code,
            WyckoffAutoResult.analysis_date >= start_date,
            WyckoffAutoResult.status == 'success'
        ).order_by(WyckoffAutoResult.analysis_date).all()

        if not records:
            return {'stock_code': stock_code, 'total': 0, 'message': '无历史分析记录'}

        # 获取足够长的走势数据用于验证
        extra_days = max(EVAL_PERIODS) + 5
        trend_result = self.data_service.get_trend_data(
            [stock_code], days=lookback_days + extra_days
        )

        price_data = self._extract_price_series(trend_result, stock_code)
        if not price_data:
            return {'stock_code': stock_code, 'total': 0, 'message': '无走势数据'}

        results = []
        for record in records:
            eval_result = self._evaluate_wyckoff_record(record, price_data)
            if eval_result:
                results.append(eval_result)

        return self._summarize_wyckoff(stock_code, results)

    def backtest_signals(self, stock_code: str, lookback_days: int = 365) -> dict:
        """回测买卖信号

        1. 获取历史信号记录（SignalCache表）
        2. 验证信号触发后5/10/20天的实际走势
        3. 输出：信号胜率、平均收益、最大回撤
        """
        start_date = date.today() - timedelta(days=lookback_days)

        signals = SignalCache.query.filter(
            SignalCache.stock_code == stock_code,
            SignalCache.signal_date >= start_date
        ).order_by(SignalCache.signal_date).all()

        if not signals:
            return {'stock_code': stock_code, 'total': 0, 'message': '无历史信号'}

        extra_days = max(EVAL_PERIODS) + 5
        trend_result = self.data_service.get_trend_data(
            [stock_code], days=lookback_days + extra_days
        )

        price_data = self._extract_price_series(trend_result, stock_code)
        if not price_data:
            return {'stock_code': stock_code, 'total': 0, 'message': '无走势数据'}

        results = []
        for signal in signals:
            eval_result = self._evaluate_signal(signal, price_data)
            if eval_result:
                results.append(eval_result)

        return self._summarize_signals(stock_code, results)

    def backtest_batch(self, stock_codes: list) -> dict:
        """批量回测所有持仓股"""
        wyckoff_results = {}
        signal_results = {}

        for code in stock_codes:
            try:
                wyckoff_results[code] = self.backtest_wyckoff(code)
            except Exception as e:
                logger.warning(f'[Backtest] 威科夫回测失败 {code}: {e}')
                wyckoff_results[code] = {'stock_code': code, 'total': 0, 'message': str(e)}

            try:
                signal_results[code] = self.backtest_signals(code)
            except Exception as e:
                logger.warning(f'[Backtest] 信号回测失败 {code}: {e}')
                signal_results[code] = {'stock_code': code, 'total': 0, 'message': str(e)}

        return {
            'wyckoff': wyckoff_results,
            'signals': signal_results,
            'summary': self._batch_summary(wyckoff_results, signal_results)
        }

    def get_summary(self) -> dict:
        """汇总统计：整体胜率、最佳/最差信号类型"""
        # 获取所有有信号的股票代码
        signal_codes = db.session.query(SignalCache.stock_code).distinct().all()
        signal_codes = [row[0] for row in signal_codes]

        wyckoff_codes = db.session.query(WyckoffAutoResult.stock_code).filter(
            WyckoffAutoResult.status == 'success'
        ).distinct().all()
        wyckoff_codes = [row[0] for row in wyckoff_codes]

        all_codes = list(set(signal_codes + wyckoff_codes))

        if not all_codes:
            return {'total_stocks': 0, 'message': '无历史数据'}

        return self.backtest_batch(all_codes)

    # --- 信号胜率查询（供前端信号类型旁显示） ---

    def get_signal_win_rates(self) -> dict:
        """获取各信号类型的历史胜率，用于前端显示

        Returns:
            {'信号名': {'win_rate': 0.65, 'total': 20, 'wins': 13}, ...}
        """
        all_signals = SignalCache.query.all()
        if not all_signals:
            return {}

        # 按股票分组获取走势数据
        codes = list(set(s.stock_code for s in all_signals))
        extra_days = max(EVAL_PERIODS) + 5

        price_cache = {}
        for code in codes:
            trend_result = self.data_service.get_trend_data([code], days=400)
            price_cache[code] = self._extract_price_series(trend_result, code)

        # 按信号名称分组统计
        stats = defaultdict(lambda: {'wins': 0, 'total': 0})

        for signal in all_signals:
            prices = price_cache.get(signal.stock_code)
            if not prices:
                continue

            eval_result = self._evaluate_signal(signal, prices)
            if not eval_result:
                continue

            name = signal.signal_name
            stats[name]['total'] += 1
            # 用10天收益率判断胜负
            ret_10 = eval_result.get('returns', {}).get(10)
            if ret_10 is not None:
                if signal.signal_type == 'buy' and ret_10 > 0:
                    stats[name]['wins'] += 1
                elif signal.signal_type == 'sell' and ret_10 < 0:
                    stats[name]['wins'] += 1

        result = {}
        for name, s in stats.items():
            result[name] = {
                'win_rate': round(s['wins'] / s['total'], 2) if s['total'] > 0 else 0,
                'total': s['total'],
                'wins': s['wins'],
            }
        return result

    # --- 内部方法 ---

    def _extract_price_series(self, trend_result: dict, stock_code: str) -> dict:
        """从走势数据中提取价格序列，返回 {date_str: close_price}"""
        if not trend_result or not trend_result.get('stocks'):
            return {}

        for stock in trend_result['stocks']:
            if stock.get('stock_code') == stock_code:
                data = stock.get('data', [])
                return {item['date']: item['close'] for item in data if item.get('close')}
        return {}

    def _evaluate_wyckoff_record(self, record: WyckoffAutoResult, price_data: dict) -> dict:
        """评估单条威科夫分析记录"""
        analysis_date = record.analysis_date.isoformat()
        expected_dir = PHASE_EXPECTED_DIRECTION.get(record.phase)
        if not expected_dir:
            return None

        base_price = record.current_price
        if not base_price:
            base_price = price_data.get(analysis_date)
        if not base_price:
            return None

        sorted_dates = sorted(price_data.keys())
        try:
            start_idx = sorted_dates.index(analysis_date)
        except ValueError:
            # 找最近的日期
            start_idx = None
            for i, d in enumerate(sorted_dates):
                if d >= analysis_date:
                    start_idx = i
                    break
            if start_idx is None:
                return None

        returns = {}
        correct = {}
        for period in EVAL_PERIODS:
            target_idx = start_idx + period
            if target_idx < len(sorted_dates):
                future_price = price_data[sorted_dates[target_idx]]
                ret = (future_price - base_price) / base_price * 100
                returns[period] = round(ret, 2)
                if expected_dir == 'up':
                    correct[period] = ret > 0
                else:
                    correct[period] = ret < 0

        if not returns:
            return None

        return {
            'date': analysis_date,
            'phase': record.phase,
            'advice': record.advice,
            'expected_direction': expected_dir,
            'base_price': base_price,
            'returns': returns,
            'correct': correct,
        }

    def _evaluate_signal(self, signal: SignalCache, price_data: dict) -> dict:
        """评估单条信号"""
        signal_date = signal.signal_date.isoformat()

        sorted_dates = sorted(price_data.keys())
        start_idx = None
        for i, d in enumerate(sorted_dates):
            if d >= signal_date:
                start_idx = i
                break
        if start_idx is None:
            return None

        base_price = price_data.get(sorted_dates[start_idx])
        if not base_price:
            return None

        returns = {}
        max_drawdown = 0
        for period in EVAL_PERIODS:
            target_idx = start_idx + period
            if target_idx < len(sorted_dates):
                future_price = price_data[sorted_dates[target_idx]]
                ret = (future_price - base_price) / base_price * 100
                returns[period] = round(ret, 2)

                # 计算期间最大回撤
                for j in range(start_idx, target_idx + 1):
                    p = price_data[sorted_dates[j]]
                    dd = (p - base_price) / base_price * 100
                    if signal.signal_type == 'buy':
                        max_drawdown = min(max_drawdown, dd)
                    else:
                        max_drawdown = max(max_drawdown, dd)

        if not returns:
            return None

        return {
            'date': signal_date,
            'type': signal.signal_type,
            'name': signal.signal_name,
            'base_price': base_price,
            'returns': returns,
            'max_drawdown': round(max_drawdown, 2),
        }

    def _summarize_wyckoff(self, stock_code: str, results: list) -> dict:
        """汇总威科夫回测结果"""
        if not results:
            return {'stock_code': stock_code, 'total': 0, 'message': '无可评估记录'}

        total = len(results)
        accuracy = {}
        avg_returns = {}

        for period in EVAL_PERIODS:
            correct_count = sum(1 for r in results if r['correct'].get(period, False))
            valid_count = sum(1 for r in results if period in r['correct'])
            accuracy[period] = round(correct_count / valid_count * 100, 1) if valid_count > 0 else None

            period_returns = [r['returns'][period] for r in results if period in r['returns']]
            avg_returns[period] = round(sum(period_returns) / len(period_returns), 2) if period_returns else None

        # 按阶段分组
        phase_stats = defaultdict(lambda: {'total': 0, 'correct': 0, 'returns': []})
        for r in results:
            phase = r['phase']
            phase_stats[phase]['total'] += 1
            ret_10 = r['returns'].get(10)
            if ret_10 is not None:
                phase_stats[phase]['returns'].append(ret_10)
                if r['correct'].get(10, False):
                    phase_stats[phase]['correct'] += 1

        phase_summary = {}
        for phase, stats in phase_stats.items():
            phase_summary[phase] = {
                'total': stats['total'],
                'accuracy': round(stats['correct'] / stats['total'] * 100, 1) if stats['total'] > 0 else 0,
                'avg_return': round(sum(stats['returns']) / len(stats['returns']), 2) if stats['returns'] else 0,
            }

        return {
            'stock_code': stock_code,
            'total': total,
            'accuracy': accuracy,
            'avg_returns': avg_returns,
            'phase_summary': phase_summary,
            'details': results[-10:],  # 最近10条
        }

    def _summarize_signals(self, stock_code: str, results: list) -> dict:
        """汇总信号回测结果"""
        if not results:
            return {'stock_code': stock_code, 'total': 0, 'message': '无可评估信号'}

        total = len(results)
        buy_results = [r for r in results if r['type'] == 'buy']
        sell_results = [r for r in results if r['type'] == 'sell']

        def calc_stats(items, signal_type):
            if not items:
                return None
            win_rates = {}
            avg_returns = {}
            for period in EVAL_PERIODS:
                period_items = [r for r in items if period in r['returns']]
                if not period_items:
                    continue
                if signal_type == 'buy':
                    wins = sum(1 for r in period_items if r['returns'][period] > 0)
                else:
                    wins = sum(1 for r in period_items if r['returns'][period] < 0)
                win_rates[period] = round(wins / len(period_items) * 100, 1)
                returns = [r['returns'][period] for r in period_items]
                avg_returns[period] = round(sum(returns) / len(returns), 2)

            drawdowns = [r['max_drawdown'] for r in items]
            return {
                'total': len(items),
                'win_rates': win_rates,
                'avg_returns': avg_returns,
                'max_drawdown': round(min(drawdowns), 2) if signal_type == 'buy' else round(max(drawdowns), 2),
            }

        # 按信号名称分组
        name_stats = defaultdict(list)
        for r in results:
            name_stats[r['name']].append(r)

        by_name = {}
        for name, items in name_stats.items():
            signal_type = items[0]['type']
            by_name[name] = calc_stats(items, signal_type)
            if by_name[name]:
                by_name[name]['type'] = signal_type

        return {
            'stock_code': stock_code,
            'total': total,
            'buy': calc_stats(buy_results, 'buy'),
            'sell': calc_stats(sell_results, 'sell'),
            'by_name': by_name,
            'details': results[-10:],
        }

    def _batch_summary(self, wyckoff_results: dict, signal_results: dict) -> dict:
        """批量回测汇总"""
        # 威科夫整体准确率
        w_totals = {p: {'correct': 0, 'total': 0} for p in EVAL_PERIODS}
        for result in wyckoff_results.values():
            if result.get('total', 0) == 0:
                continue
            for detail in result.get('details', []):
                for p in EVAL_PERIODS:
                    if p in detail.get('correct', {}):
                        w_totals[p]['total'] += 1
                        if detail['correct'][p]:
                            w_totals[p]['correct'] += 1

        wyckoff_accuracy = {}
        for p in EVAL_PERIODS:
            if w_totals[p]['total'] > 0:
                wyckoff_accuracy[p] = round(
                    w_totals[p]['correct'] / w_totals[p]['total'] * 100, 1
                )

        # 信号整体胜率
        s_buy_wins = 0
        s_buy_total = 0
        s_sell_wins = 0
        s_sell_total = 0
        for result in signal_results.values():
            buy_stats = result.get('buy')
            if buy_stats and buy_stats.get('win_rates', {}).get(10) is not None:
                total = buy_stats['total']
                s_buy_total += total
                s_buy_wins += int(buy_stats['win_rates'][10] / 100 * total)

            sell_stats = result.get('sell')
            if sell_stats and sell_stats.get('win_rates', {}).get(10) is not None:
                total = sell_stats['total']
                s_sell_total += total
                s_sell_wins += int(sell_stats['win_rates'][10] / 100 * total)

        return {
            'wyckoff_accuracy': wyckoff_accuracy,
            'signal_buy_win_rate': round(s_buy_wins / s_buy_total * 100, 1) if s_buy_total > 0 else None,
            'signal_sell_win_rate': round(s_sell_wins / s_sell_total * 100, 1) if s_sell_total > 0 else None,
            'total_stocks': len(set(list(wyckoff_results.keys()) + list(signal_results.keys()))),
        }
