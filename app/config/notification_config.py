"""消息推送配置

支持 Slack Webhook 和 SMTP 邮件推送。
"""
import os

SLACK_WEBHOOK_URL = os.environ.get('SLACK_WEBHOOK_URL', '')
SMTP_HOST = os.environ.get('SMTP_HOST', '')
SMTP_PORT = int(os.environ.get('SMTP_PORT', '465'))
SMTP_USER = os.environ.get('SMTP_USER', '')
SMTP_PASSWORD = os.environ.get('SMTP_PASSWORD', '')
NOTIFY_EMAIL_TO = os.environ.get('NOTIFY_EMAIL_TO', '')

SLACK_ENABLED = bool(SLACK_WEBHOOK_URL)
EMAIL_ENABLED = bool(SMTP_HOST and SMTP_USER and SMTP_PASSWORD and NOTIFY_EMAIL_TO)
