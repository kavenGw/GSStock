import json
import shutil
from pathlib import Path
from unittest.mock import patch

import pytest

from app.services.hithink import financials

FIXTURES = Path(__file__).parent / 'fixtures' / 'hithink'


def load_fixture(name):
    with open(FIXTURES / name, encoding='utf-8') as f:
        return json.load(f)


@pytest.fixture(autouse=True)
def _isolate_cache_dir(tmp_path):
    """财务缓存落盘到 tmp_path，避免污染仓库 data/cache/hithink/ 与跨测试状态泄漏。"""
    with patch.object(financials, 'CACHE_DIR', tmp_path):
        yield


def test_income_statements_returns_periods_newest_first():
    data = load_fixture('income_annual.json')['data']
    with patch.object(financials, '_get', return_value=data) as m:
        rows = financials.get_income_statements('600519', period='annual', limit=2)

    assert [r['fiscal_year'] for r in rows] == [2025, 2024]
    assert rows[0]['operating_income'] == pytest.approx(168838102514.79)
    assert rows[0]['parent_holder_net_profit'] == pytest.approx(82320067101.68)
    assert m.call_args[0][1]['thscode'] == '600519.SH'
    assert m.call_args[0][1]['limit'] == 2


def test_income_statements_normalizes_bare_and_prefixed_codes():
    data = load_fixture('income_annual.json')['data']
    for raw in ('600519', 'sh600519', '600519.SH'):
        # 三种写法归一化后是同一个 thscode，缓存 key 相同 —— 每轮清空缓存，
        # 避免上一轮的缓存命中吃掉本轮对 _get 的调用，破坏"验证归一化"的原意。
        shutil.rmtree(financials.CACHE_DIR, ignore_errors=True)
        with patch.object(financials, '_get', return_value=data) as m:
            financials.get_income_statements(raw)
        assert m.call_args[0][1]['thscode'] == '600519.SH'


def test_indicators_flattens_abilities_array():
    data = load_fixture('indicators.json')['data']
    with patch.object(financials, '_get', return_value=data):
        ind = financials.get_indicators('600519', report='2025-4')

    # abilities 是数组不是字典，必须迭代
    assert ind['index_weighted_avg_roe'] == pytest.approx(32.53)
    assert ind['sale_gross_margin'] == pytest.approx(91.1796)
    assert ind['assets_debt_ratio'] == pytest.approx(16.4154)
    assert ind['calculate_operating_income_yoy_growth_ratio'] == pytest.approx(-1.206004)
    # null 保留为 None，不补零
    assert ind['earned_interest_multiple'] is None
    # 分组视图保留
    assert set(ind['_abilities']) == {
        'growth', 'profitability', 'solvency', 'operation', 'cash-flow'
    }
    assert ind['_abilities']['profitability']['index_deduct_weighted_avg_roe'] == pytest.approx(32.52)


def test_valuations_keyed_by_bare_code():
    data = load_fixture('valuations.json')['data']
    with patch.object(financials, '_get', return_value=data) as m:
        val = financials.get_valuations(['600519'])

    assert m.call_args[0][1]['thscodes'] == '600519.SH'
    assert val['600519']['name'] == '贵州茅台'
    assert val['600519']['pe_ttm'] == pytest.approx(20.421708)
    assert val['600519']['pb_mrq'] == pytest.approx(6.618895)


def test_valuations_empty_codes_short_circuits():
    with patch.object(financials, '_get') as m:
        assert financials.get_valuations([]) == {}
    m.assert_not_called()


def test_statements_cache_hits_within_ttl_and_refetches_after():
    data = load_fixture('income_annual.json')['data']
    with patch.object(financials, '_get', return_value=data) as m, \
         patch.object(financials.time, 'time', return_value=1000.0):
        first = financials.get_income_statements('600519', period='annual', limit=2)
        second = financials.get_income_statements('600519', period='annual', limit=2)

    assert m.call_count == 1
    assert first == second

    with patch.object(financials, '_get', return_value=data) as m, \
         patch.object(financials.time, 'time', return_value=1000.0 + financials.STATEMENTS_TTL + 1):
        third = financials.get_income_statements('600519', period='annual', limit=2)

    assert m.call_count == 1
    assert third == first


def test_cache_key_separates_period_and_limit():
    data = load_fixture('income_annual.json')['data']
    with patch.object(financials, '_get', return_value=data) as m:
        financials.get_income_statements('600519', period='annual', limit=2)
        financials.get_income_statements('600519', period='annual', limit=5)
        financials.get_income_statements('600519', period='quarterly', limit=2)

    assert m.call_count == 3


def test_valuations_never_cached():
    data = load_fixture('valuations.json')['data']
    with patch.object(financials, '_get', return_value=data) as m:
        financials.get_valuations(['600519'])
        financials.get_valuations(['600519'])

    assert m.call_count == 2
