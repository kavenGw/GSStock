"""腾讯港股行情解析单测 — mock HTTP，验字段映射/volume单位/market标记"""
from unittest.mock import patch, MagicMock

from app.services.unified_stock_data import unified_stock_data_service


def _tencent_resp(text: str) -> MagicMock:
    resp = MagicMock()
    resp.text = text
    return resp


def _build_line(prefix: str, fields: dict, n=78) -> str:
    arr = ['0'] * n
    for i, v in fields.items():
        arr[i] = v
    return f'v_{prefix}="' + '~'.join(arr) + '";'


HK_FIELDS = {0: '100', 1: '建滔积层板', 2: '01888', 3: '34.600', 4: '31.120',
             5: '31.120', 6: '118191487.0', 30: '2026/08/05 13:16:48',
             31: '3.480', 32: '11.18', 33: '34.760', 34: '30.500'}
A_FIELDS = {0: '1', 1: '贵州茅台', 2: '600519', 3: '1800.00', 4: '1790.00',
            5: '1795.00', 6: '1234500', 31: '10.00', 32: '0.56',
            33: '1810.00', 34: '1785.00'}


def test_hk_parse_fields_and_market():
    text = _build_line('hk01888', HK_FIELDS)
    with patch('requests.get', return_value=_tencent_resp(text)):
        result = unified_stock_data_service._fetch_from_tencent(['1888.HK'], '2026-08-05T13:20:00')
    data = result['1888.HK']
    assert data['name'] == '建滔积层板'
    assert data['current_price'] == 34.600
    assert data['prev_close'] == 31.120
    assert data['change'] == 3.480
    assert data['change_percent'] == 11.18
    assert data['high'] == 34.760
    assert data['low'] == 30.500
    assert data['market'] == 'HK'


def test_hk_volume_stays_in_shares():
    text = _build_line('hk01888', HK_FIELDS)
    with patch('requests.get', return_value=_tencent_resp(text)):
        result = unified_stock_data_service._fetch_from_tencent(['1888.HK'], '2026-08-05T13:20:00')
    assert result['1888.HK']['volume'] == 118191487


def test_a_share_volume_still_converted_to_lots():
    text = _build_line('sh600519', A_FIELDS)
    with patch('requests.get', return_value=_tencent_resp(text)):
        result = unified_stock_data_service._fetch_from_tencent(['600519'], '2026-08-05T13:20:00')
    assert result['600519']['volume'] == 12345
    assert result['600519']['market'] == 'A'
