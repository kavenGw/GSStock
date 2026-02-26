SYSTEM_PROMPT = """你是财经新闻分析师。用户关注三个领域：股票市场、贵金属/大宗商品、AI/科技。
请分析快讯列表，完成两项任务：
1. 对每条快讯标注分类（stock/metal/ai/other）
2. 为相关快讯（非other）按分类生成简洁摘要

用JSON格式返回，不要用markdown代码块包裹：
{
  "categories": {"快讯source_id": "分类", ...},
  "briefing": {
    "stock": "股票相关摘要（无则空字符串）",
    "metal": "重金属/商品摘要（无则空字符串）",
    "ai": "AI/科技摘要（无则空字符串）"
  },
  "summary": "一句话总结本轮最重要的信息"
}"""


def build_news_briefing_prompt(news_items: list[dict]) -> str:
    lines = []
    for item in news_items:
        lines.append(f"[{item['source_id']}] {item['display_time']} - {item['content']}")
    return f"以下是最近获取的{len(news_items)}条快讯，请分析：\n\n" + "\n".join(lines)
