"""全局 LLM 请求令牌桶限流"""
import os
import threading
import time
import logging

logger = logging.getLogger(__name__)

LLM_RATE_LIMIT_RPM = int(os.environ.get('LLM_RATE_LIMIT_RPM', '10'))


class RateLimiter:
    """令牌桶限流器 — 控制每分钟请求数"""

    def __init__(self, rpm: int = LLM_RATE_LIMIT_RPM):
        self._rpm = rpm
        self._tokens = float(rpm)
        self._max_tokens = float(rpm)
        self._refill_rate = rpm / 60.0  # tokens per second
        self._last_refill = time.monotonic()
        self._lock = threading.Condition(threading.Lock())

    def acquire(self, timeout: float = 60.0) -> bool:
        """获取一个令牌，不足时阻塞等待。返回 True 表示获取成功。"""
        deadline = time.monotonic() + timeout
        with self._lock:
            while True:
                self._refill()
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return True
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    logger.warning(f'[限流] 等待超时 ({timeout}s)，放弃请求')
                    return False
                wait_time = min((1.0 - self._tokens) / self._refill_rate, remaining)
                self._lock.wait(timeout=wait_time)

    def _refill(self):
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(self._max_tokens, self._tokens + elapsed * self._refill_rate)
        self._last_refill = now


rate_limiter = RateLimiter()
