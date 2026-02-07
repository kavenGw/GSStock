"""平台熔断器

当数据源连续失败时自动熔断，冷却后恢复。
"""
import logging
import threading
from datetime import datetime, timedelta
from enum import Enum

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    CLOSED = "closed"      # 正常状态
    OPEN = "open"          # 熔断状态
    HALF_OPEN = "half_open"  # 试探状态


class CircuitBreaker:
    """平台熔断器（单例）"""

    _instance = None
    _lock = threading.Lock()

    FAILURE_THRESHOLD = 3      # 连续失败次数阈值
    COOLDOWN_SECONDS = 1800    # 冷却时间（30分钟）

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._platforms = {}
        self._state_lock = threading.Lock()

    def _get_platform(self, name: str) -> dict:
        """获取平台状态，不存在则初始化"""
        if name not in self._platforms:
            self._platforms[name] = {
                'state': CircuitState.CLOSED,
                'failure_count': 0,
                'last_failure_time': None,
                'open_time': None,
            }
        return self._platforms[name]

    def is_available(self, platform: str) -> bool:
        """检查平台是否可用"""
        with self._state_lock:
            p = self._get_platform(platform)

            if p['state'] == CircuitState.CLOSED:
                return True

            if p['state'] == CircuitState.OPEN:
                # 检查是否冷却结束
                if p['open_time'] and datetime.now() - p['open_time'] >= timedelta(seconds=self.COOLDOWN_SECONDS):
                    p['state'] = CircuitState.HALF_OPEN
                    logger.info(f"{platform} 冷却结束，进入试探状态")
                    return True
                return False

            if p['state'] == CircuitState.HALF_OPEN:
                return True

            return False

    def record_success(self, platform: str):
        """记录成功，重置状态"""
        with self._state_lock:
            p = self._get_platform(platform)
            was_half_open = p['state'] == CircuitState.HALF_OPEN

            p['state'] = CircuitState.CLOSED
            p['failure_count'] = 0
            p['last_failure_time'] = None
            p['open_time'] = None

            if was_half_open:
                logger.info(f"{platform} 恢复正常")

    def record_failure(self, platform: str) -> bool:
        """记录失败，返回是否触发熔断"""
        with self._state_lock:
            p = self._get_platform(platform)
            p['failure_count'] += 1
            p['last_failure_time'] = datetime.now()

            # HALF_OPEN 状态下失败，直接熔断
            if p['state'] == CircuitState.HALF_OPEN:
                p['state'] = CircuitState.OPEN
                p['open_time'] = datetime.now()
                logger.warning(f"{platform} 试探失败，重新熔断，冷却{self.COOLDOWN_SECONDS // 60}分钟")
                return True

            # CLOSED 状态下连续失败达到阈值
            if p['failure_count'] >= self.FAILURE_THRESHOLD:
                p['state'] = CircuitState.OPEN
                p['open_time'] = datetime.now()
                logger.warning(f"{platform} 连续失败{p['failure_count']}次，熔断，冷却{self.COOLDOWN_SECONDS // 60}分钟")
                return True

            return False

    def get_status(self) -> dict:
        """获取所有平台状态"""
        with self._state_lock:
            result = {}
            for name, p in self._platforms.items():
                result[name] = {
                    'state': p['state'].value,
                    'failure_count': p['failure_count'],
                    'open_time': p['open_time'].isoformat() if p['open_time'] else None,
                }
            return result

    def reset(self, platform: str = None):
        """重置平台状态（用于测试或手动恢复）"""
        with self._state_lock:
            if platform:
                if platform in self._platforms:
                    self._platforms[platform] = {
                        'state': CircuitState.CLOSED,
                        'failure_count': 0,
                        'last_failure_time': None,
                        'open_time': None,
                    }
                    logger.info(f"{platform} 状态已重置")
            else:
                self._platforms.clear()
                logger.info("所有平台状态已重置")


# 单例实例
circuit_breaker = CircuitBreaker()
