import logging
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from app.config.notification_config import (
    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, NOTIFY_EMAIL_TO, EMAIL_ENABLED
)
from app.notifications.base import Notifier
from app.strategies.base import Signal

logger = logging.getLogger(__name__)


class EmailNotifier(Notifier):
    name = "email"
    enabled = EMAIL_ENABLED

    def format_signal(self, signal: Signal) -> str:
        return f"<h3>[{signal.strategy}] {signal.title}</h3><p>{signal.detail}</p>"

    def send(self, signal: Signal, formatted: str) -> bool:
        if not self.enabled:
            return False
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f'[{signal.priority}] {signal.title}'
            msg['From'] = SMTP_USER
            msg['To'] = NOTIFY_EMAIL_TO
            msg.attach(MIMEText(formatted, 'html', 'utf-8'))
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=context, timeout=10) as server:
                server.login(SMTP_USER, SMTP_PASSWORD)
                server.sendmail(SMTP_USER, NOTIFY_EMAIL_TO, msg.as_string())
            return True
        except Exception as e:
            logger.error(f'[通知.邮件] 推送失败: {e}')
            return False
