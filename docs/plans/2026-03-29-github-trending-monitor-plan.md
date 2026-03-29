# GitHub Trending 监控实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 每日监控 GitHub Trending Top 10，去重后推送新上榜项目到 Slack `news_ai_tool` 频道，附 LLM 中文摘要。

**Architecture:** 独立 Config + Service 模式（与博客监控、GitHub Release 监控一致）。`GitHubTrendingService` 负责 HTML 爬取、解析、去重、LLM 摘要；`NotificationService` 新增 `format_github_trending_updates()` 格式化方法，在每日简报中与 Release/Blog 一起推送到 `news_ai_tool`。

**Tech Stack:** requests（HTTP）、re/html 解析、JSON 文件去重、智谱 GLM Flash（摘要）

---

## 文件结构

| 操作 | 文件 | 职责 |
|------|------|------|
| 新建 | `app/config/github_trending.py` | 配置项（启用开关、URL、Top N） |
| 新建 | `app/services/github_trending_service.py` | 爬取、解析、去重、LLM 摘要 |
| 新建 | `app/llm/prompts/github_trending_summary.py` | LLM 摘要 prompt |
| 修改 | `app/llm/router.py:9-26` | 添加 `github_trending_summary` 路由 |
| 修改 | `app/services/notification.py:674-728` | 新增 `format_github_trending_updates()` |
| 修改 | `app/services/notification.py:1062-1068` | `push_daily_report` 集成 trending |
| 修改 | `app/services/notification.py:1097-1104` | `push_daily_extras` 集成 trending |
| 修改 | `.env.sample` | 新增环境变量 |
| 修改 | `CLAUDE.md` | 新增配置说明 |
| 修改 | `README.md` | 新增配置说明 |

---

### Task 1: 配置层

**Files:**
- Create: `app/config/github_trending.py`

- [ ] **Step 1: 创建配置文件**

```python
"""GitHub Trending 监控配置"""
import os

GITHUB_TRENDING_ENABLED = os.environ.get('GITHUB_TRENDING_ENABLED', 'true').lower() == 'true'
GITHUB_TRENDING_TOP_N = int(os.environ.get('GITHUB_TRENDING_TOP_N', '10'))
GITHUB_TRENDING_URL = 'https://github.com/trending'
```

- [ ] **Step 2: Commit**

```bash
git add app/config/github_trending.py
git commit -m "feat: add GitHub Trending monitor config"
```

---

### Task 2: LLM Prompt

**Files:**
- Create: `app/llm/prompts/github_trending_summary.py`
- Modify: `app/llm/router.py:9-26`

- [ ] **Step 1: 创建 prompt 文件**

```python
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
```

- [ ] **Step 2: 在 LLM 路由表中注册**

在 `app/llm/router.py` 的 `TASK_LAYER_MAP` 字典中添加一行：

```python
    'github_trending_summary': LLMLayer.FLASH,
```

添加位置：在 `'blog_summary': LLMLayer.FLASH,` 这行之后。

- [ ] **Step 3: Commit**

```bash
git add app/llm/prompts/github_trending_summary.py app/llm/router.py
git commit -m "feat: add GitHub Trending summary LLM prompt and route"
```

---

### Task 3: Service 核心 — HTML 爬取与解析

**Files:**
- Create: `app/services/github_trending_service.py`

- [ ] **Step 1: 创建 service 文件，实现爬取和解析**

