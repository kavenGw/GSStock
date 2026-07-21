from datetime import date

from app.services.briefing import BriefingService


def test_compute_premium_positive():
    # us=190, home=1000 TWD, fx=32 (1 USD=32 TWD), ratio=5
    # fair = 1000 * 5 / 32 = 156.25 ; premium = 190/156.25 - 1 = +21.60%
    assert BriefingService._compute_premium(190.0, 1000.0, 32.0, 5) == 21.6


def test_compute_premium_discount():
    # fair = 156.25 ; us=150 → 150/156.25 - 1 = -4.00%
    assert BriefingService._compute_premium(150.0, 1000.0, 32.0, 5) == -4.0


def test_compute_premium_none_when_ratio_missing():
    assert BriefingService._compute_premium(190.0, 1000.0, 32.0, None) is None


def test_compute_premium_none_when_leg_missing():
    assert BriefingService._compute_premium(None, 1000.0, 32.0, 5) is None
    assert BriefingService._compute_premium(190.0, None, 32.0, 5) is None
    assert BriefingService._compute_premium(190.0, 1000.0, None, 5) is None


def test_get_adr_premium_data_degrades_per_leg(monkeypatch):
    # TSM 全腿有价 → 有 premium；SK 缺 US 价 → premium None + error
    fake_quotes = {
        'TSM': {'close': 190.0}, '2330.TW': {'close': 1000.0}, 'TWD=X': {'close': 32.0},
        '000660.KS': {'close': 200000.0}, 'KRW=X': {'close': 1380.0},
        # SKHY 缺失 → SK 腿降级
    }
    monkeypatch.setattr(
        'app.services.unified_stock_data.unified_stock_data_service.get_yfinance_batch_quotes',
        lambda symbols, cache_type: fake_quotes,
    )
    monkeypatch.setattr(BriefingService, '_load_adr_prev', staticmethod(lambda: {}))
    monkeypatch.setattr(BriefingService, '_save_adr_prev', staticmethod(lambda store: None))

    pairs = BriefingService.get_adr_premium_data()['pairs']
    by_key = {p['key']: p for p in pairs}
    assert by_key['tsmc']['premium_rate'] == 21.6
    assert by_key['skhynix']['premium_rate'] is None
    assert by_key['skhynix']['error']


def test_prev_roundtrip(tmp_path, monkeypatch):
    f = tmp_path / 'prev.json'
    monkeypatch.setattr('app.services.briefing.ADR_PREV_FILE', str(f))
    assert BriefingService._load_adr_prev() == {}          # 文件不存在
    BriefingService._save_adr_prev({'tsmc': {'date': '2026-07-20', 'premium': 1.82}})
    assert BriefingService._load_adr_prev()['tsmc']['premium'] == 1.82


def test_prev_corrupt_returns_empty(tmp_path, monkeypatch):
    f = tmp_path / 'prev.json'
    f.write_text('{ not json', encoding='utf-8')
    monkeypatch.setattr('app.services.briefing.ADR_PREV_FILE', str(f))
    assert BriefingService._load_adr_prev() == {}


def test_delta_computed_from_prev(tmp_path, monkeypatch):
    f = tmp_path / 'prev.json'
    f.write_text('{"tsmc": {"date": "2026-07-20", "premium": 20.0}}', encoding='utf-8')
    monkeypatch.setattr('app.services.briefing.ADR_PREV_FILE', str(f))
    monkeypatch.setattr(
        'app.services.unified_stock_data.unified_stock_data_service.get_yfinance_batch_quotes',
        lambda symbols, cache_type: {
            'TSM': {'close': 190.0}, '2330.TW': {'close': 1000.0}, 'TWD=X': {'close': 32.0},
            '000660.KS': {'close': 200000.0}, 'KRW=X': {'close': 1380.0},
        },
    )
    pairs = {p['key']: p for p in BriefingService.get_adr_premium_data()['pairs']}
    # 今日 tsmc=21.6, 昨日 20.0 → delta=1.6
    assert pairs['tsmc']['delta'] == 1.6
    # skhynix 缺 SKHY 报价 → premium None → delta None，且不覆盖（此处本无旧值）
    assert pairs['skhynix']['delta'] is None


def test_none_premium_does_not_overwrite_prev(tmp_path, monkeypatch):
    f = tmp_path / 'prev.json'
    f.write_text('{"skhynix": {"date": "2026-07-19", "premium": -0.5}}', encoding='utf-8')
    monkeypatch.setattr('app.services.briefing.ADR_PREV_FILE', str(f))
    monkeypatch.setattr(
        'app.services.unified_stock_data.unified_stock_data_service.get_yfinance_batch_quotes',
        lambda symbols, cache_type: {'TSM': {'close': 190.0}, '2330.TW': {'close': 1000.0}, 'TWD=X': {'close': 32.0}},
    )
    BriefingService.save_adr_premium_snapshot()
    # skhynix 今日缺 SKHY 报价 → 旧值仍在
    assert BriefingService._load_adr_prev()['skhynix']['premium'] == -0.5


