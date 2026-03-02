"""新闻看板配置"""
import os

WALLSTREETCN_API = 'https://api-prod.wallstreetcn.com/apiv1/content/lives'
WALLSTREETCN_CHANNEL = 'global-channel'

NEWS_SOURCE_LABELS = {
    'wallstreetcn': {'label': '华尔街', 'color': 'secondary'},
    'smolai': {'label': 'SmolAI', 'color': 'info'},
    'cls': {'label': '财联社', 'color': 'primary'},
    '36kr': {'label': '36kr', 'color': 'warning'},
    'google_news': {'label': 'Google', 'color': 'danger'},
    'eastmoney_stock': {'label': '东财', 'color': 'success'},
    'yahoo_finance': {'label': 'Yahoo', 'color': 'dark'},
}

MAX_DERIVATION_PER_POLL = 2
DERIVATION_URL_TIMEOUT = 30
DERIVATION_TOTAL_TIMEOUT = 120

# 公司新闻爬取配置
COMPANY_NEWS_MAX_COMPANIES = int(os.getenv('COMPANY_NEWS_MAX_COMPANIES', '3'))
COMPANY_NEWS_MAX_ARTICLES = int(os.getenv('COMPANY_NEWS_MAX_ARTICLES', '5'))
COMPANY_NEWS_INTERVAL_MINUTES = int(os.getenv('COMPANY_NEWS_INTERVAL_MINUTES', '30'))
COMPANY_NEWS_CRAWL_TIMEOUT = 30
COMPANY_NEWS_TOTAL_TIMEOUT = 120
