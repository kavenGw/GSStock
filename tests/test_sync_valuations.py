from pathlib import Path
import sys

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.sync_valuations import (
    infer_market, default_currency, build_entry, upsert, sync,
)


def test_infer_market():
    assert infer_market('603986') == 'A'
    assert infer_market('000021') == 'A'
    assert infer_market('00992.HK') == 'HK'
    assert infer_market('03888') == 'HK'
    assert infer_market('AAPL') == 'US'


def test_default_currency():
    assert default_currency('A') == 'CNY'
    assert default_currency('HK') == 'HKD'
    assert default_currency('US') == 'USD'


def test_build_entry_flattens_valuation():
    fm = {
        'stock_code': '603986', 'stock_name': '兆易创新',
        'sector': 'semiconductor', 'rating': 'watch', 'watch_reason': 'x',
        'conviction_date': '2026-05-31',
        'valuation': {'bear': 100.0, 'base': 120.0, 'bull': 150.0,
                      'currency': 'CNY', 'dividend_yield': 1.2},
    }
    e = build_entry(fm, 'sectors/semiconductor/storage/foo.md')
    assert e['stock_code'] == '603986'
    assert e['market'] == 'A'
    assert e['currency'] == 'CNY'
    assert (e['bear'], e['base'], e['bull']) == (100.0, 120.0, 150.0)
    assert e['dividend_yield'] == 1.2
    assert e['watch_reason'] == 'x'
    assert e['conviction_date'] == '2026-05-31'
    assert e['source_doc'] == 'sectors/semiconductor/storage/foo.md'
    keys = list(e.keys())
    assert keys.index('stock_code') == 0
    assert keys.index('bear') < keys.index('conviction_date')


def test_build_entry_null_and_no_dividend():
    fm = {
        'stock_code': '00992.HK', 'stock_name': '联想集团',
        'sector': 'electronics', 'rating': 'config',
        'conviction_date': '2026-06-08',
        'valuation': {'bear': None, 'base': None, 'bull': None, 'currency': 'HKD'},
    }
    e = build_entry(fm, 'foo.md')
    assert e['bear'] is None
    assert 'dividend_yield' not in e
    assert 'watch_reason' not in e
    assert e['currency'] == 'HKD'


def test_build_entry_infers_currency_when_absent():
    fm = {
        'stock_code': '603986', 'stock_name': 'X', 'sector': 'semiconductor',
        'rating': 'core', 'conviction_date': '2026-05-31',
        'valuation': {'bear': 1.0, 'base': 2.0, 'bull': 3.0},
    }
    e = build_entry(fm, 'foo.md')
    assert e['currency'] == 'CNY'


def test_upsert_updates_existing_in_place():
    entries = [{'stock_code': '603986', 'base': 1}, {'stock_code': '000001', 'base': 2}]
    upsert(entries, {'stock_code': '603986', 'base': 99})
    assert entries[0]['base'] == 99
    assert len(entries) == 2


def test_upsert_appends_new():
    entries = [{'stock_code': '603986'}]
    upsert(entries, {'stock_code': '000001'})
    assert len(entries) == 2 and entries[1]['stock_code'] == '000001'


def _write_doc(d: Path, name: str, code: str, base: float):
    d.mkdir(parents=True, exist_ok=True)
    (d / name).write_text(
        '---\n'
        'doc_type: buffett\n'
        f"stock_code: '{code}'\n"
        'stock_name: 兆易创新\n'
        'sector: semiconductor\n'
        'subsector: storage\n'
        'themes: [memory]\n'
        'rating: watch\n'
        'watch_reason: x\n'
        'conviction_date: 2026-05-31\n'
        'thesis: t\n'
        'valuation:\n'
        '  bear: 100.0\n'
        f'  base: {base}\n'
        '  bull: 150.0\n'
        '  currency: CNY\n'
        '  dividend_yield: 1.2\n'
        '---\n# 正文\n', encoding='utf-8')


def test_sync_end_to_end_creates_yaml(tmp_path):
    docs_root = tmp_path / 'docs'
    _write_doc(docs_root / 'sectors/semiconductor/storage',
               '2026-05-31-兆易创新-buffett分析.md', '603986', 120.0)
    yaml_path = tmp_path / 'valuations.yaml'
    n = sync(docs_root, yaml_path)
    assert n == 1
    data = yaml.safe_load(yaml_path.read_text(encoding='utf-8'))
    assert data[0]['stock_code'] == '603986'
    assert data[0]['base'] == 120.0
    assert data[0]['source_doc'] == 'sectors/semiconductor/storage/2026-05-31-兆易创新-buffett分析.md'


def test_sync_skips_docs_without_valuation(tmp_path):
    docs_root = tmp_path / 'docs'
    d = docs_root / 'sectors/semiconductor/storage'
    d.mkdir(parents=True)
    (d / '2026-01-01-无估值-buffett分析.md').write_text(
        "---\ndoc_type: buffett\nstock_code: '000001'\nstock_name: X\n"
        "sector: semiconductor\nsubsector: s\nthemes: [t]\nrating: core\n"
        "conviction_date: 2026-01-01\nthesis: t\n---\n# 正文\n", encoding='utf-8')
    yaml_path = tmp_path / 'valuations.yaml'
    n = sync(docs_root, yaml_path)
    assert n == 0
    assert not yaml_path.exists() or yaml.safe_load(yaml_path.read_text(encoding='utf-8')) in (None, [])


def test_sync_upserts_into_existing_yaml(tmp_path):
    docs_root = tmp_path / 'docs'
    _write_doc(docs_root / 'sectors/semiconductor/storage',
               '2026-05-31-兆易创新-buffett分析.md', '603986', 120.0)
    yaml_path = tmp_path / 'valuations.yaml'
    yaml_path.write_text(
        yaml.dump([
            {'stock_code': '000878', 'stock_name': '云南铜业', 'base': 7.78},
            {'stock_code': '603986', 'stock_name': '旧', 'base': 1.0},
        ], allow_unicode=True, sort_keys=False), encoding='utf-8')
    n = sync(docs_root, yaml_path)
    assert n == 1
    data = yaml.safe_load(yaml_path.read_text(encoding='utf-8'))
    assert len(data) == 2  # 未新增，原 603986 被更新
    by_code = {r['stock_code']: r for r in data}
    assert by_code['603986']['base'] == 120.0   # 已更新
    assert by_code['000878']['base'] == 7.78     # 未匹配条目保留


def test_sync_only_stock_code_filter(tmp_path):
    docs_root = tmp_path / 'docs'
    base_dir = docs_root / 'sectors/semiconductor/storage'
    _write_doc(base_dir, '2026-05-31-兆易创新-buffett分析.md', '603986', 120.0)
    _write_doc(base_dir, '2026-05-31-其它-buffett分析.md', '000001', 50.0)
    yaml_path = tmp_path / 'valuations.yaml'
    n = sync(docs_root, yaml_path, only_code='603986')
    assert n == 1
    data = yaml.safe_load(yaml_path.read_text(encoding='utf-8'))
    assert [r['stock_code'] for r in data] == ['603986']
