# 公司新闻Tab 实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在新闻看板新增第三个Tab「公司」，针对 CompanyKeyword 主动爬取 Google News + 雪球新闻，统一存入 NewsItem，按时间线展示。

**Architecture:** 新建 `CompanyNewsService`，复用 crawl4ai 的 AsyncWebCrawler 爬取 Google News 和雪球搜索页，结果存入 NewsItem（source_name 为 google_news/xueqiu）。在 `poll_news()` 异步触发，与 InterestPipeline 并行。前端新增 company tab，后端 `/news/items?tab=company` 筛选。

**Tech Stack:** crawl4ai (AsyncWebCrawler), GLM Flash (AI摘要), Flask/SQLAlchemy, Bootstrap 5

---

### Task 1: 新增配置项

**Files:**
- Modify: `app/config/news_config.py`
- Modify: `.env.sample`

**Step 1: 修改 news_config.py**

在 `NEWS_SOURCE_LABELS` 中新增两个来源标签，并添加公司新闻配置常量：

```python
NEWS_SOURCE_LABELS = {
    'wallstreetcn': {'label': '华尔街', 'color': 'secondary'},
    'smolai': {'label': 'SmolAI', 'color': 'info'},
    'cls': {'label': '财联社', 'color': 'primary'},
    '36kr': {'label': '36kr', 'color': 'warning'},
    'google_news': {'label': 'Google', 'color': 'danger'},
    'xueqiu': {'label': '雪球', 'color': 'success'},
}

# 公司新闻爬取配置
import os
COMPANY_NEWS_MAX_COMPANIES = int(os.getenv('COMPANY_NEWS_MAX_COMPANIES', '3'))
COMPANY_NEWS_MAX_ARTICLES = int(os.getenv('COMPANY_NEWS_MAX_ARTICLES', '5'))
COMPANY_NEWS_CRAWL_TIMEOUT = 30
COMPANY_NEWS_TOTAL_TIMEOUT = 120
```

**Step 2: 修改 .env.sample**

在新闻看板区域添加：

```
# 公司新闻爬取
# 每次轮询最多处理的公司数，默认 3
# COMPANY_NEWS_MAX_COMPANIES=3
# 每个公司最多爬取文章数，默认 5
# COMPANY_NEWS_MAX_ARTICLES=5
```

**Step 3: Commit**

```bash
git add app/config/news_config.py .env.sample
git commit -m "feat: 公司新闻配置项（source labels + env vars）"
```

---

### Task 2: 创建 CompanyNewsService 爬取服务

**Files:**
- Create: `app/services/company_news_service.py`

**Step 1: 创建 company_news_service.py**

