"""估值汇总页测试"""
import pytest

from app.routes.valuations import compute_margin, _extract_price, _fetch_code


def test_compute_margin_normal():
    assert compute_margin(7.78, 17.90) == pytest.approx(7.78 / 17.90 - 1)


def test_compute_margin_upside():
    assert compute_margin(20.0, 10.0) == pytest.approx(1.0)


def test_compute_margin_price_none():
    assert compute_margin(7.78, None) is None


def test_compute_margin_price_zero():
    assert compute_margin(7.78, 0) is None


def test_compute_margin_value_none():
    assert compute_margin(None, 17.90) is None


def test_extract_price_prefers_price_key():
    assert _extract_price({'price': 17.9, 'current_price': 99}) == 17.9


def test_extract_price_falls_back_to_current_price():
    assert _extract_price({'current_price': 12.3}) == 12.3


def test_extract_price_missing():
    assert _extract_price({}) is None


def test_extract_price_zero_is_none():
    assert _extract_price({'price': 0}) is None


def test_load_valuations_parses(tmp_path):
    from app.routes.valuations import load_valuations
    p = tmp_path / 'valuations.yaml'
    p.write_text(
        "- stock_code: '000878'\n"
        "  stock_name: 云南铜业\n"
        "  market: A\n"
        "  currency: CNY\n"
        "  rating: watch\n"
        "  bear: 6.50\n"
        "  base: 7.78\n"
        "  bull: 8.87\n"
        "  conviction_date: '2026-06-02'\n"
        "  source_doc: sectors/materials/nonferrous/2026-06-02-云南铜业-buffett分析.md\n",
        encoding='utf-8',
    )
    rows = load_valuations(p)
    assert len(rows) == 1
    assert rows[0]['stock_code'] == '000878'
    assert rows[0]['base'] == 7.78
    assert rows[0]['stock_name'] == '云南铜业'


def test_load_valuations_missing_returns_empty(tmp_path):
    from app.routes.valuations import load_valuations
    assert load_valuations(tmp_path / 'nope.yaml') == []


def test_load_valuations_empty_file_returns_empty(tmp_path):
    from app.routes.valuations import load_valuations
    p = tmp_path / 'empty.yaml'
    p.write_text('', encoding='utf-8')
    assert load_valuations(p) == []


def test_index_route_smoke(app_client):
    resp = app_client.get('/valuations/')
    assert resp.status_code == 200
    assert '估值'.encode('utf-8') in resp.data


def test_api_prices_structure(app_client, monkeypatch):
    from app.services import unified_stock_data_service

    def fake_prices(codes, force_refresh=False):
        assert force_refresh is True  # ?force=1 必须透传
        return {'000878': {'price': 17.90, 'name': '云南铜业'}}

    monkeypatch.setattr(unified_stock_data_service, 'get_realtime_prices', fake_prices)
    resp = app_client.get('/valuations/api/prices?force=1')
    assert resp.status_code == 200
    body = resp.get_json()
    assert '000878' in body
    row = body['000878']
    assert row['current_price'] == 17.90
    assert row['margin_base'] == pytest.approx(7.78 / 17.90 - 1)


def test_api_prices_missing_price_yields_none(app_client, monkeypatch):
    from app.services import unified_stock_data_service
    monkeypatch.setattr(unified_stock_data_service, 'get_realtime_prices',
                        lambda codes, force_refresh=False: {'000878': {'price': 0}})
    resp = app_client.get('/valuations/api/prices?force=1')
    row = resp.get_json()['000878']
    assert row['current_price'] is None
    assert row['margin_base'] is None


def test_index_has_table_headers_and_refresh(app_client):
    resp = app_client.get('/valuations/')
    html = resp.data.decode('utf-8')
    for col in ('Bear', 'Base', 'Bull', '当前价'):
        assert col in html, f'缺列头 {col}'
    assert 'id="refresh-btn"' in html


def test_load_valuations_filters_rows_without_code(tmp_path):
    from app.routes.valuations import load_valuations
    p = tmp_path / 'v.yaml'
    p.write_text(
        "- stock_code: '000001'\n  base: 1.0\n"
        "- note: 没有 stock_code 的脏行\n"
        "- stock_code: '000002'\n  base: 2.0\n",
        encoding='utf-8',
    )
    rows = load_valuations(p)
    assert [r['stock_code'] for r in rows] == ['000001', '000002']


