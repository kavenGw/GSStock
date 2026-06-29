"""价值洼地分析服务 — 盯盘股扁平涨幅 + 高点回退"""
import logging
from app.services.watch_service import WatchService
from app.services.unified_stock_data import unified_stock_data_service

logger = logging.getLogger(__name__)


class ValueDipService:

    @staticmethod
    def get_watch_performance() -> list:
        """盯盘股扁平涨幅明细：每只含 price / change_7d/30d/90d / high_* / pullback_* / market"""
        watch = WatchService.get_watch_list()
        codes = [w['stock_code'] for w in watch]
        name_map = {w['stock_code']: w['stock_name'] for w in watch}
        market_map = {w['stock_code']: w['market'] for w in watch}

        trend_result = unified_stock_data_service.get_trend_data(codes, days=90)
        trend_map = {}
        if trend_result and trend_result.get('stocks'):
            for stock in trend_result['stocks']:
                trend_map[stock['stock_code']] = stock.get('data', [])

        stocks = []
        for code in codes:
            data = trend_map.get(code, [])
            info = ValueDipService._calc_stock_changes(code, name_map.get(code, code), data)
            info['market'] = market_map.get(code)
            stocks.append(info)
        return stocks

    @staticmethod
    def get_pullback_ranking(days: int = 90) -> list:
        """获取所有盯盘股的高点回退排行（回退幅度从大到小）"""
        period_map = {7: '7d', 30: '30d', 90: '90d'}
        period_key = period_map.get(days, '90d')

        try:
            perf = ValueDipService.get_watch_performance()
        except Exception as e:
            logger.error(f'[价值洼地] 高点回退计算失败: {e}')
            return []

        stocks = []
        for s in perf:
            high = s.get(f'high_{period_key}')
            pullback = s.get(f'pullback_{period_key}')
            if high is not None and pullback is not None:
                stocks.append({
                    'code': s['code'],
                    'name': s['name'],
                    'market': s.get('market'),
                    'price': s['price'],
                    'high': high,
                    'pullback_pct': pullback,
                })
        stocks.sort(key=lambda x: x['pullback_pct'])
        return stocks

    @staticmethod
    def _calc_stock_changes(code: str, name: str, data: list) -> dict:
        """从走势数据计算单只股票的各周期涨幅与高点回退"""
        info = {
            'code': code,
            'name': name,
            'price': None,
            'change_7d': None,
            'change_30d': None,
            'change_90d': None,
        }
        if not data:
            return info

        last_close = data[-1].get('close')
        info['price'] = float(last_close) if last_close is not None else None

        for period_key, days in [('7d', 7), ('30d', 30), ('90d', len(data))]:
            if len(data) >= 2:
                idx = max(0, len(data) - days)
                base_price_raw = data[idx].get('close')
                current_price_raw = data[-1].get('close')
                if base_price_raw is not None and current_price_raw is not None:
                    base_price = float(base_price_raw)
                    current_price = float(current_price_raw)
                    if base_price > 0:
                        info[f'change_{period_key}'] = round(
                            (current_price - base_price) / base_price * 100, 2
                        )

        for period_key, period_days in [('7d', 7), ('30d', 30), ('90d', len(data))]:
            period_data = data[-period_days:] if period_days < len(data) else data
            highs = [float(d.get('high', d.get('close'))) for d in period_data
                     if d.get('high') is not None or d.get('close') is not None]
            if highs and info['price'] is not None:
                high_val = max(highs)
                info[f'high_{period_key}'] = round(high_val, 2)
                info[f'pullback_{period_key}'] = round(
                    (info['price'] - high_val) / high_val * 100, 2) if high_val > 0 else 0

        return info
