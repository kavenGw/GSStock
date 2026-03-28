# 博客监控推送 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 监控 Anthropic/OpenAI/DeepMind 技术博客，新文章自动生成中文摘要推送到 Slack `news_ai_tool` 频道。

**Architecture:** 配置驱动的博客监控服务，RSS 优先 + HTML 兜底。集成到现有每日简报流程，与 GitHub Release 并列推送到 `news_ai_tool`。

**Tech Stack:** feedparser（已有）、requests（已有）、crawl4ai（已有）、GLM Flash（已有 LLM 路由）

**Spec:** `docs/plans/2026-03-28-blog-monitor-design.md`

---

### Task 1: 博客源配置

**Files:**
- Create: `app/config/blog_monitor.py`

- [ ] **Step 1: 创建配置文件**

```python
"""技术博客监控配置"""
import os

BLOG_MONITOR_ENABLED = os.environ.get('BLOG_MONITOR_ENABLED', 'true').lower() == 'true'

BLOG_SOURCES = [
    {
        'key': 'anthropic_engineering',
        'name': 'Anthropic Engineering',
        'type': 'html',
        'list_url': 'https://www.anthropic.com/engineering',
        'base_url': 'https://www.anthropic.com',
        'enabled': True,
    },
    {
        'key': 'openai_blog',
        'name': 'OpenAI Blog',
        'type': 'rss',
        'feed_url': 'https://openai.com/blog/rss.xml',
        'enabled': True,
    },
    {
        'key': 'deepmind_blog',
        'name': 'DeepMind Blog',
        'type': 'rss',
        'feed_url': 'https://deepmind.google/blog/feed/',
        'enabled': True,
    },
]
```

- [ ] **Step 2: Commit**

```bash
git add app/config/blog_monitor.py
git commit -m "feat: 添加博客监控配置"
```

---

### Task 2: LLM Prompt

**Files:**
- Create: `app/llm/prompts/blog_summary.py`

- [ ] **Step 1: 创建博客摘要 prompt**

参照 `app/llm/prompts/github_release_update.py` 的模式：

```python
"""技术博客文章摘要 Prompt"""

BLOG_SUMMARY_SYSTEM_PROMPT = (
    "你是技术博客摘要助手。根据文章内容生成简洁的中文摘要。"
)


def build_blog_summary_prompt(title: str, content: str) -> str:
    """构建博客文章摘要 prompt"""
    # 截断过长内容
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
```

- [ ] **Step 2: 在 LLM 路由中注册任务类型**

修改 `app/llm/router.py:9` 的 `TASK_LAYER_MAP`，在 `'github_release_update': LLMLayer.FLASH` 后面添加：

```python
'blog_summary': LLMLayer.FLASH,
```

- [ ] **Step 3: Commit**

```bash
git add app/llm/prompts/blog_summary.py app/llm/router.py
git commit -m "feat: 添加博客摘要 LLM prompt 和路由"
```

---

### Task 3: BlogMonitorService 核心服务

**Files:**
- Create: `app/services/blog_monitor_service.py`

- [ ] **Step 1: 创建服务文件 — 导入和常量**

```python
"""技术博客监控服务 — 检测新文章并生成中文摘要"""
import asyncio
import json
import logging
import os
import re
import ssl

import certifi
import feedparser
import requests

from app.config.blog_monitor import BLOG_SOURCES, BLOG_MONITOR_ENABLED

logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data')
FETCH_TIMEOUT = 15
```

- [ ] **Step 2: 实现已推送记录的读写**

```python
class BlogMonitorService:

    @staticmethod
    def _get_pushed(key: str) -> set[str]:
        """读取已推送 URL 集合"""
        filepath = os.path.join(DATA_DIR, f'blog_monitor_{key}_pushed.json')
        try:
            if os.path.exists(filepath):
                with open(filepath, 'r', encoding='utf-8') as f:
                    return set(json.load(f))
        except Exception as e:
            logger.warning(f'[博客监控] 读取 {key} 已推送记录失败: {e}')
        return set()

    @staticmethod
    def _mark_pushed(key: str, urls: list[str]):
        """追加写入已推送记录"""
        filepath = os.path.join(DATA_DIR, f'blog_monitor_{key}_pushed.json')
        existing = BlogMonitorService._get_pushed(key)
        existing.update(urls)
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(list(existing), f, ensure_ascii=False)
        except Exception as e:
            logger.warning(f'[博客监控] 写入 {key} 已推送记录失败: {e}')
```

- [ ] **Step 3: 实现 RSS 获取**

