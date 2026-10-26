from types import SimpleNamespace
from unittest.mock import Mock

from datetime import datetime, timedelta, timezone
import pytest
from flask import Flask

from app import db
from app.models.news import NewsItem
from app.models.oil_alert import OilAlert
from app.services.oil_alert_service import OilAlertService, trading_date

from app.services import interest_pipeline
from app.services.interest_pipeline import InterestPipeline


EXAMPLE = ('【WTI原油期货跌幅扩大至2%】财联社10月26日电，WTI原油期货跌幅扩大至2%，'
           '报101.19美元/桶。布伦特原油期货下跌1.8%至114.62美元/桶。')


def test_oil_news_matches_even_when_classifier_returns_nothing(monkeypatch):
    keywords, companies = Mock(), Mock()
    monkeypatch.setattr(interest_pipeline, 'InterestKeyword', keywords)
    monkeypatch.setattr(interest_pipeline, 'CompanyKeyword', companies)
    keywords.query.filter_by.return_value.all.return_value = [SimpleNamespace(keyword='期货')]
    companies.query.filter_by.return_value.all.return_value = []
    item = SimpleNamespace(content=EXAMPLE, is_interest=False, matched_keywords=None)
    InterestPipeline._match_keywords([item], [])
    assert item.is_interest, '分类缺失时，已拉取的原油新闻仍应完成正文关键词匹配'


NOW = datetime(2026, 10, 26, 8)


@pytest.fixture
def oil_db(monkeypatch):
    app = Flask(__name__)
    app.config.update(SQLALCHEMY_DATABASE_URI='sqlite://',
                      SQLALCHEMY_BINDS={'private': 'sqlite://'})
    db.init_app(app)
    with app.app_context():
        db.create_all()
        sender = Mock(return_value=True)
        monkeypatch.setattr('app.services.notification.NotificationService.send_slack', sender)
        yield app, sender
        db.session.remove()


def news(content=EXAMPLE, published=None, item_id=1):
    return SimpleNamespace(id=item_id, content=content,
                           display_time=published or NOW + timedelta(hours=8),
                           is_interest=False, matched_keywords=None)


def quotes(pct=-2, timestamp=NOW, code='CL=F'):
    return {code: {'current_price': 101.19, 'change_percent': pct,
                   'quote_time': timestamp.isoformat() + '+00:00',
                   'trading_date': trading_date(timestamp)}}


def test_example_sends_once_even_after_session_restart_and_quote(oil_db):
    _, sender = oil_db
    OilAlertService.process_news([news()], NOW)
    assert sender.call_count == 1
    assert '101.19' in sender.call_args.args[0]
    assert sender.call_args.args[1] == 'news_watch'
    db.session.remove()
    OilAlertService.process_news([news(item_id=2)], NOW)
    OilAlertService.process_quotes(quotes(), NOW)
    assert sender.call_count == 1
    assert OilAlert.query.one().sent_band == 2


def test_quote_then_news_merges_and_expansion_pushes(oil_db):
    _, sender = oil_db
    OilAlertService.process_quotes(quotes(), NOW)
    OilAlertService.process_news([news()], NOW)
    OilAlertService.process_quotes(quotes(-3.2), NOW)
    OilAlertService.process_quotes(quotes(-2.5), NOW)
    OilAlertService.process_quotes(quotes(-3.5), NOW)
    assert sender.call_count == 2
    OilAlertService.process_quotes(quotes(2.1), NOW)
    OilAlertService.process_quotes(quotes(-2, code='BZ=F'), NOW)
    assert sender.call_count == 4


def test_first_observation_beyond_three_does_not_backfill_lower_band(oil_db):
    _, sender = oil_db
    OilAlertService.process_quotes(quotes(-3.2), NOW)
    OilAlertService.process_quotes(quotes(-2.1), NOW)
    assert sender.call_count == 1


def test_failure_retries_from_durable_queue(oil_db):
    _, sender = oil_db
    sender.side_effect = [False, True]
    OilAlertService.process_news([news()], NOW)
    assert OilAlert.query.one().sent_band == 0
    db.session.remove()
    OilAlertService.deliver_pending(NOW + timedelta(minutes=1))
    assert sender.call_count == 2
    assert OilAlert.query.one().sent_band == 2


def test_expired_failed_higher_band_does_not_block_fresh_lower_alert(oil_db):
    _, sender = oil_db
    sender.side_effect = [False, True]
    OilAlertService.process_quotes(quotes(-3), NOW)
    later = NOW + timedelta(minutes=30)
    OilAlertService.process_quotes(quotes(-2, timestamp=later), later)
    assert sender.call_count == 2
    assert OilAlert.query.one().sent_band == 2


