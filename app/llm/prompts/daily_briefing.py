"""每日简报 GLM 综合分析 Prompt"""

DAILY_BRIEFING_SYSTEM_PROMPT = (
    "你是专业的投资分析助手。根据以下市场数据和持仓信息，生成投资分析。"
    "用简洁中文回答，数据以JSON格式返回。"
)


def build_daily_briefing_prompt(all_data: dict) -> str:
    """构建每日简报综合分析 prompt

    Args:
        all_data: 包含以下 key 的字典，每个 value 为格式化后的文本字符串：
            - position_summary: 持仓概览
            - alert_signals: 预警信号
            - earnings_alerts: 财报提醒
            - pe_alerts: PE估值预警
            - watch_analysis: 盯盘分析(7d+30d)
            - indices: 指数行情
            - futures: 期货数据
            - etf_premium: ETF溢价
            - sectors: 板块涨跌
            - dram: DRAM价格
            - technical: 技术评分
    """
    sections = []
    label_map = {
        'position_summary': '持仓概览',
        'indices': '指数行情',
        'futures': '期货数据',
        'etf_premium': 'ETF溢价',
        'sectors': '板块涨跌',
        'dram': 'DRAM价格',
        'technical': '技术评分',
        'alert_signals': '预警信号',
        'earnings_alerts': '财报提醒',
        'pe_alerts': 'PE估值预警',
        'watch_analysis': '盯盘分析',
    }

    for key, label in label_map.items():
        text = all_data.get(key, '')
        if text:
            sections.append(f"【{label}】\n{text}")

    data_text = "\n\n".join(sections)

    return f"""以下是今日完整的市场数据和持仓信息：

{data_text}

请综合分析以上所有数据，返回JSON（不要markdown代码块包裹）：
{{
  "core_insights": "今日核心观点（200字以内，涵盖市场环境、持仓关注点、关键变化）",
  "action_suggestions": "操作建议（100字以内，具体的关注/操作方向）"
}}"""
