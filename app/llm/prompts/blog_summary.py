"""技术博客文章摘要 Prompt"""

BLOG_SUMMARY_SYSTEM_PROMPT = (
    "你是技术博客摘要助手。根据文章内容生成简洁的中文摘要。"
)


def build_blog_summary_prompt(title: str, content: str) -> str:
    """构建博客文章摘要 prompt"""
    if len(content) > 3000:
        content = content[:3000] + '...'

    return f"""以下是一篇技术博客文章：

标题: {title}

内容:
{content}

请用中文总结这篇文章，要求：
- 2-3句话概括核心内容和关键发现
- 总长度不超过200字
- 直接返回纯文本，不要JSON或markdown代码块"""
