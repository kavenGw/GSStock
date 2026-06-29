"""同步盯盘池 WATCH_CODES 进 company_keyword（source='watch'）。
WATCH_CODES 是唯一权威源，本 seed 只做 DB 投影同步。"""
import logging

from app import db
from app.models.news import CompanyKeyword
from app.config.stock_codes import WATCH_CODES

logger = logging.getLogger(__name__)


def seed_watch_companies():
    try:
        watch_names = {e['name'] for e in WATCH_CODES}
        existing = {c.name: c for c in CompanyKeyword.query.all()}

        for name in watch_names:
            row = existing.get(name)
            if row is None:
                db.session.add(CompanyKeyword(name=name, source='watch', is_active=True))
            else:
                row.source = 'watch'
                row.is_active = True

        for c in CompanyKeyword.query.filter_by(source='watch').all():
            if c.name not in watch_names:
                db.session.delete(c)

        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.warning(f'[seed] watch companies 同步失败: {e}')