```python
"""公司新闻爬取服务：Google News + 雪球 → crawl4ai 爬取 → AI 摘要 → 存入 NewsItem"""
import asyncio
import hashlib
import logging
import re
from datetime import datetime

from app import db
from app.models.news import NewsItem, CompanyKeyword
from app.config.news_config import (
    COMPANY_NEWS_MAX_COMPANIES, COMPANY_NEWS_MAX_ARTICLES,
    COMPANY_NEWS_CRAWL_TIMEOUT, COMPANY_NEWS_TOTAL_TIMEOUT,
)

logger = logging.getLogger(__name__)

COMPANY_SUMMARY_PROMPT = """将以下新闻文章压缩为50-100字的中文摘要，保留核心事实。直接返回摘要文本。"""


class CompanyNewsService:

    @staticmethod
    def fetch_company_news():
        """主入口：爬取所有活跃公司的相关新闻（后台线程调用）"""
        from app import create_app
        app = create_app()

        with app.app_context():
            companies = CompanyKeyword.query.filter_by(is_active=True).limit(
                COMPANY_NEWS_MAX_COMPANIES
            ).all()
            if not companies:
                return

            company_names = [c.name for c in companies]
            logger.info(f'[公司新闻] 开始爬取: {company_names}')

            try:
                results = asyncio.run(
                    CompanyNewsService._fetch_all(company_names)
                )
                saved = CompanyNewsService._save_results(results)
                logger.info(f'[公司新闻] 完成，新增 {saved} 条')
            except Exception as e:
                logger.error(f'[公司新闻] 爬取失败: {e}')

    @staticmethod
    async def _fetch_all(company_names: list[str]) -> list[dict]:
        """并发爬取所有公司新闻"""
        from crawl4ai import AsyncWebCrawler

        all_results = []
        async with AsyncWebCrawler() as crawler:
            for name in company_names:
                try:
                    results = await asyncio.wait_for(
                        CompanyNewsService._fetch_single_company(crawler, name),
                        timeout=COMPANY_NEWS_TOTAL_TIMEOUT,
                    )
                    all_results.extend(results)
                except asyncio.TimeoutError:
                    logger.warning(f'[公司新闻] {name} 爬取超时')
                except Exception as e:
                    logger.error(f'[公司新闻] {name} 爬取失败: {e}')
        return all_results

    @staticmethod
    async def _fetch_single_company(crawler, company_name: str) -> list[dict]:
        """爬取单个公司的新闻（Google News + 雪球）"""
        results = []

        # Google News 搜索
        google_results = await CompanyNewsService._search_google_news(
            crawler, company_name
        )
        results.extend(google_results)

        # 雪球搜索
        xueqiu_results = await CompanyNewsService._search_xueqiu(
            crawler, company_name
        )
        results.extend(xueqiu_results)

        # 限制每个公司最多 N 条
        return results[:COMPANY_NEWS_MAX_ARTICLES]

    @staticmethod
    async def _search_google_news(crawler, company_name: str) -> list[dict]:
        """Google News 搜索公司新闻"""
        import urllib.parse
        query = urllib.parse.quote(f'{company_name} 新闻')
        search_url = f'https://www.google.com/search?q={query}&tbm=nws'

        try:
            result = await crawler.arun(url=search_url, timeout=COMPANY_NEWS_CRAWL_TIMEOUT)
            if not result.markdown:
                return []

            # 提取URL
            url_pattern = re.compile(r'\[.*?\]\((https?://[^)]+)\)')
            skip_domains = {'google.com', 'youtube.com', 'accounts.google'}
            urls = []
            for match in url_pattern.finditer(result.markdown):
                url = match.group(1)
                if any(d in url for d in skip_domains):
                    continue
                urls.append(url)
                if len(urls) >= 3:
                    break

            # 爬取文章内容
            articles = []
            for url in urls:
                try:
                    article = await crawler.arun(url=url, timeout=COMPANY_NEWS_CRAWL_TIMEOUT)
                    if article.markdown:
                        articles.append({
                            'url': url,
                            'content': article.markdown[:2000],
                            'source_name': 'google_news',
                            'company': company_name,
                        })
                except Exception:
                    continue
            return articles
        except Exception as e:
            logger.error(f'[公司新闻] Google搜索失败 ({company_name}): {e}')
            return []

    @staticmethod
    async def _search_xueqiu(crawler, company_name: str) -> list[dict]:
        """雪球搜索公司新闻"""
        import urllib.parse
        query = urllib.parse.quote(company_name)
        search_url = f'https://xueqiu.com/k?q={query}'

        try:
            result = await crawler.arun(url=search_url, timeout=COMPANY_NEWS_CRAWL_TIMEOUT)
            if not result.markdown:
                return []

            # 提取雪球文章链接
            url_pattern = re.compile(r'\[.*?\]\((https?://xueqiu\.com/\d+/\d+)\)')
            urls = []
            for match in url_pattern.finditer(result.markdown):
                urls.append(match.group(1))
                if len(urls) >= 3:
                    break

            articles = []
            for url in urls:
                try:
                    article = await crawler.arun(url=url, timeout=COMPANY_NEWS_CRAWL_TIMEOUT)
                    if article.markdown:
                        articles.append({
                            'url': url,
                            'content': article.markdown[:2000],
                            'source_name': 'xueqiu',
                            'company': company_name,
                        })
                except Exception:
                    continue
            return articles
        except Exception as e:
            logger.error(f'[公司新闻] 雪球搜索失败 ({company_name}): {e}')
            return []

    @staticmethod
    def _save_results(results: list[dict]) -> int:
        """AI 摘要并存入 NewsItem"""
        from app.llm.router import llm_router

        saved = 0
        provider = llm_router.route('news_classify')

        for item in results:
            url_hash = hashlib.md5(item['url'].encode()).hexdigest()[:16]
            source_name = item['source_name']

            # 去重
            existing = NewsItem.query.filter_by(
                source_id=url_hash, source_name=source_name
            ).first()
            if existing:
                continue

            # AI 摘要
            content = item['content'][:500]
            if provider:
                try:
                    summary = provider.chat([
                        {'role': 'system', 'content': COMPANY_SUMMARY_PROMPT},
                        {'role': 'user', 'content': item['content'][:1500]},
                    ], temperature=0.3, max_tokens=200).strip()
                    if summary:
                        content = summary
                except Exception as e:
                    logger.error(f'[公司新闻] AI摘要失败: {e}')

            news = NewsItem(
                source_id=url_hash,
                source_name=source_name,
                content=content,
                display_time=datetime.now(),
                score=1,
                is_interest=True,
                matched_keywords=item['company'],
            )
            db.session.add(news)
            saved += 1

        if saved:
            db.session.commit()
        return saved
```

**Step 2: Commit**

```bash
git add app/services/company_news_service.py
git commit -m "feat: CompanyNewsService 公司新闻爬取服务"
```

---

### Task 3: 集成到 poll_news 触发链路

**Files:**
- Modify: `app/services/news_service.py:110-129`

**Step 1: 在 poll_news() 中添加异步触发**

在 `poll_news()` 方法中，与 InterestPipeline 并行提交 CompanyNewsService：

