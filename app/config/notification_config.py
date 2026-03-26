"""消息推送配置"""
import os

SLACK_BOT_TOKEN = os.environ.get('SLACK_BOT_TOKEN', '')
SLACK_ENABLED = bool(SLACK_BOT_TOKEN)

# 频道常量（不带 # 前缀，chat.postMessage 要求频道名或频道 ID）
CHANNEL_NEWS = 'news'
CHANNEL_WATCH = 'news_watch'
CHANNEL_AI_TOOL = 'news_ai_tool'
CHANNEL_LOL = 'news_lol'
CHANNEL_NBA = 'news_nba'
CHANNEL_DAILY = 'news_daily'
