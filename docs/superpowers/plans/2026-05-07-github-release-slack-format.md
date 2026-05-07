# GitHub Release Slack 推送格式优化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 GitHub Release Slack 推送从「连续段落摘要」改造为「✨新功能 / 🐛修复 分类 bullet」结构，让用户 5 秒抓重点。

**Architecture:** Prompt 改为要求 LLM 输出结构化 JSON（`{versions: [{version, date, features, fixes}]}`），`format_github_release_updates()` 负责 JSON 解析 + 装组成 Slack mrkdwn。LLM 失败 / JSON 解析失败 / 分类全空 → 走原有的纯文本 changelog 截断降级。

**Tech Stack:** Python 3 / Flask / pytest / Slack mrkdwn / 智谱 GLM (FLASH 层)

**Spec:** `docs/superpowers/specs/2026-05-07-github-release-slack-format-design.md`

**File Structure:**
- Modify: `app/llm/prompts/github_release_update.py` — 改 prompt，要求 JSON
- Modify: `app/services/notification.py` — `format_github_release_updates()` 装组逻辑 + 新增 `_format_release_block()` 辅助函数
- Create: `tests/test_github_release_format.py` — 单测

---

### Task 1: 改 prompt 让 LLM 返回 JSON

**Files:**
- Modify: `app/llm/prompts/github_release_update.py`
- Test: `tests/test_github_release_format.py`

- [ ] **Step 1: 写 prompt 的失败测试**

创建 `tests/test_github_release_format.py`：

```python
"""GitHub Release Slack 推送格式优化测试"""
from unittest.mock import MagicMock, patch

import pytest


def test_prompt_requests_json_with_features_and_fixes():
    from app.llm.prompts.github_release_update import build_github_release_update_prompt

    releases = [{
        'version': 'v2.1.132',
        'published_at': '2026-05-06',
        'body': 'Added X env var. Fixed SIGINT handling.',
    }]
    prompt = build_github_release_update_prompt('Claude Code', releases)

    assert 'JSON' in prompt
    assert 'features' in prompt
    assert 'fixes' in prompt
    assert 'versions' in prompt
    assert 'v2.1.132' in prompt
    assert '2026-05-06' in prompt
```

- [ ] **Step 2: 跑测试确认失败**

```bash
PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 python -m pytest tests/test_github_release_format.py::test_prompt_requests_json_with_features_and_fixes -v
```

Expected: FAIL（旧 prompt 不含 `JSON` / `features` / `fixes` 关键字）

- [ ] **Step 3: 改 prompt 实现**

完整替换 `app/llm/prompts/github_release_update.py`：

```python
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
```

- [ ] **Step 4: 跑测试确认通过**

```bash
PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 python -m pytest tests/test_github_release_format.py::test_prompt_requests_json_with_features_and_fixes -v
```

Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add app/llm/prompts/github_release_update.py tests/test_github_release_format.py
git commit -m "$(cat <<'EOF'
feat(release-format): GitHub Release 摘要 prompt 改为 JSON 输出

要求 LLM 返回 {versions: [{version, date, features, fixes}]} 结构，
为后续装组分类 bullet 做准备。
EOF
)"
```

---

### Task 2: 新增 `_format_release_block()` 辅助函数

把单个 version 的 JSON 数据渲染为 Slack mrkdwn 文本块。

**Files:**
- Modify: `app/services/notification.py`（新增静态方法 `_format_release_block`）
- Test: `tests/test_github_release_format.py`

- [ ] **Step 1: 写完整渲染的失败测试**

追加到 `tests/test_github_release_format.py`：

```python
def test_format_release_block_full():
    from app.services.notification import NotificationService

    version_data = {
        'version': 'v2.1.132',
        'date': '2026-05-06',
        'features': [
            '新增 `CLAUDE_CODE_SESSION_ID` 环境变量',
            '粘贴图片时显示 "Pasting..." 提示',
        ],
        'fixes': [
            'SIGINT 信号未正确处理',
            '`--permission-mode` 标志被忽略',
        ],
    }
    text = NotificationService._format_release_block('Claude Code', '🤖', version_data)

    assert text.startswith('🤖 *Claude Code v2.1.132* (2026-05-06)')
    assert '✨ *新功能*' in text
    assert '• 新增 `CLAUDE_CODE_SESSION_ID` 环境变量' in text
    assert '🐛 *修复*' in text
    assert '• SIGINT 信号未正确处理' in text


