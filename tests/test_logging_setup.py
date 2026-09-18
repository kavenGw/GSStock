import logging
from logging.handlers import TimedRotatingFileHandler

import pytest
from flask import Flask

from app import setup_logging, SafeTimedRotatingFileHandler


@pytest.fixture
def fresh_root():
    root = logging.getLogger()
    saved = root.handlers[:]
    root.handlers = []
    news_loggers = [logging.getLogger(n) for n in ('app.services.news_service', 'app.services.news_sources')]
    saved_news = [(lg, lg.handlers[:]) for lg in news_loggers]
    for lg in news_loggers:
        lg.handlers = []
    yield root
    for h in root.handlers:
        h.close()
    root.handlers = saved
    for lg, hs in saved_news:
        for h in lg.handlers:
            h.close()
        lg.handlers = hs


def _handlers_by_file(logger):
    return {h.baseFilename.rsplit('\\', 1)[-1].rsplit('/', 1)[-1]: h
            for h in logger.handlers if isinstance(h, TimedRotatingFileHandler)}


def test_file_handlers_rotate_daily_and_keep_seven(tmp_path, fresh_root):
    app = Flask(__name__)
    app.config['LOG_DIR'] = str(tmp_path)
    setup_logging(app)

    files = _handlers_by_file(fresh_root)
    assert set(files) == {'app.log', 'error.log'}
    for h in files.values():
        assert isinstance(h, SafeTimedRotatingFileHandler)
        assert h.when == 'MIDNIGHT'
        assert h.backupCount == 7
    assert files['app.log'].level == logging.INFO
    assert files['error.log'].level == logging.ERROR
    assert (tmp_path / 'app.log').exists()


def test_news_loggers_get_dedicated_file(tmp_path, fresh_root):
    app = Flask(__name__)
    app.config['LOG_DIR'] = str(tmp_path)
    setup_logging(app)

    for name in ('app.services.news_service', 'app.services.news_sources'):
        lg = logging.getLogger(name)
        assert 'news.log' in _handlers_by_file(lg)
        assert lg.level == logging.DEBUG

    logging.getLogger('app.services.news_sources.smolai').debug('probe-line')
    for h in logging.getLogger('app.services.news_sources').handlers:
        h.flush()
    assert 'probe-line' in (tmp_path / 'news.log').read_text(encoding='utf-8')


def test_setup_logging_is_idempotent(tmp_path, fresh_root):
    app = Flask(__name__)
    app.config['LOG_DIR'] = str(tmp_path)
    setup_logging(app)
    n = len(fresh_root.handlers)
    setup_logging(app)
    assert len(fresh_root.handlers) == n
