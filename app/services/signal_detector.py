"""
信号检测服务 - 分析OHLC数据，识别买卖点信号
"""
import logging

logger = logging.getLogger(__name__)


class SignalDetector:
    """股票买卖点信号检测器"""

    @staticmethod
    def detect_all(ohlc_data: list) -> dict:
        """
        检测所有信号

        Args:
            ohlc_data: OHLC数据列表，每项包含 {date, open, high, low, close, volume, change_pct}

        Returns:
            dict: {buy_signals: [...], sell_signals: [...]}
        """
        if not ohlc_data or len(ohlc_data) < 5:
            logger.warning(f'[SignalDetector] 数据不足: {len(ohlc_data) if ohlc_data else 0}条')
            return {'buy_signals': [], 'sell_signals': []}

        all_signals = []

        # 缩量突破 (需要5天数据)
        if len(ohlc_data) >= 5:
            signals = SignalDetector._detect_volume_breakout(ohlc_data)
            all_signals.extend(signals)

        # 突破新高 (需要60天数据)
        if len(ohlc_data) >= 60:
            signals = SignalDetector._detect_new_high(ohlc_data)
            all_signals.extend(signals)

        # 顶部巨量 (需要20天数据)
        if len(ohlc_data) >= 20:
            signals = SignalDetector._detect_top_volume(ohlc_data)
            all_signals.extend(signals)

        # MA5突破/跌破 (需要5天数据)
        if len(ohlc_data) >= 5:
            signals = SignalDetector._detect_ma5_cross(ohlc_data)
            all_signals.extend(signals)

        # 分离买卖点
        buy_signals = [s for s in all_signals if s['type'] == 'buy']
        sell_signals = [s for s in all_signals if s['type'] == 'sell']

        logger.info(f'[SignalDetector] 检测完成: 买点{len(buy_signals)}个, 卖点{len(sell_signals)}个')

        return {'buy_signals': buy_signals, 'sell_signals': sell_signals}

    @staticmethod
    def _get_close(item: dict) -> float:
        """获取收盘价，兼容 close 和 price 字段"""
        return item.get('close') or item.get('price') or 0

    @staticmethod
    def _get_high(item: dict) -> float:
        """获取最高价，兼容 high 和 close/price 字段"""
        return item.get('high') or item.get('close') or item.get('price') or 0

    @staticmethod
    def _detect_volume_breakout(ohlc_data: list) -> list:
        """缩量突破信号检测"""
        signals = []

        for i in range(4, len(ohlc_data)):
            # 检查前3天是否缩量下跌
            shrinking = True
            shrink_days = 0

            for j in range(i - 3, i):
                prev = ohlc_data[j - 1]
                curr = ohlc_data[j]
                curr_vol = curr.get('volume') or 0
                prev_vol = prev.get('volume') or 0
                curr_close = SignalDetector._get_close(curr)
                prev_close = SignalDetector._get_close(prev)
                if curr_vol >= prev_vol or curr_close >= prev_close:
                    shrinking = False
                    break
                shrink_days += 1

            if shrinking and shrink_days >= 3:
                # 检查当日是否放量上涨
                volumes = [(ohlc_data[k].get('volume') or 0) for k in range(i - 3, i)]
                avg_volume = sum(volumes) / len(volumes) if volumes else 0
                curr_volume = ohlc_data[i].get('volume') or 0
                volume_ratio = curr_volume / avg_volume if avg_volume > 0 else 0

                today_close = SignalDetector._get_close(ohlc_data[i])
                prev_day_close = SignalDetector._get_close(ohlc_data[i - 1])
                if volume_ratio >= 1.5 and today_close > prev_day_close:
                    signals.append({
                        'index': i,
                        'type': 'buy',
                        'name': '缩量突破',
                        'date': ohlc_data[i].get('date', ''),
                        'description': f'连续{shrink_days}天缩量下跌后放量上涨，放量倍数{volume_ratio:.1f}倍'
                    })

        return signals

    @staticmethod
    def _detect_new_high(ohlc_data: list, lookback: int = 60) -> list:
        """突破历史新高信号检测"""
        signals = []

        for i in range(lookback, len(ohlc_data)):
            historical_high = max(SignalDetector._get_high(d) for d in ohlc_data[i - lookback:i])
            curr_close = SignalDetector._get_close(ohlc_data[i])

            if curr_close > historical_high:
                signals.append({
                    'index': i,
                    'type': 'buy',
                    'name': '突破历史新高',
                    'date': ohlc_data[i].get('date', ''),
                    'description': f'突破{lookback}日新高，前高{historical_high:.2f}，现价{curr_close:.2f}'
                })

        return signals

    @staticmethod
    def _detect_top_volume(ohlc_data: list, lookback: int = 20) -> list:
        """顶部巨量信号检测"""
        signals = []

        for i in range(lookback, len(ohlc_data)):
            volumes = [(d.get('volume') or 0) for d in ohlc_data[i - lookback:i]]
            avg_volume = sum(volumes) / len(volumes) if volumes else 0
            curr_volume = ohlc_data[i].get('volume') or 0
            volume_ratio = curr_volume / avg_volume if avg_volume > 0 else 0

            # 检查是否在近期高位
            recent_high = max(SignalDetector._get_high(d) for d in ohlc_data[i - lookback:i + 1])
            curr_high = SignalDetector._get_high(ohlc_data[i])
            is_near_top = curr_high >= recent_high * 0.95

            if volume_ratio >= 3 and is_near_top:
                signals.append({
                    'index': i,
                    'type': 'sell',
                    'name': '顶部巨量',
                    'date': ohlc_data[i].get('date', ''),
                    'description': f'成交量为{lookback}日均量的{volume_ratio:.1f}倍，处于近期高位'
                })

        return signals

    @staticmethod
    def _detect_ma5_cross(ohlc_data: list) -> list:
        """均线突破/跌破信号检测"""
        signals = []

        # 计算MA5
        ma5 = []
        for i in range(len(ohlc_data)):
            if i < 4:
                ma5.append(None)
            else:
                avg = sum(SignalDetector._get_close(d) for d in ohlc_data[i - 4:i + 1]) / 5
                ma5.append(avg)

        for i in range(1, len(ohlc_data)):
            if ma5[i] is None or ma5[i - 1] is None:
                continue

            prev_close = SignalDetector._get_close(ohlc_data[i - 1])
            curr_close = SignalDetector._get_close(ohlc_data[i])
            prev_above_ma = prev_close > ma5[i - 1]
            curr_above_ma = curr_close > ma5[i]

            if not prev_above_ma and curr_above_ma:
                signals.append({
                    'index': i,
                    'type': 'buy',
                    'name': '突破5日均线',
                    'date': ohlc_data[i].get('date', ''),
                    'description': f'股价从{prev_close:.2f}突破至{curr_close:.2f}，均线值{ma5[i]:.2f}'
                })
            elif prev_above_ma and not curr_above_ma:
                signals.append({
                    'index': i,
                    'type': 'sell',
                    'name': '跌破5日均线',
                    'date': ohlc_data[i].get('date', ''),
                    'description': f'股价从{prev_close:.2f}跌至{curr_close:.2f}，均线值{ma5[i]:.2f}'
                })

        return signals
