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
