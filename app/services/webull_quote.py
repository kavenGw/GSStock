"""Webull 公开行情 — 美股盘前/盘后/夜盘报价（无需 API key）

session 一律由调用方按 TradingCalendarService.get_us_session() 给定。

例外：夜盘（overnight）时段额外以 Webull 自报的 overnight 字段为准入闸——
该字段非 1 时 pPrice 是冻结的盘后陈价（2026-09-17 实测），不予采用。
盘前/盘后不受此闸影响。
"""
import logging
from concurrent.futures import ThreadPoolExecutor

import requests

logger = logging.getLogger(__name__)

SEARCH_URL = 'https://quotes-gw.webullfintech.com/api/search/pc/tickers'
QUOTE_URL = 'https://quotes-gw.webullfintech.com/api/stock/tickerRealTime/getQuote'
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
           'Accept': 'application/json'}
US_REGION_ID = 6
TIMEOUT = 5

_ticker_ids = {}


def resolve_ticker_id(symbol: str) -> int | None:
    """symbol → Webull tickerId，进程内永久缓存（tickerId 稳定不变，查无结果也缓存 None 避免重复请求；
    网络异常不缓存，留给下次调用重试）"""
    if symbol in _ticker_ids:
        return _ticker_ids[symbol]
    try:
        resp = requests.get(SEARCH_URL,
                            params={'keyword': symbol, 'pageIndex': 1, 'pageSize': 10},
                            headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()
        for item in (resp.json().get('data') or []):
            if item.get('symbol') == symbol and item.get('regionId') == US_REGION_ID:
                _ticker_ids[symbol] = item['tickerId']
                return item['tickerId']
    except Exception as e:
        logger.debug(f'[Webull] {symbol} tickerId 解析失败: {e}')
        return None
    _ticker_ids[symbol] = None
    return None


def _is_overnight_flag(value) -> bool:
    """Webull 的 overnight 字段可能是 int / bool / str，统一判真"""
    return str(value).strip().lower() in ('1', 'true')


def _fetch_quote(ticker_id: int) -> dict:
    resp = requests.get(QUOTE_URL,
                        params={'tickerId': ticker_id, 'includeSecu': 1, 'includeQuote': 1},
                        headers=HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json() or {}


def parse_quote(raw: dict, session: str) -> dict | None:
    """pPrice/pChRatio → 扩展时段报价；pChRatio 是小数比率，×100 转百分比"""
    price = raw.get('pPrice')
    if price in (None, ''):
        return None
    ratio = raw.get('pChRatio')
    return {
        'session': session,
        'price': round(float(price), 2),
        'change_pct': round(float(ratio) * 100, 2) if ratio not in (None, '') else 0.0,
        'time': raw.get('tradeTime'),
        'source': 'webull',
    }


def get_extended_quotes(symbols: list, session: str) -> dict:
    """批量取扩展时段报价 {symbol: quote}；取不到的 symbol 直接缺席"""
    if not symbols or not session:
        return {}

    def fetch_one(symbol: str) -> tuple:
        try:
            ticker_id = resolve_ticker_id(symbol)
            if ticker_id is None:
                return symbol, None
            raw = _fetch_quote(ticker_id)
            quote = parse_quote(raw, session)
            if quote and session == 'overnight' and not _is_overnight_flag(raw.get('overnight')):
                logger.debug(f'[Webull] {symbol} 时钟判夜盘但 overnight=0，pPrice 视为盘后陈价不采用')
                return symbol, None
            return symbol, quote
        except Exception as e:
            logger.debug(f'[Webull] {symbol} 取价失败: {e}')
            return symbol, None

    result = {}
    with ThreadPoolExecutor(max_workers=3) as executor:
        for symbol, quote in executor.map(fetch_one, symbols):
            if quote:
                result[symbol] = quote
    return result
