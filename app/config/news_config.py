"""新闻看板配置"""

WALLSTREETCN_API = 'https://api-prod.wallstreetcn.com/apiv1/content/lives'
WALLSTREETCN_CHANNEL = 'global-channel'

NEWS_SOURCE_LABELS = {
    'wallstreetcn': {'label': '华尔街', 'color': 'secondary'},
    'smolai': {'label': 'SmolAI', 'color': 'info'},
    'cls': {'label': '财联社', 'color': 'primary'},
    '36kr': {'label': '36kr', 'color': 'warning'},
}

MAX_DERIVATION_PER_POLL = 2
DERIVATION_URL_TIMEOUT = 30
DERIVATION_TOTAL_TIMEOUT = 120
