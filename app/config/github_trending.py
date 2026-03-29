"""GitHub Trending 监控配置"""
import os

GITHUB_TRENDING_ENABLED = os.environ.get('GITHUB_TRENDING_ENABLED', 'true').lower() == 'true'
GITHUB_TRENDING_TOP_N = int(os.environ.get('GITHUB_TRENDING_TOP_N', '10'))
GITHUB_TRENDING_URL = 'https://github.com/trending'
