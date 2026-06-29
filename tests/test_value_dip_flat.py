from app.services.value_dip import ValueDipService


def _fake_trend(codes, days=90):
    # 造 30 天递减再回升的收盘价：高点在中段，末值低于高点 → 有回退
    def series(base):
        closes = [base + i for i in range(20)] + [base + 20 - j for j in range(10)]
        return [{'date': f'2026-06-{(i % 28) + 1:02d}', 'close': c, 'high': c}
                for i, c in enumerate(closes)]
    return {'stocks': [{'stock_code': c, 'stock_name': c, 'data': series(10 + idx)}
                       for idx, c in enumerate(codes)],
            'date_range': {}}


def _patch(monkeypatch, codes):
    watch = [{'stock_code': c, 'stock_name': f'N{c}', 'market': m}
             for c, m in codes]
    monkeypatch.setattr('app.services.value_dip.WatchService.get_watch_list',
                        staticmethod(lambda: watch))
    monkeypatch.setattr('app.services.value_dip.unified_stock_data_service.get_trend_data',
                        _fake_trend)


def test_get_watch_performance_flat_shape(monkeypatch):
    _patch(monkeypatch, [('300223', 'A'), ('2631.HK', 'HK'), ('000660.KS', 'KR')])
    rows = ValueDipService.get_watch_performance()
    assert [r['code'] for r in rows] == ['300223', '2631.HK', '000660.KS']
    r = rows[0]
    assert r['market'] == 'A'
    assert r['name'] == 'N300223'
    for k in ('price', 'change_7d', 'change_30d', 'change_90d',
              'high_90d', 'pullback_90d'):
        assert k in r
    # 无 trend_data 字段（纯表格不需要）
    assert 'trend_data' not in r


def test_pullback_ranking_has_market_and_sorted(monkeypatch):
    _patch(monkeypatch, [('300223', 'A'), ('2631.HK', 'HK')])
    ranking = ValueDipService.get_pullback_ranking(90)
    assert ranking, '应有回退数据'
    assert 'market' in ranking[0] and 'sector' not in ranking[0]
    pks = [s['pullback_pct'] for s in ranking]
    assert pks == sorted(pks)  # 回退最深在前


def test_sector_methods_removed():
    assert not hasattr(ValueDipService, 'get_sector_performance')
    assert not hasattr(ValueDipService, 'detect_value_dips')
