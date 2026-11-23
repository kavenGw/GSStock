"""币安公开永续行情缓存与连续十五分钟价格窗口。"""
import logging
import math
import time
from collections import deque
from copy import deepcopy
from threading import RLock

import httpx

from app.config.binance_config import BINANCE_FUTURES_BASE_URL, PERPETUAL_MAPPINGS

logger = logging.getLogger(__name__)


def _number(value):
    number = float(value)
    if not math.isfinite(number):
        raise ValueError('non_finite_number')
    return number


class BinancePerpetualService:
    FRESH_SECONDS = 180
    WINDOW_SECONDS = 15 * 60

    def __init__(self):
        self._lock = RLock()
        self._refresh_lock = RLock()
        self._quotes = {}
        self._history = {}
        self._symbols = {}
        self._symbols_at = 0
        self._last_attempt = 0
        self._error = None

    @staticmethod
    def targets():
        from app.config.stock_codes import WATCH_CODES, BENCHMARK_CODES

        targets = []
        for item in WATCH_CODES + BENCHMARK_CODES:
            mapping = PERPETUAL_MAPPINGS.get(item['code'])
            if mapping:
                symbol, underlying_type = mapping
                targets.append({
                    'source_code': item['code'], 'name': item['name'],
                    'symbol': symbol, 'underlying_type': underlying_type,
                    'kind': '商品永续' if underlying_type == 'COMMODITY' else '股票/ETF永续',
                    'price_unit': 'HKD（quanto）' if symbol.startswith('HK') else 'USDT',
                })
        return targets

    @staticmethod
    def _get(client, endpoint):
        response = client.get(f'{BINANCE_FUTURES_BASE_URL}/fapi/v1/{endpoint}')
        response.raise_for_status()
        return response.json()

    def refresh(self):
        with self._refresh_lock:
            now = time.time()
            if now - self._last_attempt < 50:
                return
            self._last_attempt = now
            try:
                with httpx.Client(timeout=10) as client:
                    if not self._symbols_at or now - self._symbols_at >= 900:
                        info = self._get(client, 'exchangeInfo')
                        self._symbols = {s['symbol']: s for s in info['symbols']}
                        self._symbols_at = now
                    tickers = self._get(client, 'ticker/24hr')
                    marks = self._get(client, 'premiumIndex')
                if not isinstance(tickers, list) or not isinstance(marks, list):
                    raise ValueError('invalid_market_payload')
                tickers = {q['symbol']: q for q in tickers}
                marks = {q['symbol']: q for q in marks}
            except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
                with self._lock:
                    self._error = '行情不可用'
                    self._history.clear()
                logger.warning('[币安永续] 行情获取失败 error_type=%s status=%s',
                               type(exc).__name__, getattr(getattr(exc, 'response', None), 'status_code', None))
                return

            self._update_quotes(tickers, marks, now)

    def _update_quotes(self, tickers, marks, now):
        with self._lock:
            self._error = None
            for target in self.targets():
                symbol = target['symbol']
                meta = self._symbols.get(symbol, {})
                valid = (meta.get('status') == 'TRADING'
                         and meta.get('contractType') in ('PERPETUAL', 'TRADIFI_PERPETUAL')
                         and meta.get('quoteAsset') == 'USDT'
                         and meta.get('underlyingType') == target['underlying_type'])
                try:
                    if not valid:
                        raise ValueError('contract_unavailable')
                    ticker, mark = tickers[symbol], marks[symbol]
                    price = _number(ticker['lastPrice'])
                    mark_price = _number(mark['markPrice'])
                    updated_at = min(_number(ticker['closeTime']), _number(mark['time'])) / 1000
                    if price <= 0 or mark_price <= 0 or not -30 <= now - updated_at <= self.FRESH_SECONDS:
                        raise ValueError('stale_or_invalid_quote')
                    quote = {
                        'price': price, 'mark_price': mark_price,
                        'change_pct': _number(ticker['priceChangePercent']),
                        'funding_rate_pct': _number(mark['lastFundingRate']) * 100,
                        'next_funding_time': mark.get('nextFundingTime'),
                        'updated_at': updated_at, 'available': True,
                    }
                    self._record(symbol, now, price)
                    self._quotes[symbol] = quote
                except (ValueError, TypeError, KeyError):
                    self._history.pop(symbol, None)
                    if symbol in self._quotes:
                        self._quotes[symbol]['available'] = False

    def _record(self, symbol, now, price):
        history = self._history.setdefault(symbol, deque())
        if history and now - history[-1][0] > self.FRESH_SECONDS:
            history.clear()
        history.append((now, price))
        while len(history) > 1 and history[1][0] <= now - self.WINDOW_SECONDS:
            history.popleft()

    def snapshot(self):
        with self._lock:
            now = time.time()
            rows = []
            for target in self.targets():
                quote = deepcopy(self._quotes.get(target['symbol'], {}))
                age = now - quote.get('updated_at', 0)
                available = bool(quote.get('available') and not self._error
                                 and -30 <= age <= self.FRESH_SECONDS)
                row = {**target, **quote, 'available': available,
                       'status': '交易中' if available else '行情不可用', 'change_15m_pct': None}
                history = self._history.get(target['symbol'], [])
                if available and history and now - history[-1][0] <= self.FRESH_SECONDS:
                    elapsed = history[-1][0] - history[0][0]
                    if self.WINDOW_SECONDS <= elapsed <= self.WINDOW_SECONDS + 90:
                        row['change_15m_pct'] = (history[-1][1] / history[0][1] - 1) * 100
                rows.append(row)
            return {'data': rows, 'error': self._error}


binance_perpetual_service = BinancePerpetualService()
