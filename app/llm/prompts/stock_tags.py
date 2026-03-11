"""股票标签生成 prompts"""

TAGS_SYSTEM_PROMPT = """你是股票分析助手。根据给定的股票代码和名称，生成一组关联关键词标签。
标签应包括：公司全称、简称、核心产品/品牌、所属行业、概念板块、英文名（如有）。
标签用于匹配新闻内容，应尽量覆盖该公司可能出现在新闻中的各种提法。

要求：
- 返回严格的JSON数组，每个元素是一个关键词字符串
- 标签数量5-15个，优先覆盖常见提法
- 不要包含过于宽泛的词（如"科技"、"公司"）
- 只返回JSON数组，不要其他文字"""


def build_tags_prompt(stock_code: str, stock_name: str) -> str:
    return f"请为以下股票生成关联关键词标签：\n股票代码：{stock_code}\n股票名称：{stock_name}"


def build_batch_tags_prompt(stocks: list[dict]) -> str:
    """批量生成标签的prompt，每个stock含code和name"""
    lines = []
    for i, s in enumerate(stocks):
        lines.append(f"[{i}] {s['code']} {s['name']}")
    return (
        f"请为以下{len(stocks)}只股票分别生成关联关键词标签。\n"
        f"返回JSON数组，每个元素格式：{{\"index\": 序号, \"tags\": [\"标签1\", \"标签2\", ...]}}\n\n"
        + "\n".join(lines)
    )
