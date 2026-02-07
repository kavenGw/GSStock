# 统一股票代码配置
# 所有服务模块从此处导入股票代码配置，确保一致性

# 期货代码映射（使用 yfinance 可用的代码）
FUTURES_CODES = {
    # 黄金
    'AU0': {'name': '沪金主连', 'yf_code': 'GC=F'},
    'GC=F': {'name': 'COMEX黄金', 'yf_code': 'GC=F'},
    'GLD': {'name': '黄金ETF', 'yf_code': 'GLD'},
    # 白银
    'AG0': {'name': '沪银主连', 'yf_code': 'SI=F'},
    'SI=F': {'name': 'COMEX白银', 'yf_code': 'SI=F'},
    'SLV': {'name': '白银ETF', 'yf_code': 'SLV'},
    # 铜
    'CU0': {'name': '沪铜主连', 'yf_code': 'HG=F'},
    'HG=F': {'name': 'COMEX铜', 'yf_code': 'HG=F'},
    'HG0': {'name': '纽铜主连', 'yf_code': 'HG=F'},
    'LME_CU': {'name': '伦铜主连', 'yf_code': 'COPA.L'},
    'CPER': {'name': '铜ETF', 'yf_code': 'CPER'},
    # 铝
    'AL0': {'name': '沪铝主连', 'yf_code': 'ALI=F'},
    'ALI=F': {'name': 'COMEX铝', 'yf_code': 'ALI=F'},
    # 有色
    '159652.SZ': {'name': '有色50ETF', 'yf_code': '159652.SZ'},
}

# 指数代码映射
INDEX_CODES = {
    '000001.SS': {'name': '上证指数', 'yf_code': '000001.SS'},
    '399001.SZ': {'name': '深证成指', 'yf_code': '399001.SZ'},
    '399006.SZ': {'name': '创业板指', 'yf_code': '399006.SZ', 'etf_code': '159915.SZ'},
    '000300.SS': {'name': '沪深300', 'yf_code': '000300.SS'},
    '^GSPC': {'name': '标普500', 'yf_code': '^GSPC'},
    '000016.SS': {'name': '上证50', 'yf_code': '000016.SS', 'etf_code': '510050.SS'},
    '2800.HK': {'name': '恒生科技', 'yf_code': '2800.HK'},
    '^NDX': {'name': '纳指100', 'yf_code': '^NDX'},
}

# 分类代码映射（仅期货/指数/ETF，股票从数据库获取）
CATEGORY_CODES = {
    'heavy_metals': ['GC=F', 'HG=F', 'ALI=F', 'SI=F'],
    'gold': ['GLD', 'AU0'],
    'copper': ['HG0', 'LME_CU', 'CU0'],
    'aluminum': ['AL0'],
    'silver': ['SLV', 'AG0'],
    'index': ['000001.SS', '399001.SZ', '399006.SZ', '000300.SS', '^GSPC', '000016.SS', '2800.HK', '^NDX'],
    'cpu': ['AMD', 'INTC'],
}

# 分类名称映射
CATEGORY_NAMES = {
    'heavy_metals': '重金属',
    'gold': '黄金',
    'copper': '铜',
    'aluminum': '铝',
    'silver': '银',
    'index': '指数',
    'etf': 'ETF',
    'storage': '存储',
    'pcb': 'PCB',
    'cpu': 'CPU',
    'custom': '自定义'
}
