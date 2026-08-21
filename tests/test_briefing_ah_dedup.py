"""简报页财报预警的 A+H 去重 —— A+H 处理的第三处

本分支之前 A 股财报日期取不到会被静默丢弃，同时持有 0981.HK 与 688981 也只会
出一行；本分支把 A 股财报日打通后，同一家中芯国际会在简报页出现两行。
"""
import pytest
from flask import Flask


WATCH_STUB = [
    {'code': '0981.HK', 'name': '中芯国际', 'market': 'HK',
     'ah': {'code': '688981', 'market': 'A', 'name': '中芯国际'}},
    {'code': '0763.HK', 'name': '中兴通讯', 'market': 'HK',
     'ah': {'code': '000063', 'market': 'A', 'name': '中兴通讯'}},
    {'code': '002156', 'name': '通富微电', 'market': 'A'},
]


def test_dedup_ah_codes_drops_counterpart_when_both_present(monkeypatch):
    from app.services import watch_service as mod
    monkeypatch.setattr(mod, 'WATCH_CODES', WATCH_STUB)

    out = mod.WatchService.dedup_ah_codes(['0981.HK', '688981', '002156'])

    assert out == ['0981.HK', '002156'], '同公司两地代码只留盯盘池顶层代码'


def test_dedup_ah_codes_keeps_lone_a_share(monkeypatch):
    """只持 A 股那边时不能把它也丢掉——否则这家公司一行都不剩。"""
    from app.services import watch_service as mod
    monkeypatch.setattr(mod, 'WATCH_CODES', WATCH_STUB)

    assert mod.WatchService.dedup_ah_codes(['688981', '002156']) == ['688981', '002156']


def test_dedup_ah_codes_preserves_input_order(monkeypatch):
    from app.services import watch_service as mod
    monkeypatch.setattr(mod, 'WATCH_CODES', WATCH_STUB)

    out = mod.WatchService.dedup_ah_codes(
        ['002156', '000063', '0763.HK', '688981', '0981.HK'])

    assert out == ['002156', '0763.HK', '0981.HK']


@pytest.fixture
def app_ctx(tmp_path):
    from app import db
    import app.models.stock  # noqa: F401
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{tmp_path}/t.db'
    app.config['SQLALCHEMY_BINDS'] = {'private': f'sqlite:///{tmp_path}/tp.db'}
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()


def test_earnings_alert_data_reports_one_row_per_company(app_ctx, monkeypatch):
    """/briefing/api/earnings 不得把 A+H 同一家公司报两行。"""
    from app.services import briefing as bmod
    from app.services import watch_service as wmod
    from app.services.earnings import EarningsService

    monkeypatch.setattr(wmod, 'WATCH_CODES', WATCH_STUB)
    monkeypatch.setattr(bmod, 'get_categories', lambda: [{'id': 1, 'name': '半导体'}])
    monkeypatch.setattr(bmod, 'get_stocks_by_category', lambda cid: [
        {'stock_code': '0981.HK', 'stock_name': '中芯国际'},
        {'stock_code': '688981', 'stock_name': '中芯国际'},
        {'stock_code': '002156', 'stock_name': '通富微电'},
    ])

    seen = {}

    def _upcoming(codes, days=7):
        seen['codes'] = list(codes)
        return [{'code': c, 'name': c, 'earnings_date': '2026-08-25',
                 'days_until': 4, 'is_today': False} for c in codes]

    monkeypatch.setattr(EarningsService, 'get_upcoming_earnings',
                        staticmethod(_upcoming))

    data = bmod.BriefingService.get_earnings_alert_data()

    assert '688981' not in seen['codes'], 'A+H 对应代码不应重复送去查财报日'
    codes = [a['stock_code'] for a in data['earnings_alerts']]
    assert codes.count('0981.HK') == 1
    assert sorted(codes) == ['002156', '0981.HK']
