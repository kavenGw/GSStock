"""持仓操作建议服务

为持仓中的每只股票生成操作建议，包括：
1. 压力区和支撑区
2. 三角形整理区识别
3. 均线信息（MA5, MA20, MA60）
"""
import logging
from typing import Optional
from statistics import mean, stdev

logger = logging.getLogger(__name__)


class PortfolioAdviceService:
    """持仓操作建议服务"""

    @staticmethod
    def calculate_advice(ohlcv_data: list) -> Optional[dict]:
        """计算单只股票的操作建议

        Args:
            ohlcv_data: OHLCV数据列表，每项含 {date, open, high, low, close, volume}
                        按日期升序排列（最早的在前）

        Returns:
            操作建议结果，数据不足返回None
        """
        if not ohlcv_data or len(ohlcv_data) < 20:
            return None

        closes = [d.get('close', 0) for d in ohlcv_data]
        highs = [d.get('high', 0) for d in ohlcv_data]
        lows = [d.get('low', 0) for d in ohlcv_data]
        volumes = [d.get('volume', 0) for d in ohlcv_data]

        current_price = closes[-1]

        # 1. 计算均线信息
        ma_info = PortfolioAdviceService._calculate_moving_averages(closes)

        # 2. 计算支撑区和压力区
        zones = PortfolioAdviceService._calculate_price_zones(
            highs, lows, closes, ma_info
        )

        # 3. 检测三角形整理形态
        triangle = PortfolioAdviceService._detect_triangle_pattern(
            highs, lows, closes, ma_info
        )

        # 4. 计算量价关系
        volume_info = PortfolioAdviceService._analyze_volume(volumes, closes)

        # 5. 生成综合建议
        advice = PortfolioAdviceService._generate_advice(
            current_price, ma_info, zones, triangle, volume_info
        )

        return {
            'current_price': round(current_price, 2),
            'ma': ma_info,
            'zones': zones,
            'triangle': triangle,
            'volume': volume_info,
            'advice': advice,
        }

    @staticmethod
    def _calculate_moving_averages(closes: list) -> dict:
        """计算均线信息"""
        result = {
            'ma5': None,
            'ma10': None,
            'ma20': None,
            'ma60': None,
            'trend': '数据不足',
            'ma_distance': None,  # MA5与MA20的距离百分比
        }

        if len(closes) < 5:
            return result

        ma5 = mean(closes[-5:])
        result['ma5'] = round(ma5, 2)

        if len(closes) >= 10:
            ma10 = mean(closes[-10:])
            result['ma10'] = round(ma10, 2)

        if len(closes) >= 20:
            ma20 = mean(closes[-20:])
            result['ma20'] = round(ma20, 2)
            # 计算MA5与MA20的距离
            result['ma_distance'] = round((ma5 - ma20) / ma20 * 100, 2)

        if len(closes) >= 60:
            ma60 = mean(closes[-60:])
            result['ma60'] = round(ma60, 2)

            # 判断趋势
            if ma5 > ma20 > ma60:
                result['trend'] = '多头排列'
            elif ma5 < ma20 < ma60:
                result['trend'] = '空头排列'
            elif ma5 > ma20 and ma20 < ma60:
                result['trend'] = '底部反转'
            elif ma5 < ma20 and ma20 > ma60:
                result['trend'] = '顶部回落'
            else:
                result['trend'] = '震荡整理'
        elif len(closes) >= 20:
            if ma5 > ma20:
                result['trend'] = '短期多头'
            else:
                result['trend'] = '短期空头'

        return result

    @staticmethod
    def _calculate_price_zones(highs: list, lows: list, closes: list,
                               ma_info: dict) -> dict:
        """计算支撑区和压力区

        支撑区：
        - 近20日最低价
        - MA20（如果在价格下方）
        - MA60（如果在价格下方）

        压力区：
        - 近20日最高价
        - MA20（如果在价格上方）
        - MA60（如果在价格上方）
        """
        result = {
            'support': [],  # 支撑位列表，按强度排序
            'resistance': [],  # 压力位列表，按强度排序
            'support_zone': None,  # 支撑区范围 {min, max}
            'resistance_zone': None,  # 压力区范围 {min, max}
            'position': None,  # 当前价格位置: 'near_support', 'near_resistance', 'middle'
        }

        current_price = closes[-1]

        # 近期高低点
        recent_20_low = min(lows[-20:]) if len(lows) >= 20 else min(lows)
        recent_20_high = max(highs[-20:]) if len(highs) >= 20 else max(highs)

        support_levels = []
        resistance_levels = []

        # 添加近期低点作为支撑
        support_levels.append({
            'price': round(recent_20_low, 2),
            'type': '近期低点',
            'strength': 3  # 1-5强度
        })

        # 添加近期高点作为压力
        resistance_levels.append({
            'price': round(recent_20_high, 2),
            'type': '近期高点',
            'strength': 3
        })

        # 均线作为支撑/压力
        ma20 = ma_info.get('ma20')
        ma60 = ma_info.get('ma60')

        if ma20:
            if ma20 < current_price:
                support_levels.append({
                    'price': ma20,
                    'type': 'MA20',
                    'strength': 4
                })
            else:
                resistance_levels.append({
                    'price': ma20,
                    'type': 'MA20',
                    'strength': 4
                })

        if ma60:
            if ma60 < current_price:
                support_levels.append({
                    'price': ma60,
                    'type': 'MA60',
                    'strength': 5
                })
            else:
                resistance_levels.append({
                    'price': ma60,
                    'type': 'MA60',
                    'strength': 5
                })

        # 检测密集成交区（简化版：近期收盘价聚集区域）
        if len(closes) >= 20:
            price_clusters = PortfolioAdviceService._find_price_clusters(
                closes[-20:], current_price
            )
            for cluster in price_clusters:
                if cluster['price'] < current_price:
                    support_levels.append({
                        'price': cluster['price'],
                        'type': '密集成交区',
                        'strength': cluster['strength']
                    })
                else:
                    resistance_levels.append({
                        'price': cluster['price'],
                        'type': '密集成交区',
                        'strength': cluster['strength']
                    })

        # 按价格排序（支撑从高到低，压力从低到高）
        support_levels = sorted(support_levels, key=lambda x: x['price'], reverse=True)
        resistance_levels = sorted(resistance_levels, key=lambda x: x['price'])

        # 取最强的支撑位和压力位作为区间
        if support_levels:
            result['support'] = support_levels[:3]  # 最多3个支撑位
            prices = [s['price'] for s in support_levels[:2]]
            if len(prices) >= 2:
                result['support_zone'] = {
                    'min': round(min(prices), 2),
                    'max': round(max(prices), 2)
                }
            elif prices:
                result['support_zone'] = {
                    'min': round(prices[0] * 0.98, 2),
                    'max': round(prices[0], 2)
                }

        if resistance_levels:
            result['resistance'] = resistance_levels[:3]  # 最多3个压力位
            prices = [r['price'] for r in resistance_levels[:2]]
            if len(prices) >= 2:
                result['resistance_zone'] = {
                    'min': round(min(prices), 2),
                    'max': round(max(prices), 2)
                }
            elif prices:
                result['resistance_zone'] = {
                    'min': round(prices[0], 2),
                    'max': round(prices[0] * 1.02, 2)
                }

        # 判断当前价格位置
        price_range = recent_20_high - recent_20_low
        if price_range > 0:
            position_pct = (current_price - recent_20_low) / price_range
            if position_pct < 0.2:
                result['position'] = 'near_support'
            elif position_pct > 0.8:
                result['position'] = 'near_resistance'
            else:
                result['position'] = 'middle'

        return result

    @staticmethod
    def _find_price_clusters(prices: list, current_price: float) -> list:
        """找出价格聚集区域"""
        if len(prices) < 5:
            return []

        # 将价格分成若干区间，找出成交密集区
        price_min = min(prices)
        price_max = max(prices)
        price_range = price_max - price_min

        if price_range == 0:
            return []

        # 分成10个区间
        bins = 10
        bin_size = price_range / bins
        counts = [0] * bins
        bin_prices = [0.0] * bins

        for p in prices:
            bin_idx = min(int((p - price_min) / bin_size), bins - 1)
            counts[bin_idx] += 1
            bin_prices[bin_idx] += p

        # 找出成交量最大的区间
        clusters = []
        avg_count = len(prices) / bins
        for i, count in enumerate(counts):
            if count > avg_count * 1.5:  # 超过平均1.5倍
                cluster_price = bin_prices[i] / count if count > 0 else 0
                if abs(cluster_price - current_price) / current_price > 0.01:  # 排除当前价格附近
                    clusters.append({
                        'price': round(cluster_price, 2),
                        'strength': min(int(count / avg_count), 5)
                    })

        return clusters

    @staticmethod
    def _detect_triangle_pattern(highs: list, lows: list, closes: list,
                                 ma_info: dict) -> dict:
        """检测三角形整理形态

        三角形特征：
        1. 高点递减
        2. 低点递增
        3. 波动率收窄
        4. 均线收敛
        """
        result = {
            'detected': False,
            'type': None,  # 'ascending' 上升三角形, 'descending' 下降三角形, 'symmetric' 对称三角形
            'convergence': None,  # 收敛程度 0-100
            'breakout_direction': None,  # 预期突破方向 'up', 'down', 'uncertain'
            'apex_distance': None,  # 距离收敛点的百分比
        }

        if len(highs) < 10:
            return result

        # 分析近10日的高点和低点趋势
        recent_highs = highs[-10:]
        recent_lows = lows[-10:]

        # 计算高点和低点的趋势
        high_trend = PortfolioAdviceService._calculate_trend_slope(recent_highs)
        low_trend = PortfolioAdviceService._calculate_trend_slope(recent_lows)

        # 计算波动率变化
        if len(closes) >= 20:
            early_volatility = stdev(closes[-20:-10]) if len(closes) >= 20 else 0
            recent_volatility = stdev(closes[-10:])
            volatility_change = (recent_volatility - early_volatility) / early_volatility if early_volatility > 0 else 0
        else:
            volatility_change = 0

        # 检查均线收敛
        ma_convergence = False
        if ma_info.get('ma5') and ma_info.get('ma20'):
            ma_distance = abs(ma_info.get('ma_distance', 100))
            if ma_distance < 2:  # MA5与MA20距离小于2%
                ma_convergence = True

        # 三角形判定
        # 上升三角形：高点基本持平，低点递增
        # 下降三角形：高点递减，低点基本持平
        # 对称三角形：高点递减，低点递增

        high_flat = abs(high_trend) < 0.005
        low_flat = abs(low_trend) < 0.005
        high_declining = high_trend < -0.005
        low_rising = low_trend > 0.005

        if high_flat and low_rising:
            result['detected'] = True
            result['type'] = 'ascending'
            result['breakout_direction'] = 'up'
        elif high_declining and low_flat:
            result['detected'] = True
            result['type'] = 'descending'
            result['breakout_direction'] = 'down'
        elif high_declining and low_rising:
            result['detected'] = True
            result['type'] = 'symmetric'
            result['breakout_direction'] = 'uncertain'

        # 如果检测到三角形，计算收敛程度
        if result['detected']:
            # 收敛程度基于波动率缩小和均线收敛
            convergence_score = 0
            if volatility_change < -0.2:  # 波动率缩小超过20%
                convergence_score += 50
            elif volatility_change < -0.1:
                convergence_score += 30
            elif volatility_change < 0:
                convergence_score += 10

            if ma_convergence:
                convergence_score += 50

            result['convergence'] = min(convergence_score, 100)

            # 计算距离收敛点的距离（简化版）
            current_range = recent_highs[-1] - recent_lows[-1]
            initial_range = recent_highs[0] - recent_lows[0]
            if initial_range > 0:
                result['apex_distance'] = round(current_range / initial_range * 100, 1)

        return result

    @staticmethod
    def _calculate_trend_slope(values: list) -> float:
        """计算趋势斜率（简单线性回归）"""
        if len(values) < 2:
            return 0.0

        n = len(values)
        x_mean = (n - 1) / 2
        y_mean = mean(values)

        numerator = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(values))
        denominator = sum((i - x_mean) ** 2 for i in range(n))

        if denominator == 0:
            return 0.0

        slope = numerator / denominator
        # 标准化斜率（相对于均值的百分比）
        return slope / y_mean if y_mean > 0 else 0.0

    @staticmethod
    def _analyze_volume(volumes: list, closes: list) -> dict:
        """分析量价关系"""
        result = {
            'trend': '数据不足',
            'ratio': None,  # 近5日成交量/近20日平均
            'price_volume_match': None,  # 量价配合情况
        }

        if len(volumes) < 20 or len(closes) < 20:
            return result

        vol_5 = mean(volumes[-5:])
        vol_20 = mean(volumes[-20:])
        ratio = vol_5 / vol_20 if vol_20 > 0 else 1.0
        result['ratio'] = round(ratio, 2)

        # 判断量能趋势
        if ratio > 1.5:
            result['trend'] = '放量'
        elif ratio > 1.1:
            result['trend'] = '温和放量'
        elif ratio > 0.7:
            result['trend'] = '缩量'
        else:
            result['trend'] = '极度缩量'

        # 量价配合判断
        price_change = (closes[-1] - closes[-5]) / closes[-5] if closes[-5] > 0 else 0
        if price_change > 0.02 and ratio > 1.2:
            result['price_volume_match'] = '放量上涨'
        elif price_change > 0.02 and ratio < 0.8:
            result['price_volume_match'] = '缩量上涨'
        elif price_change < -0.02 and ratio > 1.2:
            result['price_volume_match'] = '放量下跌'
        elif price_change < -0.02 and ratio < 0.8:
            result['price_volume_match'] = '缩量下跌'
        else:
            result['price_volume_match'] = '量价平稳'

        return result

    @staticmethod
    def _generate_advice(current_price: float, ma_info: dict, zones: dict,
                         triangle: dict, volume_info: dict) -> dict:
        """生成综合操作建议"""
        result = {
            'signal': 'watch',  # buy, sell, hold, watch
            'signal_text': '观望',
            'reason': '',
            'key_prices': [],  # 关键价位提示
        }

        reasons = []
        key_prices = []

        # 分析均线位置
        ma5 = ma_info.get('ma5')
        ma20 = ma_info.get('ma20')
        ma60 = ma_info.get('ma60')

        if ma20:
            if current_price > ma20:
                key_prices.append(f"MA20支撑: {ma20}")
            else:
                key_prices.append(f"MA20压力: {ma20}")

        if ma60:
            if current_price > ma60:
                key_prices.append(f"MA60支撑: {ma60}")
            else:
                key_prices.append(f"MA60压力: {ma60}")

        # 支撑/压力位
        if zones.get('support') and zones['support']:
            top_support = zones['support'][0]
            key_prices.append(f"支撑位: {top_support['price']} ({top_support['type']})")

        if zones.get('resistance') and zones['resistance']:
            top_resistance = zones['resistance'][0]
            key_prices.append(f"压力位: {top_resistance['price']} ({top_resistance['type']})")

        result['key_prices'] = key_prices[:4]  # 最多4个关键价位

        # 综合判断信号
        position = zones.get('position')
        trend = ma_info.get('trend', '')
        vol_match = volume_info.get('price_volume_match', '')

        # 买入信号
        if position == 'near_support' and trend in ['多头排列', '短期多头', '底部反转']:
            result['signal'] = 'buy'
            result['signal_text'] = '买入'
            reasons.append('接近支撑位')
            reasons.append(f'均线{trend}')
        elif position == 'near_support' and vol_match == '缩量下跌':
            result['signal'] = 'buy'
            result['signal_text'] = '买入'
            reasons.append('支撑位缩量企稳')

        # 卖出信号
        elif position == 'near_resistance' and trend in ['空头排列', '短期空头', '顶部回落']:
            result['signal'] = 'sell'
            result['signal_text'] = '卖出'
            reasons.append('接近压力位')
            reasons.append(f'均线{trend}')
        elif position == 'near_resistance' and vol_match == '放量下跌':
            result['signal'] = 'sell'
            result['signal_text'] = '卖出'
            reasons.append('压力位放量下跌')

        # 持有信号
        elif trend in ['多头排列', '短期多头'] and vol_match in ['放量上涨', '温和放量']:
            result['signal'] = 'hold'
            result['signal_text'] = '持有'
            reasons.append(f'均线{trend}')
            if vol_match:
                reasons.append(vol_match)

        # 三角形整理特殊处理
        if triangle.get('detected'):
            triangle_type = triangle.get('type')
            convergence = triangle.get('convergence', 0)
            if triangle_type == 'ascending':
                reasons.append(f'上升三角形整理(收敛{convergence}%)')
                if result['signal'] not in ['buy']:
                    result['signal'] = 'watch'
                    result['signal_text'] = '关注突破'
            elif triangle_type == 'descending':
                reasons.append(f'下降三角形整理(收敛{convergence}%)')
                if result['signal'] not in ['sell']:
                    result['signal'] = 'watch'
                    result['signal_text'] = '警惕下破'
            elif triangle_type == 'symmetric':
                reasons.append(f'对称三角形整理(收敛{convergence}%)')
                result['signal'] = 'watch'
                result['signal_text'] = '等待方向'

        if not reasons:
            reasons.append('无明显信号')

        result['reason'] = '，'.join(reasons)
        return result


