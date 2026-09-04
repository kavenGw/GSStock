"""同花顺取价面

snapshot 端点不返回中文名，valuations 端点返回 name 且同样支持批量，
故一次取价并发打两个端点再合并——补齐 name，并白拿 pe_ttm / pb / ps_ttm。
估值端点失败不拖垮取价：价格是主产物，估值降级为 None。
"""
import logging
from concurrent.futures import ThreadPoolExecutor

from app.services.data_source_providers import DataSourceProvider
from app.services.hithink.client import get_client, to_thscode, from_thscode

logger = logging.getLogger(__name__)

_SNAPSHOT = '/api/a-share/prices/snapshot'
_HISTORICAL = '/api/a-share/prices/historical'


def _get(path, params):
    return get_client().get(path, params)


def fetch_snapshot(codes, now_str):
    """批量取 A 股快照，返回 {裸代码: 价格 dict}。"""
    if not codes:
        return {}

    from app.services.hithink import financials
    from app.services.unified_stock_data import _normalize_volume

    thscodes = ','.join(to_thscode(c) for c in codes)

    with ThreadPoolExecutor(max_workers=2) as executor:
        snap_future = executor.submit(_get, _SNAPSHOT, {'thscodes': thscodes})
        val_future = executor.submit(financials.get_valuations, codes)

        data = snap_future.result()
        try:
            valuations = val_future.result()
        except Exception as e:
            logger.warning(f'[同花顺.估值] 合并失败，价格不受影响: {e}')
            valuations = {}

    result = {}
    for item in data.get('item') or []:
        code = from_thscode(item['thscode'])
        val = valuations.get(code) or {}
        result[code] = {
            'code': code,
            'name': val.get('name') or code,
            'current_price': item.get('last_price'),
            'change': item.get('price_change'),
            'change_percent': item.get('price_change_ratio_pct'),
            'volume': _normalize_volume(item.get('volume'), 'hithink_snapshot', 'A'),
            'high': item.get('high_price'),
            'low': item.get('low_price'),
            'open': item.get('open_price'),
            'prev_close': item.get('prev_price'),
            'pe_ttm': val.get('pe_ttm'),
            'pb': val.get('pb_mrq'),
            'ps_ttm': val.get('ps_ttm'),
            'last_fetch_time': now_str,
            'market': 'A',
        }

    if result:
        names = ', '.join(d['name'] for d in result.values())
        logger.info(f'[数据服务.实时价格] 同花顺 → {names} ({len(result)}只)')
    return result


class HithinkProvider(DataSourceProvider):
    """同花顺 A 股数据源。日 K 仅作 fallback——复权因子需自行推导，腾讯 fqkline 直接给 qfq。"""

    name = 'hithink'
    market = 'A'

    def is_available(self) -> bool:
        return get_client().is_available()

    def get_realtime_price(self, symbol: str):
        from datetime import datetime
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        return fetch_snapshot([symbol], now_str).get(from_thscode(to_thscode(symbol)))

    def get_batch_prices(self, symbols: list) -> dict:
        from datetime import datetime
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        return fetch_snapshot(symbols, now_str)

    def get_historical_data(self, symbol: str, days: int):
        from datetime import datetime, timedelta

        from app.services.unified_stock_data import _normalize_volume

        end_ms = int(datetime.now().timestamp() * 1000)
        start_ms = int((datetime.now() - timedelta(days=days * 2)).timestamp() * 1000)

        data = _get(_HISTORICAL, {
            'thscode': to_thscode(symbol),
            'start': start_ms,
            'end': end_ms,
            'interval': '1d',
            'adjust': 'forward',
        })
        items = data.get('item') or []
        if not items:
            return None

        bars = []
        prev_close = None
        for row in sorted(items, key=lambda r: r.get('date_ms') or 0):
            close = row.get('close_price')
            change_pct = ((close - prev_close) / prev_close * 100) if (prev_close and close) else 0
            bars.append({
                'date': datetime.fromtimestamp(row['date_ms'] / 1000).strftime('%Y-%m-%d'),
                'open': row.get('open_price'),
                'high': row.get('high_price'),
                'low': row.get('low_price'),
                'close': close,
                'volume': _normalize_volume(row.get('volume'), 'hithink_snapshot', 'A'),
                'change_pct': round(change_pct, 2),
            })
            prev_close = close

        return {
            'stock_code': from_thscode(to_thscode(symbol)),
            'stock_name': from_thscode(to_thscode(symbol)),
            'data': bars[-days:] if len(bars) > days else bars,
            'source': 'hithink',
        }
