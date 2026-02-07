"""估值分析服务

计算品种的综合估值评分，包含：
- 价格位置分：当前价格在历史区间的百分位
- 均线偏离分：当前价格偏离MA20的程度
"""


class ValuationService:
    """估值计算服务类"""

    @staticmethod
    def calculate_price_position(prices: list[float], lookback: int = 60) -> float:
        """计算价格位置百分位

        公式：(当前价 - N日最低) / (N日最高 - N日最低) × 100
        - 0 = 处于N日最低点
        - 100 = 处于N日最高点

        Args:
            prices: 历史价格列表，最后一个为当前价格
            lookback: 回看天数，默认60

        Returns:
            0-100的价格位置分
        """
        if not prices or len(prices) < 2:
            return 50.0

        # 使用可用数据，不超过lookback
        use_prices = prices[-lookback:] if len(prices) >= lookback else prices
        current_price = prices[-1]

        price_high = max(use_prices)
        price_low = min(use_prices)
        price_range = price_high - price_low

        if price_range <= 0:
            return 50.0

        position = (current_price - price_low) / price_range * 100
        return round(max(0, min(100, position)), 1)

    @staticmethod
    def calculate_ma_deviation(prices: list[float], ma_period: int = 20) -> float:
        """计算均线偏离分

        偏离度 = (当前价 - MA20) / MA20 × 100
        偏离分 = clamp((偏离度 + 10) / 20 × 100, 0, 100)

        说明：偏离度范围假定为[-10%, +10%]，映射到[0, 100]
        - 低于MA20 10%以上 → 0分（极度低估）
        - 高于MA20 10%以上 → 100分（极度高估）

        Args:
            prices: 历史价格列表，最后一个为当前价格
            ma_period: 均线周期，默认20

        Returns:
            0-100的均线偏离分
        """
        if not prices or len(prices) < ma_period:
            return 50.0

        current_price = prices[-1]
        ma = sum(prices[-ma_period:]) / ma_period

        if ma <= 0:
            return 50.0

        # 计算偏离度（百分比）
        deviation = (current_price - ma) / ma * 100

        # 映射到0-100：[-10%, +10%] -> [0, 100]
        score = (deviation + 10) / 20 * 100
        return round(max(0, min(100, score)), 1)

    @staticmethod
    def calculate_valuation(code: str, prices: list[float],
                            current_price: float = None) -> dict | None:
        """计算综合估值评分

        综合评分 = 价格位置分 × 0.6 + 均线偏离分 × 0.4

        Args:
            code: 品种代码（预留，可用于未来扩展PE/PB）
            prices: 历史价格列表
            current_price: 当前价格（可选，默认使用prices最后一个）

        Returns:
            估值信息字典，若数据不足返回None
            {
                'valuation_score': 0-100,  # 综合估值分
                'price_position': 0-100,   # 价格位置分
                'ma_deviation': 0-100,     # 均线偏离分
                'valuation_level': 'low'|'fair'|'high'  # 估值等级
            }
        """
        if not prices or len(prices) < 20:
            return None

        # 如果传入了current_price，替换prices最后一个
        if current_price is not None:
            prices = prices[:-1] + [current_price]

        price_position = ValuationService.calculate_price_position(prices)
        ma_deviation = ValuationService.calculate_ma_deviation(prices)

        # 综合评分：价格位置权重0.6，均线偏离权重0.4
        valuation_score = price_position * 0.6 + ma_deviation * 0.4
        valuation_score = round(valuation_score, 1)

        # 估值等级判断
        if valuation_score < 30:
            valuation_level = 'low'
        elif valuation_score > 70:
            valuation_level = 'high'
        else:
            valuation_level = 'fair'

        return {
            'valuation_score': valuation_score,
            'price_position': price_position,
            'ma_deviation': ma_deviation,
            'valuation_level': valuation_level
        }
