import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / '.claude' / 'skills' / 'news-impact' / 'scripts'))
from pool_index import match_pool  # noqa: E402


def _rec(code, name, sector, subsector, date, themes=(), doc_type='buffett', rating='watch'):
    return {
        'path': f'sectors/{sector}/{subsector}/{date}-{name}-{doc_type}.md',
        'doc_type': doc_type, 'codes': [code], 'names': [name],
        'sector': sector, 'subsector': subsector, 'themes': list(themes),
        'rating': rating, 'thesis': 'x' * 200, 'date': date,
    }


POOL = [
    _rec('603986', '兆易创新', 'semiconductor', 'storage', '2026-08-19', ['memory', 'MCU']),
    _rec('603986', '兆易创新', 'semiconductor', 'storage', '2026-05-01', ['memory']),
    _rec('603986', '兆易创新', 'semiconductor', 'storage', '2026-08-20', doc_type='quarterly'),
    _rec('688766', '普冉股份', 'semiconductor', 'storage', '2026-08-10', ['NOR']),
    _rec('688396', '华润微', 'semiconductor', 'power', '2026-07-01', ['功率半导体']),
    _rec('600519', '贵州茅台', 'consumer', 'liquor', '2026-06-01', ['白酒']),
    _rec('300223', '北京君正', 'semiconductor', 'storage', '2026-07-15', ['memory', 'MCU']),
]


def _codes(tier):
    return [r['code'] for r in tier]


def test_t1_direct_hit_by_name_and_code():
    out = match_pool(POOL, keywords=['兆易'], codes=['688396'])
    assert _codes(out['T1']) == ['603986', '688396']


def test_t2_same_subsector_as_t1_hit():
    out = match_pool(POOL, keywords=['兆易'])
    assert set(_codes(out['T2'])) == {'688766', '300223'}


def test_t3_theme_keyword_hit_beats_same_sector():
    out = match_pool(POOL, keywords=['兆易', '功率半导体', '白酒'])
    assert _codes(out['T3']) == ['688396', '600519']


def test_t4_same_sector_only_when_wide():
    narrow = match_pool(POOL, keywords=['兆易'])
    assert narrow['T4'] == []
    assert narrow['T4_count'] == 1
    wide = match_pool(POOL, keywords=['兆易'], wide=True)
    assert _codes(wide['T4']) == ['688396']
    assert '600519' not in sum((_codes(wide[t]) for t in ('T1', 'T2', 'T3', 'T4')), [])


def test_explicit_sector_subsector_seed_t2_t4():
    out = match_pool(POOL, keywords=[], sector='semiconductor', subsector='power', wide=True)
    assert _codes(out['T2']) == ['688396']
    assert set(_codes(out['T4'])) == {'603986', '688766', '300223'}


def test_keyword_matching_subsector_name_seeds_t2():
    out = match_pool(POOL, keywords=['Power'])
    assert _codes(out['T1']) == []
    assert _codes(out['T2']) == ['688396']


def test_dedup_keeps_latest_buffett_doc_and_truncates_thesis():
    out = match_pool(POOL, keywords=['兆易'])
    hit = out['T1'][0]
    assert hit['path'].endswith('2026-08-19-兆易创新-buffett.md')
    assert hit['rating'] == 'watch'
    assert len(hit['thesis']) == 80


def test_no_hit_returns_empty_tiers():
    out = match_pool(POOL, keywords=['不存在'])
    assert all(out[t] == [] for t in ('T1', 'T2', 'T3', 'T4'))
    assert out['T4_count'] == 0
