"""威科夫量价分析核心算法"""
from dataclasses import dataclass
from statistics import mean, stdev


@dataclass
class AnalysisResult:
    """分析结果数据类"""
    phase: str
    events: list
    advice: str
    support_price: float
    resistance_price: float
    current_price: float
    details: dict


class WyckoffAnalyzer:
    """威科夫分析器"""

    def analyze(self, ohlcv_data: list) -> AnalysisResult:
        """分析单只股票的OHLCV数据

        Args:
            ohlcv_data: OHLCV数据列表，每项包含 date, open, high, low, close, volume
                        按日期升序排列（最早的在前）

        Returns:
            AnalysisResult 分析结果
        """
        closes = [d['close'] for d in ohlcv_data]
        highs = [d['high'] for d in ohlcv_data]
        lows = [d['low'] for d in ohlcv_data]
        volumes = [d['volume'] for d in ohlcv_data]

        # 计算技术指标
        ma20 = self._calculate_ma(closes, 20)
        ma60 = self._calculate_ma(closes, 60)
        current_price = closes[-1]

        # 计算分析详情
        details = self._calculate_details(closes, volumes, ma20, ma60)

        # 识别阶段
        phase = self._detect_phase(closes, volumes, highs, lows, ma20, ma60)

        # 检测事件
        events = self._detect_events(closes, volumes, highs, lows, phase)

        # 生成建议
        advice = self._generate_advice(phase, events)

        # 计算支撑位和阻力位
        support, resistance = self._calculate_levels(closes, lows, highs, ma20, ma60)

        return AnalysisResult(
            phase=phase,
            events=events,
            advice=advice,
            support_price=round(support, 2),
            resistance_price=round(resistance, 2),
            current_price=round(current_price, 2),
            details=details
        )

    def _calculate_ma(self, prices: list, period: int) -> float:
        """计算移动平均线"""
        if len(prices) < period:
            return mean(prices)
        return mean(prices[-period:])

    def _calculate_std(self, prices: list) -> float:
        """计算标准差"""
        if len(prices) < 2:
            return 0.0
        return stdev(prices)

    def _calculate_details(self, closes: list, volumes: list, ma20: float, ma60: float) -> dict:
        """计算分析详情"""
        current_price = closes[-1]

        # 价格位置 (0-1)
        price_high = max(closes[-60:]) if len(closes) >= 60 else max(closes)
        price_low = min(closes[-60:]) if len(closes) >= 60 else min(closes)
        price_range = price_high - price_low
        price_position = (current_price - price_low) / price_range if price_range > 0 else 0.5

        # 成交量比率
        vol_5 = mean(volumes[-5:]) if len(volumes) >= 5 else mean(volumes)
        vol_20 = mean(volumes[-20:]) if len(volumes) >= 20 else mean(volumes)
        volume_ratio = vol_5 / vol_20 if vol_20 > 0 else 1.0

        # 波动率
        recent_prices = closes[-10:] if len(closes) >= 10 else closes
        volatility = self._calculate_std(recent_prices) / ma20 if ma20 > 0 else 0

        # 近期涨跌幅
        price_5_ago = closes[-6] if len(closes) >= 6 else closes[0]
        change_5d = (current_price - price_5_ago) / price_5_ago * 100 if price_5_ago > 0 else 0

        return {
            'ma20': round(ma20, 2),
            'ma60': round(ma60, 2),
            'price_position': round(price_position, 3),
            'volume_ratio': round(volume_ratio, 2),
            'volatility': round(volatility, 4),
            'change_5d': round(change_5d, 2),
        }

    def _detect_phase(self, closes: list, volumes: list, highs: list, lows: list,
                      ma20: float, ma60: float) -> str:
        """识别威科夫阶段

        Returns: accumulation/markup/distribution/markdown
        """
        current_price = closes[-1]

        # 价格位置
        price_high = max(closes[-60:]) if len(closes) >= 60 else max(closes)
        price_low = min(closes[-60:]) if len(closes) >= 60 else min(closes)
        price_range = price_high - price_low
        price_position = (current_price - price_low) / price_range if price_range > 0 else 0.5

        # 成交量比率
        vol_5 = mean(volumes[-5:]) if len(volumes) >= 5 else mean(volumes)
        vol_20 = mean(volumes[-20:]) if len(volumes) >= 20 else mean(volumes)
        volume_ratio = vol_5 / vol_20 if vol_20 > 0 else 1.0

        # 波动率
        recent_prices = closes[-10:] if len(closes) >= 10 else closes
        volatility = self._calculate_std(recent_prices) / ma20 if ma20 > 0 else 0

        # 近5日涨幅
        price_5_ago = closes[-6] if len(closes) >= 6 else closes[0]
        change_5d = (current_price - price_5_ago) / price_5_ago * 100 if price_5_ago > 0 else 0

        # 阶段判断
        # 吸筹：低位放量，波动收窄
        if price_position < 0.3 and volume_ratio > 1.2 and volatility < 0.03:
            return 'accumulation'

        # 上涨：均线多头，价格在均线上方
        if ma20 > ma60 and current_price > ma20 and volume_ratio > 0.8:
            return 'markup'

        # 派发：高位放量但滞涨
        if price_position > 0.7 and volume_ratio > 1.2 and change_5d < 2:
            return 'distribution'

        # 下跌：其他情况
        return 'markdown'

    def _detect_events(self, closes: list, volumes: list, highs: list, lows: list,
                       phase: str) -> list:
        """检测威科夫关键事件

        Returns: 事件列表 ['spring', 'shakeout', 'breakout', 'utad']
        """
        events = []
        current_price = closes[-1]

        # 成交量指标
        vol_20 = mean(volumes[-20:]) if len(volumes) >= 20 else mean(volumes)
        current_vol = volumes[-1]

        # 前期高低点
        prev_20_low = min(lows[-21:-1]) if len(lows) >= 21 else min(lows[:-1]) if len(lows) > 1 else lows[0]
        prev_20_high = max(highs[-21:-1]) if len(highs) >= 21 else max(highs[:-1]) if len(highs) > 1 else highs[0]
        prev_60_high = max(highs[-61:-1]) if len(highs) >= 61 else max(highs[:-1]) if len(highs) > 1 else highs[0]

        # 近3日最低
        recent_3_low = min(lows[-3:]) if len(lows) >= 3 else min(lows)
        recent_3_high = max(highs[-3:]) if len(highs) >= 3 else max(highs)

        # Spring 检测（吸筹阶段）：假跌破后快速收回
        if phase == 'accumulation':
            if recent_3_low < prev_20_low and current_price > prev_20_low:
                events.append('spring')

        # Shakeout 检测：快速下跌后恢复
        if len(closes) >= 7:
            price_5_ago = closes[-6]
            price_2_ago = closes[-3]
            drop_5d = (price_5_ago - min(closes[-5:])) / price_5_ago * 100 if price_5_ago > 0 else 0
            rise_2d = (current_price - price_2_ago) / price_2_ago * 100 if price_2_ago > 0 else 0
            if drop_5d > 5 and rise_2d > 3:
                events.append('shakeout')

        # Breakout 检测：放量突破前期高点
        if current_price > prev_60_high and current_vol > vol_20 * 1.5:
            events.append('breakout')

        # UTAD 检测（派发阶段）：冲高回落
        if phase == 'distribution':
            if recent_3_high > prev_20_high and current_price < prev_20_high:
                events.append('utad')

        return events

    def _generate_advice(self, phase: str, events: list) -> str:
        """生成操作建议

        Returns: buy/hold/sell/watch
        """
        # 吸筹阶段 + spring/shakeout = 买入
        if phase == 'accumulation' and ('spring' in events or 'shakeout' in events):
            return 'buy'

        # 上涨阶段（非breakout刚发生）= 持有
        if phase == 'markup' and 'breakout' not in events:
            return 'hold'

        # 派发阶段或utad = 卖出
        if phase == 'distribution' or 'utad' in events:
            return 'sell'

        # 其他情况 = 观望
        return 'watch'

    def _calculate_levels(self, closes: list, lows: list, highs: list,
                          ma20: float, ma60: float) -> tuple:
        """计算支撑位和阻力位

        Returns: (support_price, resistance_price)
        """
        # 支撑位：近20日最低价和MA60的较小值
        low_20 = min(lows[-20:]) if len(lows) >= 20 else min(lows)
        support = min(low_20, ma60)

        # 阻力位：近20日最高价和MA20*1.05的较大值
        high_20 = max(highs[-20:]) if len(highs) >= 20 else max(highs)
        resistance = max(high_20, ma20 * 1.05)

        return support, resistance
