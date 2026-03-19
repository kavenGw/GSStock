"""GitHub Release 版本更新摘要 Prompt（通用）"""

GITHUB_RELEASE_UPDATE_SYSTEM_PROMPT = (
    "你是技术工具更新摘要助手。根据 changelog 生成简洁的中文版本更新摘要。"
)


def build_github_release_update_prompt(project_name: str, releases: list[dict]) -> str:
    """构建版本更新摘要 prompt

    Args:
        project_name: 项目显示名称（如 "Claude Code"）
        releases: [{"version": "v1.0.30", "published_at": "2026-03-19", "body": "..."}]
    """
    max_chars = 200 if len(releases) == 1 else 150 * len(releases)

    parts = []
    for r in releases:
        parts.append(f"版本: {r['version']} ({r['published_at']})\n{r['body']}")

    releases_text = '\n---\n'.join(parts)

    return f"""以下是 {project_name} 的版本更新日志：

{releases_text}

请用中文总结以上版本更新，要求：
- 每个版本一段，以版本号开头
- 重点提炼：新功能、重要修复、破坏性变更
- 总长度不超过{max_chars}字
- 直接返回纯文本，不要JSON或markdown代码块"""
