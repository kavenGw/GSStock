from app.services.unified_stock_data import _tencent_code


def test_bare_stock_codes():
    assert _tencent_code('600519') == 'sh600519'
    assert _tencent_code('300223') == 'sz300223'
    assert _tencent_code('510300') == 'sh510300'


def test_index_codes_respect_suffix():
    assert _tencent_code('000001.SS') == 'sh000001'   # 上证：0开头但在沪
    assert _tencent_code('000688.SS') == 'sh000688'   # 科创50：0开头但在沪
    assert _tencent_code('399006.SZ') == 'sz399006'   # 创业板指


def test_hk_codes_zero_padded():
    assert _tencent_code('1888.HK') == 'r_hk01888'
    assert _tencent_code('700.HK') == 'r_hk00700'
    assert _tencent_code('03690.HK') == 'r_hk03690'
    assert _tencent_code('9992.hk') == 'r_hk09992'
