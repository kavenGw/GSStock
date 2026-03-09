"""盯盘助手三维度技术分析 Prompt"""

SYSTEM_PROMPT = "你是专业的技术分析师，擅长识别趋势、关键位和市场形态。用简洁中文回答，数据以JSON格式返回。"


def build_realtime_analysis_prompt(stock_name: str, stock_code: str,
                                    intraday_data: list, current_price: float,
                                    ohlc_60d: list = None) -> str:
    data_lines = []
    for d in intraday_data[-60:]:
        data_lines.append(f"{d.get('time', '')}: {d.get('close', '')}")
    data_text = "\n".join(data_lines)

    ohlc_text = ""
    if ohlc_60d:
        ohlc_lines = []
        for d in ohlc_60d[-10:]:
            ohlc_lines.append(f"{d['date']}: O={d['open']} H={d['high']} L={d['low']} C={d['close']}")
        ohlc_text = f"\n\n近10日K线：\n" + "\n".join(ohlc_lines)

    return f"""分析 {stock_name}({stock_code}) 的当日走势，当前价格 {current_price}。

今日分时数据（最近60个点）：
{data_text}{ohlc_text}

请返回JSON（不要markdown代码块包裹）：
{{
  "support_levels": [支撑位1, 支撑位2],
  "resistance_levels": [阻力位1, 阻力位2],
  "signal": "buy或sell或hold或watch",
  "signal_text": "买入或卖出或持有或观望",
  "summary": "80字以内的走势解读和操作建议",
  "ma_levels": {{"ma5": 数值, "ma20": 数值, "ma60": 数值或null}},
  "price_range": {{"low": 建议买入下限, "high": 建议卖出上限}}
}}"""


def build_7d_analysis_prompt(stock_name: str, stock_code: str,
                              ohlc_data: list, current_price: float) -> str:
    data_lines = []
    for d in ohlc_data[-7:]:
        data_lines.append(f"{d['date']}: O={d['open']} H={d['high']} L={d['low']} C={d['close']} V={d.get('volume', 'N/A')}")
    data_text = "\n".join(data_lines)

    return f"""分析 {stock_name}({stock_code}) 的短期趋势，当前价格 {current_price}。

近7日K线数据：
{data_text}

请返回JSON（不要markdown代码块包裹）：
{{
  "support_levels": [短期支撑位1, 支撑位2],
  "resistance_levels": [短期阻力位1, 阻力位2],
  "signal": "buy或sell或hold或watch",
  "signal_text": "买入或卖出或持有或观望",
  "summary": "80字以内的短期趋势分析，含量价关系和方向判断",
  "ma_levels": {{"ma5": 数值, "ma20": 数值, "ma60": 数值或null}},
  "price_range": {{"low": 建议买入下限, "high": 建议卖出上限}}
}}"""


def build_30d_analysis_prompt(stock_name: str, stock_code: str,
                               ohlc_data: list, current_price: float) -> str:
    data_lines = []
    for d in ohlc_data[-30:]:
        data_lines.append(f"{d['date']}: O={d['open']} H={d['high']} L={d['low']} C={d['close']} V={d.get('volume', 'N/A')}")
    data_text = "\n".join(data_lines)

    return f"""分析 {stock_name}({stock_code}) 的中期趋势，当前价格 {current_price}。

近30日K线数据：
{data_text}

请返回JSON（不要markdown代码块包裹）：
{{
  "support_levels": [中期支撑位1, 支撑位2],
  "resistance_levels": [中期阻力位1, 阻力位2],
  "signal": "buy或sell或hold或watch",
  "signal_text": "买入或卖出或持有或观望",
  "summary": "100字以内的中期形态和趋势分析",
  "ma_levels": {{"ma5": 数值, "ma20": 数值, "ma60": 数值或null}},
  "price_range": {{"low": 建议买入下限, "high": 建议卖出上限}}
}}"""
