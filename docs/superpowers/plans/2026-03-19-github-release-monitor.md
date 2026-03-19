# GitHub Release 通用监控服务 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将硬编码的 `ClaudeCodeVersionService` 重构为通用 `GitHubReleaseService`，支持通过配置监控多个 GitHub 仓库的 release 更新。

**Architecture:** 配置驱动的多仓库监控。`app/config/github_releases.py` 定义仓库列表，`GitHubReleaseService` 按 repo/key 参数通用化所有方法，`notification.py` 循环处理所有仓库并生成独立 Slack 段落。

**Tech Stack:** Python, Flask, GitHub REST API, 智谱 GLM (FLASH layer)

**Spec:** `docs/superpowers/specs/2026-03-19-github-release-monitor-design.md`

---

### Task 1: 新建配置模块

**Files:**
- Create: `app/config/github_releases.py`

- [ ] **Step 1: 创建配置文件**

```python
"""GitHub Release 监控仓库配置"""

GITHUB_RELEASE_REPOS = [
    {
        'key': 'claude-code',
        'repo': 'anthropics/claude-code',
        'name': 'Claude Code',
        'emoji': '🤖',
    },
    {
        'key': 'superpowers',
        'repo': 'obra/superpowers',
        'name': 'Superpowers',
        'emoji': '⚡',
    },
]
```

- [ ] **Step 2: Commit**

```bash
git add app/config/github_releases.py
git commit -m "feat: add github release repos config"
```

---

### Task 2: 新建通用服务 `GitHubReleaseService`

**Files:**
- Create: `app/services/github_release.py`

- [ ] **Step 1: 创建通用服务**

基于现有 `claude_code_version.py` 重构，所有方法参数化：

```python
"""GitHub Release 通用监控服务 - 从 GitHub Releases 获取多仓库版本信息"""
import json
import logging
import os
import ssl
from urllib.request import urlopen, Request

import certifi

from app.config.github_releases import GITHUB_RELEASE_REPOS

logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data')


class GitHubReleaseService:

    @staticmethod
    def get_new_releases(repo: str, key: str) -> list[dict]:
        """获取指定仓库自上次推送以来的新版本"""
        releases = GitHubReleaseService._fetch_releases_from_github(repo)
        if not releases:
            return []

        last_version = GitHubReleaseService._get_last_pushed_version(key)
        return GitHubReleaseService._filter_new_releases(releases, last_version)

    @staticmethod
    def _fetch_releases_from_github(repo: str) -> list[dict]:
        """从 GitHub API 获取最近 10 个 release"""
        url = f'https://api.github.com/repos/{repo}/releases?per_page=10'
        try:
            req = Request(
                url,
                headers={'Accept': 'application/vnd.github.v3+json', 'User-Agent': 'stock-briefing-bot'},
            )
            ssl_ctx = ssl.create_default_context(cafile=certifi.where())
            with urlopen(req, timeout=15, context=ssl_ctx) as resp:
                if resp.status != 200:
                    logger.warning(f'[GitHub Release] {repo} API 返回 {resp.status}')
                    return []
                data = json.loads(resp.read().decode())

            return [
                {
                    'version': r.get('tag_name', ''),
                    'published_at': (r.get('published_at') or '')[:10],
                    'body': r.get('body') or '',
                }
                for r in data
                if not r.get('draft') and not r.get('prerelease')
            ]
        except Exception as e:
            logger.warning(f'[GitHub Release] {repo} API 调用失败: {e}')
            return []

    @staticmethod
    def _get_last_pushed_version(key: str) -> str | None:
        """读取指定仓库上次推送的版本号"""
        version_file = os.path.join(DATA_DIR, f'github_release_{key}_last_version.txt')
        try:
            if os.path.exists(version_file):
                with open(version_file, 'r') as f:
                    return f.read().strip() or None
        except OSError as e:
            logger.warning(f'[GitHub Release] 读取 {key} 版本标记失败: {e}')
        return None

    @staticmethod
    def mark_pushed_version(key: str, version: str) -> None:
        """写入指定仓库已推送版本号"""
        version_file = os.path.join(DATA_DIR, f'github_release_{key}_last_version.txt')
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
            with open(version_file, 'w') as f:
                f.write(version)
        except OSError as e:
            logger.warning(f'[GitHub Release] 写入 {key} 版本标记失败: {e}')

    @staticmethod
    def _filter_new_releases(releases: list[dict], last_version: str | None) -> list[dict]:
        """筛选出比 last_version 更新的版本；首次运行只取最新 1 个"""
        if not releases:
            return []

        if last_version is None:
            return releases[:1]

        new_releases = []
        for r in releases:
            if r['version'] == last_version:
                break
            new_releases.append(r)
        return new_releases

    @staticmethod
    def get_all_updates() -> list[dict]:
        """遍历所有配置仓库，返回每个仓库的更新"""
        results = []
        for repo_cfg in GITHUB_RELEASE_REPOS:
            releases = GitHubReleaseService.get_new_releases(repo_cfg['repo'], repo_cfg['key'])
            results.append({'config': repo_cfg, 'releases': releases})
        return results
```

