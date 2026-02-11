"""数据源配置

配置各市场的数据源优先级、权重和API密钥环境变量。

环境变量配置：
- TWELVE_DATA_API_KEY: Twelve Data API密钥 (免费: 8请求/分钟, 800请求/天)
- POLYGON_API_KEY: Polygon.io API密钥 (免费: 5请求/分钟)
"""
import os

# 各市场数据源配置
# sources: 数据源列表（按优先级排序）
# fallback: 兜底数据源
# weights: 初始权重分配（总和不需要为100）
MARKET_DATA_SOURCES = {
    # A股市场
    'A': {
        'sources': ['sina', 'tencent', 'eastmoney'],
        'fallback': 'yfinance',
        'weights': {
            'sina': 35,      # 新浪财经 - 稳定性较好
            'tencent': 45,   # 腾讯财经 - 批量获取效率高，优先使用
            'eastmoney': 20  # 东方财富 - 最后备选
        },
        'description': 'A股市场使用国内数据源，yfinance作为兜底'
    },

    # 美股市场
    'US': {
        'sources': ['yfinance', 'twelvedata', 'polygon'],
        'fallback': 'yfinance',
        'weights': {
            'yfinance': 70,      # Yahoo Finance - 免费无限制
            'twelvedata': 20,    # Twelve Data - 8请求/分钟
            'polygon': 10        # Polygon - 5请求/分钟
        },
        'description': '美股市场使用多数据源负载均衡'
    },

    # 港股市场
    'HK': {
        'sources': ['yfinance', 'twelvedata'],
        'fallback': 'yfinance',
        'weights': {
            'yfinance': 75,
            'twelvedata': 25
        },
        'description': '港股市场使用yfinance为主，Twelve Data辅助'
    },

    # 韩国市场
    'KR': {
        'sources': ['yfinance'],
        'fallback': 'yfinance',
        'weights': {'yfinance': 100},
        'description': '韩国市场目前仅支持yfinance'
    },

    # 台湾市场
    'TW': {
        'sources': ['yfinance'],
        'fallback': 'yfinance',
        'weights': {'yfinance': 100},
        'description': '台湾市场目前仅支持yfinance'
    },
}

# 数据源API配置
DATA_SOURCE_API_CONFIG = {
    'yfinance': {
        'name': 'Yahoo Finance',
        'rate_limit': None,  # 无明确限制
        'api_key_env': None,
        'markets': ['A', 'US', 'HK', 'KR', 'TW'],
        'features': ['realtime', 'historical', 'info']
    },
    'twelvedata': {
        'name': 'Twelve Data',
        'rate_limit': '8/minute, 800/day (free)',
        'api_key_env': 'TWELVE_DATA_API_KEY',
        'markets': ['US', 'HK'],
        'features': ['realtime', 'historical']
    },
    'polygon': {
        'name': 'Polygon.io',
        'rate_limit': '5/minute (free)',
        'api_key_env': 'POLYGON_API_KEY',
        'markets': ['US'],
        'features': ['realtime', 'historical']
    },
    'sina': {
        'name': '新浪财经',
        'rate_limit': None,
        'api_key_env': None,
        'markets': ['A'],
        'features': ['realtime']
    },
    'tencent': {
        'name': '腾讯财经',
        'rate_limit': None,
        'api_key_env': None,
        'markets': ['A'],
        'features': ['realtime']
    },
    'eastmoney': {
        'name': '东方财富',
        'rate_limit': None,
        'api_key_env': None,
        'markets': ['A'],
        'features': ['realtime', 'historical']
    },
}


def get_market_sources(market: str) -> dict:
    """获取指定市场的数据源配置"""
    return MARKET_DATA_SOURCES.get(market, MARKET_DATA_SOURCES.get('US'))


def get_available_sources(market: str) -> list:
    """获取指定市场可用的数据源列表（已配置API密钥的）"""
    config = get_market_sources(market)
    sources = config.get('sources', ['yfinance'])

    available = []
    for source in sources:
        api_config = DATA_SOURCE_API_CONFIG.get(source, {})
        api_key_env = api_config.get('api_key_env')

        # 如果不需要API密钥，或者已配置API密钥
        if api_key_env is None or os.environ.get(api_key_env):
            available.append(source)

    # 确保至少有一个数据源
    if not available:
        fallback = config.get('fallback', 'yfinance')
        available.append(fallback)

    return available


def get_data_source_status() -> dict:
    """获取所有数据源的配置状态"""
    status = {}

    for source, config in DATA_SOURCE_API_CONFIG.items():
        api_key_env = config.get('api_key_env')
        is_configured = api_key_env is None or bool(os.environ.get(api_key_env))

        status[source] = {
            'name': config.get('name'),
            'configured': is_configured,
            'rate_limit': config.get('rate_limit'),
            'markets': config.get('markets', []),
            'features': config.get('features', [])
        }

    return status