def test_format_release_block_skips_empty_features():
    from app.services.notification import NotificationService

    version_data = {
        'version': 'v1.0.0',
        'date': '2026-05-01',
        'features': [],
        'fixes': ['修复 A'],
    }
    text = NotificationService._format_release_block('Tool', '🛠', version_data)

    assert '✨ *新功能*' not in text
    assert '🐛 *修复*' in text
    assert '• 修复 A' in text


def test_format_release_block_skips_empty_fixes():
    from app.services.notification import NotificationService

    version_data = {
        'version': 'v1.0.0',
        'date': '2026-05-01',
        'features': ['新增 A'],
        'fixes': [],
    }
    text = NotificationService._format_release_block('Tool', '🛠', version_data)

    assert '✨ *新功能*' in text
    assert '• 新增 A' in text
    assert '🐛 *修复*' not in text
```

- [ ] **Step 2: 跑测试确认失败**

```bash
PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 python -m pytest tests/test_github_release_format.py -v -k "format_release_block"
```

Expected: FAIL with "AttributeError: type object 'NotificationService' has no attribute '_format_release_block'"

- [ ] **Step 3: 实现 `_format_release_block`**

在 `app/services/notification.py` 的 `format_github_release_updates` 方法**之前**插入新静态方法：

```python
    @staticmethod
    def _format_release_block(name: str, emoji: str, version_data: dict) -> str:
        """渲染单个 version 的 Slack mrkdwn 文本块

        Args:
            name: 项目名（如 "Claude Code"）
            emoji: 项目 emoji（如 "🤖"）
            version_data: {version, date, features, fixes}
        """
        version = version_data.get('version', '')
        date = version_data.get('date', '')
        features = version_data.get('features') or []
        fixes = version_data.get('fixes') or []

        lines = [f"{emoji} *{name} {version}* ({date})"]
        if features:
            lines.append('')
            lines.append('✨ *新功能*')
            lines.extend(f"• {item}" for item in features)
        if fixes:
            lines.append('')
            lines.append('🐛 *修复*')
            lines.extend(f"• {item}" for item in fixes)
        return '\n'.join(lines)
```

- [ ] **Step 4: 跑测试确认通过**

```bash
PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 python -m pytest tests/test_github_release_format.py -v -k "format_release_block"
```

Expected: 3 passed

- [ ] **Step 5: 提交**

```bash
git add app/services/notification.py tests/test_github_release_format.py
git commit -m "$(cat <<'EOF'
feat(release-format): 新增 _format_release_block 渲染分类 bullet

单个 version 的 JSON 数据渲染为 Slack mrkdwn，
features/fixes 为空时整段跳过。
EOF
)"
```

---

### Task 3: 接入 JSON 解析 + 降级路径

把 `format_github_release_updates()` 主流程改为「调 LLM → 解析 JSON → 装组 → 失败降级」。

**Files:**
- Modify: `app/services/notification.py:733-801`（`format_github_release_updates` 整体重写）
- Test: `tests/test_github_release_format.py`

- [ ] **Step 1: 写集成测试**

追加到 `tests/test_github_release_format.py`：

```python
@pytest.fixture
def fake_repo_cfg():
    return {
        'key': 'claude_code',
        'repo': 'anthropics/claude-code',
        'name': 'Claude Code',
        'emoji': '🤖',
    }


def _patch_get_all_updates(repo_cfg, releases):
    """Helper: 替换 GitHubReleaseService.get_all_updates 的返回"""
    return patch(
        'app.services.github_release.GitHubReleaseService.get_all_updates',
        return_value=[{'config': repo_cfg, 'releases': releases}],
    )