```python
"""GitHub Trending 监控服务 — 爬取热门项目并推送新上榜的"""
import json
import logging
import os
import re

import requests

from app.config.github_trending import (
    GITHUB_TRENDING_ENABLED, GITHUB_TRENDING_TOP_N, GITHUB_TRENDING_URL,
)

logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data')
PUSHED_FILE = os.path.join(DATA_DIR, 'github_trending_pushed.json')
FETCH_TIMEOUT = 15


class GitHubTrendingService:

    @staticmethod
    def _fetch_html() -> str:
        """请求 GitHub Trending 页面"""
        try:
            resp = requests.get(
                GITHUB_TRENDING_URL,
                headers={'User-Agent': 'Mozilla/5.0 (compatible; stock-bot/1.0)'},
                timeout=FETCH_TIMEOUT,
            )
            resp.raise_for_status()
            return resp.text
        except Exception as e:
            logger.warning(f'[GitHub Trending] 页面获取失败: {e}')
            return ''

    @staticmethod
    def _parse_html(html: str) -> list[dict]:
        """解析 Trending 页面，提取 Top N 项目信息

        GitHub Trending 页面结构：
        - 每个项目在 <article class="Box-row"> 内
        - repo 链接在 h2 > a[href] 中，href 格式 /owner/repo
        - 描述在 <p class="..."> 中
        - star 总数和今日增量在 <span> 中
        """
        repos = []
        article_pattern = re.compile(
            r'<article\s+class="Box-row">(.*?)</article>',
            re.DOTALL,
        )
        for match in article_pattern.finditer(html):
            block = match.group(1)

            # repo 全名
            name_match = re.search(r'href="(/[^"]+)"', block)
            if not name_match:
                continue
            full_name = name_match.group(1).strip('/')
            if '/' not in full_name:
                continue

            # 描述
            desc_match = re.search(r'<p\s+class="[^"]*col-9[^"]*"[^>]*>(.*?)</p>', block, re.DOTALL)
            description = ''
            if desc_match:
                description = re.sub(r'<[^>]+>', '', desc_match.group(1)).strip()

            # star 总数
            stars = ''
            star_links = re.findall(r'href="/[^"]+/stargazers"[^>]*>(.*?)</a>', block, re.DOTALL)
            if star_links:
                stars = re.sub(r'<[^>]+>', '', star_links[0]).strip().replace(',', ',')

            # 今日新增 star
            today_stars = ''
            today_match = re.search(r'(\d[\d,]*)\s+stars?\s+today', block, re.IGNORECASE)
            if today_match:
                today_stars = today_match.group(1)

            repos.append({
                'full_name': full_name,
                'description': description,
                'stars': stars,
                'today_stars': today_stars,
                'url': f'https://github.com/{full_name}',
            })

            if len(repos) >= GITHUB_TRENDING_TOP_N:
                break

        return repos

    @staticmethod
    def _get_pushed() -> set[str]:
        """读取已推送的 repo 全名集合"""
        try:
            if os.path.exists(PUSHED_FILE):
                with open(PUSHED_FILE, 'r', encoding='utf-8') as f:
                    return set(json.load(f))
        except Exception as e:
            logger.warning(f'[GitHub Trending] 读取已推送记录失败: {e}')
        return set()

    @staticmethod
    def _mark_pushed(names: list[str]):
        """追加已推送的 repo 全名"""
        existing = GitHubTrendingService._get_pushed()
        existing.update(names)
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
            with open(PUSHED_FILE, 'w', encoding='utf-8') as f:
                json.dump(list(existing), f, ensure_ascii=False)
        except Exception as e:
            logger.warning(f'[GitHub Trending] 写入已推送记录失败: {e}')

    @staticmethod
    def _summarize(repo_name: str, description: str) -> str:
        """GLM Flash 生成中文摘要"""
        try:
            from app.llm.router import llm_router
            from app.llm.prompts.github_trending_summary import (
                GITHUB_TRENDING_SUMMARY_SYSTEM_PROMPT,
                build_github_trending_summary_prompt,
            )

            provider = llm_router.route('github_trending_summary')
            if not provider:
                return ''

            prompt = build_github_trending_summary_prompt(repo_name, description)
            summary = provider.chat(
                [
                    {'role': 'system', 'content': GITHUB_TRENDING_SUMMARY_SYSTEM_PROMPT},
                    {'role': 'user', 'content': prompt},
                ],
                temperature=0.3,
                max_tokens=150,
            )
            return summary.strip()
        except Exception as e:
            logger.warning(f'[GitHub Trending] LLM 摘要失败 {repo_name}: {e}')
            return ''

    @staticmethod
    def fetch_trending() -> list[dict]:
        """主入口：获取新上榜的 trending 项目（含摘要）

        Returns:
            新项目列表，每项包含 full_name, description, stars, today_stars, url, summary
            首次运行返回空列表（只记录，不推送）
        """
        if not GITHUB_TRENDING_ENABLED:
            return []

        html = GitHubTrendingService._fetch_html()
        if not html:
            return []

        repos = GitHubTrendingService._parse_html(html)
        if not repos:
            logger.warning('[GitHub Trending] 未解析到任何项目')
            return []

        pushed = GitHubTrendingService._get_pushed()

        # 首次运行：记录当前列表，不推送
        if not pushed:
            logger.info(f'[GitHub Trending] 首次运行，记录 {len(repos)} 个项目')
            GitHubTrendingService._mark_pushed([r['full_name'] for r in repos])
            return []

        new_repos = [r for r in repos if r['full_name'] not in pushed]
        if not new_repos:
            logger.info('[GitHub Trending] 无新上榜项目')
            return []

        logger.info(f'[GitHub Trending] 发现 {len(new_repos)} 个新上榜项目')

        # LLM 摘要
        for repo in new_repos:
            summary = GitHubTrendingService._summarize(repo['full_name'], repo['description'])
            repo['summary'] = summary or repo['description']

        # 标记已推送
        GitHubTrendingService._mark_pushed([r['full_name'] for r in new_repos])

        return new_repos
```

