import logging
from app.strategies.base import Signal
from app.notifications.base import Notifier

logger = logging.getLogger(__name__)


class NotificationManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._channels = []
            cls._instance._initialized = False
        return cls._instance

    def init_channels(self):
        if self._initialized:
            return
        from app.notifications.channels.slack import SlackNotifier
        from app.notifications.channels.email import EmailNotifier
        self._channels = [SlackNotifier(), EmailNotifier()]
        self._initialized = True

    def dispatch(self, signal: Signal):
        if not self._initialized:
            self.init_channels()
        for channel in self._channels:
            if not channel.enabled:
                continue
            if signal.priority == "LOW":
                continue
            try:
                formatted = channel.format_signal(signal)
                channel.send(signal, formatted)
            except Exception as e:
                logger.error(f'[通知分发] {channel.name} 发送失败: {e}')


notification_manager = NotificationManager()
