"""技术指标计算服务

基于OHLCV数据计算经典技术指标，复用 UnifiedStockDataService.get_trend_data() 数据。
纯Python实现，不依赖TA-Lib等第三方库。
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class TechnicalIndicatorService:
    """技术指标计算服务"""

    # 评分权重
    SCORE_WEIGHTS = {
        'trend': 0.30,      # 趋势（均线排列）
        'bias': 0.20,       # 乖离率
        'macd': 0.15,       # MACD
        'volume': 0.15,     # 量能
        'rsi': 0.10,        # RSI
        'support': 0.10,    # 支撑/压力
    }

    @staticmethod
    def calculate_all(ohlcv_data: list) -> Optional[dict]:
        """一次性计算所有指标

        Args:
            ohlcv_data: OHLC数据列表，每项含 {date, open, high, low, close, volume}

        Returns:
            综合指标结果，数据不足返回None
        """
        if not ohlcv_data or len(ohlcv_data) < 26:
            return None

        closes = [d.get('close', 0) for d in ohlcv_data]
        volumes = [d.get('volume', 0) for d in ohlcv_data]
        highs = [d.get('high', 0) for d in ohlcv_data]
        lows = [d.get('low', 0) for d in ohlcv_data]

        macd = TechnicalIndicatorService.calculate_macd(closes)
        rsi = TechnicalIndicatorService.calculate_rsi(closes)
        bias = TechnicalIndicatorService.calculate_bias(closes)
        trend = TechnicalIndicatorService._calculate_trend(closes)
        vol = TechnicalIndicatorService._calculate_volume_indicator(volumes)
        support = TechnicalIndicatorService._calculate_support_resistance(highs, lows, closes)

        indicators = {
            'macd': macd,
            'rsi': rsi,
            'bias': bias,
            'trend': trend,
            'volume': vol,
            'support': support,
        }

        score_result = TechnicalIndicatorService.calculate_score(indicators)
        indicators['score'] = score_result['score']
        indicators['signal'] = score_result['signal']
        indicators['signal_text'] = score_result['signal_text']
        indicators['detail_scores'] = score_result['detail_scores']

        return indicators

    @staticmethod
    def calculate_macd(closes: list, fast=12, slow=26, signal=9) -> dict:
        """MACD(12,26,9)

        Returns:
            {dif, dea, histogram, signal: 金叉/死叉/零轴上金叉/零轴下死叉,
             history: [{dif, dea, histogram}]}
        """
        if len(closes) < slow + signal:
            return {'dif': 0, 'dea': 0, 'histogram': 0, 'signal': '数据不足', 'history': []}

        ema_fast = TechnicalIndicatorService._ema(closes, fast)
        ema_slow = TechnicalIndicatorService._ema(closes, slow)

        # DIF = 快线EMA - 慢线EMA
        min_len = min(len(ema_fast), len(ema_slow))
        offset_fast = len(ema_fast) - min_len
        offset_slow = len(ema_slow) - min_len
        dif_series = [ema_fast[offset_fast + i] - ema_slow[offset_slow + i] for i in range(min_len)]

        # DEA = DIF的EMA
        dea_series = TechnicalIndicatorService._ema(dif_series, signal)

        # 柱状图
        offset_dif = len(dif_series) - len(dea_series)
        hist_series = [dif_series[offset_dif + i] - dea_series[i] for i in range(len(dea_series))]

        dif = dif_series[-1] if dif_series else 0
        dea = dea_series[-1] if dea_series else 0
        histogram = hist_series[-1] if hist_series else 0

        # 判断信号
        macd_signal = '中性'
        if len(hist_series) >= 2:
            prev_hist = hist_series[-2]
            curr_hist = hist_series[-1]
            prev_dif = dif_series[offset_dif + len(dea_series) - 2] if len(dea_series) >= 2 else 0
            prev_dea = dea_series[-2] if len(dea_series) >= 2 else 0

            if prev_dif <= prev_dea and dif > dea:
                macd_signal = '零轴上金叉' if dif > 0 else '金叉'
            elif prev_dif >= prev_dea and dif < dea:
                macd_signal = '零轴下死叉' if dif < 0 else '死叉'
            elif dif > dea:
                macd_signal = '多头'
            else:
                macd_signal = '空头'

        # 最近30根的历史数据（供副图绘制）
        history_len = min(30, len(dea_series))
        history = []
        for i in range(history_len):
            idx = len(dea_series) - history_len + i
            history.append({
                'dif': round(dif_series[offset_dif + idx], 4),
                'dea': round(dea_series[idx], 4),
                'histogram': round(hist_series[idx], 4),
            })

        return {
            'dif': round(dif, 4),
            'dea': round(dea, 4),
            'histogram': round(histogram, 4),
            'signal': macd_signal,
            'history': history,
        }

    @staticmethod
    def calculate_rsi(closes: list, periods=(6, 12, 24)) -> dict:
        """RSI多周期计算

        Returns:
            {rsi_6, rsi_12, rsi_24, status: 超买/超卖/中性,
             history: [{rsi_6, rsi_12, rsi_24}]}
        """
        result = {'status': '数据不足', 'history': []}

        rsi_series_map = {}
        for period in periods:
            series = TechnicalIndicatorService._rsi_series(closes, period)
            key = f'rsi_{period}'
            rsi_series_map[key] = series
            result[key] = round(series[-1], 2) if series else 0

        # 状态判断（基于RSI6）
        rsi6 = result.get('rsi_6', 50)
        if rsi6 > 80:
            result['status'] = '严重超买'
        elif rsi6 > 70:
            result['status'] = '超买'
        elif rsi6 < 20:
            result['status'] = '严重超卖'
        elif rsi6 < 30:
            result['status'] = '超卖'
        else:
            result['status'] = '中性'

        # 最近30根历史
        all_series = list(rsi_series_map.values())
        if all_series:
            min_series_len = min(len(s) for s in all_series)
            history_len = min(30, min_series_len)
            for i in range(history_len):
                point = {}
                for key, series in rsi_series_map.items():
                    idx = len(series) - history_len + i
                    point[key] = round(series[idx], 2)
                result['history'].append(point)

        return result

    @staticmethod
    def calculate_bias(closes: list) -> dict:
        """乖离率计算 (BIAS5, BIAS20)

        Returns:
            {bias_5, bias_20, warning: bool, warning_text}
        """
        result = {'bias_5': 0, 'bias_20': 0, 'warning': False, 'warning_text': ''}

        if len(closes) < 20:
            return result

        ma5 = sum(closes[-5:]) / 5
        ma20 = sum(closes[-20:]) / 20
        current = closes[-1]

        bias5 = ((current - ma5) / ma5) * 100 if ma5 else 0
        bias20 = ((current - ma20) / ma20) * 100 if ma20 else 0

        result['bias_5'] = round(bias5, 2)
        result['bias_20'] = round(bias20, 2)

        if bias20 > 5:
            result['warning'] = True
            result['warning_text'] = f'偏离MA20达{bias20:.1f}%，追高风险'
        elif bias20 < -5:
            result['warning'] = True
            result['warning_text'] = f'偏离MA20达{bias20:.1f}%，超跌可能反弹'

        return result

    @staticmethod
    def calculate_score(indicators: dict) -> dict:
        """综合评分(100分制)

        权重: 趋势30% + 乖离20% + MACD15% + 量能15% + RSI10% + 支撑10%

        Returns:
            {score, signal, signal_text, detail_scores}
        """
        weights = TechnicalIndicatorService.SCORE_WEIGHTS
        detail = {}

        # 趋势评分 (0-100)
        trend = indicators.get('trend', {})
        trend_state = trend.get('state', '')
        if trend_state == '多头排列':
            detail['trend'] = 90
        elif trend_state == '多头发散':
            detail['trend'] = 75
        elif trend_state == '短多长空':
            detail['trend'] = 55
        elif trend_state == '空头收敛':
            detail['trend'] = 45
        elif trend_state == '空头排列':
            detail['trend'] = 15
        else:
            detail['trend'] = 50

        # 乖离率评分 (0-100)
        bias = indicators.get('bias', {})
        bias20 = abs(bias.get('bias_20', 0))
        if bias20 < 2:
            detail['bias'] = 70  # 靠近均线，中性偏好
        elif bias20 < 4:
            detail['bias'] = 55
        elif bias20 < 6:
            detail['bias'] = 35  # 偏离较大
        else:
            detail['bias'] = 15  # 严重偏离

        # 考虑乖离方向
        bias20_raw = bias.get('bias_20', 0)
        if bias20_raw > 5:
            detail['bias'] = 20  # 过度上涨偏离
        elif bias20_raw < -5:
            detail['bias'] = 60  # 超跌可能反弹

        # MACD评分 (0-100)
        macd = indicators.get('macd', {})
        macd_signal = macd.get('signal', '')
        macd_scores = {
            '零轴上金叉': 95,
            '金叉': 80,
            '多头': 65,
            '中性': 50,
            '空头': 35,
            '死叉': 20,
            '零轴下死叉': 10,
        }
        detail['macd'] = macd_scores.get(macd_signal, 50)

        # 量能评分 (0-100)
        vol = indicators.get('volume', {})
        vol_state = vol.get('state', '')
        if vol_state == '放量上涨':
            detail['volume'] = 90
        elif vol_state == '温和放量':
            detail['volume'] = 70
        elif vol_state == '缩量整理':
            detail['volume'] = 50
        elif vol_state == '放量下跌':
            detail['volume'] = 15
        else:
            detail['volume'] = 50

        # RSI评分 (0-100)
        rsi = indicators.get('rsi', {})
        rsi6 = rsi.get('rsi_6', 50)
        if rsi6 > 80:
            detail['rsi'] = 15  # 严重超买，风险高
        elif rsi6 > 70:
            detail['rsi'] = 30
        elif rsi6 > 50:
            detail['rsi'] = 65
        elif rsi6 > 30:
            detail['rsi'] = 70  # 低位有机会
        elif rsi6 > 20:
            detail['rsi'] = 80
        else:
            detail['rsi'] = 85  # 严重超卖，反弹可能大

        # 支撑评分 (0-100)
        support = indicators.get('support', {})
        near_support = support.get('near_support', False)
        near_resistance = support.get('near_resistance', False)
        if near_support:
            detail['support'] = 75
        elif near_resistance:
            detail['support'] = 30
        else:
            detail['support'] = 50

        # 加权计算总分
        total = sum(detail[k] * weights[k] for k in weights)
        score = round(total)

        # 信号判定
        if score >= 80:
            signal, signal_text = 'STRONG_BUY', '强烈买入'
        elif score >= 60:
            signal, signal_text = 'BUY', '买入'
        elif score >= 40:
            signal, signal_text = 'HOLD', '观望'
        elif score >= 20:
            signal, signal_text = 'SELL', '卖出'
        else:
            signal, signal_text = 'STRONG_SELL', '强烈卖出'

        return {
            'score': score,
            'signal': signal,
            'signal_text': signal_text,
            'detail_scores': detail,
        }

    # ---- 内部计算方法 ----

    @staticmethod
    def _ema(data: list, period: int) -> list:
        """指数移动平均线"""
        if len(data) < period:
            return []
        multiplier = 2 / (period + 1)
        ema_values = [sum(data[:period]) / period]
        for i in range(period, len(data)):
            ema_values.append(data[i] * multiplier + ema_values[-1] * (1 - multiplier))
        return ema_values

    @staticmethod
    def _sma(data: list, period: int) -> list:
        """简单移动平均线"""
        if len(data) < period:
            return []
        return [sum(data[i - period:i]) / period for i in range(period, len(data) + 1)]

    @staticmethod
    def _rsi_series(closes: list, period: int) -> list:
        """计算RSI序列"""
        if len(closes) < period + 1:
            return []

        deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
        gains = [max(d, 0) for d in deltas]
        losses = [abs(min(d, 0)) for d in deltas]

        avg_gain = sum(gains[:period]) / period
        avg_loss = sum(losses[:period]) / period

        rsi_values = []
        if avg_loss == 0:
            rsi_values.append(100.0)
        else:
            rs = avg_gain / avg_loss
            rsi_values.append(100 - (100 / (1 + rs)))

        for i in range(period, len(deltas)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period
            if avg_loss == 0:
                rsi_values.append(100.0)
            else:
                rs = avg_gain / avg_loss
                rsi_values.append(100 - (100 / (1 + rs)))

        return rsi_values

    @staticmethod
    def _calculate_trend(closes: list) -> dict:
        """均线趋势分析"""
        result = {'state': '数据不足', 'ma5': 0, 'ma20': 0, 'ma60': 0}
        if len(closes) < 60:
            if len(closes) >= 20:
                ma5 = sum(closes[-5:]) / 5
                ma20 = sum(closes[-20:]) / 20
                result['ma5'] = round(ma5, 2)
                result['ma20'] = round(ma20, 2)
                result['state'] = '多头排列' if ma5 > ma20 else '空头排列'
            return result

        ma5 = sum(closes[-5:]) / 5
        ma20 = sum(closes[-20:]) / 20
        ma60 = sum(closes[-60:]) / 60

        result['ma5'] = round(ma5, 2)
        result['ma20'] = round(ma20, 2)
        result['ma60'] = round(ma60, 2)

        if ma5 > ma20 > ma60:
            result['state'] = '多头排列'
        elif ma5 > ma20 and ma20 < ma60:
            result['state'] = '多头发散'
        elif ma5 > ma20:
            result['state'] = '短多长空'
        elif ma5 < ma20 and ma20 > ma60:
            result['state'] = '空头收敛'
        elif ma5 < ma20 < ma60:
            result['state'] = '空头排列'
        else:
            result['state'] = '震荡'

        return result

    @staticmethod
    def _calculate_volume_indicator(volumes: list) -> dict:
        """量能分析"""
        result = {'ratio': 0, 'state': '数据不足'}
        if len(volumes) < 20:
            return result

        recent_5 = volumes[-5:]
        recent_20 = volumes[-20:]
        avg5 = sum(recent_5) / 5 if recent_5 else 0
        avg20 = sum(recent_20) / 20 if recent_20 else 0

        ratio = avg5 / avg20 if avg20 > 0 else 1
        result['ratio'] = round(ratio, 2)

        if ratio > 1.5:
            result['state'] = '放量上涨' if volumes[-1] > avg20 else '放量下跌'
        elif ratio > 1.1:
            result['state'] = '温和放量'
        elif ratio > 0.7:
            result['state'] = '缩量整理'
        else:
            result['state'] = '极度缩量'

        return result

    @staticmethod
    def _calculate_support_resistance(highs: list, lows: list, closes: list) -> dict:
        """支撑/阻力位分析"""
        result = {'support': 0, 'resistance': 0, 'near_support': False, 'near_resistance': False}
        if len(closes) < 20:
            return result

        recent_lows = lows[-20:]
        recent_highs = highs[-20:]
        current = closes[-1]

        support = min(recent_lows)
        resistance = max(recent_highs)

        result['support'] = round(support, 2)
        result['resistance'] = round(resistance, 2)

        price_range = resistance - support if resistance > support else 1
        result['near_support'] = (current - support) / price_range < 0.15
        result['near_resistance'] = (resistance - current) / price_range < 0.15

        return result
