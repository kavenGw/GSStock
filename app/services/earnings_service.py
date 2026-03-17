"""财报数据服务 - 获取过去4个季度的营收、利润和季末股价"""
import logging
from datetime import date, datetime, timedelta

from app.utils.market_identifier import MarketIdentifier
from app.models.unified_cache import UnifiedStockCache

logger = logging.getLogger(__name__)


class QuarterlyEarningsService:

    CACHE_TYPE = 'quarterly_earnings'
    CACHE_TTL_DAYS = 7

    @classmethod
    def get_earnings(cls, stock_code: str) -> list[dict]:
        """获取过去4个季度的财报数据 + 季末股价"""
        cached = cls._get_cache(stock_code)
        if cached is not None:
            return cached

        market = MarketIdentifier.identify(stock_code)
        try:
            if market == 'A':
                financials = cls._fetch_a_share(stock_code)
            elif market in ('US', 'HK'):
                financials = cls._fetch_yfinance(stock_code)
            else:
                financials = []
        except Exception as e:
            logger.warning(f'[季度财报] {stock_code} 获取失败: {e}')
            financials = []

        if financials:
            financials = cls._attach_quarter_prices(stock_code, financials)

        cls._set_cache(stock_code, financials)
        return financials

    @classmethod
    def _fetch_a_share(cls, stock_code: str) -> list[dict]:
        """A股财报数据（akshare 东方财富单季利润表）"""
        from app.services.akshare_client import ak

        pure_code = stock_code.replace('.SS', '').replace('.SH', '').replace('.SZ', '')
        if pure_code.startswith('6'):
            symbol = f'SH{pure_code}'
        else:
            symbol = f'SZ{pure_code}'

        result = []
        try:
            df = ak.stock_profit_sheet_by_quarterly_em(symbol=symbol)
            if df is None or df.empty:
                return []

            df = df.sort_values('REPORT_DATE', ascending=False).head(4)

            for _, row in df.iterrows():
                report_date = str(row.get('REPORT_DATE', ''))[:10]
                quarter_label = cls._date_to_quarter_label(report_date)

                revenue = row.get('TOTAL_OPERATE_INCOME') or row.get('OPERATE_INCOME') or 0
                profit = row.get('NETPROFIT') or 0

                result.append({
                    'quarter': quarter_label,
                    'report_date': report_date,
                    'revenue': float(revenue) if revenue else 0,
                    'profit': float(profit) if profit else 0,
                })
        except Exception as e:
            logger.warning(f'[季度财报] A股 {stock_code} akshare获取失败: {e}')

        return result

    @classmethod
    def _fetch_yfinance(cls, stock_code: str) -> list[dict]:
        """美股/港股财报数据（yfinance）"""
        import yfinance as yf

        result = []
        try:
            yf_code = MarketIdentifier.to_yfinance(stock_code)
            ticker = yf.Ticker(yf_code)
            financials = ticker.quarterly_financials

            if financials is None or financials.empty:
                return []

            cols = list(financials.columns)[:4]

            for col_date in cols:
                col = financials[col_date]
                report_date = col_date.strftime('%Y-%m-%d') if hasattr(col_date, 'strftime') else str(col_date)[:10]
                quarter_label = cls._date_to_quarter_label(report_date)

                revenue = 0
                for key in ['Total Revenue', 'Operating Revenue']:
                    if key in col.index and col[key] and not (isinstance(col[key], float) and col[key] != col[key]):
                        revenue = float(col[key])
                        break

                profit = 0
                for key in ['Net Income', 'Net Income Common Stockholders']:
                    if key in col.index and col[key] and not (isinstance(col[key], float) and col[key] != col[key]):
                        profit = float(col[key])
                        break

                result.append({
                    'quarter': quarter_label,
                    'report_date': report_date,
                    'revenue': revenue,
                    'profit': profit,
                })
        except Exception as e:
            logger.warning(f'[季度财报] yfinance {stock_code} 获取失败: {e}')

        return result

    @classmethod
    def _attach_quarter_prices(cls, stock_code: str, financials: list) -> list:
        """附加季末股价数据"""
        from app.services.unified_stock_data import unified_stock_data_service

        try:
            trend = unified_stock_data_service.get_trend_data([stock_code], days=400)
            stocks = trend.get('stocks', [])
            ohlc_data = stocks[0]['data'] if stocks else []
        except Exception as e:
            logger.warning(f'[季度财报] {stock_code} 获取OHLC失败: {e}')
            ohlc_data = []

        if not ohlc_data:
            for item in financials:
                item.update({'price_high': None, 'price_low': None, 'price_close': None, 'price_avg': None})
            return financials

        for item in financials:
            report_date = item.get('report_date', '')
            quarter_end = cls._get_quarter_end_date(report_date)
            prices = cls._get_quarter_prices(ohlc_data, quarter_end)
            item.update(prices)

        return financials

    @classmethod
    def _get_quarter_prices(cls, ohlc_data: list, quarter_end: str) -> dict:
        """从OHLC数据中提取某季度的股价区间"""
        empty = {'price_high': None, 'price_low': None, 'price_close': None, 'price_avg': None}
        if not quarter_end or not ohlc_data:
            return empty

        try:
            end_date = datetime.strptime(quarter_end, '%Y-%m-%d').date()
            start_date = end_date - timedelta(days=95)

            quarter_data = [
                d for d in ohlc_data
                if start_date <= datetime.strptime(d['date'], '%Y-%m-%d').date() <= end_date
            ]

            if not quarter_data:
                return empty

            highs = [d['high'] for d in quarter_data]
            lows = [d['low'] for d in quarter_data]
            last_close = quarter_data[-1]['close']

            return {
                'price_high': round(max(highs), 2),
                'price_low': round(min(lows), 2),
                'price_close': round(last_close, 2),
                'price_avg': round((max(highs) + min(lows)) / 2, 2),
            }
        except Exception as e:
            logger.debug(f'[季度财报] 季末股价计算失败: {e}')
            return empty

    @staticmethod
    def _get_quarter_end_date(report_date: str) -> str:
        """从报告日期推断季度末日期"""
        try:
            dt = datetime.strptime(report_date[:10], '%Y-%m-%d')
            month = dt.month
            year = dt.year
            quarter_end_months = {1: 3, 2: 3, 3: 3, 4: 6, 5: 6, 6: 6,
                                  7: 9, 8: 9, 9: 9, 10: 12, 11: 12, 12: 12}
            end_month = quarter_end_months[month]
            if end_month == 12:
                end_date = date(year, 12, 31)
            elif end_month == 3:
                end_date = date(year, 3, 31)
            elif end_month == 6:
                end_date = date(year, 6, 30)
            else:
                end_date = date(year, 9, 30)
            return end_date.isoformat()
        except Exception:
            return ''

    @staticmethod
    def _date_to_quarter_label(report_date: str) -> str:
        """日期转季度标签：如 2025-12-31 -> Q4'25"""
        try:
            dt = datetime.strptime(report_date[:10], '%Y-%m-%d')
            q = (dt.month - 1) // 3 + 1
            return f"Q{q}'{str(dt.year)[2:]}"
        except Exception:
            return report_date[:7]

    @classmethod
    def _get_cache(cls, stock_code: str) -> list | None:
        """从DB缓存读取"""
        try:
            cached = UnifiedStockCache.get_cached_data(stock_code, cls.CACHE_TYPE)
            if cached is None:
                return None
            cache_obj = UnifiedStockCache.query.filter_by(
                stock_code=stock_code, cache_type=cls.CACHE_TYPE
            ).order_by(UnifiedStockCache.updated_at.desc()).first()
            if cache_obj and cache_obj.updated_at:
                age = (datetime.now() - cache_obj.updated_at).days
                if age <= cls.CACHE_TTL_DAYS:
                    return cached
            return None
        except Exception:
            return None

    @classmethod
    def _set_cache(cls, stock_code: str, data: list) -> None:
        """写入DB缓存"""
        try:
            UnifiedStockCache.set_cached_data(stock_code, cls.CACHE_TYPE, data)
        except Exception as e:
            logger.debug(f'[季度财报] 缓存写入失败 {stock_code}: {e}')
