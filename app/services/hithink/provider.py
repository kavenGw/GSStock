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
