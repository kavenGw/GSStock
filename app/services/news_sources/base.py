"""新闻源基类"""
import time
import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

# 默认：连续失败 3 次后冷却 30 分钟
DEFAULT_MAX_FAILURES = 3
DEFAULT_COOLDOWN_SECONDS = 30 * 60


class NewsSourceBase(ABC):
    name: str = ''

    def __init__(self):
        self._consecutive_failures = 0
        self._cooldown_until = 0.0
        self._max_failures = DEFAULT_MAX_FAILURES
        self._cooldown_seconds = DEFAULT_COOLDOWN_SECONDS

    def fetch(self) -> list[dict]:
        """带冷却机制的获取入口"""
        now = time.time()
        if self._cooldown_until > now:
            remaining = int(self._cooldown_until - now)
            logger.debug(f'{self.name} 冷却中，剩余 {remaining}s')
            return []

        try:
            results = self.fetch_latest()
            if results:
                self._on_success()
            return results
        except Exception as e:
            self._on_failure(e)
            return []

    def _on_success(self):
        if self._consecutive_failures > 0:
            logger.info(f'{self.name} 恢复正常，重置失败计数')
        self._consecutive_failures = 0
        self._cooldown_until = 0.0

    def _on_failure(self, error: Exception):
        self._consecutive_failures += 1
        if self._consecutive_failures >= self._max_failures:
            self._cooldown_until = time.time() + self._cooldown_seconds
            logger.warning(
                f'{self.name} 连续失败 {self._consecutive_failures} 次，'
                f'冷却 {self._cooldown_seconds // 60} 分钟: {error}'
            )
        else:
            logger.warning(
                f'{self.name} 获取失败 ({self._consecutive_failures}/{self._max_failures}): {error}'
            )

    @abstractmethod
    def fetch_latest(self) -> list[dict]:
        """获取最新新闻，返回统一格式:
        [{
            'content': str,
            'source_id': str,
            'display_time': float,
            'source_name': str,
            'score': int,
        }]
        """
        ...
