import pytest
from flask import Flask


@pytest.fixture
def app_ctx(tmp_path):
    """独立 sqlite Flask app，含 company_keyword 表，隔离于 data/stock.db。"""
    from app import db
    import app.models.news  # noqa: F401  注册模型到 metadata
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{tmp_path}/t.db'
    app.config['SQLALCHEMY_BINDS'] = {'private': f'sqlite:///{tmp_path}/tp.db'}
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()


def test_company_keyword_source_defaults_manual(app_ctx):
    from app import db
    from app.models.news import CompanyKeyword
    c = CompanyKeyword(name='测试公司')
    db.session.add(c)
    db.session.commit()
    assert c.source == 'manual'


def test_migrate_company_keyword_idempotent(app_ctx):
    from sqlalchemy import inspect
    from app import db, migrate_company_keyword_table
    migrate_company_keyword_table()
    migrate_company_keyword_table()  # 连跑两次不抛错
    columns = [c['name'] for c in inspect(db.engine).get_columns('company_keyword')]
    assert 'source' in columns


def test_seed_watch_companies_idempotent(app_ctx):
    from app import db
    from app.models.news import CompanyKeyword
    from app.seeds.watch_companies import seed_watch_companies
    from app.config.stock_codes import WATCH_CODES

    watch_names = {e['name'] for e in WATCH_CODES}
    seed_watch_companies()
    seed_watch_companies()  # 第二次不应重复建行

    rows = CompanyKeyword.query.filter_by(source='watch').all()
    assert {r.name for r in rows} == watch_names
    assert len(rows) == len(watch_names)  # 无重复


def test_seed_upgrades_manual_to_watch(app_ctx):
    from app import db
    from app.models.news import CompanyKeyword
    from app.seeds.watch_companies import seed_watch_companies
    from app.config.stock_codes import WATCH_CODES

    name = WATCH_CODES[0]['name']
    db.session.add(CompanyKeyword(name=name, source='manual'))
    db.session.commit()

    seed_watch_companies()

    rows = CompanyKeyword.query.filter_by(name=name).all()
    assert len(rows) == 1
    assert rows[0].source == 'watch'


def test_seed_cleans_stale_watch_rows(app_ctx):
    from app import db
    from app.models.news import CompanyKeyword
    from app.seeds.watch_companies import seed_watch_companies

    db.session.add(CompanyKeyword(name='已退出盯盘的公司', source='watch'))
    db.session.commit()

    seed_watch_companies()

    assert CompanyKeyword.query.filter_by(name='已退出盯盘的公司').first() is None


def test_seed_preserves_manual_rows(app_ctx):
    from app import db
    from app.models.news import CompanyKeyword
    from app.seeds.watch_companies import seed_watch_companies

    db.session.add(CompanyKeyword(name='我手动加的公司', source='manual'))
    db.session.commit()

    seed_watch_companies()

    row = CompanyKeyword.query.filter_by(name='我手动加的公司').first()
    assert row is not None
    assert row.source == 'manual'  # 手动行不受影响


@pytest.fixture
def client_ctx(tmp_path):
    """带 news_bp + DB 的测试 client，隔离于 data/stock.db。"""
    from app import db
    from app.routes import news_bp
    import app.models.news  # noqa: F401
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{tmp_path}/t.db'
    app.config['SQLALCHEMY_BINDS'] = {'private': f'sqlite:///{tmp_path}/tp.db'}
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)
    app.register_blueprint(news_bp)
    with app.app_context():
        db.create_all()
        with app.test_client() as client:
            yield app, client
        db.session.remove()


def test_get_companies_returns_source(client_ctx):
    from app import db
    from app.models.news import CompanyKeyword
    app, client = client_ctx
    db.session.add(CompanyKeyword(name='手动公司', source='manual'))
    db.session.add(CompanyKeyword(name='盯盘公司', source='watch'))
    db.session.commit()

    data = client.get('/news/companies').get_json()
    assert data['success']
    by_name = {c['name']: c for c in data['companies']}
    assert by_name['手动公司']['source'] == 'manual'
    assert by_name['盯盘公司']['source'] == 'watch'


def test_delete_watch_company_rejected(client_ctx):
    from app import db
    from app.models.news import CompanyKeyword
    app, client = client_ctx
    c = CompanyKeyword(name='盯盘公司', source='watch')
    db.session.add(c)
    db.session.commit()
    cid = c.id

    resp = client.delete(f'/news/companies/{cid}').get_json()
    assert resp['success'] is False
    assert db.session.get(CompanyKeyword, cid) is not None  # 行仍在


def test_delete_manual_company_ok(client_ctx):
    from app import db
    from app.models.news import CompanyKeyword
    app, client = client_ctx
    c = CompanyKeyword(name='手动公司', source='manual')
    db.session.add(c)
    db.session.commit()
    cid = c.id

    resp = client.delete(f'/news/companies/{cid}').get_json()
    assert resp['success'] is True
    assert db.session.get(CompanyKeyword, cid) is None


def test_add_existing_watch_keeps_source(client_ctx):
    from app import db
    from app.models.news import CompanyKeyword
    app, client = client_ctx
    c = CompanyKeyword(name='盯盘公司', source='watch')
    db.session.add(c)
    db.session.commit()

    client.post('/news/companies', json={'name': '盯盘公司'})

    row = CompanyKeyword.query.filter_by(name='盯盘公司').first()
    assert row.source == 'watch'  # 不被降级为 manual


def test_get_news_items_company_tab_includes_watch(app_ctx):
    from datetime import datetime
    from app import db
    from app.models.news import CompanyKeyword, NewsItem
    from app.services.news_service import NewsService

    db.session.add(CompanyKeyword(name='盯盘公司', source='watch', is_active=True))
    db.session.add(NewsItem(
        source_id='x1', source_name='test', content='盯盘公司发布利好',
        display_time=datetime(2026, 6, 29, 10, 0), matched_keywords='盯盘公司',
    ))
    db.session.commit()

    items = NewsService.get_news_items(tab='company')
    assert any('盯盘公司' in (i['matched_keywords'] or '') for i in items)