```python
@staticmethod
def poll_news() -> tuple[list[dict], int]:
    """拉取所有源最新快讯并返回新增条目"""
    raw_items = NewsService.fetch_all_sources()
    if not raw_items:
        return [], 0

    new_items = NewsService.save_news_items(raw_items)
    logger.info(f'[新闻] 新增 {len(new_items)} 条（共获取 {len(raw_items)} 条）')
    if not new_items:
        return [], 0

    # 异步执行分类流水线（不阻塞返回）
    from app.services.interest_pipeline import InterestPipeline
    item_ids = [n.id for n in new_items]
    _executor.submit(InterestPipeline.process_new_items, item_ids)

    # 异步执行公司新闻爬取（不阻塞返回）
    from app.services.company_news_service import CompanyNewsService
    _executor.submit(CompanyNewsService.fetch_company_news)

    _executor.submit(NewsService._notify_slack, [n.content for n in new_items])

    items_data = [NewsService._item_to_dict(n) for n in new_items]
    return items_data, len(new_items)
```

**Step 2: Commit**

```bash
git add app/services/news_service.py
git commit -m "feat: poll_news 集成公司新闻爬取"
```

---

### Task 4: 后端 company tab 筛选

**Files:**
- Modify: `app/services/news_service.py:62-70` (get_news_items 方法)

**Step 1: 在 get_news_items 中添加 company tab 筛选逻辑**

```python
@staticmethod
def get_news_items(tab='all', limit=30, before_id=None) -> list[dict]:
    """分页查询快讯"""
    query = NewsItem.query
    if tab == 'interest':
        query = query.filter(NewsItem.is_interest == True)
    elif tab == 'company':
        # 筛选 matched_keywords 中包含任意活跃 CompanyKeyword 的记录
        from app.models.news import CompanyKeyword
        companies = CompanyKeyword.query.filter_by(is_active=True).all()
        if companies:
            conditions = [NewsItem.matched_keywords.contains(c.name) for c in companies]
            from sqlalchemy import or_
            query = query.filter(or_(*conditions))
        else:
            return []
    if before_id:
        query = query.filter(NewsItem.id < before_id)
    items = query.order_by(NewsItem.display_time.desc()).limit(limit).all()
    return [NewsService._item_to_dict(n) for n in items]
```

**Step 2: Commit**

```bash
git add app/services/news_service.py
git commit -m "feat: get_news_items 支持 company tab 筛选"
```

---

### Task 5: 前端新增公司Tab

**Files:**
- Modify: `app/templates/news.html:82-89` (tab 栏)
- Modify: `app/static/js/news.js:1-6` (NEWS_SOURCE_LABELS)
- Modify: `app/static/js/news.js:115-137` (poll 方法中公司tab处理)

**Step 1: 修改 news.html — 添加公司 tab**

在 `#newsTabs` 的 `<ul>` 中添加第三个 tab：

```html
<ul class="nav nav-tabs mb-3" id="newsTabs">
    <li class="nav-item">
        <a class="nav-link active" data-tab="all" href="#">全部</a>
    </li>
    <li class="nav-item">
        <a class="nav-link" data-tab="interest" href="#">兴趣</a>
    </li>
    <li class="nav-item">
        <a class="nav-link" data-tab="company" href="#">公司</a>
    </li>
</ul>
```

**Step 2: 修改 news.js — 添加来源标签**

```javascript
const NEWS_SOURCE_LABELS = {
    wallstreetcn: { label: '华尔街', color: 'secondary' },
    smolai: { label: 'SmolAI', color: 'info' },
    cls: { label: '财联社', color: 'primary' },
    '36kr': { label: '36kr', color: 'warning' },
    google_news: { label: 'Google', color: 'danger' },
    xueqiu: { label: '雪球', color: 'success' },
};
```

**Step 3: 修改 news.js poll() — 公司tab轮询行为**

公司tab与兴趣tab类似，poll 时从 DB 重新加载（因为 CompanyNewsService 异步处理）：

在 `poll()` 方法中，将 `if (this.currentTab === 'interest')` 改为：

```javascript
if (this.currentTab === 'interest' || this.currentTab === 'company') {
    await this.loadItems();
}
```

**Step 4: Commit**

```bash
git add app/templates/news.html app/static/js/news.js
git commit -m "feat: 前端新增公司Tab + 来源标签"
```

---

### Task 6: 更新文档

**Files:**
- Modify: `CLAUDE.md`
- Modify: `README.md`（如果有新闻看板相关段落）

**Step 1: 更新 CLAUDE.md**

在环境变量表格区域添加公司新闻配置：

```markdown
## 公司新闻配置

| 环境变量 | 说明 | 默认值 |
|---------|------|-------|
| `COMPANY_NEWS_MAX_COMPANIES` | 每次轮询最多处理的公司数 | `3` |
| `COMPANY_NEWS_MAX_ARTICLES` | 每个公司最多爬取文章数 | `5` |
```

**Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: 更新公司新闻配置文档"
```
