from app.routes.valuations import group_by_sector


def _row(code, sector, subsector, base=None, category=None):
    return {
        'stock_code': code,
        'sector': sector,
        'subsector': subsector,
        'category': category,
        'margin_base': base,
    }


def test_nonferrous_promoted_to_flat_toplevel():
    rows = [_row('601899', 'materials', 'nonferrous'),
            _row('000630', 'materials', 'nonferrous')]
    groups = group_by_sector(rows)
    g = next(x for x in groups if x['label'] == '有色金属')
    assert g['sector'] == 'mat:nonferrous'
    assert g['flat'] is True
    assert g['count'] == 2
    assert len(g['subgroups']) == 1


def test_lithium_single_stock_still_promoted():
    rows = [_row('002460', 'materials', 'lithium')]
    groups = group_by_sector(rows)
    g = next(x for x in groups if x['label'] == '锂')
    assert g['sector'] == 'mat:lithium'
    assert g['flat'] is True


def test_copper_foil_promoted():
    rows = [_row('301217', 'materials', 'copper-foil')]
    groups = group_by_sector(rows)
    g = next(x for x in groups if x['label'] == '铜箔')
    assert g['flat'] is True


def test_singleton_subsectors_go_to_materials_other():
    rows = [_row('600309', 'materials', 'chemicals'),
            _row('300224', 'materials', 'ceramics')]
    groups = group_by_sector(rows)
    g = next(x for x in groups if x['sector'] == 'materials-other')
    assert g['label'] == '其余材料'
    assert g['flat'] is False
    assert {sg['label'] for sg in g['subgroups']} == {'化工', '陶瓷'}


def test_non_materials_sector_unaffected():
    rows = [_row('002463', 'electronics', 'pcb')]
    groups = group_by_sector(rows)
    g = next(x for x in groups if x['sector'] == 'electronics')
    assert g['flat'] is False
    assert g['label'] == '电子'


def test_carveout_category_beats_materials_promotion():
    rows = [_row('000729', 'materials', 'nonferrous', category='啤酒')]
    groups = group_by_sector(rows)
    g = next(x for x in groups if x['sector'] == '啤酒')
    assert g['flat'] is False


def test_materials_no_subsector_falls_to_other_unclassified():
    rows = [_row('600309', 'materials', None)]
    groups = group_by_sector(rows)
    g = next(x for x in groups if x['sector'] == 'materials-other')
    assert g['subgroups'][0]['label'] == '未分类'