def test_index_degrades_when_price_fetch_raises(app_client, monkeypatch):
    from app.services import unified_stock_data_service
    def boom(codes, force_refresh=False):
        raise RuntimeError('network down')
    monkeypatch.setattr(unified_stock_data_service, 'get_realtime_prices', boom)
    resp = app_client.get('/valuations/')
    assert resp.status_code == 200  # 降级渲染而非 500


def test_index_renders_market_tabs_with_counts(app_client):
    html = app_client.get('/valuations/').data.decode('utf-8')
    for label in ('全部', 'A股', '港股', '美股'):
        assert label in html, f'缺 tab 文案 {label}'
    from collections import Counter
    from app.routes.valuations import load_valuations
    rows = load_valuations()
    counts = Counter(r.get('market') for r in rows)
    assert f'全部 ({len(rows)})' in html
    assert f"A股 ({counts.get('A', 0)})" in html
    assert f"港股 ({counts.get('HK', 0)})" in html
    assert f"美股 ({counts.get('US', 0)})" in html


def test_index_has_currency_column_and_data_market(app_client):
    html = app_client.get('/valuations/').data.decode('utf-8')
    assert '币种' in html, '缺币种列头'
    assert 'data-market=' in html, '缺行 data-market 属性'
    assert 'switchMarket' in html, '缺 switchMarket JS'
    assert 'toggleSector' in html, '缺 toggleSector JS'
    assert 'toggleSub' in html, '缺 toggleSub JS'


def test_group_by_sector_orders_groups_by_count_desc():
    from app.routes.valuations import group_by_sector
    rows = [
        {'stock_code': 'a', 'sector': 'electronics', 'margin_base': 0.1},
        {'stock_code': 'b', 'sector': 'semiconductor', 'margin_base': 0.2},
        {'stock_code': 'c', 'sector': 'semiconductor', 'margin_base': 0.3},
        {'stock_code': 'd', 'sector': 'semiconductor', 'margin_base': 0.1},
    ]
    groups = group_by_sector(rows)
    assert [g['sector'] for g in groups] == ['semiconductor', 'electronics']
    assert groups[0]['count'] == 3
    assert groups[0]['label'] == '半导体'
    assert groups[1]['label'] == '电子'


def test_group_by_sector_sorts_rows_within_subgroup_by_base_margin_desc():
    from app.routes.valuations import group_by_sector
    rows = [
        {'stock_code': 'lo', 'sector': 'materials', 'subsector': 'nonferrous', 'margin_base': 0.05},
        {'stock_code': 'hi', 'sector': 'materials', 'subsector': 'nonferrous', 'margin_base': 0.50},
        {'stock_code': 'none', 'sector': 'materials', 'subsector': 'nonferrous', 'margin_base': None},
        {'stock_code': 'mid', 'sector': 'materials', 'subsector': 'nonferrous', 'margin_base': 0.20},
    ]
    [grp] = group_by_sector(rows)
    [sg] = grp['subgroups']
    assert [r['stock_code'] for r in sg['rows']] == ['hi', 'mid', 'lo', 'none']


def test_group_by_sector_unknown_sector_falls_back_to_raw():
    from app.routes.valuations import group_by_sector
    [grp] = group_by_sector([{'stock_code': 'x', 'sector': 'weird-thing', 'margin_base': 0.1}])
    assert grp['sector'] == 'weird-thing'
    assert grp['label'] == 'weird-thing'


def test_group_by_sector_none_sector_grouped_as_unclassified():
    from app.routes.valuations import group_by_sector
    [grp] = group_by_sector([{'stock_code': 'x', 'sector': None, 'margin_base': 0.1}])
    assert grp['label'] == '未分类'


def test_group_by_sector_empty_returns_empty():
    from app.routes.valuations import group_by_sector
    assert group_by_sector([]) == []


def test_group_by_sector_tiebreak_by_sector_name():
    from app.routes.valuations import group_by_sector
    rows = [
        {'stock_code': 'a', 'sector': 'semiconductor', 'margin_base': 0.1},
        {'stock_code': 'b', 'sector': 'electronics', 'margin_base': 0.2},
    ]
    groups = group_by_sector(rows)
    assert [g['sector'] for g in groups] == ['electronics', 'semiconductor']


