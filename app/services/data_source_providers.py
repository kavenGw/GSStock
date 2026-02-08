"""数据源提供器

封装多个数据源API，为不同市场提供负载均衡支持。

支持的数据源:
- A股: 东方财富(eastmoney), 新浪财经(sina), 腾讯财经(tencent), yfinance
- 美股: yfinance, Alpha Vantage, Finnhub, Twelve Data
- 港股: yfinance, Alpha Vantage, Finnhub
- 韩股/台股: yfinance
"""
import os
import logging
import requests
from datetime import datetime, date, timedelta
from typing import Optional
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)


class DataSourceProvider(ABC):
    """数据源提供器基类"""

    name: str = "base"
    market: str = "ALL"  # A, US, HK, KR, TW, ALL

    @abstractmethod
    def get_realtime_price(self, symbol: str) -> Optional[dict]:
        """获取实时价格"""
        pass

    @abstractmethod
    def get_historical_data(self, symbol: str, days: int) -> Optional[dict]:
        """获取历史K线数据"""
        pass

    def is_available(self) -> bool:
        """检查数据源是否可用（如API Key是否配置）"""
        return True

    def get_batch_prices(self, symbols: list) -> dict:
        """批量获取价格（默认实现：串行调用）"""
        result = {}
        for symbol in symbols:
            try:
                data = self.get_realtime_price(symbol)
                if data:
                    result[symbol] = data
            except Exception as e:
                logger.debug(f"[{self.name}] {symbol} 获取失败: {e}")
        return result


class YFinanceProvider(DataSourceProvider):
    """Yahoo Finance 数据源"""

    name = "yfinance"
    market = "ALL"

    def __init__(self):
        self._yf = None

    @property
    def yf(self):
        if self._yf is None:
            import yfinance
            self._yf = yfinance
        return self._yf

    def get_realtime_price(self, symbol: str) -> Optional[dict]:
        try:
            ticker = self.yf.Ticker(symbol)
            hist = ticker.history(period="5d")
            if hist.empty or len(hist) < 2:
                return None

            last = hist.iloc[-1]
            prev = hist.iloc[-2]
            change = last['Close'] - prev['Close']
            change_pct = (change / prev['Close'] * 100) if prev['Close'] else 0

            return {
                'code': symbol,
                'name': symbol,
                'price': float(last['Close']),
                'change': float(change),
                'change_pct': float(change_pct),
                'volume': int(last['Volume']) if 'Volume' in last else 0,
                'high': float(last['High']),
                'low': float(last['Low']),
                'open': float(last['Open']),
                'prev_close': float(prev['Close']),
                'source': 'yfinance',
            }
        except Exception as e:
            logger.debug(f"[yfinance] {symbol} 获取失败: {e}")
            return None

    def get_historical_data(self, symbol: str, days: int) -> Optional[dict]:
        try:
            ticker = self.yf.Ticker(symbol)
            start_date = (date.today() - timedelta(days=days * 2)).isoformat()
            end_date = (date.today() + timedelta(days=1)).isoformat()
            hist = ticker.history(start=start_date, end=end_date)

            if hist.empty:
                return None

            data_points = []
            prev_close = None
            for idx, row in hist.iterrows():
                date_str = idx.strftime('%Y-%m-%d')
                close = float(row['Close'])
                change_pct = ((close - prev_close) / prev_close * 100) if prev_close else 0

                data_points.append({
                    'date': date_str,
                    'open': float(row['Open']),
                    'high': float(row['High']),
                    'low': float(row['Low']),
                    'close': close,
                    'volume': int(row['Volume']) if 'Volume' in row else 0,
                    'change_pct': round(change_pct, 2)
                })
                prev_close = close

            # 只返回最近 days 天
            data_points = data_points[-days:] if len(data_points) > days else data_points

            return {
                'stock_code': symbol,
                'stock_name': symbol,
                'data': data_points,
                'source': 'yfinance',
            }
        except Exception as e:
            logger.debug(f"[yfinance] {symbol} 历史数据获取失败: {e}")
            return None

    def get_batch_prices(self, symbols: list) -> dict:
        """并行批量获取价格"""
        result = {}

        def fetch_single(sym: str) -> tuple:
            data = self.get_realtime_price(sym)
            return sym, data

        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {executor.submit(fetch_single, s): s for s in symbols}
            for future in as_completed(futures):
                sym, data = future.result()
                if data:
                    result[sym] = data

        return result


