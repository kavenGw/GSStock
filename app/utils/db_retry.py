"""CockroachDB 事务重试工具

CockroachDB 在并发事务冲突时会返回 SerializationFailure，
客户端需要自动 rollback 并重试事务。

- 读操作：通过 setup_db_retry() patch Session.execute 自动重试
- 写操作：使用 @with_db_retry 装饰器在业务层重试整个事务
"""
import time
import logging
from functools import wraps
from sqlalchemy.exc import OperationalError

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_DELAY = 0.1


def is_retryable_error(error):
    """判断是否为CockroachDB可重试的序列化冲突错误"""
    error_str = str(error)
    return any(keyword in error_str for keyword in [
        'SerializationFailure',
        'restart transaction',
        'TransactionRetryWithProtoRefreshError',
        'ReadWithinUncertaintyIntervalError',
    ])


def with_db_retry(func):
    """CockroachDB事务重试装饰器

    用于写操作（add+commit），遇到序列化冲突时自动rollback并重试整个函数。
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        from app import db
        for attempt in range(MAX_RETRIES):
            try:
                return func(*args, **kwargs)
            except OperationalError as e:
                if is_retryable_error(e) and attempt < MAX_RETRIES - 1:
                    logger.warning(f"[CockroachDB] {func.__name__} 序列化冲突，重试 {attempt + 1}/{MAX_RETRIES}")
                    db.session.rollback()
                    time.sleep(RETRY_DELAY * (2 ** attempt))
                    continue
                raise
    return wrapper


def setup_db_retry(db, app):
    """Patch Session.execute，使读查询在CockroachDB序列化冲突时自动重试

    仅对无待写入变更的纯读查询生效。
    写操作需使用 @with_db_retry 装饰器在业务层重试。
    """
    if not app.config.get('COCKROACH_CONFIGURED'):
        return

    try:
        session_cls = db.session.session_factory.class_
        _original_execute = session_cls.execute

        @wraps(_original_execute)
        def _execute_with_retry(self, *args, **kwargs):
            for attempt in range(MAX_RETRIES):
                try:
                    return _original_execute(self, *args, **kwargs)
                except OperationalError as e:
                    if is_retryable_error(e) and attempt < MAX_RETRIES - 1:
                        has_pending = self.new or self.dirty or self.deleted
                        self.rollback()
                        if has_pending:
                            raise
                        logger.warning(f"[CockroachDB] 读查询序列化冲突，自动重试 {attempt + 1}/{MAX_RETRIES}")
                        time.sleep(RETRY_DELAY * (2 ** attempt))
                        continue
                    raise

        session_cls.execute = _execute_with_retry
        logger.info("[CockroachDB] Session.execute 自动读重试已启用")
    except Exception as e:
        logger.warning(f"[CockroachDB] 无法启用Session级自动重试: {e}")
