import json
from pathlib import Path
from unittest.mock import patch

import pytest

from app.services.hithink import provider

FIXTURES = Path(__file__).parent / 'fixtures' / 'hithink'


def load_fixture(name):
    with open(FIXTURES / name, encoding='utf-8') as f:
        return json.load(f)


SNAPSHOT_DATA = load_fixture('snapshot.json')['data']
VALUATION_DATA = load_fixture('valuations.json')['data']


def _patched_fetch(codes, now_str='2026-09-04 15:00:00'):
    """snapshot 走 _get，估值走 financials.get_valuations。"""
    from app.services.hithink import financials
    vals = {
        item['thscode'].split('.')[0]: {
            'name': item['name'], 'pe_ttm': item['pe_ttm'], 'pe_mrq': item['pe_mrq'],
            'pb_mrq': item['pb_mrq'], 'ps_ttm': item['ps_ttm'], 'pcf_ttm': item['pcf_ttm'],
        }
        for item in VALUATION_DATA['item']
    }
    with patch.object(provider, '_get', return_value=SNAPSHOT_DATA):
        with patch.object(financials, 'get_valuations', return_value=vals):
            return provider.fetch_snapshot(codes, now_str)


def test_field_mapping():
    r = _patched_fetch(['600519', '000001'])['600519']

    assert r['code'] == '600519'
    assert r['current_price'] == pytest.approx(1330.33)
    assert r['prev_close'] == pytest.approx(1298.88)
    assert r['open'] == pytest.approx(1295.88)
    assert r['high'] == pytest.approx(1338.86)
    assert r['low'] == pytest.approx(1295.6)
    assert r['change'] == pytest.approx(31.45)
    assert r['change_percent'] == pytest.approx(2.421317)
    assert r['market'] == 'A'
    assert r['last_fetch_time'] == '2026-09-04 15:00:00'


def test_volume_normalized_shares_to_lots():
    r = _patched_fetch(['600519'])['600519']
    # 上游 3418300 股 → A 股契约「手」= // 100
    assert r['volume'] == 34183


def test_valuation_merged_in():
    r = _patched_fetch(['600519'])['600519']
    assert r['name'] == '贵州茅台'
    assert r['pe_ttm'] == pytest.approx(20.421708)
    assert r['pb'] == pytest.approx(6.618895)
    assert r['ps_ttm'] == pytest.approx(9.599605)


def test_missing_valuation_degrades_to_code_as_name():
    """估值端点失败不能拖垮取价——价格是主产物。"""
    from app.services.hithink import financials
    with patch.object(provider, '_get', return_value=SNAPSHOT_DATA):
        with patch.object(financials, 'get_valuations', side_effect=Exception('boom')):
            r = provider.fetch_snapshot(['600519'], '2026-09-04 15:00:00')['600519']

    assert r['current_price'] == pytest.approx(1330.33)
    assert r['name'] == '600519'
    assert r['pe_ttm'] is None
    assert r['pb'] is None


def test_empty_codes_short_circuits():
    with patch.object(provider, '_get') as m:
        assert provider.fetch_snapshot([], '2026-09-04 15:00:00') == {}
    m.assert_not_called()
