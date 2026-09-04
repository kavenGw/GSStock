"""同花顺财务面：三表 / 能力指标 / 估值快照

失败不静默降级——取不到就抛。悄悄回落到旧口径的财务数字会直接写进建档，
比取不到危险得多。
"""
import logging

from app.services.hithink.client import get_client, to_thscode, from_thscode

logger = logging.getLogger(__name__)

_INCOME = '/api/a-share/financials/income-statements'
_BALANCE = '/api/a-share/financials/balance-sheets'
_CASHFLOW = '/api/a-share/financials/cash-flow-statements'
_INDICATORS = '/api/a-share/financials/indicators'
_VALUATIONS = '/api/a-share/valuations/snapshot'


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


def _statements(path, code, period, limit):
    data = _get(path, {'thscode': to_thscode(code), 'period': period, 'limit': limit})
    items = data.get('item') or []
    return sorted(items, key=lambda r: r.get('period_end_ms') or 0, reverse=True)


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
    data = _get(_INDICATORS, {'thscode': to_thscode(code), 'report': report})
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
