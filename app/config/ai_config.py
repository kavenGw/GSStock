"""AI分析配置

支持OpenAI兼容API（OpenAI、DeepSeek、本地模型等）。
"""
import os

AI_API_KEY = os.environ.get('AI_API_KEY', '')
AI_BASE_URL = os.environ.get('AI_BASE_URL', 'https://api.openai.com/v1')
AI_MODEL = os.environ.get('AI_MODEL', 'gpt-4o-mini')

# AI分析是否启用（需要配置API Key）
AI_ENABLED = bool(AI_API_KEY)
