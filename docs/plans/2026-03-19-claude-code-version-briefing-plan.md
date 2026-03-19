# Claude Code 版本更新简报 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 每日 Slack 简报中自动推送 Claude Code 新版本的中文摘要

**Architecture:** 新建 `ClaudeCodeVersionService` 从 GitHub Releases API 获取版本数据，通过文件标记追踪已推送版本，GLM Flash 生成中文摘要，集成到 `NotificationService.push_daily_report()` 消息流

**Tech Stack:** GitHub REST API, GLM Flash (智谱), 文件标记持久化

---

### Task 1: ClaudeCodeVersionService — 数据获取层

**Files:**
- Create: `app/services/claude_code_version.py`

- [ ] **Step 1: 创建 ClaudeCodeVersionService**

```python
"""Claude Code 版本更新服务 - 从 GitHub Releases 获取版本信息"""
import json
import logging
import os
import ssl
from urllib.request import urlopen, Request

import certifi

logger = logging.getLogger(__name__)

GITHUB_RELEASES_URL = 'https://api.github.com/repos/anthropics/claude-code/releases'
VERSION_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'claude_code_last_version.txt')


class ClaudeCodeVersionService:

    @staticmethod
    def get_new_releases() -> list[dict]:
        """获取自上次推送以来的新版本"""
        releases = ClaudeCodeVersionService._fetch_releases_from_github()
        if not releases:
            return []

        last_version = ClaudeCodeVersionService._get_last_pushed_version()
        return ClaudeCodeVersionService._filter_new_releases(releases, last_version)

    @staticmethod
    def _fetch_releases_from_github() -> list[dict]:
        """从 GitHub API 获取最近 10 个 release"""
        try:
            req = Request(
                f'{GITHUB_RELEASES_URL}?per_page=10',
                headers={'Accept': 'application/vnd.github.v3+json', 'User-Agent': 'stock-briefing-bot'},
            )
            ssl_ctx = ssl.create_default_context(cafile=certifi.where())
            with urlopen(req, timeout=15, context=ssl_ctx) as resp:
                if resp.status != 200:
                    logger.warning(f'[Claude Code 版本] GitHub API 返回 {resp.status}')
                    return []
                data = json.loads(resp.read().decode())

            return [
                {
                    'version': r.get('tag_name', ''),
                    'published_at': (r.get('published_at') or '')[:10],
                    'body': r.get('body', ''),
                }
                for r in data
                if not r.get('draft') and not r.get('prerelease')
            ]
        except Exception as e:
            logger.warning(f'[Claude Code 版本] GitHub API 调用失败: {e}')
            return []

    @staticmethod
    def _get_last_pushed_version() -> str | None:
        """读取上次推送的版本号"""
        try:
            if os.path.exists(VERSION_FILE):
                with open(VERSION_FILE, 'r') as f:
                    return f.read().strip() or None
        except OSError as e:
            logger.warning(f'[Claude Code 版本] 读取版本标记失败: {e}')
        return None

    @staticmethod
    def mark_pushed_version(version: str) -> None:
        """写入已推送版本号"""
        try:
            os.makedirs(os.path.dirname(VERSION_FILE), exist_ok=True)
            with open(VERSION_FILE, 'w') as f:
                f.write(version)
        except OSError as e:
            logger.warning(f'[Claude Code 版本] 写入版本标记失败: {e}')

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
```

- [ ] **Step 2: 验证文件可正常 import**

Run: `cd D:/Git/stock && python -c "from app.services.claude_code_version import ClaudeCodeVersionService; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add app/services/claude_code_version.py
git commit -m "feat: add ClaudeCodeVersionService for GitHub releases"
```

---

### Task 2: GLM Prompt + 路由注册

**Files:**
- Create: `app/llm/prompts/claude_code_update.py`
- Modify: `app/llm/router.py:9-23` (TASK_LAYER_MAP)

- [ ] **Step 1: 创建 prompt 文件**

```python
"""Claude Code 版本更新摘要 Prompt"""

CLAUDE_CODE_UPDATE_SYSTEM_PROMPT = (
    "你是技术工具更新摘要助手。根据 changelog 生成简洁的中文版本更新摘要。"
)


def build_claude_code_update_prompt(releases: list[dict]) -> str:
    """构建 Claude Code 版本更新摘要 prompt

    Args:
        releases: [{"version": "v1.0.30", "published_at": "2026-03-19", "body": "..."}]
    """
    max_chars = 200 if len(releases) == 1 else 150 * len(releases)

    parts = []
    for r in releases:
        parts.append(f"版本: {r['version']} ({r['published_at']})\n{r['body']}")

    releases_text = '\n---\n'.join(parts)

    return f"""以下是 Claude Code（Anthropic CLI 工具）的版本更新日志：

{releases_text}

请用中文总结以上版本更新，要求：
- 每个版本一段，以版本号开头
- 重点提炼：新功能、重要修复、破坏性变更
- 总长度不超过{max_chars}字
- 直接返回纯文本，不要JSON或markdown代码块"""
```

