import pytest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts._docs_schema import (
    DOC_TYPES, SECTORS, RATINGS,
    REQUIRED_FIELDS_BY_TYPE,
    parse_frontmatter, validate_frontmatter,
)

FIXTURE_DIR = Path(__file__).parent / 'fixtures' / 'docs_stub'

def test_enums_are_correct():
    assert DOC_TYPES == {'buffett', 'quarterly', 'cross-sector', 'theme', 'comps'}
    assert 'semiconductor' in SECTORS
    assert 'other' in SECTORS
    assert RATINGS == {'core', 'config', 'watch', 'exclude'}

def test_required_fields_by_type():
    assert 'stock_code' in REQUIRED_FIELDS_BY_TYPE['buffett']
    assert 'period' in REQUIRED_FIELDS_BY_TYPE['quarterly']
    assert 'stock_codes' in REQUIRED_FIELDS_BY_TYPE['cross-sector']
    assert 'theme_name' in REQUIRED_FIELDS_BY_TYPE['theme']
    assert 'period' in REQUIRED_FIELDS_BY_TYPE['comps']

def test_parse_frontmatter_valid():
    fm, body = parse_frontmatter(FIXTURE_DIR / 'valid_buffett.md')
    assert fm['doc_type'] == 'buffett'
    assert fm['stock_code'] == '603986'
    assert isinstance(fm['stock_code'], str)
    assert fm['rating'] == 'watch'
    assert '# 正文' in body

def test_parse_frontmatter_no_yaml():
    p = FIXTURE_DIR / '_no_yaml.md'
    p.write_text('# 纯正文\n', encoding='utf-8')
    try:
        fm, body = parse_frontmatter(p)
        assert fm == {}
        assert '# 纯正文' in body
    finally:
        p.unlink()

def test_validate_valid():
    fm, _ = parse_frontmatter(FIXTURE_DIR / 'valid_buffett.md')
    violations = validate_frontmatter(fm, FIXTURE_DIR / 'valid_buffett.md')
    assert violations == []

def test_validate_missing_required():
    fm, _ = parse_frontmatter(FIXTURE_DIR / 'missing_required.md')
    violations = validate_frontmatter(fm, FIXTURE_DIR / 'missing_required.md')
    assert any('sector' in v for v in violations)
    assert any('rating' in v for v in violations)

def test_validate_bad_enum_and_int_stock_code():
    fm, _ = parse_frontmatter(FIXTURE_DIR / 'bad_enum.md')
    violations = validate_frontmatter(fm, FIXTURE_DIR / 'bad_enum.md')
    assert any('sector' in v and '不存在板块' in v for v in violations)
    assert any('rating' in v and 'invalid_rating' in v for v in violations)
    assert any('stock_code' in v and 'str' in v for v in violations)

def test_validate_watch_requires_watch_reason():
    fm = {
        'doc_type': 'buffett', 'stock_code': '600000', 'stock_name': 'X',
        'sector': 'financial', 'subsector': 'bank', 'themes': ['银行'],
        'rating': 'watch', 'conviction_date': '2026-01-01', 'thesis': 'x',
    }
    violations = validate_frontmatter(fm, Path('/dummy.md'))
    assert any('watch_reason' in v for v in violations)

def test_validate_exclude_requires_exclude_reason():
    fm = {
        'doc_type': 'buffett', 'stock_code': '600000', 'stock_name': 'X',
        'sector': 'financial', 'subsector': 'bank', 'themes': ['银行'],
        'rating': 'exclude', 'conviction_date': '2026-01-01', 'thesis': 'x',
    }
    violations = validate_frontmatter(fm, Path('/dummy.md'))
    assert any('exclude_reason' in v for v in violations)

def test_validate_quarterly_period_matches_dir():
    fm = {
        'doc_type': 'quarterly', 'stock_code': '600000', 'stock_name': 'X',
        'sector': 'financial', 'subsector': 'bank',
        'period': '26Q2', 'date': '2026-04-29',
    }
    path = Path('docs/stock-analytics/quarterly/26q1/foo.md')
    violations = validate_frontmatter(fm, path)
    assert any('period' in v and '26q1' in v for v in violations)
