# 板块评级配置

SECTOR_RATING_CONFIG = {
    'storage': {
        'name': '存储板块',
        'stocks': ['WDC', 'MU', 'SNDK', '285A.T'],
        'weights': {
            'change': 0.6,
            'consistency': 0.3,
            'volume': 0.1
        },
        'thresholds': {
            'bullish': 60,
            'bearish': 40
        }
    }
}
