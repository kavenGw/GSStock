"""事件总线 — 策略信号到通知的桥梁"""
import logging
from typing import Callable
from app.strategies.base import Signal

logger = logging.getLogger(__name__)


class EventBus:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._handlers = []
        return cls._instance

    def subscribe(self, handler: Callable[[Signal], None]):
        self._handlers.append(handler)

    def publish(self, signal: Signal):
        for handler in self._handlers:
            try:
                handler(signal)
            except Exception as e:
                logger.error(f'[事件总线] handler 失败: {e}')


event_bus = EventBus()
