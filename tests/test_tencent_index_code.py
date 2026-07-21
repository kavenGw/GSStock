from app.services.unified_stock_data import _tencent_code


def test_bare_stock_codes():
    assert _tencent_code('600519') == 'sh600519'
    assert _tencent_code('300223') == 'sz300223'
    assert _tencent_code('510300') == 'sh510300'


def test_index_codes_respect_suffix():
    assert _tencent_code('000001.SS') == 'sh000001'   # 上证：0开头但在沪
    assert _tencent_code('000688.SS') == 'sh000688'   # 科创50：0开头但在沪
    assert _tencent_code('399006.SZ') == 'sz399006'   # 创业板指
