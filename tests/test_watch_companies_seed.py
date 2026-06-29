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
