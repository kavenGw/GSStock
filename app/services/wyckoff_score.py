"""威科夫评分计算服务"""
import logging
from statistics import mean, stdev
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta
import yfinance as yf

from app.services.wyckoff_analyzer import WyckoffAnalyzer

logger = logging.getLogger(__name__)


class WyckoffScoreCalculator:
    """威科夫综合评分计算器 (0-100)"""

    # 阶段评分映射 (0-40分)
    PHASE_SCORES = {
        'accumulation': 35,  # 吸筹阶段
        'markup': 40,        # 上涨阶段
        'distribution': 15,  # 派发阶段
        'markdown': 5,       # 下跌阶段
    }

    # 事件评分映射
    EVENT_SCORES = {
        'spring': 12,      # 假跌破后回升
        'breakout': 8,     # 放量突破
        'shakeout': 8,     # 洗盘后恢复
        'utad': -10,       # 派发末端冲高
    }

    @staticmethod
    def _get_phase_score(phase: str) -> int:
        """根据阶段返回 0-40 分

        Args:
            phase: 威科夫阶段 (accumulation/markup/distribution/markdown)

        Returns:
            阶段得分 0-40
        """
        return WyckoffScoreCalculator.PHASE_SCORES.get(phase, 10)

    @staticmethod
    def _get_volume_score(volume_ratio: float) -> int:
        """根据成交量比率返回 0-15 分

        Args:
            volume_ratio: 近5日成交量 / 近20日成交量

        Returns:
            成交量得分 0-15
        """
        if volume_ratio > 1.5:
            return 15  # 显著放量
        elif volume_ratio > 1.2:
            return 12  # 温和放量
        elif volume_ratio > 0.8:
            return 8   # 成交稳定
        else:
            return 4   # 成交萎缩

    @staticmethod
    def _get_event_score(events: list) -> int:
        """根据事件列表返回 0-20 分

        Args:
            events: 威科夫事件列表 ['spring', 'breakout', ...]

        Returns:
            事件得分 0-20 (累加后限制范围)
        """
        score = 0
        for event in events:
            score += WyckoffScoreCalculator.EVENT_SCORES.get(event, 0)
        return max(0, min(20, score))

    @staticmethod
    def _calculate_relative_strength(change_pct: float, avg_change: float, std_change: float) -> float:
        """计算相对强度得分 (-15 到 +15)

        Args:
            change_pct: 股票涨跌幅
            avg_change: 分组平均涨跌幅
            std_change: 分组涨跌幅标准差

        Returns:
            相对强度得分 -15 到 +15
        """
        if std_change == 0:
            return 0

        relative_strength = (change_pct - avg_change) / std_change

        if relative_strength > 1:
            return min(relative_strength * 5, 15)
        elif relative_strength < -1:
            return max(-abs(relative_strength) * 5, -15)
        else:
            return 0

    @staticmethod
    def _normalize_score(raw_score: float) -> int:
        """归一化总分到 0-100

        原始分数范围：10-115
        归一化公式：score = max(0, min(100, (raw_score - 10) * 100 / 105))

        Args:
            raw_score: 原始评分

        Returns:
            归一化后的评分 0-100
        """
        normalized = (raw_score - 10) * 100 / 105
        return max(0, min(100, int(round(normalized))))

    @staticmethod
    def _calculate_single_score(ohlcv_data: list, change_pct: float, avg_change: float, std_change: float) -> dict:
        """计算单只股票评分

        Args:
            ohlcv_data: OHLCV 数据列表
            change_pct: 股票涨跌幅
            avg_change: 分组平均涨跌幅
            std_change: 分组涨跌幅标准差

        Returns:
            {
                'score': 75,
                'score_details': {...},
                'analysis': {...}
            }
            或数据不足时返回 {'score': None, 'status': 'insufficient'}
        """
        # 至少需要5天数据
        if len(ohlcv_data) < 5:
            return {
                'score': None,
                'status': 'insufficient',
                'score_details': None,
                'analysis': None
            }

        # 调用 WyckoffAnalyzer 获取分析结果
        analyzer = WyckoffAnalyzer()
        result = analyzer.analyze(ohlcv_data)

        # 计算各项得分
        phase_score = WyckoffScoreCalculator._get_phase_score(result.phase)
        event_score = WyckoffScoreCalculator._get_event_score(result.events)
        volume_ratio = result.details.get('volume_ratio', 1.0)
        volume_score = WyckoffScoreCalculator._get_volume_score(volume_ratio)
        relative_strength_score = WyckoffScoreCalculator._calculate_relative_strength(
            change_pct, avg_change, std_change
        )

        # 计算总分
        base_score = 25
        raw_score = phase_score + event_score + base_score + relative_strength_score + volume_score
        final_score = WyckoffScoreCalculator._normalize_score(raw_score)

        # 确定成交量趋势
        if volume_ratio > 1.2:
            volume_trend = 'increasing'
        elif volume_ratio < 0.8:
            volume_trend = 'decreasing'
        else:
            volume_trend = 'stable'

        return {
            'score': final_score,
            'status': 'success',
            'score_details': {
                'phase_score': phase_score,
                'event_score': event_score,
                'relative_strength_score': round(relative_strength_score, 1),
                'volume_score': volume_score
            },
            'analysis': {
                'phase': result.phase,
                'events': result.events,
                'support': result.support_price,
                'resistance': result.resistance_price,
                'current_price': result.current_price,
                'volume_trend': volume_trend,
                'volume_ratio': volume_ratio
            }
        }

    @staticmethod
    def _get_yf_code(code: str) -> str:
        """转换为 yfinance 代码格式"""
        # 期货代码映射
        FUTURES_YF = {
            'AU0': 'GC=F', 'GLD': 'GLD',
            'AG0': 'SI=F', 'SLV': 'SLV',
            'CU0': 'HG=F', 'HG0': 'HG=F',
            'LME_CU': 'COPA.L', 'CPER': 'CPER',
            'AL0': 'HG=F',
        }
        if code in FUTURES_YF:
            return FUTURES_YF[code]

        # 指数代码（已含后缀的直接返回）
        if '.' in code or code.startswith('^'):
            return code

        # 股票代码
        if code.startswith('6'):
            return f"{code}.SS"
        elif code.startswith(('0', '3')):
            return f"{code}.SZ"

        return code

    @staticmethod
    def _get_analysis_days(timeframe_days: int) -> int:
        """根据时间周期获取分析所需的数据天数

        Args:
            timeframe_days: 用户选择的时间周期 (7, 30, 365)

        Returns:
            分析所需的数据天数
        """
        return timeframe_days

    @staticmethod
    def _fetch_ohlcv(code: str, days: int = 120) -> list:
        """获取 OHLCV 数据

        Args:
            code: 股票/期货代码
            days: 获取天数

        Returns:
            OHLCV 数据列表
        """
        yf_code = WyckoffScoreCalculator._get_yf_code(code)

        try:
            ticker = yf.Ticker(yf_code)
            hist = ticker.history(period=f"{days + 30}d")

            if hist.empty:
                return []

            data = []
            for idx, row in hist.iterrows():
                data.append({
                    'date': idx.strftime('%Y-%m-%d'),
                    'open': float(row['Open']),
                    'high': float(row['High']),
                    'low': float(row['Low']),
                    'close': float(row['Close']),
                    'volume': int(row['Volume']) if row['Volume'] > 0 else 0,
                })

            return data[-days:] if len(data) > days else data

        except Exception as e:
            logger.error(f"获取 {code} OHLCV 数据失败: {e}")
            return []

    @staticmethod
    def _process_single_stock(code: str, change_pct: float, avg_change: float, std_change: float, analysis_days: int = 120) -> dict:
        """处理单只股票的评分计算（用于线程池）

        Args:
            code: 股票代码
            change_pct: 股票涨跌幅
            avg_change: 分组平均涨跌幅
            std_change: 分组涨跌幅标准差
            analysis_days: 分析所需数据天数
        """
        try:
            ohlcv_data = WyckoffScoreCalculator._fetch_ohlcv(code, analysis_days)
            if not ohlcv_data:
                return {
                    'code': code,
                    'score': None,
                    'status': 'failed',
                    'score_details': None,
                    'analysis': None
                }

            result = WyckoffScoreCalculator._calculate_single_score(
                ohlcv_data, change_pct, avg_change, std_change
            )
            result['code'] = code
            return result

        except Exception as e:
            logger.error(f"计算 {code} 评分失败: {e}")
            return {
                'code': code,
                'score': None,
                'status': 'failed',
                'score_details': None,
                'analysis': None
            }

    @staticmethod
    def calculate_scores(trend_data: dict, category: str, timeframe_days: int = 30) -> list:
        """计算分组内所有股票的威科夫评分

        Args:
            trend_data: FuturesService 返回的走势数据
            category: 分类标识符
            timeframe_days: 时间周期天数 (7, 30, 365)

        Returns:
            [
                {
                    'code': 'AU0',
                    'score': 75,
                    'score_details': {...},
                    'analysis': {...}
                },
                ...
            ]
        """
        if not trend_data or not trend_data.get('stocks'):
            return []

        stocks = trend_data['stocks']

        # 根据时间周期确定分析所需数据天数
        analysis_days = WyckoffScoreCalculator._get_analysis_days(timeframe_days)

        # 收集所有股票的涨跌幅
        change_pcts = []
        stock_changes = {}
        for stock in stocks:
            if not stock.get('data') or len(stock['data']) < 2:
                continue
            change_pct = stock['data'][-1].get('change_pct', 0)
            change_pcts.append(change_pct)
            stock_changes[stock['stock_code']] = change_pct

        # 计算分组平均涨跌幅和标准差
        if len(change_pcts) > 1:
            avg_change = mean(change_pcts)
            std_change = stdev(change_pcts)
        elif len(change_pcts) == 1:
            avg_change = change_pcts[0]
            std_change = 0  # 单只股票不计算相对强度
        else:
            return []

        # 并发计算评分
        results = []
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {
                executor.submit(
                    WyckoffScoreCalculator._process_single_stock,
                    code,
                    stock_changes.get(code, 0),
                    avg_change,
                    std_change,
                    analysis_days
                ): code
                for code in stock_changes.keys()
            }

            for future in as_completed(futures):
                result = future.result()
                results.append(result)

        return results