- [ ] **Step 2: 在 router.py TASK_LAYER_MAP 中注册路由**

在 `app/llm/router.py` 的 `TASK_LAYER_MAP` 字典末尾添加：

```python
    'claude_code_update': LLMLayer.FLASH,
```

- [ ] **Step 3: 验证 import**

Run: `cd D:/Git/stock && python -c "from app.llm.prompts.claude_code_update import build_claude_code_update_prompt; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add app/llm/prompts/claude_code_update.py app/llm/router.py
git commit -m "feat: add Claude Code update GLM prompt and FLASH routing"
```

---

### Task 3: notification.py — format 方法 + 集成到 push_daily_report

**Files:**
- Modify: `app/services/notification.py`

- [ ] **Step 1: 在 `format_technical_summary()` 方法之后（约 L514）添加 `format_claude_code_update()` 方法**

```python
    @staticmethod
    def format_claude_code_update() -> tuple[str, str | None]:
        """格式化 Claude Code 版本更新摘要

        Returns:
            (formatted_text, latest_version) — latest_version 为 None 表示无新版本
        """
        try:
            from app.services.claude_code_version import ClaudeCodeVersionService
            releases = ClaudeCodeVersionService.get_new_releases()

            if not releases:
                return '🤖 Claude Code 更新\nClaude Code 无版本更新', None

            latest_version = releases[0]['version']

            # GLM 摘要
            try:
                from app.llm.router import llm_router
                from app.llm.prompts.claude_code_update import (
                    CLAUDE_CODE_UPDATE_SYSTEM_PROMPT, build_claude_code_update_prompt,
                )

                provider = llm_router.route('claude_code_update')
                if provider:
                    prompt = build_claude_code_update_prompt(releases)
                    summary = provider.chat(
                        [
                            {'role': 'system', 'content': CLAUDE_CODE_UPDATE_SYSTEM_PROMPT},
                            {'role': 'user', 'content': prompt},
                        ],
                        temperature=0.3,
                        max_tokens=500,
                    )
                    return f"🤖 Claude Code 更新\n{summary.strip()}", latest_version
            except Exception as e:
                logger.warning(f'[通知.Claude Code更新] GLM摘要失败: {e}')

            # 降级：纯文本
            lines = ['🤖 Claude Code 更新']
            for r in releases:
                lines.append(f"{r['version']} ({r['published_at']})")
            return '\n'.join(lines), latest_version
        except Exception as e:
            logger.warning(f'[通知.Claude Code更新] 获取失败: {e}')
            return '', None
```

- [ ] **Step 2: 在 `push_daily_report()` 数据收集阶段（盯盘分析之后、GLM 综合分析之前）添加 Claude Code 版本获取**

在 `app/services/notification.py` 的 `push_daily_report()` 中，`watch_text` 收集块之后（L573）、GLM 综合分析之前（L575），添加：

```python
        # Claude Code 版本更新
        claude_code_text, claude_code_version = NotificationService.format_claude_code_update()
```

- [ ] **Step 3: 在消息组装阶段，`watch_text` 之后、`action_suggestions` 之前插入**

在 `text_parts` 组装中，`if watch_text:` 块之后（约 L646 之后），添加：

```python
        if claude_code_text:
            text_parts.append(claude_code_text)
```

- [ ] **Step 4: 在消息组装完成后、`send_all()` 之前标记版本**

在 `full_text = '\n---\n'.join(text_parts)` 之后（L651）、`results = NotificationService.send_all(...)` 之前（L653），添加：

```python
        # 标记已推送的 Claude Code 版本
        if claude_code_version:
            from app.services.claude_code_version import ClaudeCodeVersionService
            ClaudeCodeVersionService.mark_pushed_version(claude_code_version)
```

- [ ] **Step 5: 验证语法**

Run: `cd D:/Git/stock && python -c "from app.services.notification import NotificationService; print('OK')"`
Expected: `OK`

- [ ] **Step 6: Commit**

```bash
git add app/services/notification.py
git commit -m "feat: integrate Claude Code version update into daily briefing push"
```
