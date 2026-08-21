from datetime import date, datetime, timedelta

import pytest
from flask import Flask


@pytest.fixture
def app_ctx(tmp_path):
    """独立 sqlite Flask app，含 stock_event 表，隔离于 data/stock.db。"""
    from app import db
    import app.models.stock_event  # noqa: F401  注册模型到 metadata
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{tmp_path}/t.db'
    app.config['SQLALCHEMY_BINDS'] = {'private': f'sqlite:///{tmp_path}/tp.db'}
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()


def _ev(**kw):
    base = {
        'event_date': date(2026, 8, 26),
        'event_type': 'earnings',
        'stock_code': '002156',
        'stock_name': '通富微电',
        'market': 'A',
        'title': '中报披露',
        'detail': None,
        'priority': 'MEDIUM',
        'source': 'cninfo',
        'status': 'scheduled',
        'period_key': '2026H1',
        'extra': None,
    }
    base.update(kw)
    return base


def test_upsert_same_business_key_updates_in_place(app_ctx):
    from app.models.stock_event import StockEvent
    from app.services.calendar_event import CalendarEventService

    ids1 = CalendarEventService.upsert_events([_ev()])
    ids2 = CalendarEventService.upsert_events([
        _ev(event_date=date(2026, 8, 29), status='changed',
            detail='预约 2026-08-26 → 2026-08-29')
    ])

    rows = StockEvent.query.all()
    assert len(rows) == 1, '改期必须 update 而非新增行'
    assert ids1 == ids2
    assert rows[0].event_date == date(2026, 8, 29)
    assert rows[0].status == 'changed'
    assert rows[0].detail == '预约 2026-08-26 → 2026-08-29'


def test_macro_event_uses_empty_stock_code_not_null(app_ctx):
    """SQLite 唯一索引里 NULL 互不相等，宏观事件必须存空串才能去重。"""
    from app.models.stock_event import StockEvent
    from app.services.calendar_event import CalendarEventService

    macro = _ev(event_type='macro', stock_code='', stock_name=None,
                market='US', title='FOMC 议息', source='fomc',
                period_key='2026-09-16', event_date=date(2026, 9, 16),
                priority='HIGH')
    CalendarEventService.upsert_events([macro])
    CalendarEventService.upsert_events([macro])

    rows = StockEvent.query.filter_by(event_type='macro').all()
    assert len(rows) == 1
    assert rows[0].stock_code == ''


def test_prune_stale_removes_unmatched_but_keeps_manual(app_ctx):
    from app.models.stock_event import StockEvent
    from app.services.calendar_event import CalendarEventService

    CalendarEventService.upsert_events([
        _ev(stock_code='002156', period_key='2026H1'),
        _ev(stock_code='300223', stock_name='君正股份', period_key='2026H1',
            event_date=date(2026, 8, 29)),
        _ev(stock_code='603986', stock_name='兆易创新', source='manual',
            period_key='M1', event_date=date(2026, 8, 27)),
    ])
    keep = CalendarEventService.upsert_events([_ev(stock_code='002156', period_key='2026H1')])

    removed = CalendarEventService.prune_stale(
        date(2026, 8, 1), date(2026, 8, 31), keep, ['cninfo'])

    codes = {r.stock_code for r in StockEvent.query.all()}
    assert removed == 1
    assert codes == {'002156', '603986'}, 'manual 行不可被清理'


def test_prune_stale_only_touches_given_sources(app_ctx):
    """某个 collector 挂了时，不能连带删掉它那一类的历史事件。"""
    from app.models.stock_event import StockEvent
    from app.services.calendar_event import CalendarEventService

    CalendarEventService.upsert_events([
        _ev(source='cninfo', stock_code='002156', period_key='2026H1'),
        _ev(source='yfinance', stock_code='0700.HK', stock_name='腾讯控股',
            market='HK', period_key='2026Q3', event_date=date(2026, 8, 20)),
    ])

    removed = CalendarEventService.prune_stale(
        date(2026, 8, 1), date(2026, 8, 31), [], ['cninfo'])

    sources = {r.source for r in StockEvent.query.all()}
    assert removed == 1
    assert sources == {'yfinance'}


def test_get_events_sorted_by_date_then_priority(app_ctx):
    from app.services.calendar_event import CalendarEventService

    CalendarEventService.upsert_events([
        _ev(stock_code='300223', period_key='A', event_date=date(2026, 8, 26),
            priority='LOW', title='除息'),
        _ev(stock_code='002156', period_key='B', event_date=date(2026, 8, 26),
            priority='HIGH', title='中报披露'),
        _ev(stock_code='603986', period_key='C', event_date=date(2026, 8, 25),
            priority='MEDIUM', title='中报披露'),
    ])

    out = CalendarEventService.get_events(date(2026, 8, 1), date(2026, 8, 31))

    assert [e['title'] for e in out] == ['中报披露', '中报披露', '除息']
    assert out[0]['event_date'] == '2026-08-25'
    assert out[1]['stock_code'] == '002156'


def test_hours_since_refresh_none_when_empty(app_ctx):
    from app.services.calendar_event import CalendarEventService
    assert CalendarEventService.hours_since_refresh() is None


def test_hours_since_refresh_reads_max_updated_at(app_ctx):
    from app import db
    from app.models.stock_event import StockEvent
    from app.services.calendar_event import CalendarEventService

    CalendarEventService.upsert_events([_ev()])
    row = StockEvent.query.first()
    row.updated_at = datetime.now() - timedelta(hours=30)
    db.session.commit()

    hours = CalendarEventService.hours_since_refresh()
    assert 29 < hours < 31
