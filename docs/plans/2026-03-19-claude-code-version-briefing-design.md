# 每日简报增加 Claude Code 版本更新介绍

## 概述

在每日 Slack 简报推送中新增 Claude Code 版本更新模块。从 GitHub Releases (`anthropics/claude-code`) 自动抓取自上次推送以来的新版本，通过 GLM Flash 生成中文摘要，嵌入简报消息。

## 数据获取层

### ClaudeCodeVersionService

新建 `app/services/claude_code_version.py`：

```
ClaudeCodeVersionService
├── get_new_releases() -> list[dict]
├── _fetch_releases_from_github() -> list[dict]
├── _get_last_pushed_version() -> str | None
├── _mark_pushed_version(version: str)
└── _filter_new_releases(releases, last_version) -> list[dict]
```

**GitHub API**：`GET https://api.github.com/repos/anthropics/claude-code/releases`，取前 10 条，无需认证（公开仓库，60次/小时速率限制足够）。API 调用失败（网络错误、非200状态码、JSON解析异常）时，记录 warning 日志并返回空列表，简报继续推送其他模块。

**版本标记文件**：`data/claude_code_last_version.txt`，内容仅一行版本号（如 `v1.0.30`）。首次运行时文件不存在，只取最新 1 个版本推送（不做发布时间校验，确保首次推送能看到当前版本信息）。

**返回格式**：

```python
[{
    "version": "v1.0.30",
    "published_at": "2026-03-19",
    "body": "原始 release notes markdown"
}]
```

## GLM 摘要层

### Prompt

新建 `app/llm/prompts/claude_code_update.py`：

```python
def build_claude_code_update_prompt(releases: list[dict]) -> str
```

将版本号 + release notes 拼成 prompt，要求 GLM 生成中文摘要：
- 每个版本一段，版本号开头
- 重点提炼：新功能、重要修复、破坏性变更
- 总长度：单版本 200 字以内，多版本按 150 字/版本计算上限

### LLM 路由

使用 FLASH 层。在 `app/llm/router.py` 注册路由 `claude_code_update -> FLASH`。

### 失败降级

GLM 调用失败时，直接拼接 `版本号 + published_at` 作为纯文本输出，不阻塞简报推送。

## 简报集成层

### notification.py 变更

新增 `format_claude_code_update() -> str` 方法：
1. 调用 `ClaudeCodeVersionService.get_new_releases()`
2. 有新版本 → 调用 GLM 生成中文摘要，返回格式化字符串
3. 无新版本 → 返回 `"🤖 Claude Code 更新\nClaude Code 无版本更新"`

### Slack 消息位置

放在最末尾、"操作建议"之前：

```
...（现有模块）

🤖 Claude Code 更新
[GLM 中文摘要 或 "Claude Code 无版本更新"]

---

💡 操作建议
```

### 版本标记时机

与现有 `_mark_daily_push()` 一致，在数据收集完成后、`send_all()` 调用前标记版本。这与现有的每日推送标记模式保持一致（推送失败不回滚标记）。

### 集成位置

在 `push_daily_report()` 中，`claude_code_text` 插入到 `text_parts` 列表的 `action_suggestions` 之前（即 `watch_text` 之后）。

## 涉及文件

| 操作 | 文件 |
|------|------|
| 新建 | `app/services/claude_code_version.py` |
| 新建 | `app/llm/prompts/claude_code_update.py` |
| 修改 | `app/llm/router.py`（注册路由） |
| 修改 | `app/services/notification.py`（新增 format 方法 + 集成到 push_daily_report） |
