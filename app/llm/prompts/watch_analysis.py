"""盯盘助手技术分析 Prompt"""

SYSTEM_PROMPT = "你是专业的技术分析师，擅长识别关键支撑位、阻力位和波动特征。用简洁中文回答，数据以JSON格式返回。"


def build_watch_analysis_prompt(stock_name: str, stock_code: str, ohlc_data: list, current_price: float) -> str:
    data_lines = []
    for d in ohlc_data[-30:]:
        data_lines.append(f"{d['date']}: O={d['open']} H={d['high']} L={d['low']} C={d['close']} V={d.get('volume', 'N/A')}")
    data_text = "\n".join(data_lines)

    return f"""分析 {stock_name}({stock_code}) 的技术面，当前价格 {current_price}。

近30日K线数据：
{data_text}

请计算并返回JSON（不要markdown代码块包裹）：
{{
  "support_levels": [支撑位1, 支撑位2],
  "resistance_levels": [阻力位1, 阻力位2],
  "volatility_threshold": 基于近期波动率的合理日内监控阈值（小数，如0.02表示2%），
  "summary": "一句话分析要点"
}}"""