def _patch_llm(json_str_or_exception):
    """Helper: mock llm_router.route(...).chat(...) 的返回或抛异常"""
    provider = MagicMock()
    if isinstance(json_str_or_exception, Exception):
        provider.chat.side_effect = json_str_or_exception
    else:
        provider.chat.return_value = json_str_or_exception

    router_mock = MagicMock()
    router_mock.route.return_value = provider
    return patch('app.llm.router.llm_router', router_mock)


def test_format_uses_json_for_categorized_output(fake_repo_cfg):
    from app.services.notification import NotificationService

    releases = [{
        'version': 'v2.1.132',
        'published_at': '2026-05-06',
        'body': 'Added X. Fixed Y.',
        'url': 'https://github.com/anthropics/claude-code/releases/tag/v2.1.132',
    }]
    llm_json = (
        '{"versions": [{"version": "v2.1.132", "date": "2026-05-06", '
        '"features": ["新增 `X` 环境变量"], "fixes": ["修复 Y 问题"]}]}'
    )

    with _patch_get_all_updates(fake_repo_cfg, releases), _patch_llm(llm_json):
        texts, pushed = NotificationService.format_github_release_updates()

    assert len(texts) == 1
    assert '🤖 *Claude Code v2.1.132* (2026-05-06)' in texts[0]
    assert '✨ *新功能*' in texts[0]
    assert '• 新增 `X` 环境变量' in texts[0]
    assert '🐛 *修复*' in texts[0]
    assert '• 修复 Y 问题' in texts[0]
    assert 'https://github.com/anthropics/claude-code/releases/tag/v2.1.132' in texts[0]
    assert pushed == [('claude_code', 'v2.1.132')]


def test_format_falls_back_when_llm_returns_non_json(fake_repo_cfg, caplog):
    from app.services.notification import NotificationService

    releases = [{
        'version': 'v2.1.132',
        'published_at': '2026-05-06',
        'body': 'Some changelog body content here',
        'url': 'https://github.com/x/y/releases/tag/v2.1.132',
    }]
    with _patch_get_all_updates(fake_repo_cfg, releases), _patch_llm('not valid json at all'):
        texts, _ = NotificationService.format_github_release_updates()

    assert len(texts) == 1
    # 降级路径：含原 changelog 内容
    assert 'Some changelog body content here' in texts[0]
    assert '🤖 Claude Code 更新' in texts[0]
    assert 'https://github.com/x/y/releases/tag/v2.1.132' in texts[0]


def test_format_falls_back_when_all_categories_empty(fake_repo_cfg):
    from app.services.notification import NotificationService

    releases = [{
        'version': 'v2.1.132',
        'published_at': '2026-05-06',
        'body': 'Internal refactor only',
        'url': 'https://github.com/x/y/releases/tag/v2.1.132',
    }]
    llm_json = (
        '{"versions": [{"version": "v2.1.132", "date": "2026-05-06", '
        '"features": [], "fixes": []}]}'
    )
    with _patch_get_all_updates(fake_repo_cfg, releases), _patch_llm(llm_json):
        texts, _ = NotificationService.format_github_release_updates()

    assert len(texts) == 1
    # 走降级：含原 body
    assert 'Internal refactor only' in texts[0]


def test_format_handles_multi_versions(fake_repo_cfg):
    from app.services.notification import NotificationService

    releases = [
        {
            'version': 'v2.1.132',
            'published_at': '2026-05-06',
            'body': 'Added X.',
            'url': 'https://github.com/x/y/releases/tag/v2.1.132',
        },
        {
            'version': 'v2.1.131',
            'published_at': '2026-05-05',
            'body': 'Fixed Z.',
            'url': 'https://github.com/x/y/releases/tag/v2.1.131',
        },
    ]
    llm_json = (
        '{"versions": ['
        '{"version": "v2.1.132", "date": "2026-05-06", "features": ["新增 X"], "fixes": []},'
        '{"version": "v2.1.131", "date": "2026-05-05", "features": [], "fixes": ["修复 Z"]}'
        ']}'
    )
    with _patch_get_all_updates(fake_repo_cfg, releases), _patch_llm(llm_json):
        texts, pushed = NotificationService.format_github_release_updates()

    assert len(texts) == 1
    assert '🤖 *Claude Code v2.1.132*' in texts[0]
    assert '🤖 *Claude Code v2.1.131*' in texts[0]
    # 链接只出现一次（用最新版本）
    assert texts[0].count('🔗') == 1
    assert 'releases/tag/v2.1.132' in texts[0]
    # pushed 取最新（releases[0]）
    assert pushed == [('claude_code', 'v2.1.132')]