- [ ] **Step 2: Commit**

```bash
git add app/services/github_trending_service.py
git commit -m "feat: add GitHubTrendingService with HTML parsing, dedup, and LLM summary"
```

---

### Task 4: 推送集成 — notification.py

**Files:**
- Modify: `app/services/notification.py`

- [ ] **Step 1: 添加 `format_github_trending_updates()` 方法**

在 `format_blog_updates()` 方法（约第 731 行）之后，添加新方法：

```python
    @staticmethod
    def format_github_trending_updates() -> list[str]:
        """获取 GitHub Trending 新上榜项目并格式化推送文本"""
        try:
            from app.services.github_trending_service import GitHubTrendingService
            repos = GitHubTrendingService.fetch_trending()
            if not repos:
                return []

            lines = [f'🔥 GitHub Trending 新上榜（{len(repos)}个）']
            for repo in repos:
                lines.append('')
                lines.append(f"⭐ {repo['full_name']} - {repo['description'][:60] if repo['description'] else '无描述'}")
                star_info = f"⭐ {repo['stars']}" if repo['stars'] else ''
                if repo['today_stars']:
                    star_info += f" | 今日 +{repo['today_stars']}"
                if star_info:
                    lines.append(star_info)
                if repo.get('summary'):
                    lines.append(repo['summary'])
                lines.append(f"🔗 {repo['url']}")

            return ['\n'.join(lines)]
        except Exception as e:
            logger.warning(f'[通知.GitHub Trending] 获取失败: {e}')
            return []
```

- [ ] **Step 2: 集成到 `push_daily_report()`**

找到 `push_daily_report()` 中如下代码块（约第 1062-1068 行）：

```python
        # GitHub Release + 博客监控 → news_ai_tool
        blog_texts = NotificationService.format_blog_updates()
        ai_tool_texts = release_texts + blog_texts
```

替换为：

```python
        # GitHub Release + 博客监控 + GitHub Trending → news_ai_tool
        blog_texts = NotificationService.format_blog_updates()
        trending_texts = NotificationService.format_github_trending_updates()
        ai_tool_texts = release_texts + blog_texts + trending_texts
```

- [ ] **Step 3: 集成到 `push_daily_extras()`**

找到 `push_daily_extras()` 中如下代码块（约第 1098-1100 行）：