def test_index_renders_sector_group_headers(app_client):
    html = app_client.get('/valuations/').data.decode('utf-8')
    assert 'group-header' in html, '缺板块组头'
    assert 'data-sector=' in html, '缺行/组头 data-sector 属性'
    assert '半导体' in html


def test_group_by_sector_assigns_sector_label_to_rows():
    from app.routes.valuations import group_by_sector
    groups = group_by_sector([
        {'stock_code': 'a', 'sector': 'semiconductor', 'subsector': 'storage', 'margin_base': 0.1},
        {'stock_code': 'b', 'sector': None, 'subsector': None, 'margin_base': 0.2},
    ])
    by_sector = {g['sector']: g for g in groups}
    assert by_sector['semiconductor']['subgroups'][0]['rows'][0]['sector_label'] == '半导体'
    assert by_sector['__none__']['subgroups'][0]['rows'][0]['sector_label'] == '未分类'


def test_index_has_sortable_headers_and_sector_column(app_client):
    html = app_client.get('/valuations/').data.decode('utf-8')
    assert 'data-sort="bear"' in html, '缺 Bear 可排序列头'
    assert 'data-sort="base"' in html, '缺 Base 可排序列头'
    assert 'data-sort="bull"' in html, '缺 Bull 可排序列头'
    assert 'data-mbase=' in html, '缺行 base 边际 data 属性'
    assert 'data-mbear=' in html, '缺行 bear 边际 data 属性'
    assert 'data-mbull=' in html, '缺行 bull 边际 data 属性'
    assert 'col-sector' in html, '缺板块列'
    assert 'sortBy(' in html, '缺 sortBy 列头绑定'


def test_index_has_sort_and_mode_js(app_client):
    html = app_client.get('/valuations/').data.decode('utf-8')
    assert 'function sortBy' in html, '缺 sortBy'
    assert 'function applySort' in html, '缺 applySort'
    assert 'function setMode' in html, '缺 setMode'
    assert 'valuationsSortPref' in html, '缺 localStorage 键'
    assert "setMode('flat')" in html, '缺平铺模式按钮绑定'


def test_fetch_code_hk_zero_padded_numeric():
    assert _fetch_code({'stock_code': '01810', 'market': 'HK'}) == '1810.HK'
    assert _fetch_code({'stock_code': '02643', 'market': 'HK'}) == '2643.HK'
    assert _fetch_code({'stock_code': '03690', 'market': 'HK'}) == '3690.HK'
    assert _fetch_code({'stock_code': '06862', 'market': 'HK'}) == '6862.HK'


def test_fetch_code_a_share_untouched():
    assert _fetch_code({'stock_code': '600519', 'market': 'A'}) == '600519'
    assert _fetch_code({'stock_code': '000878', 'market': 'A'}) == '000878'


def test_fetch_code_us_untouched():
    assert _fetch_code({'stock_code': 'AMD', 'market': 'US'}) == 'AMD'


def test_fetch_code_already_hk_suffixed_untouched():
    assert _fetch_code({'stock_code': '1810.HK', 'market': 'HK'}) == '1810.HK'


def test_fetch_code_missing_market_untouched():
    assert _fetch_code({'stock_code': '01810'}) == '01810'


def test_api_prices_hk_normalizes_and_maps_back(app_client, monkeypatch):
    from app.services import unified_stock_data_service

    seen = {}

    def fake_prices(codes, force_refresh=False):
        seen['codes'] = list(codes)
        return {'1810.HK': {'price': 27.32, 'name': '小米集团-W'}}

    monkeypatch.setattr(unified_stock_data_service, 'get_realtime_prices', fake_prices)
    resp = app_client.get('/valuations/api/prices?force=1')
    assert resp.status_code == 200
    assert '1810.HK' in seen['codes']
    assert '01810' not in seen['codes']
    body = resp.get_json()
    assert body['01810']['current_price'] == 27.32


def test_fetch_code_hk_zero_padded_with_suffix():
    assert _fetch_code({'stock_code': '09992.HK', 'market': 'HK'}) == '9992.HK'
    assert _fetch_code({'stock_code': '01024.HK', 'market': 'HK'}) == '1024.HK'