```python
    @staticmethod
    def _fetch_rss(source: dict) -> list[dict]:
        """feedparser 解析 RSS，返回文章列表"""
        try:
            feed = feedparser.parse(source['feed_url'])
            articles = []
            for entry in feed.entries[:20]:
                articles.append({
                    'title': entry.get('title', ''),
                    'url': entry.get('link', ''),
                    'summary': entry.get('summary', '')[:200] if entry.get('summary') else '',
                })
            return articles
        except Exception as e:
            logger.warning(f"[博客监控] RSS 获取失败 {source['name']}: {e}")
            return []
```

- [ ] **Step 4: 实现 Anthropic HTML 解析**

```python
    @staticmethod
    def _fetch_html_anthropic(source: dict) -> list[dict]:
        """requests + 正则解析 Anthropic Engineering 页面"""
        try:
            resp = requests.get(
                source['list_url'],
                headers={'User-Agent': 'Mozilla/5.0 (compatible; stock-bot/1.0)'},
                timeout=FETCH_TIMEOUT,
            )
            resp.raise_for_status()
            html = resp.text

            articles = []
            # 匹配 /engineering/xxx 链接和标题
            pattern = r'href="(/engineering/[a-z0-9-]+)"[^>]*>([^<]+)<'
            seen_urls = set()
            for match in re.finditer(pattern, html):
                path, title = match.group(1), match.group(2).strip()
                if not title or path in seen_urls:
                    continue
                seen_urls.add(path)
                url = source['base_url'] + path
                articles.append({
                    'title': title,
                    'url': url,
                    'summary': '',
                })

            return articles
        except Exception as e:
            logger.warning(f"[博客监控] HTML 获取失败 {source['name']}: {e}")
            return []
```

- [ ] **Step 5: 实现全文抓取**

```python
    @staticmethod
    def _fetch_full_content(url: str) -> str:
        """crawl4ai 抓取文章全文"""
        try:
            from crawl4ai import AsyncWebCrawler

            async def _fetch():
                async with AsyncWebCrawler() as crawler:
                    result = await asyncio.wait_for(
                        crawler.arun(url=url),
                        timeout=FETCH_TIMEOUT,
                    )
                    if result and result.markdown:
                        return result.markdown[:3000]
                return ''

            return asyncio.run(_fetch())
        except ImportError:
            logger.warning('[博客监控] crawl4ai 不可用')
            return ''
        except Exception as e:
            logger.warning(f'[博客监控] 全文抓取失败 {url}: {e}')
            return ''
```

- [ ] **Step 6: 实现 LLM 摘要**

```python
    @staticmethod
    def _summarize(title: str, content: str) -> str:
        """GLM Flash 生成中文摘要"""
        try:
            from app.llm.router import llm_router
            from app.llm.prompts.blog_summary import (
                BLOG_SUMMARY_SYSTEM_PROMPT, build_blog_summary_prompt,
            )

            provider = llm_router.route('blog_summary')
            if not provider:
                return ''

            prompt = build_blog_summary_prompt(title, content)
            summary = provider.chat(
                [
                    {'role': 'system', 'content': BLOG_SUMMARY_SYSTEM_PROMPT},
                    {'role': 'user', 'content': prompt},
                ],
                temperature=0.3,
                max_tokens=300,
            )
            return summary.strip()
        except Exception as e:
            logger.warning(f'[博客监控] LLM 摘要失败: {e}')
            return ''
```

- [ ] **Step 7: 实现主入口 check_all_blogs()**

```python
    @staticmethod
    def check_all_blogs() -> list[dict]:
        """遍历所有博客源，返回新文章列表（含摘要）"""
        if not BLOG_MONITOR_ENABLED:
            return []

        all_new = []
        for source in BLOG_SOURCES:
            if not source.get('enabled'):
                continue

            key = source['key']
            source_type = source['type']

            # 获取文章列表
            if source_type == 'rss':
                articles = BlogMonitorService._fetch_rss(source)
            elif source_type == 'html':
                articles = BlogMonitorService._fetch_html_anthropic(source)
            else:
                logger.warning(f"[博客监控] 未知类型 {source_type}")
                continue

            if not articles:
                continue

            # 对比已推送记录
            pushed = BlogMonitorService._get_pushed(key)
            article_urls = [a['url'] for a in articles]

            if not pushed:
                # 首次运行：记录当前文章，不推送
                logger.info(f"[博客监控] {source['name']} 首次运行，记录 {len(article_urls)} 篇文章")
                BlogMonitorService._mark_pushed(key, article_urls)
                continue

            new_articles = [a for a in articles if a['url'] not in pushed]
            if not new_articles:
                continue

            logger.info(f"[博客监控] {source['name']} 发现 {len(new_articles)} 篇新文章")

            # 抓取全文 + LLM 摘要
            for article in new_articles:
                content = BlogMonitorService._fetch_full_content(article['url'])
                if content:
                    summary = BlogMonitorService._summarize(article['title'], content)
                    article['summary'] = summary or article.get('summary', '')
                all_new.append({
                    'source_name': source['name'],
                    'title': article['title'],
                    'url': article['url'],
                    'summary': article.get('summary', ''),
                })

            # 标记已推送
            BlogMonitorService._mark_pushed(key, [a['url'] for a in new_articles])

        return all_new
```

