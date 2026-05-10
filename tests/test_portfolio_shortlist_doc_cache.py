import json
import pytest
from pathlib import Path

from app.services.portfolio_shortlist.doc_cache import DocCache


@pytest.fixture
def cache_dir(tmp_path):
    return tmp_path / 'shortlist'


@pytest.fixture
def doc_a(tmp_path):
    p = tmp_path / 'doc_a.md'
    p.write_text('content A v1', encoding='utf-8')
    return p


@pytest.fixture
def doc_b(tmp_path):
    p = tmp_path / 'doc_b.md'
    p.write_text('content B', encoding='utf-8')
    return p


def test_first_call_invokes_extractor_and_writes_cache(cache_dir, doc_a):
    cache = DocCache(cache_dir)
    calls = []

    def extractor(code, paths):
        calls.append(code)
        return {'logic': 'L', 'valuation': 'V', 'catalyst': 'C',
                'theme_fit': 'T', 'realized_or_invalidated': 'R'}

    summary = cache.get_or_compute('600000', '某股', [doc_a], extractor)

    assert calls == ['600000']
    assert summary['logic'] == 'L'
    cache_file = cache_dir / '600000.json'
    assert cache_file.exists()
    data = json.loads(cache_file.read_text(encoding='utf-8'))
    assert data['stock_code'] == '600000'
    assert len(data['docs']) == 1
    assert data['docs'][0]['md5']  # md5 字段非空


def test_unchanged_md5_skips_extractor(cache_dir, doc_a):
    cache = DocCache(cache_dir)
    calls = []

    def extractor(code, paths):
        calls.append(code)
        return {'logic': 'first', 'valuation': '', 'catalyst': '',
                'theme_fit': '', 'realized_or_invalidated': ''}

    cache.get_or_compute('600000', '某股', [doc_a], extractor)
    cache.get_or_compute('600000', '某股', [doc_a], extractor)

    assert calls == ['600000'], '第二次应命中缓存，不调 extractor'


def test_md5_change_triggers_recompute(cache_dir, doc_a):
    cache = DocCache(cache_dir)
    calls = []

    def extractor(code, paths):
        calls.append(code)
        return {'logic': 'x', 'valuation': '', 'catalyst': '',
                'theme_fit': '', 'realized_or_invalidated': ''}

    cache.get_or_compute('600000', '某股', [doc_a], extractor)
    doc_a.write_text('content A v2 CHANGED', encoding='utf-8')
    cache.get_or_compute('600000', '某股', [doc_a], extractor)

    assert calls == ['600000', '600000'], 'doc 内容变化应重算'


def test_new_doc_added_triggers_recompute(cache_dir, doc_a, doc_b):
    cache = DocCache(cache_dir)
    calls = []

    def extractor(code, paths):
        calls.append(code)
        return {'logic': 'x', 'valuation': '', 'catalyst': '',
                'theme_fit': '', 'realized_or_invalidated': ''}

    cache.get_or_compute('600000', '某股', [doc_a], extractor)
    cache.get_or_compute('600000', '某股', [doc_a, doc_b], extractor)

    assert calls == ['600000', '600000'], '新增 doc 应重算'


def test_version_mismatch_triggers_recompute(cache_dir, doc_a):
    cache = DocCache(cache_dir, schema_version=1)
    calls = []

    def extractor(code, paths):
        calls.append(code)
        return {'logic': 'x', 'valuation': '', 'catalyst': '',
                'theme_fit': '', 'realized_or_invalidated': ''}

    cache.get_or_compute('600000', '某股', [doc_a], extractor)
    cache_v2 = DocCache(cache_dir, schema_version=2)
    cache_v2.get_or_compute('600000', '某股', [doc_a], extractor)

    assert calls == ['600000', '600000'], 'schema_version 变化应重算'