class AlphaVantageProvider(DataSourceProvider):
    """Alpha Vantage 数据源 (免费版: 25请求/天)"""

    name = "alphavantage"
    market = "US,HK"  # 支持美股和港股

    API_BASE = "https://www.alphavantage.co/query"

    def __init__(self):
        self.api_key = os.environ.get('ALPHA_VANTAGE_API_KEY', '')

    def is_available(self) -> bool:
        return bool(self.api_key)

    def _make_request(self, params: dict) -> Optional[dict]:
        if not self.api_key:
            return None

        params['apikey'] = self.api_key
        try:
            resp = requests.get(self.API_BASE, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()

            # 检查API限制错误
            if 'Note' in data or 'Information' in data:
                logger.debug(f"[alphavantage] API限制: {data.get('Note', data.get('Information', ''))}")
                return None

            return data
        except Exception as e:
            logger.debug(f"[alphavantage] 请求失败: {e}")
            return None

    def get_realtime_price(self, symbol: str) -> Optional[dict]:
        data = self._make_request({
            'function': 'GLOBAL_QUOTE',
            'symbol': symbol
        })

        if not data or 'Global Quote' not in data:
            return None

        quote = data['Global Quote']
        if not quote:
            return None

        try:
            price = float(quote.get('05. price', 0))
            prev_close = float(quote.get('08. previous close', 0))
            change = float(quote.get('09. change', 0))
            change_pct = float(quote.get('10. change percent', '0%').rstrip('%'))

            return {
                'code': symbol,
                'name': symbol,
                'price': price,
                'change': change,
                'change_pct': change_pct,
                'volume': int(float(quote.get('06. volume', 0))),
                'high': float(quote.get('03. high', price)),
                'low': float(quote.get('04. low', price)),
                'open': float(quote.get('02. open', price)),
                'prev_close': prev_close,
                'source': 'alphavantage',
            }
        except Exception as e:
            logger.debug(f"[alphavantage] {symbol} 解析失败: {e}")
            return None

    def get_historical_data(self, symbol: str, days: int) -> Optional[dict]:
        data = self._make_request({
            'function': 'TIME_SERIES_DAILY',
            'symbol': symbol,
            'outputsize': 'compact' if days <= 100 else 'full'
        })

        if not data or 'Time Series (Daily)' not in data:
            return None

        time_series = data['Time Series (Daily)']

        data_points = []
        prev_close = None

        # 按日期排序
        dates = sorted(time_series.keys())[-days:]

        for date_str in dates:
            day_data = time_series[date_str]
            close = float(day_data['4. close'])
            change_pct = ((close - prev_close) / prev_close * 100) if prev_close else 0

            data_points.append({
                'date': date_str,
                'open': float(day_data['1. open']),
                'high': float(day_data['2. high']),
                'low': float(day_data['3. low']),
                'close': close,
                'volume': int(float(day_data['5. volume'])),
                'change_pct': round(change_pct, 2)
            })
            prev_close = close

        return {
            'stock_code': symbol,
            'stock_name': symbol,
            'data': data_points,
            'source': 'alphavantage',
        }


class FinnhubProvider(DataSourceProvider):
    """Finnhub 数据源 (免费版: 60请求/分钟)"""

    name = "finnhub"
    market = "US,HK"  # 支持美股和港股

    API_BASE = "https://finnhub.io/api/v1"

    def __init__(self):
        self.api_key = os.environ.get('FINNHUB_API_KEY', '')

    def is_available(self) -> bool:
        return bool(self.api_key)

    def _make_request(self, endpoint: str, params: dict = None) -> Optional[dict]:
        if not self.api_key:
            return None

        params = params or {}
        params['token'] = self.api_key

        try:
            resp = requests.get(f"{self.API_BASE}/{endpoint}", params=params, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.debug(f"[finnhub] 请求失败: {e}")
            return None

    def get_realtime_price(self, symbol: str) -> Optional[dict]:
        data = self._make_request('quote', {'symbol': symbol})

        if not data or data.get('c') is None:
            return None

        try:
            price = float(data.get('c', 0))  # current price
            prev_close = float(data.get('pc', 0))  # previous close
            change = float(data.get('d', 0))  # change
            change_pct = float(data.get('dp', 0))  # change percent

            return {
                'code': symbol,
                'name': symbol,
                'price': price,
                'change': change,
                'change_pct': change_pct,
                'volume': 0,  # Finnhub quote不返回volume
                'high': float(data.get('h', price)),
                'low': float(data.get('l', price)),
                'open': float(data.get('o', price)),
                'prev_close': prev_close,
                'source': 'finnhub',
            }
        except Exception as e:
            logger.debug(f"[finnhub] {symbol} 解析失败: {e}")
            return None

    def get_historical_data(self, symbol: str, days: int) -> Optional[dict]:
        # Finnhub使用Unix时间戳
        end_ts = int(datetime.now().timestamp())
        start_ts = int((datetime.now() - timedelta(days=days * 2)).timestamp())

        data = self._make_request('stock/candle', {
            'symbol': symbol,
            'resolution': 'D',
            'from': start_ts,
            'to': end_ts
        })

        if not data or data.get('s') != 'ok':
            return None

        data_points = []
        prev_close = None

        timestamps = data.get('t', [])
        opens = data.get('o', [])
        highs = data.get('h', [])
        lows = data.get('l', [])
        closes = data.get('c', [])
        volumes = data.get('v', [])

        for i in range(len(timestamps)):
            date_str = datetime.fromtimestamp(timestamps[i]).strftime('%Y-%m-%d')
            close = closes[i]
            change_pct = ((close - prev_close) / prev_close * 100) if prev_close else 0

            data_points.append({
                'date': date_str,
                'open': opens[i],
                'high': highs[i],
                'low': lows[i],
                'close': close,
                'volume': volumes[i] if i < len(volumes) else 0,
                'change_pct': round(change_pct, 2)
            })
            prev_close = close

        # 只返回最近 days 天
        data_points = data_points[-days:] if len(data_points) > days else data_points

        return {
            'stock_code': symbol,
            'stock_name': symbol,
            'data': data_points,
            'source': 'finnhub',
        }


class TwelveDataProvider(DataSourceProvider):
    """Twelve Data 数据源 (免费版: 8请求/分钟, 800请求/天)"""

    name = "twelvedata"
    market = "US,HK"  # 支持美股和港股

    API_BASE = "https://api.twelvedata.com"

    def __init__(self):
        self.api_key = os.environ.get('TWELVE_DATA_API_KEY', '')

    def is_available(self) -> bool:
        return bool(self.api_key)

    def _make_request(self, endpoint: str, params: dict = None) -> Optional[dict]:
        if not self.api_key:
            return None

        params = params or {}
        params['apikey'] = self.api_key

        try:
            resp = requests.get(f"{self.API_BASE}/{endpoint}", params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()

            if data.get('status') == 'error':
                logger.debug(f"[twelvedata] API错误: {data.get('message', '')}")
                return None

            return data
        except Exception as e:
            logger.debug(f"[twelvedata] 请求失败: {e}")
            return None

    def get_realtime_price(self, symbol: str) -> Optional[dict]:
        data = self._make_request('quote', {'symbol': symbol})

        if not data or 'close' not in data:
            return None

        try:
            price = float(data.get('close', 0))
            prev_close = float(data.get('previous_close', 0))
            change = float(data.get('change', 0))
            change_pct = float(data.get('percent_change', 0))

            return {
                'code': symbol,
                'name': data.get('name', symbol),
                'price': price,
                'change': change,
                'change_pct': change_pct,
                'volume': int(float(data.get('volume', 0))),
                'high': float(data.get('high', price)),
                'low': float(data.get('low', price)),
                'open': float(data.get('open', price)),
                'prev_close': prev_close,
                'source': 'twelvedata',
            }
        except Exception as e:
            logger.debug(f"[twelvedata] {symbol} 解析失败: {e}")
            return None

    def get_historical_data(self, symbol: str, days: int) -> Optional[dict]:
        data = self._make_request('time_series', {
            'symbol': symbol,
            'interval': '1day',
            'outputsize': days
        })

        if not data or 'values' not in data:
            return None

        data_points = []
        prev_close = None

        # Twelve Data返回倒序数据，需要反转
        values = list(reversed(data.get('values', [])))

        for item in values:
            close = float(item['close'])
            change_pct = ((close - prev_close) / prev_close * 100) if prev_close else 0

            data_points.append({
                'date': item['datetime'].split(' ')[0],  # 去掉时间部分
                'open': float(item['open']),
                'high': float(item['high']),
                'low': float(item['low']),
                'close': close,
                'volume': int(float(item.get('volume', 0))),
                'change_pct': round(change_pct, 2)
            })
            prev_close = close

        return {
            'stock_code': symbol,
            'stock_name': data.get('meta', {}).get('symbol', symbol),
            'data': data_points,
            'source': 'twelvedata',
        }


class MarketDataProvider(DataSourceProvider):
    """MarketData.app 数据源 (免费版: 100请求/天)"""

    name = "marketdata"
    market = "US"  # 仅支持美股

    API_BASE = "https://api.marketdata.app/v1"

    def __init__(self):
        self.api_key = os.environ.get('MARKETDATA_API_KEY', '')

    def is_available(self) -> bool:
        return bool(self.api_key)

    def _make_request(self, endpoint: str, params: dict = None) -> Optional[dict]:
        if not self.api_key:
            return None

        headers = {'Authorization': f'Token {self.api_key}'}
        params = params or {}

        try:
            resp = requests.get(f"{self.API_BASE}/{endpoint}",
                              params=params, headers=headers, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.debug(f"[marketdata] 请求失败: {e}")
            return None

    def get_realtime_price(self, symbol: str) -> Optional[dict]:
        data = self._make_request(f'stocks/quotes/{symbol}/')

        if not data or data.get('s') != 'ok':
            return None

        try:
            price = data.get('last', [0])[0]
            change = data.get('change', [0])[0]
            change_pct = data.get('changepct', [0])[0]

            return {
                'code': symbol,
                'name': symbol,
                'price': price,
                'change': change,
                'change_pct': change_pct * 100,  # 转为百分比
                'volume': data.get('volume', [0])[0],
                'high': data.get('high', [price])[0],
                'low': data.get('low', [price])[0],
                'open': data.get('open', [price])[0],
                'prev_close': data.get('prevClose', [0])[0],
                'source': 'marketdata',
            }
        except Exception as e:
            logger.debug(f"[marketdata] {symbol} 解析失败: {e}")
            return None

    def get_historical_data(self, symbol: str, days: int) -> Optional[dict]:
        end_date = date.today().isoformat()
        start_date = (date.today() - timedelta(days=days * 2)).isoformat()

        data = self._make_request(f'stocks/candles/D/{symbol}/', {
            'from': start_date,
            'to': end_date
        })

        if not data or data.get('s') != 'ok':
            return None

        data_points = []
        prev_close = None

        timestamps = data.get('t', [])
        opens = data.get('o', [])
        highs = data.get('h', [])
        lows = data.get('l', [])
        closes = data.get('c', [])
        volumes = data.get('v', [])

        for i in range(len(timestamps)):
            date_str = datetime.fromtimestamp(timestamps[i]).strftime('%Y-%m-%d')
            close = closes[i]
            change_pct = ((close - prev_close) / prev_close * 100) if prev_close else 0

            data_points.append({
                'date': date_str,
                'open': opens[i],
                'high': highs[i],
                'low': lows[i],
                'close': close,
                'volume': volumes[i] if i < len(volumes) else 0,
                'change_pct': round(change_pct, 2)
            })
            prev_close = close

        # 只返回最近 days 天
        data_points = data_points[-days:] if len(data_points) > days else data_points

        return {
            'stock_code': symbol,
            'stock_name': symbol,
            'data': data_points,
            'source': 'marketdata',
        }


class PolygonProvider(DataSourceProvider):
    """Polygon.io 数据源 (免费版: 5请求/分钟)"""

    name = "polygon"
    market = "US"  # 仅支持美股

    API_BASE = "https://api.polygon.io"

    def __init__(self):
        self.api_key = os.environ.get('POLYGON_API_KEY', '')

    def is_available(self) -> bool:
        return bool(self.api_key)

    def _make_request(self, endpoint: str, params: dict = None) -> Optional[dict]:
        if not self.api_key:
            return None

        params = params or {}
        params['apiKey'] = self.api_key

        try:
            resp = requests.get(f"{self.API_BASE}{endpoint}",
                              params=params, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.debug(f"[polygon] 请求失败: {e}")
            return None

    def get_realtime_price(self, symbol: str) -> Optional[dict]:
        data = self._make_request(f'/v2/aggs/ticker/{symbol}/prev')

        if not data or data.get('status') != 'OK' or not data.get('results'):
            return None

        try:
            result = data['results'][0]
            price = result.get('c', 0)  # close
            prev_open = result.get('o', 0)

            return {
                'code': symbol,
                'name': symbol,
                'price': price,
                'change': price - prev_open,
                'change_pct': ((price - prev_open) / prev_open * 100) if prev_open else 0,
                'volume': result.get('v', 0),
                'high': result.get('h', price),
                'low': result.get('l', price),
                'open': prev_open,
                'prev_close': prev_open,
                'source': 'polygon',
            }
        except Exception as e:
            logger.debug(f"[polygon] {symbol} 解析失败: {e}")
            return None

    def get_historical_data(self, symbol: str, days: int) -> Optional[dict]:
        end_date = date.today().isoformat()
        start_date = (date.today() - timedelta(days=days * 2)).isoformat()

        data = self._make_request(
            f'/v2/aggs/ticker/{symbol}/range/1/day/{start_date}/{end_date}'
        )

        if not data or data.get('status') != 'OK' or not data.get('results'):
            return None

        data_points = []
        prev_close = None

        for result in data['results']:
            date_str = datetime.fromtimestamp(result['t'] / 1000).strftime('%Y-%m-%d')
            close = result['c']
            change_pct = ((close - prev_close) / prev_close * 100) if prev_close else 0

            data_points.append({
                'date': date_str,
                'open': result['o'],
                'high': result['h'],
                'low': result['l'],
                'close': close,
                'volume': result.get('v', 0),
                'change_pct': round(change_pct, 2)
            })
            prev_close = close

        # 只返回最近 days 天
        data_points = data_points[-days:] if len(data_points) > days else data_points

        return {
            'stock_code': symbol,
            'stock_name': symbol,
            'data': data_points,
            'source': 'polygon',
        }


# 数据源注册表
DATA_SOURCE_REGISTRY = {
    # A股数据源（优先级顺序）
    'A': {
        'sources': ['sina', 'tencent', 'eastmoney'],  # 原有A股数据源在unified_stock_data中实现
        'fallback': 'yfinance'
    },
    # 美股数据源（优先级顺序）
    'US': {
        'sources': ['yfinance', 'finnhub', 'alphavantage', 'twelvedata', 'marketdata', 'polygon'],
        'fallback': 'yfinance'
    },
    # 港股数据源（优先级顺序）
    'HK': {
        'sources': ['yfinance', 'finnhub', 'alphavantage', 'twelvedata'],
        'fallback': 'yfinance'
    },
    # 韩股/台股数据源
    'KR': {
        'sources': ['yfinance'],
        'fallback': 'yfinance'
    },
    'TW': {
        'sources': ['yfinance'],
        'fallback': 'yfinance'
    },
}


class DataSourceFactory:
    """数据源工厂"""

    _instances = {}

    @classmethod
    def get_provider(cls, name: str) -> Optional[DataSourceProvider]:
        """获取数据源提供器实例"""
        if name not in cls._instances:
            provider_class = {
                'yfinance': YFinanceProvider,
                'alphavantage': AlphaVantageProvider,
                'finnhub': FinnhubProvider,
                'twelvedata': TwelveDataProvider,
                'marketdata': MarketDataProvider,
                'polygon': PolygonProvider,
            }.get(name)

            if provider_class:
                cls._instances[name] = provider_class()

        return cls._instances.get(name)

    @classmethod
    def get_available_sources(cls, market: str) -> list:
        """获取市场可用的数据源列表"""
        config = DATA_SOURCE_REGISTRY.get(market, DATA_SOURCE_REGISTRY.get('US'))
        sources = config.get('sources', ['yfinance'])

        available = []
        for source in sources:
            provider = cls.get_provider(source)
            if provider and provider.is_available():
                available.append(source)

        return available if available else [config.get('fallback', 'yfinance')]

    @classmethod
    def get_fallback_source(cls, market: str) -> str:
        """获取市场的兜底数据源"""
        config = DATA_SOURCE_REGISTRY.get(market, DATA_SOURCE_REGISTRY.get('US'))
        return config.get('fallback', 'yfinance')
