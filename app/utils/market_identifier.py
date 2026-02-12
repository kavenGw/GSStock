"""市场识别工具类

提供统一的股票市场识别和代码转换功能。
"""
import logging
import re

logger = logging.getLogger(__name__)


class MarketIdentifier:
    """统一的市场识别工具类"""

    # 指数代码模式
    INDEX_PATTERNS = [
        r'^000001\.SS$',  # 上证指数
        r'^399001\.SZ$',  # 深证成指
        r'^399006\.SZ$',  # 创业板指
        r'^000300\.SS$',  # 沪深300
        r'^\^',           # yfinance格式指数（如 ^GSPC）
    ]

    @staticmethod
    def identify(code: str) -> str | None:
        """识别市场类型

        Args:
            code: 股票代码

        Returns:
            'A' - A股 (6位纯数字)
            'US' - 美股 (字母开头，不含.HK/.TW后缀)
            'HK' - 港股 (.HK后缀)
            'TW' - 台股 (.TW后缀)
            'KR' - 韩股 (.KS后缀)
            None - 无法识别
        """
        if not code or not isinstance(code, str):
            logger.warning(f"无效的股票代码: {code}")
            return None

        code = code.strip()

        # 港股：以.HK结尾
        if code.upper().endswith('.HK'):
            return 'HK'

        # 台股：以.TW结尾
        if code.upper().endswith('.TW'):
            return 'TW'

        # 韩股：以.KS结尾
        if code.upper().endswith('.KS'):
            return 'KR'

        # 美股指数：以^开头（如 ^GSPC, ^DJI, ^IXIC, ^VIX）
        if code.startswith('^'):
            return 'US'

        # A股：6位纯数字，或数字开头带.SS/.SZ后缀
        if code.isdigit() and len(code) == 6:
            return 'A'
        if re.match(r'^\d{6}\.(SS|SZ)$', code):
            return 'A'

        # 美股：字母开头（可包含数字），不含点号或以特殊后缀结尾
        if re.match(r'^[A-Za-z]', code):
            # 排除已知的A股yfinance格式
            if code.endswith('.SS') or code.endswith('.SZ'):
                return 'A'
            return 'US'

        logger.warning(f"无法识别市场类型: {code}")
        return None

    @staticmethod
    def to_yfinance(code: str) -> str:
        """转换为yfinance格式代码

        Args:
            code: 原始股票代码

        Returns:
            yfinance格式的代码
        """
        if not code:
            return code

        # 已有后缀，直接返回
        if '.' in code or code.startswith('^'):
            return code

        market = MarketIdentifier.identify(code)
        if market == 'A':
            # 6开头：上海证券交易所 .SS
            if code.startswith('6'):
                return f"{code}.SS"
            # 0或3开头：深圳证券交易所 .SZ
            else:
                return f"{code}.SZ"

        # 美股和港股直接返回
        return code

    @staticmethod
    def is_a_share(code: str) -> bool:
        """判断是否为A股

        Args:
            code: 股票代码

        Returns:
            True if A股
        """
        return MarketIdentifier.identify(code) == 'A'

    @staticmethod
    def is_index(code: str) -> bool:
        """判断是否为指数代码

        Args:
            code: 股票代码

        Returns:
            True if 指数
        """
        if not code:
            return False

        for pattern in MarketIdentifier.INDEX_PATTERNS:
            if re.match(pattern, code):
                return True

        return False

    @staticmethod
    def is_etf(code: str) -> bool:
        """判断是否为ETF代码

        Args:
            code: 股票代码

        Returns:
            True if ETF
        """
        if not code or not code.isdigit() or len(code) != 6:
            return False

        # 上交所ETF: 51/52开头
        # 深交所ETF: 15/16开头
        return code.startswith(('51', '52', '15', '16'))
