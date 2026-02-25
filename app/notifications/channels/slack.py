import json
import logging
from urllib.request import urlopen, Request
from app.config.notification_config import SLACK_WEBHOOK_URL, SLACK_ENABLED
from app.notifications.base import Notifier
from app.strategies.base import Signal

logger = logging.getLogger(__name__)

PRIORITY_EMOJI = {"HIGH": "\U0001f534", "MEDIUM": "\U0001f7e1", "LOW": "\U0001f7e2"}


class SlackNotifier(Notifier):
    name = "slack"
    enabled = SLACK_ENABLED

    def format_signal(self, signal: Signal) -> str:
        emoji = PRIORITY_EMOJI.get(signal.priority, "")
        return f"{emoji} *[{signal.strategy}]* {signal.title}\n{signal.detail}"

    def send(self, signal: Signal, formatted: str) -> bool:
        if not self.enabled:
            return False
        try:
            payload = json.dumps({'text': formatted}).encode('utf-8')
            req = Request(SLACK_WEBHOOK_URL, data=payload,
                         headers={'Content-Type': 'application/json'})
            with urlopen(req, timeout=10) as resp:
                return resp.status == 200
        except Exception as e:
            logger.error(f'[通知.Slack] 推送失败: {e}')
            return False
