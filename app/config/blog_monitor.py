"""技术博客监控配置"""
import os

BLOG_MONITOR_ENABLED = os.environ.get('BLOG_MONITOR_ENABLED', 'true').lower() == 'true'

BLOG_SOURCES = [
    {
        'key': 'anthropic_engineering',
        'name': 'Anthropic Engineering',
        'type': 'html',
        'list_url': 'https://www.anthropic.com/engineering',
        'base_url': 'https://www.anthropic.com',
        'enabled': True,
    },
    {
        'key': 'openai_blog',
        'name': 'OpenAI Blog',
        'type': 'rss',
        'feed_url': 'https://openai.com/blog/rss.xml',
        'enabled': True,
    },
    {
        'key': 'deepmind_blog',
        'name': 'DeepMind Blog',
        'type': 'rss',
        'feed_url': 'https://deepmind.google/blog/feed/',
        'enabled': True,
    },
]
