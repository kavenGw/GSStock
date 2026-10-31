from copy import deepcopy
from datetime import date

import pytest
import yaml

from app.services.performance import (
    load_companies, performance_rows, previous_period, quarter_change, research_path, validate_company,
)
from scripts.sync_performance import load_input, merge_performance


@pytest.fixture
def company(tmp_path):
    folder = tmp_path / 'sectors' / 'electronics' / 'pcb' / '测试公司'
    folder.mkdir(parents=True)
    (folder / 'index.md').write_text(
        "---\nstock_code: '000001'\nstock_name: 测试公司\n---\n# 测试公司\n", encoding='utf-8',
    )
    data = {
        'schema_version': 1, 'stock_code': '000001', 'stock_name': '测试公司', 'unit': 'CNY_100M',
        'periods': [{
            'period': '2026Q1', 'report_type': 'formal', 'updated_at': '2026-10-31',
            'revenue': 100, 'adjusted_profit': 10, 'inventory': 20,
            'sources': [{'title': '正式季报', 'url': 'https://example.com/q1.pdf', 'locator': 'p2主要指标/p5合并存货'}],
        }],
    }
    return folder, data


@pytest.mark.parametrize('current,previous,profit,label', [
    (10, -20, True, '扭亏'), (-10, 20, True, '转亏'),
    (-10, -20, True, '减亏'), (-20, -10, True, '增亏'),
    (0, -10, True, '减亏'), (10, 0, True, '上季为零'),
    (0, 0, True, '持平'), (10, 0, False, '上季为零'),
    (None, 0, True, '—'), (1, None, False, '—'),
])
def test_change_without_misleading_percentage(current, previous, profit, label):
    assert quarter_change(current, previous, profit) == {'value': None, 'label': label}


def test_positive_base_and_real_zero():
    assert quarter_change(120, 100)['value'] == pytest.approx(20)
    assert quarter_change(0, 100)['value'] == -100
    assert quarter_change(100, 100)['value'] == 0


def test_comparison_requires_adjacent_quarter_and_same_company(company):
    _, data = company
    q1 = data['periods'][0]
    data['source_doc'] = 'sectors/electronics/pcb/测试公司/index.md'
    data['periods'].extend([
        {**q1, 'period': '2025Q4', 'revenue': 80},
        {**q1, 'period': '2026Q3', 'revenue': 200},
    ])
    other = deepcopy(data)
    other['stock_code'] = '000002'
    other['periods'] = [{**q1, 'period': '2026Q2', 'revenue': 50}]
    rows = performance_rows([data, other])
    january = next(row for row in rows if row['period'] == '2026Q1')
    september = next(row for row in rows if row['period'] == '2026Q3')
    assert previous_period('2026Q1') == '2025Q4'
    assert january['revenue_qoq']['value'] == 25
    assert september['revenue_qoq']['value'] is None


@pytest.mark.parametrize('key,value', [
    ('unit', 'CNY'), ('stock_code', '000002'), ('stock_name', '其他公司'),
])
def test_reject_wrong_identity_or_unit(company, key, value):
    folder, data = company
    data[key] = value
    with pytest.raises(ValueError):
        validate_company(data, folder)


@pytest.mark.parametrize('key,value', [
    ('period', '2026H1'), ('report_type', 'forecast'), ('updated_at', '昨天'),
    ('revenue', float('nan')), ('inventory', -1), ('adjusted_profit', True),
    ('sources', []),
])
def test_reject_unusable_financial_record(company, key, value):
    folder, data = company
    data['periods'][0][key] = value
    with pytest.raises(ValueError):
        validate_company(data, folder)


def test_missing_value_requires_reason_and_preserves_zero(company):
    folder, data = company
    row = data['periods'][0]
    row['inventory'] = None
    with pytest.raises(ValueError, match='未解释原因'):
        validate_company(data, folder)
    row['missing_reasons'] = {'inventory': '本期未披露'}
    row['adjusted_profit'] = 0
    row['updated_at'] = date(2026, 10, 31)
    validate_company(data, folder)
    assert row['adjusted_profit'] == 0
    assert row['inventory'] is None
    assert row['updated_at'] == '2026-10-31'


def test_upsert_keeps_history_and_recomputes_after_revision(company, tmp_path):
    folder, data = company
    target = merge_performance(data, folder)
    q2 = deepcopy(data)
    q2['periods'][0].update(period='2026Q2', revenue=120)
    merge_performance(q2, folder)
    data['periods'][0]['revenue'] = 80
    merge_performance(data, folder)
    content = target.read_bytes()
    merge_performance(data, folder)
    assert target.read_bytes() == content
    loaded = load_companies(tmp_path)
    rows = performance_rows(loaded)
    assert len(rows) == 2
    assert rows[0]['revenue_qoq']['value'] == 50
    assert not list(folder.glob('*.tmp'))


def test_a1_structured_block_and_duplicate_guard(company, tmp_path):
    _, data = company
    path = tmp_path / 'A1.md'
    block = '```performance\n' + yaml.safe_dump(data, allow_unicode=True) + '```\n'
    path.write_text('# 明细\n' + block + '## 结论层\n事实已核\n', encoding='utf-8')
    assert load_input(path) == data
    path.write_text(block + block, encoding='utf-8')
    with pytest.raises(ValueError, match='只包含一个'):
        load_input(path)


def test_research_document_cannot_escape_root(company, tmp_path):
    folder, _ = company
    assert research_path((folder / 'index.md').relative_to(tmp_path).as_posix(), tmp_path).is_file()
    for document in ('../secret.md', 'sectors/../../secret.md', 'sectors/missing.md', 'sectors/data.yaml'):
        with pytest.raises(ValueError):
            research_path(document, tmp_path)
