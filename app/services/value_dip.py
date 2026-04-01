"""价值洼地分析服务 — 对比板块涨幅，找出洼地"""
import logging
from app.config.stock_codes import VALUE_DIP_SECTORS
from app.services.unified_stock_data import unified_stock_data_service

logger = logging.getLogger(__name__)

DIP_THRESHOLD = 0.5


class ValueDipService:

    @staticmethod
    def get_sector_performance() -> dict:
        """获取所有板块的 7d/30d/90d 涨幅及个股明细"""
        all_codes = []
        code_to_name = {}
        for sector in VALUE_DIP_SECTORS.values():
            for code, name in sector['stocks'].items():
                all_codes.append(code)
                code_to_name[code] = name

        trend_result = unified_stock_data_service.get_trend_data(all_codes, days=90)
        trend_map = {}
        if trend_result and trend_result.get('stocks'):
            for stock in trend_result['stocks']:
                trend_map[stock['stock_code']] = stock.get('data', [])

        sectors = []
        for key, sector_cfg in VALUE_DIP_SECTORS.items():
            stocks = []
            for code, name in sector_cfg['stocks'].items():
                data = trend_map.get(code, [])
                stock_info = ValueDipService._calc_stock_changes(code, name, data)
                stocks.append(stock_info)

            sector_info = {
                'key': key,
                'name': sector_cfg['name'],
                'stocks': stocks,
            }
            for period in ('7d', '30d', '90d'):
                changes = [s[f'change_{period}'] for s in stocks if s[f'change_{period}'] is not None]
                sector_info[f'change_{period}'] = round(sum(changes) / len(changes), 2) if changes else None

            sectors.append(sector_info)

        averages = {}
        for period in ('7d', '30d', '90d'):
            values = [s[f'change_{period}'] for s in sectors if s[f'change_{period}'] is not None]
            avg = sum(values) / len(values) if values else 0
            averages[f'avg_{period}'] = round(avg, 2)

            for s in sectors:
                val = s[f'change_{period}']
                if val is not None:
                    threshold = avg - abs(avg) * DIP_THRESHOLD
                    s[f'is_dip_{period}'] = val < threshold
                else:
                    s[f'is_dip_{period}'] = False

        return {
            'sectors': sectors,
            'averages': averages,
            'dip_threshold': DIP_THRESHOLD,
        }

    @staticmethod
    def get_pullback_ranking(days: int = 90) -> list:
        """获取所有股票的高点回退排行（回退幅度从大到小）"""
        period_map = {7: '7d', 30: '30d', 90: '90d'}
        period_key = period_map.get(days, '90d')

        try:
            result = ValueDipService.get_sector_performance()
        except Exception as e:
            logger.error(f'[价值洼地] 高点回退计算失败: {e}')
            return []

        stocks = []
        for sector in result['sectors']:
            for s in sector['stocks']:
                high = s.get(f'high_{period_key}')
                pullback = s.get(f'pullback_{period_key}')
                if high is not None and pullback is not None:
                    stocks.append({
                        'code': s['code'],
                        'name': s['name'],
                        'sector': sector['name'],
                        'price': s['price'],
                        'high': high,
                        'pullback_pct': pullback,
                    })
        stocks.sort(key=lambda x: x['pullback_pct'])
        return stocks

    @staticmethod
    def detect_value_dips() -> list:
        """检测洼地板块，返回需推送的洼地信息列表"""
        try:
            result = ValueDipService.get_sector_performance()
        except Exception as e:
            logger.error(f'[价值洼地] 检测失败: {e}')
            return []

        dips = []
        averages = result['averages']
        for sector in result['sectors']:
            for period in ('7d', '30d', '90d'):
                if sector.get(f'is_dip_{period}'):
                    dips.append({
                        'period': period,
                        'sector_name': sector['name'],
                        'sector_change': sector[f'change_{period}'],
                        'avg_change': averages[f'avg_{period}'],
                        'stocks': [
                            {'name': s['name'], 'change': s[f'change_{period}']}
                            for s in sector['stocks']
                        ],
                    })
        return dips

    @staticmethod
    def _calc_stock_changes(code: str, name: str, data: list) -> dict:
        """从走势数据计算单只股票的各周期涨幅"""
        info = {
            'code': code,
            'name': name,
            'price': None,
            'change_7d': None,
            'change_30d': None,
            'change_90d': None,
            'trend_data': [],
        }
        if not data:
            return info

        # 统一类型转换，确保 close 是 float
        info['trend_data'] = [
            {
                'date': d.get('date', ''),
                'close': float(d.get('close')) if d.get('close') is not None else 0.0
            }
            for d in data
        ]

        # price 添加 None 检查
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

        # 计算各周期高点回退（使用日内最高价）
        for period_key, period_days in [('7d', 7), ('30d', 30), ('90d', len(data))]:
            period_data = data[-period_days:] if period_days < len(data) else data
            highs = [float(d.get('high', d.get('close'))) for d in period_data if d.get('high') is not None or d.get('close') is not None]
            if highs and info['price'] is not None:
                high_val = max(highs)
                info[f'high_{period_key}'] = round(high_val, 2)
                info[f'pullback_{period_key}'] = round((info['price'] - high_val) / high_val * 100, 2) if high_val > 0 else 0

        return info
