"""CockroachDB 事务重试工具

CockroachDB 在并发事务冲突或连接断开时需要客户端自动重试。

- 读操作：通过 setup_db_retry() patch Session.execute 自动重试
- 写操作：使用 @with_db_retry 装饰器在业务层重试整个事务
- UPSERT操作：使用 upsert_with_retry() 避免读-写竞态
"""
import time
import random
import logging
from functools import wraps
from sqlalchemy.exc import OperationalError, DisconnectionError

logger = logging.getLogger(__name__)

MAX_RETRIES = 5  # 增加重试次数以应对高并发场景
RETRY_DELAY = 0.1
RETRY_JITTER = 0.05  # 随机抖动，减少重试碰撞


def _get_retry_delay(attempt: int) -> float:
    """计算带抖动的重试延迟"""
    base_delay = RETRY_DELAY * (2 ** attempt)
    jitter = random.uniform(-RETRY_JITTER, RETRY_JITTER) * base_delay
    return base_delay + jitter


def is_retryable_error(error):
    """判断是否为可重试的数据库错误（序列化冲突 + 连接层错误）"""
    error_str = str(error)
    return any(keyword in error_str for keyword in [
        'SerializationFailure',
        'restart transaction',
        'TransactionRetryWithProtoRefreshError',
        'ReadWithinUncertaintyIntervalError',
        'SSL SYSCALL error',
        'EOF detected',
        'server closed the connection unexpectedly',
        'connection reset by peer',
        'broken pipe',
    ])


def with_db_retry(func):
    """CockroachDB事务重试装饰器

    用于写操作（add+commit），遇到序列化冲突或连接断开时自动rollback并重试。
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        from app import db
        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                return func(*args, **kwargs)
            except (OperationalError, DisconnectionError) as e:
                last_error = e
                if is_retryable_error(e) and attempt < MAX_RETRIES - 1:
                    delay = _get_retry_delay(attempt)
                    logger.warning(f"[DB重试] {func.__name__} 数据库错误，重试 {attempt + 1}/{MAX_RETRIES}，延迟 {delay:.3f}s: {type(e).__name__}")
                    db.session.rollback()
                    time.sleep(delay)
                    continue
                raise
        # 所有重试都失败
        if last_error:
            raise last_error
    return wrapper


def setup_db_retry(db, app):
    """Patch Session.execute，使读查询在CockroachDB出错时自动重试

    覆盖序列化冲突和连接层错误（SSL EOF等）。
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
                except (OperationalError, DisconnectionError) as e:
                    if is_retryable_error(e) and attempt < MAX_RETRIES - 1:
                        has_pending = self.new or self.dirty or self.deleted
                        self.rollback()
                        if has_pending:
                            raise
                        delay = _get_retry_delay(attempt)
                        logger.warning(f"[DB重试] 读查询连接错误，自动重试 {attempt + 1}/{MAX_RETRIES}，延迟 {delay:.3f}s: {type(e).__name__}")
                        time.sleep(delay)
                        continue
                    raise

        session_cls.execute = _execute_with_retry
        logger.info("[DB重试] Session.execute 自动读重试已启用（含连接层错误）")
    except Exception as e:
        logger.warning(f"[DB重试] 无法启用Session级自动重试: {e}")


def execute_upsert(db, table, values: dict, index_elements: list, update_columns: list):
    """执行 UPSERT 操作，避免读-写竞态导致的序列化冲突

    使用 INSERT ... ON CONFLICT DO UPDATE 语法，原子性地插入或更新记录。

    Args:
        db: Flask-SQLAlchemy db 实例
        table: SQLAlchemy Table 对象（如 Model.__table__）
        values: 要插入的值字典
        index_elements: 唯一约束列名列表（用于冲突检测）
        update_columns: 冲突时要更新的列名列表

    Returns:
        执行结果
    """
    from sqlalchemy.dialects.postgresql import insert

    stmt = insert(table).values(**values)

    update_dict = {col: stmt.excluded[col] for col in update_columns}

    upsert_stmt = stmt.on_conflict_do_update(
        index_elements=index_elements,
        set_=update_dict
    )

    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            result = db.session.execute(upsert_stmt)
            db.session.commit()
            return result
        except (OperationalError, DisconnectionError) as e:
            last_error = e
            if is_retryable_error(e) and attempt < MAX_RETRIES - 1:
                delay = _get_retry_delay(attempt)
                logger.warning(f"[DB重试] UPSERT 操作失败，重试 {attempt + 1}/{MAX_RETRIES}，延迟 {delay:.3f}s: {type(e).__name__}")
                db.session.rollback()
                time.sleep(delay)
                continue
            raise
    if last_error:
        raise last_error
