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
            cls._instance._signal_state = {}  # 状态机去重: {key: direction}
        return cls._instance

    def init_channels(self):
        if self._initialized:
            return
        from app.notifications.channels.slack import SlackNotifier
        self._channels = [SlackNotifier()]
        self._initialized = True

    def _make_signal_key(self, signal: Signal) -> str:
        """生成信号去重 key: strategy:stock_code:signal_name"""
        data = signal.data or {}
        stock_code = data.get('stock_code') or data.get('code', '')
        signal_name = data.get('name', '')
        if stock_code and signal_name:
            return f"{signal.strategy}:{stock_code}:{signal_name}"
        return ''

    def _get_signal_direction(self, signal: Signal) -> str:
        """获取信号方向: buy/sell/涨/跌"""
        data = signal.data or {}
        # price_alert 用 type 字段
        direction = data.get('type', '')
        if direction:
            return direction
        # change_alert 用涨跌幅判断
        change_pct = data.get('change_pct')
        if change_pct is not None:
            return 'up' if change_pct > 0 else 'down'
        return ''

    def _is_duplicate(self, signal: Signal) -> bool:
        """状态机去重：方向未变化则视为重复"""
        key = self._make_signal_key(signal)
        if not key:
            return False

        direction = self._get_signal_direction(signal)
        if not direction:
            return False

        last_direction = self._signal_state.get(key)
        if last_direction == direction:
            logger.debug(f'[通知去重] 跳过重复信号: {key} direction={direction}')
            return True

        self._signal_state[key] = direction
        return False

    def dispatch(self, signal: Signal):
        if not self._initialized:
            self.init_channels()
        if signal.priority == "LOW":
            return
        if self._is_duplicate(signal):
            return
        for channel in self._channels:
            if not channel.enabled:
                continue
            try:
                formatted = channel.format_signal(signal)
                channel.send(signal, formatted)
            except Exception as e:
                logger.error(f'[通知分发] {channel.name} 发送失败: {e}')


notification_manager = NotificationManager()