def test_load_category_map_degrades_to_empty_on_error(monkeypatch):
    from app.routes.valuations import load_category_map

    class _BoomQuery:
        @staticmethod
        def all():
            raise RuntimeError('db down')

    class _BoomModel:
        query = _BoomQuery()

    monkeypatch.setattr('app.models.category.StockCategory', _BoomModel)
    assert load_category_map() == {}


def test_load_category_map_returns_dict(app_client):
    from app.routes.valuations import load_category_map
    with app_client.application.app_context():
        m = load_category_map()
    assert isinstance(m, dict)


def test_enrich_attaches_category_from_cat_map():
    from app.routes.valuations import _enrich
    out = _enrich([{'stock_code': '600132', 'base': 10.0}], {'600132': {'price': 5.0}}, {'600132': '啤酒'})
    assert out[0]['category'] == '啤酒'


def test_enrich_category_none_without_map():
    from app.routes.valuations import _enrich
    out = _enrich([{'stock_code': 'x', 'base': 1.0}], {})
    assert out[0]['category'] is None


def test_group_by_sector_carves_out_whitelisted_category():
    from app.routes.valuations import group_by_sector
    rows = [
        {'stock_code': '600600', 'sector': 'other', 'category': '啤酒', 'subsector': 'beer', 'margin_base': 0.1},
        {'stock_code': '600132', 'sector': 'consumer', 'category': '啤酒', 'subsector': 'beer', 'margin_base': 0.3},
        {'stock_code': '000001', 'sector': 'consumer', 'category': None, 'subsector': None, 'margin_base': 0.2},
    ]
    groups = {g['sector']: g for g in group_by_sector(rows)}
    assert '啤酒' in groups
    beer = groups['啤酒']
    assert beer['label'] == '啤酒'
    assert beer['count'] == 2
    [beer_sg] = beer['subgroups']
    assert [r['stock_code'] for r in beer_sg['rows']] == ['600132', '600600']
    [cons_sg] = groups['consumer']['subgroups']
    assert [r['stock_code'] for r in cons_sg['rows']] == ['000001']


def test_group_by_sector_non_whitelisted_category_uses_sector():
    from app.routes.valuations import group_by_sector
    [grp] = group_by_sector([{'stock_code': 'x', 'sector': 'consumer', 'category': '赛事消费', 'margin_base': 0.1}])
    assert grp['sector'] == 'consumer'
    assert grp['label'] == '消费'


def test_group_by_sector_carveout_row_gets_category_label():
    from app.routes.valuations import group_by_sector
    [grp] = group_by_sector([{'stock_code': '600132', 'sector': 'consumer', 'category': '啤酒', 'subsector': 'beer', 'margin_base': 0.1}])
    assert grp['subgroups'][0]['rows'][0]['sector_label'] == '啤酒'


def test_index_renders_beer_group_when_categorized(app_client, monkeypatch):
    from app.routes import valuations as val
    monkeypatch.setattr(val, 'load_category_map',
                        lambda: {'600132': '啤酒', '600600': '啤酒', '000729': '啤酒'})
    html = app_client.get('/valuations/').data.decode('utf-8')
    assert '啤酒' in html
    assert 'data-sector="啤酒"' in html


def test_index_has_group_reorder_js(app_client):
    html = app_client.get('/valuations/').data.decode('utf-8')
    assert 'MARGIN_SORT_KEYS' in html, '缺组联动触发列常量'
    assert 'defaultSectorOrder' in html, '缺默认一级组顺序捕获'
    assert 'defaultSubOrder' in html, '缺默认二级组顺序捕获'
    assert 'function repRows' in html, '缺组代表值函数'


def test_switch_market_triggers_resort(app_client):
    import re
    html = app_client.get('/valuations/').data.decode('utf-8')
    m = re.search(r'function switchMarket\([^)]*\)\s*\{(.*?)\n\}', html, re.S)
    assert m, '找不到 switchMarket 函数体'
    assert 'applySort()' in m.group(1), 'switchMarket 未调用 applySort'


def test_subsector_of_extracts_from_source_doc():
    from app.routes.valuations import subsector_of
    assert subsector_of({'source_doc': 'sectors/semiconductor/storage/2026-x.md'}) == 'storage'


def test_subsector_of_missing_doc_returns_none():
    from app.routes.valuations import subsector_of
    assert subsector_of({}) is None


def test_subsector_of_short_path_returns_none():
    from app.routes.valuations import subsector_of
    assert subsector_of({'source_doc': 'sectors/semiconductor'}) is None