- [ ] **Step 2: Commit**

```bash
git add app/services/github_release.py
git commit -m "feat: add generic GitHubReleaseService for multi-repo monitoring"
```

---

### Task 3: 新建通用 Prompt

**Files:**
- Create: `app/llm/prompts/github_release_update.py`

- [ ] **Step 1: 创建通用 prompt 文件**

```python
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
```

- [ ] **Step 2: Commit**

```bash
git add app/llm/prompts/github_release_update.py
git commit -m "feat: add generic github release update prompt"
```

---

### Task 4: 修改 LLM 路由

**Files:**
- Modify: `app/llm/router.py:23`

- [ ] **Step 1: 替换 task key**

将 `app/llm/router.py` 第 23 行：

```python
    'claude_code_update': LLMLayer.FLASH,
```

替换为：

```python
    'github_release_update': LLMLayer.FLASH,
```

- [ ] **Step 2: Commit**

```bash
git add app/llm/router.py
git commit -m "refactor: rename claude_code_update to github_release_update in LLM router"
```

---

### Task 5: 修改 Notification 集成

**Files:**
- Modify: `app/services/notification.py:516-561` (替换 `format_claude_code_update`)
- Modify: `app/services/notification.py:622-623` (调用处)
- Modify: `app/services/notification.py:698-709` (消息组装 + 版本标记)

- [ ] **Step 1: 替换 `format_claude_code_update` 方法为 `format_github_release_updates`**

删除 `notification.py` 第 516-561 行的 `format_claude_code_update` 方法，替换为：

```python
    @staticmethod
    def format_github_release_updates() -> tuple[list[str], list[tuple[str, str]]]:
        """格式化所有 GitHub 仓库的版本更新摘要

        Returns:
            (texts, pushed_versions)
            - texts: 每个有更新的仓库一段文本
            - pushed_versions: [(key, version), ...] 需要标记已推送的版本
        """
        texts = []
        pushed_versions = []
        try:
            from app.services.github_release import GitHubReleaseService
            all_updates = GitHubReleaseService.get_all_updates()

            for item in all_updates:
                cfg = item['config']
                releases = item['releases']
                if not releases:
                    continue

                latest_version = releases[0]['version']
                pushed_versions.append((cfg['key'], latest_version))

                # GLM 摘要
                try:
                    from app.llm.router import llm_router
                    from app.llm.prompts.github_release_update import (
                        GITHUB_RELEASE_UPDATE_SYSTEM_PROMPT, build_github_release_update_prompt,
                    )

                    provider = llm_router.route('github_release_update')
                    if provider:
                        prompt = build_github_release_update_prompt(cfg['name'], releases)
                        summary = provider.chat(
                            [
                                {'role': 'system', 'content': GITHUB_RELEASE_UPDATE_SYSTEM_PROMPT},
                                {'role': 'user', 'content': prompt},
                            ],
                            temperature=0.3,
                            max_tokens=500,
                        )
                        texts.append(f"{cfg['emoji']} {cfg['name']} 更新\n{summary.strip()}")
                        continue
                except Exception as e:
                    logger.warning(f"[通知.{cfg['name']}更新] GLM摘要失败: {e}")

                # 降级：纯文本
                lines = [f"{cfg['emoji']} {cfg['name']} 更新"]
                for r in releases:
                    lines.append(f"{r['version']} ({r['published_at']})")
                texts.append('\n'.join(lines))
        except Exception as e:
            logger.warning(f'[通知.GitHub Release更新] 获取失败: {e}')

        return texts, pushed_versions
```

