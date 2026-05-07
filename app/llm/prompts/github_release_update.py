"""GitHub Release 版本更新摘要 Prompt（通用，输出 JSON）"""

GITHUB_RELEASE_UPDATE_SYSTEM_PROMPT = (
    "你是技术工具更新摘要助手。根据 changelog 提炼新功能和修复，输出严格 JSON。"
)


def build_github_release_update_prompt(project_name: str, releases: list[dict]) -> str:
    """构建版本更新摘要 prompt（要求 LLM 返回 JSON）

    Args:
        project_name: 项目显示名称（如 "Claude Code"）
        releases: [{"version": "v1.0.30", "published_at": "2026-03-19", "body": "..."}]

    LLM 应返回：
        {
          "versions": [
            {
              "version": "v2.1.132",
              "date": "2026-05-06",
              "features": ["新增 `X` 环境变量", ...],
              "fixes": ["修复 Y 问题", ...]
            }
          ]
        }
    """
    parts = []
    for r in releases:
        parts.append(f"版本: {r['version']} ({r['published_at']})\n{r['body']}")
    releases_text = '\n---\n'.join(parts)

    return f"""以下是 {project_name} 的版本更新 changelog：

{releases_text}

请提炼上述更新并以 JSON 格式输出，结构如下：
{{
  "versions": [
    {{
      "version": "原始版本号，例如 v2.1.132",
      "date": "原始日期，例如 2026-05-06",
      "features": ["条目1", "条目2"],
      "fixes": ["条目1", "条目2"]
    }}
  ]
}}

要求：
- 每个原始 version 对应一项，保持原顺序
- features 包含用户可感知的新功能、增强、破坏性变更（破坏性变更在描述里点明"破坏性"）
- fixes 是 bug 修复，**全部列出，不省略**
- 文档/重构/CI/格式化/内部依赖升级**不要**列入
- 每条 ≤30 字，简洁清晰
- 关键标识符（环境变量、命令、flag、文件名）用反引号包裹，例如 `CLAUDE_CODE_SESSION_ID`
- 中文描述
- **仅返回 JSON，不要任何前后说明、不要 markdown 代码块**"""
