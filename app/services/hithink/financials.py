"""同花顺财务面：三表 / 能力指标 / 估值快照

失败不静默降级——取不到就抛。悄悄回落到旧口径的财务数字会直接写进建档，
比取不到危险得多。
"""
import hashlib
import json
import logging
import time
from pathlib import Path

from app.services.hithink.client import get_client, to_thscode, from_thscode

logger = logging.getLogger(__name__)

_INCOME = '/api/a-share/financials/income-statements'
_BALANCE = '/api/a-share/financials/balance-sheets'
_CASHFLOW = '/api/a-share/financials/cash-flow-statements'
_INDICATORS = '/api/a-share/financials/indicators'
_VALUATIONS = '/api/a-share/valuations/snapshot'

CACHE_DIR = Path('data/cache/hithink')
INFLIGHT_TTL = 6 * 3600  # 在途报告期 6 小时


def _get(path, params):
    return get_client().get(path, params)


def _to_float(v):
    """空值保留 None，不补零。"""
    if v is None or v == '':
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _cache_path(kind, key):
    digest = hashlib.md5(key.encode('utf-8')).hexdigest()[:16]
    return Path(CACHE_DIR) / kind / f'{digest}.json'


def _is_disclosed(payload):
    """已披露的历史报告期永不过期；在途/未来期给 6 小时。

    判据：最新一期的 period_end_ms 已经过去 —— 报表期已结束即视为已定稿。
    """
    rows = payload if isinstance(payload, list) else [payload]
    ends = [r.get('period_end_ms') for r in rows if isinstance(r, dict) and r.get('period_end_ms')]
    if not ends:
        return False
    return max(ends) / 1000 < time.time()


def _cached(kind, key, loader):
    path = _cache_path(kind, key)
    if path.exists():
        try:
            with open(path, encoding='utf-8') as f:
                entry = json.load(f)
            if entry.get('forever') or time.time() - entry['saved_at'] < INFLIGHT_TTL:
                return entry['payload']
        except (OSError, ValueError, KeyError):
            logger.warning(f'[同花顺.缓存] 读取失败，回源: {path}')

    payload = loader()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(
                {'saved_at': time.time(), 'forever': _is_disclosed(payload), 'payload': payload},
                f, ensure_ascii=False,
            )
    except OSError as e:
        logger.warning(f'[同花顺.缓存] 写入失败（不影响取数）: {e}')
    return payload


def _statements(path, code, period, limit):
    ths = to_thscode(code)

    def loader():
        data = _get(path, {'thscode': ths, 'period': period, 'limit': limit})
        items = data.get('item') or []
        return sorted(items, key=lambda r: r.get('period_end_ms') or 0, reverse=True)

    return _cached('statements', f'{path}|{ths}|{period}|{limit}', loader)


def get_income_statements(code, period='annual', limit=5):
    return _statements(_INCOME, code, period, limit)


def get_balance_sheets(code, period='annual', limit=5):
    return _statements(_BALANCE, code, period, limit)


def get_cash_flow_statements(code, period='annual', limit=5):
    return _statements(_CASHFLOW, code, period, limit)


def get_indicators(code, report):
    """report 形如 '2025-4'（4=年报，1-3=季报）。

    上游 abilities 是数组不是字典，必须迭代。
    """
    ths = to_thscode(code)

    def loader():
        data = _get(_INDICATORS, {'thscode': ths, 'report': report})
        flat = {}
        grouped = {}
        for block in data.get('abilities') or []:
            ability = block.get('ability')
            bucket = grouped.setdefault(ability, {})
            for ind in block.get('indicators') or []:
                val = _to_float(ind.get('value'))
                flat[ind['index_id']] = val
                bucket[ind['index_id']] = val
        flat['_abilities'] = grouped
        return flat

    return _cached('indicators', f'{ths}|{report}', loader)


def get_valuations(codes):
    """批量估值快照，返回 {裸代码: {...}}。"""
    if not codes:
        return {}
    thscodes = ','.join(to_thscode(c) for c in codes)
    data = _get(_VALUATIONS, {'thscodes': thscodes})
    result = {}
    for item in data.get('item') or []:
        result[from_thscode(item['thscode'])] = {
            'name': item.get('name'),
            'pe_ttm': _to_float(item.get('pe_ttm')),
            'pe_mrq': _to_float(item.get('pe_mrq')),
            'pb_mrq': _to_float(item.get('pb_mrq')),
            'ps_ttm': _to_float(item.get('ps_ttm')),
            'pcf_ttm': _to_float(item.get('pcf_ttm')),
        }
    return result