```

- [ ] **Step 2: 跑测试确认失败**

```bash
PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 python -m pytest tests/test_github_release_format.py -v
```

Expected: 4 个集成测试 FAIL（旧实现仍输出连续段落，无 ✨ / 🐛 标记）

- [ ] **Step 3: 重写 `format_github_release_updates`**

完整替换 `app/services/notification.py:733-801` 的方法体（保留方法签名）：

```python
    @staticmethod
    def format_github_release_updates() -> tuple[list[str], list[tuple[str, str]]]:
        """格式化所有 GitHub 仓库的版本更新摘要

        Returns:
            (texts, pushed_versions)
            - texts: 每个有更新的仓库一段文本（分类 bullet 结构）
            - pushed_versions: [(key, version), ...] 需要标记已推送的版本
        """
        import json

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
                release_url = releases[0].get('url', '')
                has_body = any(r.get('body', '').strip() for r in releases)

                rendered = None
                if has_body:
                    rendered = NotificationService._render_release_categorized(cfg, releases)

                if rendered:
                    text = rendered
                    if release_url:
                        text += f"\n\n🔗 {release_url}"
                    texts.append(text)
                else:
                    # 降级：纯文本（含 changelog 截断）
                    texts.append(NotificationService._render_release_fallback(cfg, releases, release_url))
        except Exception as e:
            logger.warning(f'[通知.GitHub Release更新] 获取失败: {e}')

        return texts, pushed_versions

    @staticmethod
    def _render_release_categorized(cfg: dict, releases: list[dict]) -> str | None:
        """调 LLM + 解析 JSON + 装组分类 bullet。失败返回 None。"""
        import json

        try:
            from app.llm.router import llm_router
            from app.llm.prompts.github_release_update import (
                GITHUB_RELEASE_UPDATE_SYSTEM_PROMPT, build_github_release_update_prompt,
            )

            provider = llm_router.route('github_release_update')
            if not provider:
                return None

            prompt = build_github_release_update_prompt(cfg['name'], releases)
            raw = provider.chat(
                [
                    {'role': 'system', 'content': GITHUB_RELEASE_UPDATE_SYSTEM_PROMPT},
                    {'role': 'user', 'content': prompt},
                ],
                temperature=0.3,
                max_tokens=800,
            )

            data = json.loads(raw.strip())
            versions = data.get('versions') or []
            if not versions:
                logger.warning(f"[通知.{cfg['name']}更新] LLM 返回 versions 为空，降级")
                return None

            # 至少要有一个 version 含 features 或 fixes，否则降级
            if not any((v.get('features') or v.get('fixes')) for v in versions):
                logger.warning(f"[通知.{cfg['name']}更新] LLM 分类全空，降级")
                return None

            blocks = [
                NotificationService._format_release_block(cfg['name'], cfg['emoji'], v)
                for v in versions
            ]
            return '\n\n'.join(blocks)

        except json.JSONDecodeError as e:
            logger.warning(f"[通知.{cfg['name']}更新] LLM JSON 解析失败: {e}，降级")
            return None
        except Exception as e:
            logger.warning(f"[通知.{cfg['name']}更新] LLM 调用失败: {e}，降级")
            return None

    @staticmethod
    def _render_release_fallback(cfg: dict, releases: list[dict], release_url: str) -> str:
        """降级路径：纯文本 changelog 截断"""
        lines = [f"{cfg['emoji']} {cfg['name']} 更新"]
        for r in releases:
            lines.append(f"{r['version']} ({r['published_at']})")
            if r.get('body'):
                body = r['body'].strip()
                if len(body) > 500:
                    body = body[:500] + '…'
                lines.append(body)
        if release_url:
            lines.append(f"\n🔗 {release_url}")
        return '\n'.join(lines)
