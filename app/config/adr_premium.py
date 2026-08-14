"""ADR 跨市场溢价标的配置

ratio = 每 1 ADR 对应几股本土股。
- TSM=5（公认，1 ADR = 5 股台积电普通股）
- SK海力士 SKHY 为 2026-07-09 挂牌的 Nasdaq 保荐 ADR，1 ADS = 1/10 普通股 → ratio=0.1。
  （旧 OTC 粉单 HXSCL/HXSCF 已无 yfinance 报价，弃用。）
- 小鹏 XPEV，1 ADS = 2 股港股 A 类普通股 → ratio=2。
- 京东 JD，1 ADS = 2 股港股 A 类普通股 → ratio=2（2026-08-12 实测 HK 123.00 / fx 7.846 / US 31.61 → +0.82%，口径自洽）。
"""

ADR_PREMIUM_PAIRS = [
    {'key': 'tsmc',    'name': 'TSM',      'us': 'TSM',   'home': '2330.TW',   'ratio': 5,    'fx': 'TWD=X'},
    {'key': 'skhynix', 'name': 'SK海力士', 'us': 'SKHY',  'home': '000660.KS', 'ratio': 0.1,  'fx': 'KRW=X'},
    {'key': 'xpeng',   'name': '小鹏',     'us': 'XPEV',  'home': '9868.HK',   'ratio': 2,    'fx': 'HKD=X'},
    {'key': 'jd',      'name': '京东',     'us': 'JD',    'home': '9618.HK',   'ratio': 2,    'fx': 'HKD=X'},
]
