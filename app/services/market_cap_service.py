import logging
from app.utils.market_identifier import MarketIdentifier

logger = logging.getLogger(__name__)


class MarketCapService:
    """获取股票市值"""

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
