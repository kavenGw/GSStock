"""行情取数守卫：拒绝集合竞价参考价、零成交、字段错位的报价。

用法：
    from scripts.quote_guard import guard, QuoteRejected
    try:
        q = guard(quote_dict)
    except QuoteRejected as exc:
        print(f'取数被拒：{exc}')

见 stock-research references/lessons.md L24。
"""
from __future__ import annotations

from datetime import datetime, time

MIN_VOLUME = 1_000
MARKET_CAP_TOLERANCE = 0.01

MARKET_SESSIONS = {
    'HK': ((time(9, 30), time(12, 0)), (time(13, 0), time(16, 0))),
    'A': ((time(9, 30), time(11, 30)), (time(13, 0), time(15, 0))),
    'US': ((time(9, 30), time(16, 0)),),
}


class QuoteRejected(Exception):
    """报价未通过守卫断言。"""


def infer_market(code: str) -> str:
    c = code.lower()
    if c.endswith('.hk'):
        return 'HK'
    if c.endswith(('.ss', '.sz')):
        return 'A'
    if c.startswith('hk'):
        return 'HK'
    if c.startswith(('sh', 'sz')):
        return 'A'
    return 'US'


def in_session(market: str, ts: datetime) -> bool:
    sessions = MARKET_SESSIONS[market]
    t = ts.time()
    return any(start <= t <= end for start, end in sessions)


def guard(quote: dict, *, allow_preopen: bool = False) -> dict:
    market = infer_market(quote['code'])
    ts = quote['timestamp']
    if not in_session(market, ts):
        if not allow_preopen:
            raise QuoteRejected(
                f"{quote['code']} 时戳 {ts:%H:%M:%S} 不在 {market} 连续交易时段内 —— "
                '这是集合竞价参考价或非交易时段快照，不可作行情锚')
        quote['preopen_warning'] = '竞价参考价，不可作行情锚'
        return quote
    if quote['volume'] < MIN_VOLUME:
        raise QuoteRejected(
            f"{quote['code']} 成交量仅 {quote['volume']} —— 疑为竞价挂单或停牌，不可作行情锚")
    implied = quote['price'] * quote['shares']
    cap = quote['market_cap']
    if not cap:
        raise QuoteRejected(
            f"{quote['code']} 市值缺失 —— 自洽校验无法进行")
    if abs(implied - cap) / cap > MARKET_CAP_TOLERANCE:
        raise QuoteRejected(
            f"{quote['code']} 市值不自洽：价×股本={implied:,.0f} vs 报市值={cap:,.0f} —— "
            '疑为字段索引错位')
    return quote
