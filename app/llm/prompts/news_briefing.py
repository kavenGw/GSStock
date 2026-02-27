SUMMARIZE_SYSTEM_PROMPT = """你是财经新闻编辑。请将以下多条快讯整理成一段简洁的摘要（50-100字），突出最重要的信息。直接返回摘要文本，不要JSON格式。"""


def build_summarize_prompt(news_items: list[dict]) -> str:
    lines = [f"- {item['content']}" for item in news_items]
    return f"请整理以下{len(news_items)}条快讯：\n\n" + "\n".join(lines)
