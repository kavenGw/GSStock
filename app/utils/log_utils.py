import time
import logging
from contextlib import contextmanager


@contextmanager
def log_operation(logger, tag, level=logging.INFO, **start_kwargs):
    """自动记录操作耗时的上下文管理器

    用法:
        with log_operation(logger, "数据服务.实时价格") as op:
            result = fetch()
            op.set_message(f"成功 {len(result)}只")
        # 自动输出: [数据服务.实时价格] 完成: 成功 5只, 耗时 2.3s

        # 简单用法（无自定义消息）:
        with log_operation(logger, "预加载.指数"):
            preload()
        # 自动输出: [预加载.指数] 完成, 耗时 1.1s
    """
    class _Op:
        def __init__(self):
            self.message = None
            self.suppressed = False

        def set_message(self, msg):
            self.message = msg

        def suppress_completion(self):
            """调用此方法可抑制自动完成日志（由调用方手动输出）"""
            self.suppressed = True

    op = _Op()
    start = time.perf_counter()
    try:
        yield op
    except Exception:
        elapsed = time.perf_counter() - start
        logger.error(f"[{tag}] 失败, 耗时 {elapsed:.2f}s", exc_info=True)
        raise
    else:
        if not op.suppressed:
            elapsed = time.perf_counter() - start
            if op.message:
                logger.log(level, f"[{tag}] 完成: {op.message}, 耗时 {elapsed:.2f}s")
            else:
                logger.log(level, f"[{tag}] 完成, 耗时 {elapsed:.2f}s")
