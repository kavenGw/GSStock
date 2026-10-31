from datetime import datetime, timedelta
import logging
import re

import requests

from app.services.memory_cache import memory_cache
from app.utils.market_identifier import MarketIdentifier

logger = logging.getLogger(__name__)

TENCENT_QUOTE_URL = 'http://qt.gtimg.cn/q='
TENCENT_BATCH_SIZE = 50
HKD_CNY_SYMBOL = 'whHKDCNY'
CNY_CAP_CACHE_TYPE = 'cny_market_cap'
# 过期条目多留一段时间，供行情整批失败时降级展示
CNY_CAP_RETENTION_SECONDS = 7 * 24 * 3600


def _positive(value):
    number = float(value)
    return number if number > 0 else None


def _quote_time(value):
    digits = re.sub(r'\D', '', value)
    if len(digits) < 12:
        return None
    return f'{digits[:4]}-{digits[4:6]}-{digits[6:8]} {digits[8:10]}:{digits[10:12]}'


def _quote_code(code):
    """研究档里的裸数字港股代码（如 02476）归一为 .HK，否则会被识别成美股。"""
    normalized = code.strip().upper()
    if normalized.isdigit() and len(normalized) < 6:
        return f'{int(normalized):05d}.HK'
    return normalized


class MarketCapService:
    """获取股票市值"""

    @classmethod
    def get_cny_market_caps(cls, stock_codes: list) -> dict:
        """全公司总市值（亿元人民币）。A 股取总市值；H 股取现价×总股本后按 HKDCNY 折算。

        只有整批失败才用过期缓存；请求成功但单只缺失时，该只不返回。
        """
        quote_codes = {
            code: quote_code for code in stock_codes
            if MarketIdentifier.identify(quote_code := _quote_code(code)) in ('A', 'HK')
        }
        cached = {
            quote_code: memory_cache.get(quote_code, CNY_CAP_CACHE_TYPE)
            for quote_code in quote_codes.values()
        }
        now = datetime.now().isoformat()
        stale = [code for code, entry in cached.items() if entry is None or entry['expires_at'] <= now]

        fetched = {}
        if stale:
            try:
                fetched = cls._fetch_cny_market_caps(stale)
            except requests.RequestException as exc:
                logger.warning(f'[市值] 腾讯行情请求失败: {exc}')

        for quote_code, entry in fetched.items():
            ttl = memory_cache._calculate_ttl(quote_code)
            entry['expires_at'] = (datetime.now() + timedelta(seconds=ttl)).isoformat()
            memory_cache.set(quote_code, CNY_CAP_CACHE_TYPE, entry, ttl=CNY_CAP_RETENTION_SECONDS)

        market_caps = {}
        for code, quote_code in quote_codes.items():
            entry = cached[quote_code]
            if quote_code in stale and fetched:
                entry = fetched.get(quote_code)
            if entry:
                market_caps[code] = {key: entry[key] for key in ('market_cap', 'as_of', 'basis', 'fx')}
        quote_times = [entry['as_of'] for entry in market_caps.values() if entry['as_of']]
        return {'market_caps': market_caps, 'as_of': min(quote_times) if quote_times else None}

    @classmethod
    def _fetch_cny_market_caps(cls, quote_codes: list) -> dict:
        from app.services.unified_stock_data import _tencent_code

        symbols = {_tencent_code(code): code for code in quote_codes}
        quotes = cls._fetch_tencent_quotes([*symbols, HKD_CNY_SYMBOL])
        try:
            hkd_cny = _positive(quotes[HKD_CNY_SYMBOL][3])
        except (KeyError, IndexError, ValueError):
            hkd_cny = None

        result = {}
        for symbol, code in symbols.items():
            fields = quotes.get(symbol)
            if not fields:
                continue
            try:
                if code.endswith('.HK'):
                    if hkd_cny is None:
                        continue
                    price, shares = _positive(fields[3]), _positive(fields[69])
                    market_cap = price * shares / 1e8 * hkd_cny if price and shares else None
                    basis, fx = 'H', hkd_cny
                else:
                    market_cap = _positive(fields[45])
                    basis, fx = 'A', None
                as_of = _quote_time(fields[30])
            except (IndexError, ValueError) as exc:
                logger.debug(f'[市值] 腾讯行情解析失败 {code}: {exc}')
                continue
            if market_cap:
                result[code] = {'market_cap': market_cap, 'as_of': as_of, 'basis': basis, 'fx': fx}
        return result

    @staticmethod
    def _fetch_tencent_quotes(symbols: list) -> dict:
        quotes = {}
        for start in range(0, len(symbols), TENCENT_BATCH_SIZE):
            batch = symbols[start:start + TENCENT_BATCH_SIZE]
            response = requests.get(
                f"{TENCENT_QUOTE_URL}{','.join(batch)}", timeout=10, headers={'User-Agent': 'Mozilla/5.0'},
            )
            response.raise_for_status()
            response.encoding = 'gbk'
            for line in response.text.splitlines():
                symbol, separator, value = line.strip().rstrip(';').partition('=')
                if separator:
                    quotes[symbol.removeprefix('v_')] = value.strip('"').split('~')
        return quotes

    @classmethod
    def get_market_caps(cls, stock_codes: list) -> dict:
        """批量获取市值，返回 {code: market_cap_float}，失败返回 None"""
        result = {}
        a_share_codes = []
        foreign_codes = []

        for code in stock_codes:
            if MarketIdentifier.is_a_share(code):
                a_share_codes.append(code)
            else:
                foreign_codes.append(code)

        # A股批量获取
        for code in a_share_codes:
            try:
                result[code] = cls._get_a_share_market_cap(code)
            except Exception as e:
                logger.warning(f"[市值] A股 {code} 获取失败: {e}")
                result[code] = None

        # 美股/港股逐个获取
        for code in foreign_codes:
            try:
                result[code] = cls._get_foreign_market_cap(code)
            except Exception as e:
                logger.warning(f"[市值] {code} 获取失败: {e}")
                result[code] = None

        return result

    @classmethod
    def _get_a_share_market_cap(cls, code: str) -> float | None:
        """A股市值 — akshare"""
        import akshare as ak
        info = ak.stock_individual_info_em(symbol=code)
        for _, row in info.iterrows():
            if row['item'] == '总市值':
                return float(row['value'])
        return None

    @classmethod
    def _get_foreign_market_cap(cls, code: str) -> float | None:
        """美股/港股市值 — yfinance"""
        import yfinance as yf
        yf_code = MarketIdentifier.to_yfinance(code)
        ticker = yf.Ticker(yf_code)
        info = ticker.info
        return info.get('marketCap')
