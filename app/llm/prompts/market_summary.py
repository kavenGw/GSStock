"""市场总结 Prompt"""

SYSTEM_PROMPT = "你是财经分析师，用简洁中文总结市场动态。"

def build_market_summary_prompt(market_data: dict) -> str:
    """每日简报市场总结"""
    indices = market_data.get('indices', [])
    futures = market_data.get('futures', [])
    sectors = market_data.get('sectors', [])

    parts = []
    if indices:
        lines = [f"- {i.get('name','')}: {i.get('change_pct',0):+.2f}%" for i in indices[:5]]
        parts.append("主要指数:\n" + "\n".join(lines))
    if futures:
        lines = [f"- {f.get('name','')}: {f.get('change_pct',0):+.2f}%" for f in futures[:4]]
        parts.append("期货:\n" + "\n".join(lines))
    if sectors:
        lines = [f"- {s.get('name','')}: {s.get('change_pct',0):+.2f}%" for s in sectors[:5]]
        parts.append("热门板块:\n" + "\n".join(lines))

    data_text = "\n\n".join(parts)
    return f"""基于以下数据生成2-3句市场概况：

{data_text}

要求：简洁、客观、突出重点。返回纯文本，不要JSON。"""