def test_skhynix_leg_priced_with_ratio(monkeypatch):
    # SKHY 有价：ratio=0.1 → fair = 1500000*0.1/1500 = 100 ; premium = 150/100-1 = +50.00%
    monkeypatch.setattr(
        'app.services.unified_stock_data.unified_stock_data_service.get_yfinance_batch_quotes',
        lambda symbols, cache_type: {
            'SKHY': {'close': 150.0}, '000660.KS': {'close': 1500000.0}, 'KRW=X': {'close': 1500.0},
        },
    )
    monkeypatch.setattr(BriefingService, '_load_adr_prev', staticmethod(lambda: {}))
    by_key = {p['key']: p for p in BriefingService.get_adr_premium_data()['pairs']}
    assert by_key['skhynix']['premium_rate'] == 50.0
    assert by_key['skhynix']['error'] is None


def test_getter_is_pure_no_write(tmp_path, monkeypatch):
    f = tmp_path / 'prev.json'
    f.write_text('{"tsmc": {"date": "2026-07-20", "premium": 20.0}}', encoding='utf-8')
    monkeypatch.setattr('app.services.briefing.ADR_PREV_FILE', str(f))
    monkeypatch.setattr(
        'app.services.unified_stock_data.unified_stock_data_service.get_yfinance_batch_quotes',
        lambda symbols, cache_type: {
            'TSM': {'close': 190.0}, '2330.TW': {'close': 1000.0}, 'TWD=X': {'close': 32.0},
        },
    )
    pairs1 = {p['key']: p for p in BriefingService.get_adr_premium_data()['pairs']}
    pairs2 = {p['key']: p for p in BriefingService.get_adr_premium_data()['pairs']}
    assert pairs1['tsmc']['delta'] == 1.6
    assert pairs2['tsmc']['delta'] == 1.6
    assert BriefingService._load_adr_prev()['tsmc']['premium'] == 20.0


def test_save_snapshot_updates_valid_and_preserves_missing(tmp_path, monkeypatch):
    f = tmp_path / 'prev.json'
    f.write_text(
        '{"tsmc": {"date": "2026-07-20", "premium": 20.0}, "skhynix": {"date": "2026-07-20", "premium": -0.5}}',
        encoding='utf-8',
    )
    monkeypatch.setattr('app.services.briefing.ADR_PREV_FILE', str(f))
    monkeypatch.setattr(
        'app.services.unified_stock_data.unified_stock_data_service.get_yfinance_batch_quotes',
        lambda symbols, cache_type: {
            'TSM': {'close': 190.0}, '2330.TW': {'close': 1000.0}, 'TWD=X': {'close': 32.0},
        },
    )
    BriefingService.save_adr_premium_snapshot()
    stored = BriefingService._load_adr_prev()
    assert stored['tsmc']['premium'] == 21.6
    assert stored['tsmc']['date'] == date.today().isoformat()
    assert stored['skhynix']['premium'] == -0.5


from app.services.notification import NotificationService


def _patch_pairs(monkeypatch, pairs):
    monkeypatch.setattr(BriefingService, 'get_adr_premium_data',
                        staticmethod(lambda: {'pairs': pairs}))


def test_format_premium_and_discount_with_arrows(monkeypatch):
    _patch_pairs(monkeypatch, [
        {'name': 'TSM', 'premium_rate': 1.82, 'delta': 0.5, 'error': None},
        {'name': 'SK海力士', 'premium_rate': -0.31, 'delta': -0.2, 'error': None},
    ])
    out = NotificationService.format_adr_premium_summary()
    assert out == '🌏 ADR溢价: TSM +1.82%(溢价)↑0.5pct | SK海力士 -0.31%(折价)↓0.2pct'


def test_format_no_arrow_when_delta_none(monkeypatch):
    _patch_pairs(monkeypatch, [{'name': 'TSM', 'premium_rate': 1.82, 'delta': None, 'error': None}])
    assert NotificationService.format_adr_premium_summary() == '🌏 ADR溢价: TSM +1.82%(溢价)'


def test_format_dash_for_missing_leg(monkeypatch):
    _patch_pairs(monkeypatch, [
        {'name': 'TSM', 'premium_rate': 1.82, 'delta': None, 'error': None},
        {'name': 'SK海力士', 'premium_rate': None, 'delta': None, 'error': '行情缺失'},
    ])
    assert NotificationService.format_adr_premium_summary() == '🌏 ADR溢价: TSM +1.82%(溢价) | SK海力士 —'


def test_format_empty_when_all_missing(monkeypatch):
    _patch_pairs(monkeypatch, [
        {'name': 'TSM', 'premium_rate': None, 'delta': None, 'error': 'x'},
        {'name': 'SK海力士', 'premium_rate': None, 'delta': None, 'error': 'x'},
    ])
    assert NotificationService.format_adr_premium_summary() == ''


from app.llm.prompts.daily_briefing import build_daily_briefing_prompt


def test_prompt_renders_adr_premium():
    prompt = build_daily_briefing_prompt({'adr_premium': '🌏 ADR溢价: TSM +1.82%(溢价)'})
    assert 'ADR溢价' in prompt
    assert 'TSM +1.82%(溢价)' in prompt


def test_market_blocks_include_adr(monkeypatch):
    _patch_pairs(monkeypatch, [
        {'name': 'TSM', 'premium_rate': 1.82, 'delta': 0.5, 'error': None},
    ])
    # 其余 BriefingService 取数在 build_market_blocks 里被 try/except 兜底，无价时走 except 分支
    blocks = NotificationService.build_market_blocks(
        indices_text='', futures_text='', etf_text='',
        sectors_text='', technical_text='', adr_text='🌏 ADR溢价: TSM +1.82%(溢价)↑0.5pct',
    )
    dumped = str(blocks)
    assert 'ADR溢价' in dumped and 'TSM' in dumped