```

注意：
- `_format_release_block` 已在 Task 2 加好
- 新增两个 helper：`_render_release_categorized` / `_render_release_fallback`
- 主方法逻辑收敛为「调 categorized → 失败走 fallback」

- [ ] **Step 4: 跑全部测试**

```bash
PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 python -m pytest tests/test_github_release_format.py -v
```

Expected: 全部 PASS（共 8 个测试：1 prompt + 3 block + 4 集成）

- [ ] **Step 5: 提交**

```bash
git add app/services/notification.py tests/test_github_release_format.py
git commit -m "$(cat <<'EOF'
feat(release-format): format_github_release_updates 接入 JSON 装组

- 新增 _render_release_categorized：调 LLM + 解析 JSON + 装组分类 bullet
- 新增 _render_release_fallback：降级路径（原纯文本截断）
- LLM 失败 / JSON 解析失败 / 分类全空 → 自动降级，warning log 标记
EOF
)"
```

---

### Task 4: 手动 smoke test

跑一次真实 GitHub Release 数据，确认 Slack 端渲染正常。**注意：调用 LLM 且会真发 Slack（如果 SLACK_BOT_TOKEN 已配置）**。

**Files:** （仅运行验证，无代码改动）

- [ ] **Step 1: 干跑 format_github_release_updates，不发 Slack**

```bash
PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 python -c "from app import create_app; app = create_app(); ctx = app.app_context(); ctx.push(); from app.services.notification import NotificationService; texts, pushed = NotificationService.format_github_release_updates(); print('---PUSHED---'); print(pushed); print('---TEXTS---'); [print(t, '\n\n---\n\n') for t in texts]"
```

Expected：每个有更新的仓库输出形如

```
🤖 *Claude Code v2.1.132* (2026-05-06)

✨ *新功能*
• ...

🐛 *修复*
• ...

🔗 https://...
```

无更新时 `texts == []`、`pushed == []`，正常。

- [ ] **Step 2: 检查日志**

确认 stderr 无 `LLM JSON 解析失败` / `LLM 调用失败` / `分类全空` warning（出现说明降级被触发，需排查 prompt 是否需要再加严）

- [ ] **Step 3: 提交（如果上面有任何 prompt / 代码微调）**

如果 Step 1 / 2 都正常，无需额外提交。

---

## Self-Review

**1. Spec coverage:**
- ✅ 输出格式（标题 + ✨ + 🐛 + 🔗）→ Task 2 `_format_release_block` + Task 3 主流程
- ✅ Prompt 改 JSON → Task 1
- ✅ 装组逻辑 → Task 3 `_render_release_categorized`
- ✅ 降级路径保留 → Task 3 `_render_release_fallback`
- ✅ features/fixes 为空段落跳过 → Task 2 实现 + 测试
- ✅ 多 version 共用一个链接 → Task 3 集成测试 `test_format_handles_multi_versions`
- ✅ 不改动 blog/trending/strategy/service → 已明确范围
- ✅ 测试覆盖：完整 JSON / 缺 features / 缺 fixes / 非 JSON / 分类全空 / 多版本 → Task 1+2+3 共 8 测试

**2. Placeholder scan:** 无 TBD / TODO / "适当处理" / "类似 Task N"。所有代码块都是完整可粘贴的内容。

**3. Type consistency:**
- `_format_release_block(name, emoji, version_data)` — Task 2 定义、Task 3 调用，签名一致
- `_render_release_categorized(cfg, releases) -> str | None` — Task 3 内部一致
- `_render_release_fallback(cfg, releases, release_url) -> str` — Task 3 内部一致
- `version_data` dict 字段 `version` / `date` / `features` / `fixes` — Task 1 prompt + Task 2 渲染 + Task 3 LLM 解析三处一致

无类型 / 命名漂移。