def test_subsector_of_non_sectors_path_returns_none():
    from app.routes.valuations import subsector_of
    assert subsector_of({'source_doc': 'cross-sector/2026-x.md'}) is None


def test_subsector_labels_maps_common_slugs():
    from app.routes.valuations import SUBSECTOR_LABELS
    assert SUBSECTOR_LABELS['storage'] == '存储'
    assert SUBSECTOR_LABELS['nonferrous'] == '有色'


def test_enrich_attaches_subsector_from_source_doc():
    from app.routes.valuations import _enrich
    out = _enrich([{'stock_code': 'a', 'base': 1.0, 'source_doc': 'sectors/materials/nonferrous/x.md'}], {})
    assert out[0]['subsector'] == 'nonferrous'


def test_enrich_subsector_none_without_doc():
    from app.routes.valuations import _enrich
    out = _enrich([{'stock_code': 'a', 'base': 1.0}], {})
    assert out[0]['subsector'] is None


def test_group_by_sector_builds_subgroups_by_subsector():
    from app.routes.valuations import group_by_sector
    rows = [
        {'stock_code': 'a', 'sector': 'semiconductor', 'subsector': 'storage', 'margin_base': 0.1},
        {'stock_code': 'b', 'sector': 'semiconductor', 'subsector': 'storage', 'margin_base': 0.2},
        {'stock_code': 'c', 'sector': 'semiconductor', 'subsector': 'design', 'margin_base': 0.3},
    ]
    [grp] = group_by_sector(rows)
    assert grp['count'] == 3
    subs = {sg['key']: sg for sg in grp['subgroups']}
    assert subs['storage']['count'] == 2
    assert subs['storage']['label'] == '存储'
    assert subs['design']['count'] == 1
    assert [sg['key'] for sg in grp['subgroups']] == ['storage', 'design']


def test_group_by_sector_none_subsector_is_unclassified_subgroup():
    from app.routes.valuations import group_by_sector
    [grp] = group_by_sector([{'stock_code': 'a', 'sector': 'energy', 'subsector': None, 'margin_base': 0.1}])
    [sg] = grp['subgroups']
    assert sg['key'] == '__none__'
    assert sg['label'] == '未分类'


def test_group_by_sector_subgroup_id_is_sector_scoped():
    from app.routes.valuations import group_by_sector
    rows = [
        {'stock_code': 'a', 'sector': 'semiconductor', 'subsector': 'pcb', 'margin_base': 0.1},
        {'stock_code': 'b', 'sector': 'electronics', 'subsector': 'pcb', 'margin_base': 0.2},
    ]
    groups = {g['sector']: g for g in group_by_sector(rows)}
    sem_id = groups['semiconductor']['subgroups'][0]['subgroup_id']
    ele_id = groups['electronics']['subgroups'][0]['subgroup_id']
    assert sem_id == 'semiconductor__pcb'
    assert ele_id == 'electronics__pcb'
    assert sem_id != ele_id


def test_group_by_sector_subgroups_tiebreak_by_key():
    from app.routes.valuations import group_by_sector
    rows = [
        {'stock_code': 'a', 'sector': 'media', 'subsector': 'short-video', 'margin_base': 0.1},
        {'stock_code': 'b', 'sector': 'media', 'subsector': 'digital-marketing', 'margin_base': 0.2},
    ]
    [grp] = group_by_sector(rows)
    assert [sg['key'] for sg in grp['subgroups']] == ['digital-marketing', 'short-video']


def test_index_renders_nested_subgroup_headers(app_client):
    html = app_client.get('/valuations/').data.decode('utf-8')
    assert 'group-header lvl1' in html, '缺一级组头'
    assert 'group-header lvl2' in html, '缺二级组头'
    assert 'data-subgroup=' in html, '缺二级组头/行 data-subgroup'
    assert 'function recompute' in html, '缺统一可见性重算函数'


def test_index_subgroup_id_is_sector_scoped_in_html(app_client):
    import re
    html = app_client.get('/valuations/').data.decode('utf-8')
    ids = set(re.findall(r'data-subgroup="([^"]+)"', html))
    assert ids, '页面无 data-subgroup'
    assert all('__' in i for i in ids), 'subgroup_id 应为 sector__sub 形态'
