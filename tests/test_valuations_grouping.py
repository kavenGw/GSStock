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
    assert g['sector'] == 'mat:copper-foil'
    assert g['flat'] is True
    assert g['count'] == 1


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


def test_semiconductor_no_longer_single_bucket():
    rows = [_row('300666', 'semiconductor', 'materials'),
            _row('603986', 'semiconductor', 'storage'),
            _row('300782', 'semiconductor', 'design')]
    groups = group_by_sector(rows)
    # 不再有单一「半导体」顶级组
    assert all(x['sector'] != 'semiconductor' for x in groups)
    sectors = {x['sector'] for x in groups}
    assert {'semi:materials', 'semi:storage', 'semi-other'} <= sectors


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


def test_semi_storage_promoted_to_flat_toplevel():
    rows = [_row('603986', 'semiconductor', 'storage'),
            _row('688008', 'semiconductor', 'storage')]
    groups = group_by_sector(rows)
    g = next(x for x in groups if x['label'] == '存储')
    assert g['sector'] == 'semi:storage'
    assert g['flat'] is True
    assert g['count'] == 2


def test_semi_materials_promoted_with_distinct_label():
    rows = [_row('300666', 'semiconductor', 'materials')]
    groups = group_by_sector(rows)
    g = next(x for x in groups if x['sector'] == 'semi:materials')
    assert g['label'] == '半导体材料'
    assert g['flat'] is True


def test_semi_power_and_equipment_promoted():
    rows = [_row('600460', 'semiconductor', 'power'),
            _row('688037', 'semiconductor', 'equipment')]
    groups = group_by_sector(rows)
    labels = {x['sector']: x for x in groups}
    assert labels['semi:power']['label'] == '功率'
    assert labels['semi:power']['flat'] is True
    assert labels['semi:equipment']['label'] == '设备'
    assert labels['semi:equipment']['flat'] is True


def test_semi_design_not_promoted_goes_to_semi_other():
    rows = [_row('300782', 'semiconductor', 'design'),
            _row('688521', 'semiconductor', 'optical')]
    groups = group_by_sector(rows)
    g = next(x for x in groups if x['sector'] == 'semi-other')
    assert g['label'] == '其余半导体'
    assert g['flat'] is False
    assert {sg['label'] for sg in g['subgroups']} == {'设计', '光学'}


def test_semi_no_subsector_falls_to_semi_other_unclassified():
    rows = [_row('688981', 'semiconductor', None)]
    groups = group_by_sector(rows)
    g = next(x for x in groups if x['sector'] == 'semi-other')
    assert g['subgroups'][0]['label'] == '未分类'
