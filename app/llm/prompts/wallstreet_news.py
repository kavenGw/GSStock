"""华尔街见闻投行观点整理 Prompt 模板"""

WALLSTREET_NEWS_SYSTEM_PROMPT = (
    "你是专业的金融信息整理师。根据提供的投行/机构观点内容，整理关键信息。"
    "用简洁中文输出，不要编造信息。"
)


def build_wallstreet_news_prompt(items: list[dict]) -> str:
    parts = []
    for i, item in enumerate(items):
        lines = [f"--- 内容{i+1} ({item['type']}) ---"]
        if item.get('title'):
            lines.append(f"标题: {item['title']}")
        lines.append(item['text'])
        parts.append('\n'.join(lines))
    materials_text = '\n\n'.join(parts)

    return f"""以下是今日华尔街见闻中与投行/机构观点相关的内容：

{materials_text}

请按以下结构整理（没有的项省略）：

1. **评级变动**：哪些机构对哪些标的做了评级调整
2. **目标价调整**：机构名 + 标的 + 新目标价
3. **重要观点**：投行对市场/行业/个股的核心看法
4. **风险提示**：机构提到的主要风险

合并重复信息，直接输出中文分析文本。"""