- [ ] **Step 8: Commit**

```bash
git add app/services/blog_monitor_service.py
git commit -m "feat: 实现 BlogMonitorService 核心服务"
```

---

### Task 4: 集成到 NotificationService

**Files:**
- Modify: `app/services/notification.py:658` (format_github_release_updates 附近)
- Modify: `app/services/notification.py:1028-1032` (push_daily_report 中 GitHub Release 推送)
- Modify: `app/services/notification.py:1061-1066` (push_daily_extras 中 GitHub Release 推送)

- [ ] **Step 1: 添加 format_blog_updates() 方法**

在 `notification.py` 的 `format_github_release_updates()` 方法（约 L712）后面添加：

```python
    @staticmethod
    def format_blog_updates() -> list[str]:
        """获取新博客文章并格式化推送文本"""
        try:
            from app.services.blog_monitor_service import BlogMonitorService
            articles = BlogMonitorService.check_all_blogs()
            texts = []
            for article in articles:
                text = f"📝 {article['source_name']} 新文章\n{article['title']}"
                if article.get('summary'):
                    text += f"\n\n{article['summary']}"
                text += f"\n\n🔗 {article['url']}"
                texts.append(text)
            return texts
        except Exception as e:
            logger.warning(f'[通知.博客监控] 获取失败: {e}')
            return []
```

- [ ] **Step 2: 修改 push_daily_report() 中 news_ai_tool 推送**

找到 `push_daily_report()` 中约 L1028-1032 的代码：

```python
        # GitHub Release → news_ai_tool
        if release_texts:
            release_msg = '\n\n'.join(release_texts)
            if NotificationService.send_slack(release_msg, CHANNEL_AI_TOOL):
                sent += 1
```

替换为：

```python
        # GitHub Release + 博客监控 → news_ai_tool
        blog_texts = NotificationService.format_blog_updates()
        ai_tool_texts = release_texts + blog_texts
        if ai_tool_texts:
            ai_tool_msg = '\n\n'.join(ai_tool_texts)
            if NotificationService.send_slack(ai_tool_msg, CHANNEL_AI_TOOL):
                sent += 1
```

- [ ] **Step 3: 修改 push_daily_extras() 中 news_ai_tool 推送**

找到 `push_daily_extras()` 中约 L1061-1066 的代码：

```python
        # GitHub Release → news_ai_tool
        release_texts, release_pushed_versions = NotificationService.format_github_release_updates()
        if release_texts:
            release_msg = '\n\n'.join(release_texts)
            if NotificationService.send_slack(release_msg, CHANNEL_AI_TOOL):
                sent += 1
```

替换为：

```python
        # GitHub Release + 博客监控 → news_ai_tool
        release_texts, release_pushed_versions = NotificationService.format_github_release_updates()
        blog_texts = NotificationService.format_blog_updates()
        ai_tool_texts = release_texts + blog_texts
        if ai_tool_texts:
            ai_tool_msg = '\n\n'.join(ai_tool_texts)
            if NotificationService.send_slack(ai_tool_msg, CHANNEL_AI_TOOL):
                sent += 1
```

- [ ] **Step 4: Commit**

```bash
git add app/services/notification.py
git commit -m "feat: 集成博客监控到每日简报推送"
```

---

### Task 5: 配置文档同步

**Files:**
- Modify: `CLAUDE.md`
- Modify: `.env.sample`

- [ ] **Step 1: 更新 CLAUDE.md**

在 `## 研报推送配置` 部分后面添加：

```markdown
## 博客监控配置

| 环境变量 | 说明 | 默认值 |
|---------|------|-------|
| `BLOG_MONITOR_ENABLED` | 是否启用博客监控 | `true` |

每日简报时自动检查 Anthropic Engineering / OpenAI Blog / DeepMind Blog 新文章，crawl4ai 抓取全文 + GLM 中文摘要，推送到 `news_ai_tool` 频道。博客源配置在 `app/config/blog_monitor.py`。
```

- [ ] **Step 2: 更新 .env.sample**

在研报推送配置部分后面添加：

```
# ============ 博客监控 ============
# 监控 AI 公司技术博客（Anthropic/OpenAI/DeepMind），新文章推送到 news_ai_tool
# BLOG_MONITOR_ENABLED=true
```

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md .env.sample
git commit -m "docs: 添加博客监控配置说明"
```