- [ ] **Step 2: 修改 `push_daily_report` 调用处**

将第 622-623 行：

```python
        # Claude Code 版本更新
        claude_code_text, claude_code_version = NotificationService.format_claude_code_update()
```

替换为：

```python
        # GitHub Release 版本更新
        release_texts, release_pushed_versions = NotificationService.format_github_release_updates()
```

- [ ] **Step 3: 修改消息组装和版本标记**

将第 698-709 行：

```python
        if claude_code_text:
            text_parts.append(claude_code_text)

        if action_suggestions:
            text_parts.append(f"💡 操作建议\n{action_suggestions}")

        full_text = '\n---\n'.join(text_parts)

        # 标记已推送的 Claude Code 版本
        if claude_code_version:
            from app.services.claude_code_version import ClaudeCodeVersionService
            ClaudeCodeVersionService.mark_pushed_version(claude_code_version)
```

替换为：

```python
        for rt in release_texts:
            text_parts.append(rt)

        if action_suggestions:
            text_parts.append(f"💡 操作建议\n{action_suggestions}")

        full_text = '\n---\n'.join(text_parts)

        # 标记已推送的 GitHub Release 版本
        if release_pushed_versions:
            from app.services.github_release import GitHubReleaseService
            for key, version in release_pushed_versions:
                GitHubReleaseService.mark_pushed_version(key, version)
```

- [ ] **Step 4: Commit**

```bash
git add app/services/notification.py
git commit -m "refactor: replace format_claude_code_update with generic format_github_release_updates"
```

---

### Task 6: 删除旧文件

**Files:**
- Delete: `app/services/claude_code_version.py`
- Delete: `app/llm/prompts/claude_code_update.py`

- [ ] **Step 1: 迁移旧版本文件（如存在）**

```bash
if [ -f data/claude_code_last_version.txt ]; then
    cp data/claude_code_last_version.txt data/github_release_claude-code_last_version.txt
    rm data/claude_code_last_version.txt
fi
```

- [ ] **Step 2: 删除旧服务和旧 prompt**

```bash
git rm app/services/claude_code_version.py
git rm app/llm/prompts/claude_code_update.py
```

- [ ] **Step 3: Commit**

```bash
git commit -m "refactor: remove deprecated ClaudeCodeVersionService and prompt"
```

---

### Task 7: 验证

- [ ] **Step 1: 启动应用确认无 import 错误**

```bash
python -c "from app.services.github_release import GitHubReleaseService; print('import ok')"
python -c "from app.services.notification import NotificationService; print('import ok')"
python -c "from app.llm.router import TASK_LAYER_MAP; assert 'github_release_update' in TASK_LAYER_MAP; print('router ok')"
```

- [ ] **Step 2: 验证 GitHub API 可达**

```bash
python -c "
from app.services.github_release import GitHubReleaseService
for item in GitHubReleaseService.get_all_updates():
    cfg = item['config']
    releases = item['releases']
    print(f\"{cfg['name']}: {len(releases)} new releases\")
    if releases:
        print(f\"  latest: {releases[0]['version']}\")
"
```

- [ ] **Step 3: 确认无残留引用**

搜索项目中是否还有对旧模块的引用：

```bash
grep -r "claude_code_version" app/ --include="*.py"
grep -r "ClaudeCodeVersionService" app/ --include="*.py"
grep -r "claude_code_update" app/ --include="*.py"
```

预期：无结果。

- [ ] **Step 4: Commit（如有修复）**
