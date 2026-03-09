"""支撑/压力位计算工具"""
from statistics import mean


def calculate_moving_averages(closes: list) -> dict:
    """计算均线信息，返回 ma5/ma10/ma20/ma60/trend"""
    result = {'ma5': None, 'ma10': None, 'ma20': None, 'ma60': None, 'trend': '数据不足'}
    if len(closes) < 5:
        return result

    ma5 = mean(closes[-5:])
    result['ma5'] = round(ma5, 2)

    if len(closes) >= 10:
        result['ma10'] = round(mean(closes[-10:]), 2)

    ma20 = None
    if len(closes) >= 20:
        ma20 = mean(closes[-20:])
        result['ma20'] = round(ma20, 2)

    if len(closes) >= 60:
        ma60 = mean(closes[-60:])
        result['ma60'] = round(ma60, 2)
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


def calculate_support_resistance(highs: list, lows: list, closes: list) -> dict:
    """计算支撑位和压力位

    Returns:
        {'support': [价格列表, 最多3个], 'resistance': [价格列表, 最多3个]}
    """
    if len(closes) < 20:
        return {'support': [], 'resistance': []}

    current_price = closes[-1]
    ma_info = calculate_moving_averages(closes)

    support_levels = []
    resistance_levels = []

    # 近20日最低/最高点
    recent_low = min(lows[-20:])
    recent_high = max(highs[-20:])
    support_levels.append((recent_low, 3))
    resistance_levels.append((recent_high, 3))

    # 均线支撑/压力
    for key, strength in [('ma20', 4), ('ma60', 5)]:
        val = ma_info.get(key)
        if val:
            if val < current_price:
                support_levels.append((val, strength))
            else:
                resistance_levels.append((val, strength))

    # 密集成交区
    price_min, price_max = min(closes[-20:]), max(closes[-20:])
    price_range = price_max - price_min
    if price_range > 0:
        bins = 10
        bin_size = price_range / bins
        counts = [0] * bins
        bin_prices = [0.0] * bins
        for p in closes[-20:]:
            idx = min(int((p - price_min) / bin_size), bins - 1)
            counts[idx] += 1
            bin_prices[idx] += p
        avg_count = len(closes[-20:]) / bins
        for i, count in enumerate(counts):
            if count > avg_count * 1.5:
                cluster_price = round(bin_prices[i] / count, 2)
                if abs(cluster_price - current_price) / current_price > 0.01:
                    if cluster_price < current_price:
                        support_levels.append((cluster_price, min(int(count / avg_count), 5)))
                    else:
                        resistance_levels.append((cluster_price, min(int(count / avg_count), 5)))

    # 按强度排序，取前3，只返回价格
    support_levels.sort(key=lambda x: x[1], reverse=True)
    resistance_levels.sort(key=lambda x: x[1], reverse=True)

    return {
        'support': [round(s[0], 2) for s in support_levels[:3]],
        'resistance': [round(r[0], 2) for r in resistance_levels[:3]],
    }
