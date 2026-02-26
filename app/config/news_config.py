"""新闻看板配置"""
import os

NEWS_INTERVAL_MINUTES = int(os.environ.get('NEWS_INTERVAL_MINUTES', '10'))

WALLSTREETCN_API = 'https://api-prod.wallstreetcn.com/apiv1/content/lives'
WALLSTREETCN_CHANNEL = 'global-channel'

INTEREST_CATEGORIES = {
    'stock': '股票',
    'metal': '重金属/商品',
    'ai': 'AI/科技',
    'other': '其他',
}
