"""矿产看板板块配置：每个板块一个期货锚 + 相关股票来自 valuations.yaml 的 commodity 字段。"""

MINERAL_BOARDS = {
    'copper': {
        'name': '铜',
        'futures_code': 'HG=F',
        'futures_name': 'COMEX铜',
        'futures_source': 'yfinance',
        'futures_fallback_code': None,
    },
    'lithium': {
        'name': '锂',
        'futures_code': 'LC0',
        'futures_name': '碳酸锂主连',
        'futures_source': 'akshare',
        'futures_fallback_code': None,
    },
}
