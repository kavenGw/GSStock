from app.services.value_dip import ValueDipService, PERIOD_DAYS


def _mk(n, start=100.0, step=1.0):
    return [{'date': f'2026-01-{i + 1:02d}', 'close': start + i * step} for i in range(n)]


def test_normalize_base_zero():
    entries = [{'code': 'X', 'name': '甲', 'market': 'A'}]
    series = ValueDipService._build_series(entries, {'X': _mk(30)}, '30d')
    assert len(series) == 1
    s = series[0]
    assert s['values'][0] == 0.0
    assert s['label'] == '甲'
    assert len(s['dates']) == len(s['values'])


def test_normalize_pct():
    entries = [{'code': 'X', 'name': '甲', 'market': 'A'}]
    trend = {'X': [{'date': 'd1', 'close': 100.0}, {'date': 'd2', 'close': 110.0}]}
    series = ValueDipService._build_series(entries, trend, '30d')
    assert series[0]['values'] == [0.0, 10.0]


def test_window_by_trading_days():
    entries = [{'code': 'X', 'name': '甲', 'market': 'A'}]
    series = ValueDipService._build_series(entries, {'X': _mk(90)}, '7d')
    assert len(series[0]['values']) == 7
    assert PERIOD_DAYS['7d'] == 7


def test_ah_expansion_labels():
    entries = [{'code': '2631.HK', 'name': '天岳先进', 'market': 'HK',
                'ah': {'code': '688234', 'name': '天岳先进', 'market': 'A'}}]
    trend = {'2631.HK': _mk(30), '688234': _mk(30)}
    series = ValueDipService._build_series(entries, trend, '30d')
    assert sorted(s['label'] for s in series) == ['天岳先进(A)', '天岳先进(H)']


def test_degrade_missing_series():
    entries = [{'code': 'X', 'name': '甲', 'market': 'A'},
               {'code': 'Y', 'name': '乙', 'market': 'A'}]
    series = ValueDipService._build_series(entries, {'X': _mk(30)}, '30d')
    assert [s['code'] for s in series] == ['X']


def test_degrade_ah_leg_only():
    entries = [{'code': '2631.HK', 'name': '天岳先进', 'market': 'HK',
                'ah': {'code': '688234', 'name': '天岳先进', 'market': 'A'}}]
    series = ValueDipService._build_series(entries, {'2631.HK': _mk(30)}, '30d')
    assert [s['label'] for s in series] == ['天岳先进(H)']