def test_claim_prevents_second_sender_and_preserves_expansion_during_send(oil_db):
    _, sender = oil_db

    def send(message, channel):
        OilAlertService.deliver_pending(NOW)
        OilAlertService._enqueue_price('CL=F', -3, '2026-10-26', 'expanded', 'quote',
                                       NOW + timedelta(minutes=20), NOW)
        return True

    sender.side_effect = send
    OilAlertService.process_quotes(quotes(), NOW)
    assert sender.call_count == 1
    assert OilAlert.query.one().sent_band == 2
    assert OilAlert.query.one().target_band == 3
    sender.side_effect = None
    OilAlertService.deliver_pending(NOW)
    assert sender.call_count == 2
    assert OilAlert.query.one().sent_band == 3


def test_stale_quotes_and_old_news_do_not_push(oil_db):
    _, sender = oil_db
    OilAlertService.process_quotes(quotes(timestamp=NOW - timedelta(minutes=21)), NOW)
    OilAlertService.process_quotes({'CL=F': {'current_price': 101.19, 'change_percent': -2,
                                           'last_fetch_time': NOW.isoformat()}}, NOW)
    OilAlertService.process_news([news(published=NOW + timedelta(hours=5))], NOW)
    assert sender.call_count == 0


def test_important_news_without_ai_and_unimportant_news_filtered(oil_db):
    _, sender = oil_db
    OilAlertService.process_news([news('OPEC宣布原油减产每日100万桶')], NOW)
    assert sender.call_count == 1
    assert sender.call_args.args[1] == 'news'
    OilAlertService.process_news([news('OPEC宣布原油减产每日100万桶', item_id=2)], NOW)
    OilAlertService.process_news([news('原油期货知识介绍', item_id=3)], NOW)
    OilAlertService.process_news([news('WTI原油期货下跌1.8%', item_id=4)], NOW)
    assert sender.call_count == 1


def test_small_price_move_does_not_hide_supply_event(oil_db):
    _, sender = oil_db
    OilAlertService.process_news([news('OPEC宣布减产，WTI原油期货下跌1.8%')], NOW)
    assert sender.call_count == 1
    assert sender.call_args.args[1] == 'news'


def test_parser_does_not_cross_contracts_or_use_forecasts_as_price_events():
    assert OilAlertService.price_moves('WTI报101美元，布伦特下跌2%') == {'BZ=F': -2}
    assert OilAlertService.price_moves('预计WTI原油期货下跌2%') == {}
    assert OilAlertService.price_moves('WTI原油期货跌近2%') == {}
    assert not OilAlertService.is_oil_news('中国石油发布半年报')


def test_daily_rollover_uses_new_york_evening_not_beijing_midnight(oil_db):
    _, sender = oil_db
    before = datetime(2026, 10, 26, 21, 59)
    after = datetime(2026, 10, 26, 22)
    OilAlertService.process_quotes(quotes(timestamp=before), before)
    OilAlertService.process_quotes(quotes(timestamp=after), after)
    assert sender.call_count == 2
    assert trading_date(datetime(2026, 10, 26, 16)) == '2026-10-26'
    assert trading_date(datetime(2026, 11, 2, 22, 59)) == '2026-11-02'
    assert trading_date(datetime(2026, 11, 2, 23)) == '2026-11-03'


def test_pipeline_sends_oil_before_ai_and_does_not_send_generic_duplicate(oil_db, monkeypatch):
    app, sender = oil_db
    clock = Mock(wraps=datetime)
    clock.now.return_value = NOW.replace(tzinfo=timezone.utc)
    monkeypatch.setattr('app.services.oil_alert_service.datetime', clock)
    item = NewsItem(source_id='oil-test', content=EXAMPLE, display_time=NOW + timedelta(hours=8))
    db.session.add(item)
    db.session.commit()
    monkeypatch.setattr(InterestPipeline, '_classify_items', lambda items: [])
    monkeypatch.setattr(InterestPipeline, '_identify_and_notify_companies', lambda items: set())
    InterestPipeline.process_new_items([item.id], app)
    assert sender.call_count == 1
    db.session.expire_all()
    assert db.session.get(NewsItem, item.id).is_interest


def test_strategy_reads_oil_without_stock_market_or_watch_list(oil_db, monkeypatch):
    from app.strategies.oil_alert import OilAlertStrategy
    fetch = Mock(return_value={})
    process = Mock()
    monkeypatch.setattr('app.services.unified_stock_data.unified_stock_data_service.get_realtime_prices', fetch)
    monkeypatch.setattr(OilAlertService, 'process_quotes', process)
    OilAlertStrategy().scan()
    fetch.assert_called_once_with(['CL=F', 'BZ=F'], cache_only=True)
    process.assert_called_once()
