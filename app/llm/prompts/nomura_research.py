"""野村研报整理 Prompt 模板"""

NOMURA_SYSTEM_PROMPT = (
    "你是专业的金融研报分析师。根据提供的野村证券研报内容，整理关键观点。"
    "用简洁中文输出，保留关键数据和预测，不要编造信息。"
)


def build_nomura_prompt(items: list[dict]) -> str:
    parts = []
    for i, item in enumerate(items):
        lines = [f"--- 文章{i+1} ({item.get('category', '')}) ---"]
        lines.append(f"标题: {item['title']}")
        if item.get('text'):
            lines.append(item['text'][:2000])
        parts.append('\n'.join(lines))
    materials_text = '\n\n'.join(parts)

    return f"""以下是野村证券近期发布的亚洲/中国相关研报内容：

{materials_text}

请按以下结构整理（没有的项省略）：

1. **宏观经济展望**：GDP预测、通胀、就业等核心指标
2. **央行政策**：利率决议、货币政策走向
3. **市场观点**：对股市/债市/汇市的判断
4. **风险提示**：主要下行风险

合并重复信息，直接输出中文分析文本。"""