class PortfolioAdviceBatchService:
    """批量获取持仓操作建议"""

    @staticmethod
    def get_batch_advice(stock_codes: list) -> dict:
        """批量获取持仓操作建议

        Args:
            stock_codes: 股票代码列表

        Returns:
            {
                'success': True,
                'data': {
                    'stock_code': {advice_data}
                },
                'failed': ['stock_code']
            }
        """
        from app.services.unified_stock_data import UnifiedStockDataService

        if not stock_codes:
            return {'success': True, 'data': {}, 'failed': []}

        result = {'success': True, 'data': {}, 'failed': []}

        # 获取OHLC数据（60天，用于计算MA60）
        service = UnifiedStockDataService()
        trend_result = service.get_trend_data(stock_codes, days=60)

        stocks_data = trend_result.get('stocks', [])
        stock_data_map = {s['stock_code']: s for s in stocks_data}

        for code in stock_codes:
            stock_info = stock_data_map.get(code)
            if not stock_info or not stock_info.get('data'):
                result['failed'].append(code)
                logger.warning(f"[持仓建议] {code} 无数据")
                continue

            ohlcv_data = stock_info['data']
            try:
                advice = PortfolioAdviceService.calculate_advice(ohlcv_data)
                if advice:
                    advice['stock_code'] = code
                    advice['stock_name'] = stock_info.get('stock_name', '')
                    result['data'][code] = advice
                else:
                    result['failed'].append(code)
                    logger.warning(f"[持仓建议] {code} 数据不足")
            except Exception as e:
                result['failed'].append(code)
                logger.error(f"[持仓建议] {code} 计算失败: {e}", exc_info=True)

        logger.info(f"[持仓建议] 完成: 成功{len(result['data'])}只, 失败{len(result['failed'])}只")
        return result
