from app.config.stock_codes import MARKET_INDICES


def test_a_market_has_three_indices():
    a = MARKET_INDICES['A']
    codes = [i['code'] for i in a]
    assert codes == ['000001.SS', '399006.SZ', '000688.SS']
    assert [i['name'] for i in a] == ['上证', '创业板', '科创50']


def test_kr_market_has_kospi():
    kr = MARKET_INDICES['KR']
    assert kr == [{'code': '^KS11', 'name': 'KOSPI'}]


def test_only_a_and_kr():
    assert set(MARKET_INDICES.keys()) == {'A', 'KR'}
