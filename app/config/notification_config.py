"""消息推送配置"""
import os

SLACK_WEBHOOK_URL = os.environ.get('SLACK_WEBHOOK_URL', '')
SLACK_ENABLED = bool(SLACK_WEBHOOK_URL)
