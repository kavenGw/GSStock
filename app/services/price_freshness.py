"""盯盘价格新鲜度闸门 — 纯函数，宁可不推也不推旧价"""
from datetime import datetime

FRESHNESS_MULTIPLIER = 2
PRELOAD_INTERVAL_MINUTES = {'A': 1}   # 其余市场默认 3，对应 watch_preload NON_A_REFRESH_EVERY
DEFAULT_INTERVAL_MINUTES = 3


def max_age_seconds(market: str) -> int:
    interval = PRELOAD_INTERVAL_MINUTES.get(market, DEFAULT_INTERVAL_MINUTES)
    return interval * FRESHNESS_MULTIPLIER * 60


def price_age_seconds(data: dict, now: datetime = None):
    ts = data.get('last_fetch_time')
    if not ts:
        return None
    try:
        fetched = datetime.fromisoformat(ts)
    except (ValueError, TypeError):
        return None
    return int(((now or datetime.now()) - fetched).total_seconds())


def is_fresh(price_data: dict, market: str, now: datetime = None) -> bool:
    if not price_data or not price_data.get('current_price'):
        return False
    if price_data.get('_is_degraded'):
        return False
    age = price_age_seconds(price_data, now)
    if age is None:
        return False
    return age <= max_age_seconds(market)


def filter_fresh_prices(prices: dict, market_map: dict, now: datetime = None) -> dict:
    now = now or datetime.now()
    return {c: d for c, d in prices.items() if is_fresh(d, market_map.get(c, ''), now)}
