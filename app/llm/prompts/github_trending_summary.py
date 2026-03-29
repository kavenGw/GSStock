"""GitHub Trending 项目摘要 Prompt"""

GITHUB_TRENDING_SUMMARY_SYSTEM_PROMPT = (
    "你是开源项目分析助手。根据项目信息生成简洁的中文介绍。"
)


def build_github_trending_summary_prompt(repo_name: str, description: str) -> str:
    """构建 GitHub Trending 项目摘要 prompt"""
    return f"""以下是一个 GitHub 热门开源项目：

项目: {repo_name}
描述: {description or '无描述'}

请用中文一句话介绍这个项目的用途和亮点，不超过80字。
直接返回纯文本，不要JSON或markdown代码块。"""
