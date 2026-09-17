"""Alpaca 夜盘（暗盘）报价 — 美股 ET 20:00–次日 04:00

免费档的 feed=overnight 实测为实时（2026-09-17 采样 24 次，quote lag 1.9–7.8s），
覆盖 Blue Ocean ATS 的隔夜成交；原始 feed=boats 需付费订阅。

涨跌幅基准取 feed=delayed_sip 的 dailyBar.c —— 前一个常规交易日的官方收盘价。
**不能用 feed=overnight 自带的 prevDailyBar**：那是前一个「夜盘时段」的收盘价。
实测 LITE 在 9/16 常规时段涨 9.6%，夜盘 prevDailyBar 仍停在 856.61 而官方收盘是 919.40，
拿它当基准会把 +0.79% 算成 +8.18%，直接触发假告警。延迟 15 分钟对「昨收」无影响。
"""
import logging
import os
import re
from datetime import datetime

import requests

logger = logging.getLogger(__name__)

SNAPSHOT_URL = 'https://data.alpaca.markets/v2/stocks/snapshots'
NIGHT_FEED = 'overnight'
REGULAR_FEED = 'delayed_sip'
TIMEOUT = 5

_NANOS_RE = re.compile(r'\.(\d{6})\d+')


def _credentials() -> tuple:
    return os.getenv('ALPACA_API_KEY_ID'), os.getenv('ALPACA_API_SECRET_KEY')


def _normalize_time(ts: str) -> str:
    """Alpaca 返回纳秒精度，datetime.fromisoformat 只吃到微秒，多余位数直接截掉"""
    if not ts or not isinstance(ts, str):
        return None
    raw = _NANOS_RE.sub(r'.\1', ts.replace('Z', '+00:00'))
    try:
        return datetime.fromisoformat(raw).isoformat()
    except ValueError:
        return ts


def _bar_date(bar: dict) -> str:
    return str((bar or {}).get('t') or '')[:10]


def _baseline_close(regular: dict, night_date: str):
    """取夜盘之前那个常规交易日的收盘价

    正常情况 dailyBar 就是它；若已翻篇到夜盘所属日（同日或更晚），退回 prevDailyBar。
    返回的基准必须带一个严格早于 night_date 的日期 —— 日期缺失或无法核验时一律返回
    None。错误基准比缺数据危险得多：前者会安静地算出假涨跌幅并触发告警，后者只是不给价。
    """
    if not night_date:
        return None
    for key in ('dailyBar', 'prevDailyBar'):
        bar = (regular or {}).get(key) or {}
        bar_date = _bar_date(bar)
        if bar.get('c') is not None and bar_date and bar_date < night_date:
            return bar.get('c')
    return None


def parse_snapshot(night: dict, regular: dict) -> dict | None:
    """夜盘 snapshot + 常规 snapshot → {session, price, change_pct, time, source}

    缺成交或缺基准收盘返回 None。
    """
    trade = (night or {}).get('latestTrade') or {}
    price = trade.get('p')
    if price is None:
        return None
    base = _baseline_close(regular, _bar_date((night or {}).get('dailyBar')))
    if not base:
        return None
    return {
        'session': 'overnight',
        'price': round(float(price), 2),
        'change_pct': round((float(price) / float(base) - 1) * 100, 2),
        'time': _normalize_time(trade.get('t')),
        'source': 'alpaca',
    }


def _snapshots(symbols: list, feed: str, key: str, secret: str) -> dict:
    try:
        resp = requests.get(SNAPSHOT_URL,
                            params={'symbols': ','.join(symbols), 'feed': feed},
                            headers={'APCA-API-KEY-ID': key,
                                     'APCA-API-SECRET-KEY': secret,
                                     'accept': 'application/json'},
                            timeout=TIMEOUT)
        if resp.status_code != 200:
            logger.debug(f'[Alpaca] {feed} snapshot HTTP {resp.status_code}: {resp.text[:200]}')
            return {}
        return resp.json() or {}
    except Exception as e:
        logger.debug(f'[Alpaca] {feed} snapshot 失败: {e}')
        return {}


def get_overnight_quotes(symbols: list) -> dict:
    """批量取夜盘报价 {symbol: quote}；两个 feed 各一次批量请求，取不到的直接缺席"""
    if not symbols:
        return {}
    key, secret = _credentials()
    if not key or not secret:
        logger.debug('[Alpaca] 未配置 ALPACA_API_KEY_ID / ALPACA_API_SECRET_KEY，夜盘取价跳过')
        return {}

    night = _snapshots(symbols, NIGHT_FEED, key, secret)
    if not night:
        return {}
    regular = _snapshots(symbols, REGULAR_FEED, key, secret)

    result = {}
    for symbol in symbols:
        try:
            quote = parse_snapshot(night.get(symbol), regular.get(symbol))
        except Exception as e:
            logger.debug(f'[Alpaca] {symbol} 解析失败: {e}')
            continue
        if quote:
            result[symbol] = quote
    return result
