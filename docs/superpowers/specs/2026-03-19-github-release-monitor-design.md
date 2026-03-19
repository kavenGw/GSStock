# GitHub Release 通用监控服务设计

## 背景

当前 `ClaudeCodeVersionService` 专门为 `anthropics/claude-code` 仓库编写，硬编码了 GitHub API URL 和版本文件路径。需要将其重构为通用服务，支持监控多个 GitHub 仓库的 release 更新，并在每日简报中推送。

初始监控仓库：
- `anthropics/claude-code` (Claude Code)
- `obra/superpowers` (Superpowers)

## 设计决策

| 决策点 | 选择 | 原因 |
|--------|------|------|
| 仓库管理方式 | 配置文件 | 修改不需要动代码，简单直接 |
| Slack 消息组织 | 每个仓库独立段落 | 各自有标题和 emoji，清晰区分 |
| GLM 摘要处理 | 统一走 GLM FLASH | 所有仓库的 release notes 都生成中文摘要 |
| LLM prompt | 共用通用模板 | 传入项目名称区分，避免维护多份 prompt |

## 架构设计

### 1. 配置模块 — `app/config/github_releases.py`

```python
GITHUB_RELEASE_REPOS = [
    {
        'key': 'claude-code',            # 版本文件命名标识
        'repo': 'anthropics/claude-code', # GitHub owner/repo
        'name': 'Claude Code',           # 显示名称
        'emoji': '🤖',                   # Slack 消息 emoji
    },
    {
        'key': 'superpowers',
        'repo': 'obra/superpowers',
        'name': 'Superpowers',
        'emoji': '⚡',
    },
]
```

版本标记文件路径：`data/github_release_{key}_last_version.txt`

### 2. 通用服务 — `app/services/github_release.py`

替代 `ClaudeCodeVersionService`，所有方法接受 `repo`/`key` 参数：

- `get_new_releases(repo, key) -> list[dict]` — 获取指定仓库的新版本
- `_fetch_releases_from_github(repo) -> list[dict]` — GitHub API 调用，URL 由 repo 拼接
- `_get_last_pushed_version(key) -> str | None` — 按 key 读取版本标记文件
- `mark_pushed_version(key, version) -> None` — 按 key 写入版本标记
- `_filter_new_releases(releases, last_version) -> list[dict]` — 不变
- `get_all_updates() -> list[dict]` — 遍历 `GITHUB_RELEASE_REPOS`，返回每个仓库的更新

`get_all_updates()` 返回格式：
```python
[
    {'config': {repo_cfg}, 'releases': [{'version': ..., 'published_at': ..., 'body': ...}]},
    ...
]
```

### 3. Prompt 通用化 — `app/llm/prompts/github_release_update.py`

替代 `claude_code_update.py`：

- system prompt 不变（"技术工具更新摘要助手"，本身已通用）
- `build_github_release_update_prompt(project_name, releases)` — 模板中项目名称由参数传入
- LLM 路由 task key：`github_release_update`（FLASH 层）

### 4. Notification 集成

`notification.py` 变更：

- `format_claude_code_update()` → `format_github_release_updates()`
- 返回值：`(texts: list[str], pushed_versions: list[tuple[key, version]])`
- 每个有更新的仓库：调用 GLM 生成摘要，失败降级为纯文本
- 有更新的仓库生成独立段落：`{emoji} {name} 更新\n{摘要内容}`
- 无更新的仓库不输出任何内容（避免多仓库时刷屏）
- `push_daily_report()` 中将每个仓库的 text 分别 append 到 `text_parts`
- 推送完成后循环调用 `mark_pushed_version(key, version)`

## 文件变更清单

| 操作 | 文件 | 说明 |
|------|------|------|
| 新建 | `app/config/github_releases.py` | 仓库配置列表 |
| 新建 | `app/services/github_release.py` | 通用 GitHub Release 服务 |
| 新建 | `app/llm/prompts/github_release_update.py` | 通用 prompt 模板 |
| 删除 | `app/services/claude_code_version.py` | 被通用服务替代 |
| 删除 | `app/llm/prompts/claude_code_update.py` | 被通用 prompt 替代 |
| 修改 | `app/llm/router.py` | `claude_code_update` → `github_release_update` |
| 修改 | `app/services/notification.py` | 替换调用方和格式化逻辑 |

## 约束

- 无新增环境变量
- 无数据库变更
- 无前端变更
- GitHub API 匿名限制 60 次/小时，两个仓库每日一次完全足够
