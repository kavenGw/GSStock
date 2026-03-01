"""新闻分类打分 prompts"""

CLASSIFY_SYSTEM_PROMPT = """你是新闻分析助手。对每条新闻评估重要性并提取关键词。
返回严格的JSON数组，每个元素包含:
- index: 新闻序号(从0开始)
- importance: 重要性评分1-5 (1=日常，3=值得关注，5=重大事件)
- keywords: 关键词列表(2-5个，中文)
- is_earnings: 是否为财报/业绩相关新闻(true/false)
- stock_code: 若为财报新闻，提取股票代码(A股6位数字如001309，美股字母代码如AAPL)，否则null
- report_type: 若为财报新闻，报告类型(年报/半年报/一季报/三季报/业绩预告/业绩快报)，否则null

财报新闻判断标准：内容涉及公司财报发布、营收/净利润/EPS等财务数据披露。

只返回JSON，不要其他文字。"""


def build_classify_prompt(news_items: list[dict]) -> str:
    lines = []
    for i, item in enumerate(news_items):
        lines.append(f"[{i}] {item['content']}")
    return f"请分析以下{len(news_items)}条新闻：\n\n" + "\n".join(lines)


RECOMMEND_SYSTEM_PROMPT = """你是投资者的个人新闻助手。根据用户最近关注的新闻内容，推荐3-5个新的关键词。
这些关键词应该是用户可能感兴趣但尚未设置的主题。
返回严格的JSON数组，每个元素是一个关键词字符串。只返回JSON。"""


def build_recommend_prompt(recent_contents: list[str], existing_keywords: list[str]) -> str:
    news_text = "\n".join(f"- {c}" for c in recent_contents[:30])
    existing_text = ", ".join(existing_keywords) if existing_keywords else "（无）"
    return f"用户已设置的关键词：{existing_text}\n\n最近关注的新闻：\n{news_text}\n\n请推荐新关键词。"