```python
        release_texts, release_pushed_versions = NotificationService.format_github_release_updates()
        blog_texts = NotificationService.format_blog_updates()
        ai_tool_texts = release_texts + blog_texts
```

替换为：

```python
        release_texts, release_pushed_versions = NotificationService.format_github_release_updates()
        blog_texts = NotificationService.format_blog_updates()
        trending_texts = NotificationService.format_github_trending_updates()
        ai_tool_texts = release_texts + blog_texts + trending_texts
```

- [ ] **Step 4: Commit**

```bash
git add app/services/notification.py
git commit -m "feat: integrate GitHub Trending updates into daily push (news_ai_tool)"
```

---

### Task 5: 环境变量与文档同步

**Files:**
- Modify: `.env.sample`
- Modify: `CLAUDE.md`
- Modify: `README.md`

- [ ] **Step 1: 更新 `.env.sample`**

在博客监控配置段之后（`# BLOG_MONITOR_ENABLED=true` 之后），添加：

```
# ============ GitHub Trending 监控 ============
# 监控 GitHub 每日热门项目，新上榜的推送到 news_ai_tool
# GITHUB_TRENDING_ENABLED=true
# 取前 N 个项目（默认 10）
# GITHUB_TRENDING_TOP_N=10
```

- [ ] **Step 2: 更新 `CLAUDE.md`**

在博客监控配置段之后，添加：

```markdown
## GitHub Trending 监控配置

| 环境变量 | 说明 | 默认值 |
|---------|------|-------|
| `GITHUB_TRENDING_ENABLED` | 是否启用 GitHub Trending 监控 | `true` |
| `GITHUB_TRENDING_TOP_N` | 取前 N 个项目 | `10` |

每日简报时自动爬取 github.com/trending 页面 Top N 项目，与已推送记录比对，仅推送新上榜的项目（含 GLM 中文摘要）到 `news_ai_tool` 频道。首次运行只记录不推送。
```

- [ ] **Step 3: 更新 `README.md`**

在相应位置添加同样的 GitHub Trending 配置说明（与 CLAUDE.md 保持一致）。

- [ ] **Step 4: Commit**

```bash
git add .env.sample CLAUDE.md README.md
git commit -m "docs: add GitHub Trending monitor config to env sample and docs"
```

---

### Task 6: 手动验证

- [ ] **Step 1: 启动应用验证无报错**

```bash
SCHEDULER_ENABLED=0 python -c "from app.services.github_trending_service import GitHubTrendingService; print('import ok')"
```

Expected: `import ok`

- [ ] **Step 2: 验证 HTML 爬取和解析**

```bash
SCHEDULER_ENABLED=0 python -c "
from app.services.github_trending_service import GitHubTrendingService
html = GitHubTrendingService._fetch_html()
repos = GitHubTrendingService._parse_html(html)
for r in repos[:3]:
    print(f\"{r['full_name']} | {r['stars']} | +{r['today_stars']} | {r['description'][:40]}\")
print(f'Total parsed: {len(repos)}')
"
```

Expected: 打印 3 个 repo 信息，`Total parsed: 10`

- [ ] **Step 3: 验证完整流程（首次运行应返回空）**

```bash
SCHEDULER_ENABLED=0 python -c "
from app import create_app
app = create_app()
with app.app_context():
    from app.services.github_trending_service import GitHubTrendingService
    result = GitHubTrendingService.fetch_trending()
    print(f'First run result: {len(result)} (should be 0)')
"
```

Expected: `First run result: 0 (should be 0)`，同时 `data/github_trending_pushed.json` 被创建

- [ ] **Step 4: 验证去重（第二次运行，清空 pushed 文件模拟新项目）**

删除 `data/github_trending_pushed.json` 中部分条目，重新运行验证能检测到"新"项目。

- [ ] **Step 5: Commit 验证通过**

```bash
git add -A
git commit -m "chore: verify GitHub Trending monitor works end-to-end"
```
