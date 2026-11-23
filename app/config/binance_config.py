"""已核实标的的币安永续映射；只启用当前盯盘池及商品基准中的条目。"""
import os

BINANCE_FUTURES_BASE_URL = os.environ.get(
    'BINANCE_FUTURES_BASE_URL', 'https://fapi.binance.com').rstrip('/')
BINANCE_ALERT_THRESHOLD_PCT = float(os.environ.get('BINANCE_ALERT_THRESHOLD_PCT', '3'))
BINANCE_ALERT_COOLDOWN_MINUTES = float(os.environ.get('BINANCE_ALERT_COOLDOWN_MINUTES', '30'))

# source_code: (contract_symbol, underlying_type)
PERPETUAL_MAPPINGS = {
    'NVDA': ('NVDAUSDT', 'EQUITY'),
    'AMD': ('AMDUSDT', 'EQUITY'),
    'LITE': ('LITEUSDT', 'EQUITY'),
    'ANT': ('ANTUSDT', 'EQUITY'),
    'SOXX': ('SOXXUSDT', 'EQUITY'),
    '000660.KS': ('SKHYNIXUSDT', 'KR_EQUITY'),
    '688825': ('CXMTUSDT', 'CN_EQUITY'),
    '0100.HK': ('MINIMAXUSDT', 'HK_EQUITY'),
    '2513.HK': ('ZHIPUUSDT', 'HK_EQUITY'),
    '0700.HK': ('TENCENTUSDT', 'HK_EQUITY'),
    '1810.HK': ('HK1810USDT', 'HK_EQUITY'),
    '9992.HK': ('POPMARTUSDT', 'HK_EQUITY'),
    'CL=F': ('CLUSDT', 'COMMODITY'),
    'BZ=F': ('BZUSDT', 'COMMODITY'),
    'GC=F': ('XAUUSDT', 'COMMODITY'),
    'SI=F': ('XAGUSDT', 'COMMODITY'),
}
