"""ADR 跨市场溢价标的配置

ratio = 每 1 ADR 对应几股本土股。TSM=5（公认）。
SK海力士 HXSCL 为 OTC 未挂牌 ADR，ratio 待实测确认（见 plan 末尾说明），
未确认前置 None → 该腿溢价不可算、推送显「—」。
"""

ADR_PREMIUM_PAIRS = [
    {'key': 'tsmc',    'name': 'TSM',      'us': 'TSM',   'home': '2330.TW',   'ratio': 5,    'fx': 'TWD=X'},
    {'key': 'skhynix', 'name': 'SK海力士', 'us': 'HXSCL', 'home': '000660.KS', 'ratio': None, 'fx': 'KRW=X'},
]
