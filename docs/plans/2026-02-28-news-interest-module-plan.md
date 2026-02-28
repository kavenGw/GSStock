# 新闻看板兴趣模块 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 完善新闻看板兴趣模块——自定义关键词匹配、GLM 智能分类打分、按重要性分级衍生搜索、多新闻源整合、AI 关键词推荐。

**Architecture:** 同步流水线 + 后台衍生。多源并行拉取→合并去重入库→GLM 批量分类打分→关键词匹配→标记兴趣→高分条目后台 crawl4ai 衍生搜索→GLM 整理专题。

**Tech Stack:** Flask + SQLAlchemy + SQLite, crawl4ai (async web crawler), feedparser (RSS), 智谱 GLM Flash/Premium, ThreadPoolExecutor

---

## Task 1: 安装新依赖

**Files:**
- Modify: `requirements.txt`

**Step 1: 添加依赖**

在 `requirements.txt` 末尾添加：

```
crawl4ai>=0.8.0
feedparser>=6.0.0
```

**Step 2: 安装**

Run: `pip install crawl4ai feedparser`

**Step 3: 初始化 crawl4ai 浏览器**

Run: `crawl4ai-setup`

(安装 Playwright 浏览器，crawl4ai 需要)

**Step 4: Commit**

```bash
git add requirements.txt
git commit -m "chore: add crawl4ai and feedparser dependencies"
```

---

## Task 2: 数据模型变更

**Files:**
- Modify: `app/models/news.py`
- Modify: `app/models/__init__.py`

**Step 1: 修改 NewsItem 模型，新增 InterestKeyword 和 NewsDerivation，删除 NewsBriefing**

`app/models/news.py` 完整重写为：

```python
from datetime import datetime
from app import db


class NewsItem(db.Model):
    __tablename__ = 'news_item'
    __table_args__ = (
        db.UniqueConstraint('source_id', 'source_name', name='uq_news_source'),
    )

    id = db.Column(db.Integer, primary_key=True)
    source_id = db.Column(db.String(100), nullable=False)
    source_name = db.Column(db.String(50), default='wallstreetcn')
    content = db.Column(db.Text, nullable=False)
    display_time = db.Column(db.DateTime, nullable=False)
    score = db.Column(db.Integer, default=1)
    category = db.Column(db.String(20), default='other')
    importance = db.Column(db.Integer, default=0)
    is_interest = db.Column(db.Boolean, default=False)
    matched_keywords = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.now)

    derivations = db.relationship('NewsDerivation', backref='news_item', lazy='dynamic')


class InterestKeyword(db.Model):
    __tablename__ = 'interest_keyword'

    id = db.Column(db.Integer, primary_key=True)
    keyword = db.Column(db.Text, nullable=False)
    source = db.Column(db.String(10), default='user')
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.now)


class NewsDerivation(db.Model):
    __tablename__ = 'news_derivation'

    id = db.Column(db.Integer, primary_key=True)
    news_item_id = db.Column(db.Integer, db.ForeignKey('news_item.id'), nullable=False)
    search_query = db.Column(db.Text)
    sources = db.Column(db.JSON)
    summary = db.Column(db.Text)
    importance = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.now)
```

**Step 2: 更新 models/__init__.py**

`app/models/__init__.py` — 替换 NewsItem/NewsBriefing 导入行：

```python
from app.models.news import NewsItem, InterestKeyword, NewsDerivation
```

在 `__all__` 列表中：移除 `'NewsBriefing'`，添加 `'InterestKeyword'`, `'NewsDerivation'`。

**Step 3: 数据库迁移**

由于项目用 SQLite 且无 Alembic，需手动处理。在 `run.py` 中 `db.create_all()` 会创建新表。对于 NewsItem 的新字段和约束变更，需要执行 SQL：

```sql
-- 添加新字段
ALTER TABLE news_item ADD COLUMN source_name TEXT DEFAULT 'wallstreetcn';
ALTER TABLE news_item ADD COLUMN importance INTEGER DEFAULT 0;
ALTER TABLE news_item ADD COLUMN is_interest BOOLEAN DEFAULT 0;
ALTER TABLE news_item ADD COLUMN matched_keywords TEXT;

-- 移除旧的唯一约束并添加新的联合唯一约束
-- SQLite 不支持 ALTER 约束，source_id 原有 unique 约束保留即可
-- 新的联合约束由 SQLAlchemy 在新表创建时生效

-- 删除废弃表
DROP TABLE IF EXISTS news_briefing;
```

将此写为 `scripts/migrate_news.py`：

```python
"""新闻模块数据库迁移脚本"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'stock.db')

def migrate():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # 添加新字段（忽略已存在的错误）
    for sql in [
        "ALTER TABLE news_item ADD COLUMN source_name TEXT DEFAULT 'wallstreetcn'",
        "ALTER TABLE news_item ADD COLUMN importance INTEGER DEFAULT 0",
        "ALTER TABLE news_item ADD COLUMN is_interest BOOLEAN DEFAULT 0",
        "ALTER TABLE news_item ADD COLUMN matched_keywords TEXT",
    ]:
        try:
            c.execute(sql)
        except sqlite3.OperationalError:
            pass

    # 删除废弃表
    c.execute("DROP TABLE IF EXISTS news_briefing")

    conn.commit()
    conn.close()
    print("Migration complete.")

if __name__ == '__main__':
    migrate()
```

**Step 4: 运行迁移并验证**

Run: `python scripts/migrate_news.py`
Run: `python -c "from app import create_app; app = create_app(); ctx = app.app_context(); ctx.push(); from app import db; db.create_all(); print('OK')"`

**Step 5: Commit**

```bash
git add app/models/news.py app/models/__init__.py scripts/migrate_news.py
git commit -m "feat: add InterestKeyword/NewsDerivation models, extend NewsItem, remove NewsBriefing"
```

---

## Task 3: 新闻源抽象层

**Files:**
- Create: `app/services/news_sources/__init__.py`
- Create: `app/services/news_sources/base.py`
- Create: `app/services/news_sources/wallstreetcn.py`
- Create: `app/services/news_sources/smolai.py`
- Create: `app/services/news_sources/cls.py` (财联社)
- Create: `app/services/news_sources/kr36.py`
- Modify: `app/config/news_config.py`

**Step 1: 创建基类**

`app/services/news_sources/base.py`:

```python
"""新闻源基类"""
from abc import ABC, abstractmethod


class NewsSourceBase(ABC):
    name: str = ''

    @abstractmethod
    def fetch_latest(self) -> list[dict]:
        """获取最新新闻，返回统一格式:
        [{
            'content': str,       # 新闻正文
            'source_id': str,     # 源内唯一ID
            'display_time': float, # Unix时间戳
            'source_name': str,   # 源标识
            'score': int,         # 重要性(1-2)
        }]
        """
        ...
```

**Step 2: 迁移华尔街见闻源**

`app/services/news_sources/wallstreetcn.py`:

```python
"""华尔街见闻新闻源"""
import logging
import requests
from app.config.news_config import WALLSTREETCN_API, WALLSTREETCN_CHANNEL
from app.services.news_sources.base import NewsSourceBase

logger = logging.getLogger(__name__)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}


class WallstreetcnSource(NewsSourceBase):
    name = 'wallstreetcn'

    def fetch_latest(self) -> list[dict]:
        params = {
            'channel': WALLSTREETCN_CHANNEL,
            'client': 'pc',
            'limit': 20,
        }
        try:
            resp = requests.get(WALLSTREETCN_API, params=params, headers=HEADERS, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            if data.get('code') != 20000:
                logger.warning(f'华尔街见闻API异常: {data.get("message")}')
                return []
            items = data.get('data', {}).get('items', [])
            return [{
                'content': item.get('content_text', ''),
                'source_id': str(item.get('id', '')),
                'display_time': item.get('display_time', 0),
                'source_name': self.name,
                'score': item.get('score', 1),
            } for item in items if item.get('id')]
        except Exception as e:
            logger.error(f'华尔街见闻获取失败: {e}')
            return []
```

**Step 3: 创建 smol.ai RSS 源**

`app/services/news_sources/smolai.py`:

```python
"""smol.ai AI新闻源 (RSS)"""
import logging
import hashlib
from datetime import datetime
from time import mktime
import feedparser
from app.services.news_sources.base import NewsSourceBase

logger = logging.getLogger(__name__)

SMOLAI_RSS_URL = 'https://news.smol.ai/rss.xml'


class SmolAISource(NewsSourceBase):
    name = 'smolai'

    def fetch_latest(self) -> list[dict]:
        try:
            feed = feedparser.parse(SMOLAI_RSS_URL)
            if feed.bozo and not feed.entries:
                logger.warning(f'smol.ai RSS解析异常: {feed.bozo_exception}')
                return []
            results = []
            for entry in feed.entries[:20]:
                title = entry.get('title', '')
                summary = entry.get('summary', '')
                content = f"{title}. {summary}" if summary else title
                source_id = entry.get('id') or hashlib.md5(title.encode()).hexdigest()
                published = entry.get('published_parsed')
                ts = mktime(published) if published else datetime.now().timestamp()
                results.append({
                    'content': content,
                    'source_id': str(source_id),
                    'display_time': ts,
                    'source_name': self.name,
                    'score': 1,
                })
            return results
        except Exception as e:
            logger.error(f'smol.ai获取失败: {e}')
            return []
```

**Step 4: 创建财联社源**

`app/services/news_sources/cls.py`:

```python
"""财联社新闻源"""
import logging
import requests
from app.services.news_sources.base import NewsSourceBase

logger = logging.getLogger(__name__)

CLS_API = 'https://www.cls.cn/nodeapi/updateTelegraph'
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Referer': 'https://www.cls.cn/',
}


class CLSSource(NewsSourceBase):
    name = 'cls'

    def fetch_latest(self) -> list[dict]:
        try:
            resp = requests.get(CLS_API, headers=HEADERS, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            items = data.get('data', {}).get('roll_data', [])
            results = []
            for item in items[:20]:
                content = item.get('content', '') or item.get('title', '')
                if not content:
                    continue
                results.append({
                    'content': content,
                    'source_id': str(item.get('id', '')),
                    'display_time': item.get('ctime', 0),
                    'source_name': self.name,
                    'score': 2 if item.get('level') == 'B' else 1,
                })
            return results
        except Exception as e:
            logger.error(f'财联社获取失败: {e}')
            return []
```

**Step 5: 创建 36kr RSS 源**

`app/services/news_sources/kr36.py`:

```python
"""36kr新闻源 (RSS)"""
import logging
import hashlib
from datetime import datetime
from time import mktime
import feedparser
from app.services.news_sources.base import NewsSourceBase

logger = logging.getLogger(__name__)

KR36_RSS_URL = 'https://36kr.com/feed'


class Kr36Source(NewsSourceBase):
    name = '36kr'

    def fetch_latest(self) -> list[dict]:
        try:
            feed = feedparser.parse(KR36_RSS_URL)
            if feed.bozo and not feed.entries:
                logger.warning(f'36kr RSS解析异常: {feed.bozo_exception}')
                return []
            results = []
            for entry in feed.entries[:20]:
                title = entry.get('title', '')
                source_id = entry.get('id') or hashlib.md5(title.encode()).hexdigest()
                published = entry.get('published_parsed')
                ts = mktime(published) if published else datetime.now().timestamp()
                results.append({
                    'content': title,
                    'source_id': str(source_id),
                    'display_time': ts,
                    'source_name': self.name,
                    'score': 1,
                })
            return results
        except Exception as e:
            logger.error(f'36kr获取失败: {e}')
            return []
```

**Step 6: 创建 __init__.py 注册所有源**

`app/services/news_sources/__init__.py`:

```python
"""新闻源注册"""
from app.services.news_sources.wallstreetcn import WallstreetcnSource
from app.services.news_sources.smolai import SmolAISource
from app.services.news_sources.cls import CLSSource
from app.services.news_sources.kr36 import Kr36Source

ALL_SOURCES = [
    WallstreetcnSource(),
    SmolAISource(),
    CLSSource(),
    Kr36Source(),
]
```

**Step 7: 更新 news_config.py**

`app/config/news_config.py` 完整重写为：

```python
"""新闻看板配置"""

WALLSTREETCN_API = 'https://api-prod.wallstreetcn.com/apiv1/content/lives'
WALLSTREETCN_CHANNEL = 'global-channel'

NEWS_SOURCE_LABELS = {
    'wallstreetcn': {'label': '华尔街', 'color': 'secondary'},
    'smolai': {'label': 'SmolAI', 'color': 'info'},
    'cls': {'label': '财联社', 'color': 'primary'},
    '36kr': {'label': '36kr', 'color': 'warning'},
}

MAX_DERIVATION_PER_POLL = 2
DERIVATION_URL_TIMEOUT = 30
DERIVATION_TOTAL_TIMEOUT = 120
```

**Step 8: Commit**

```bash
git add app/services/news_sources/ app/config/news_config.py
git commit -m "feat: add multi-source news abstraction layer (wallstreetcn, smolai, cls, 36kr)"
```

---

## Task 4: 重构 NewsService 使用多源

**Files:**
- Modify: `app/services/news_service.py`

**Step 1: 重写 news_service.py**

```python
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from app import db
from app.models.news import NewsItem
from app.services.news_sources import ALL_SOURCES

logger = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=4)


class NewsService:

    @staticmethod
    def fetch_all_sources() -> list[dict]:
        """并行获取所有新闻源"""
        all_items = []
        futures = {_executor.submit(src.fetch_latest): src.name for src in ALL_SOURCES}
        for future in as_completed(futures, timeout=15):
            source_name = futures[future]
            try:
                items = future.result()
                all_items.extend(items)
                logger.info(f'[新闻] {source_name} 获取 {len(items)} 条')
            except Exception as e:
                logger.error(f'[新闻] {source_name} 获取失败: {e}')
        return all_items

    @staticmethod
    def save_news_items(items: list[dict]) -> list[NewsItem]:
        """批量存储，按 (source_id, source_name) 去重"""
        new_items = []
        for item in items:
            source_id = item.get('source_id')
            source_name = item.get('source_name', 'unknown')
            if not source_id:
                continue
            existing = NewsItem.query.filter_by(
                source_id=str(source_id), source_name=source_name
            ).first()
            if existing:
                continue
            display_time = item.get('display_time', 0)
            if isinstance(display_time, (int, float)):
                display_time = datetime.fromtimestamp(display_time)
            news = NewsItem(
                source_id=str(source_id),
                source_name=source_name,
                content=item.get('content', ''),
                display_time=display_time,
                score=item.get('score', 1),
            )
            db.session.add(news)
            new_items.append(news)
        if new_items:
            db.session.commit()
        return new_items

    @staticmethod
    def get_news_items(tab='all', limit=30, before_id=None) -> list[dict]:
        """分页查询快讯"""
        query = NewsItem.query
        if tab == 'interest':
            query = query.filter(NewsItem.is_interest == True)
        if before_id:
            query = query.filter(NewsItem.id < before_id)
        items = query.order_by(NewsItem.display_time.desc()).limit(limit).all()
        return [NewsService._item_to_dict(n) for n in items]

    @staticmethod
    def _item_to_dict(n: NewsItem) -> dict:
        return {
            'id': n.id,
            'source_id': n.source_id,
            'source_name': n.source_name or 'wallstreetcn',
            'content': n.content,
            'display_time': n.display_time.strftime('%H:%M') if n.display_time else '',
            'display_date': n.display_time.strftime('%Y-%m-%d') if n.display_time else '',
            'score': n.score,
            'category': n.category or 'other',
            'importance': n.importance,
            'is_interest': n.is_interest,
            'matched_keywords': n.matched_keywords or '',
        }

    @staticmethod
    def summarize_items(item_ids: list[int]) -> str | None:
        items = NewsItem.query.filter(NewsItem.id.in_(item_ids)).all()
        if not items:
            return None
        from app.llm.router import llm_router
        from app.llm.prompts.news_briefing import SUMMARIZE_SYSTEM_PROMPT, build_summarize_prompt
        provider = llm_router.route('news_briefing')
        if not provider:
            return None
        items_data = [{'content': n.content} for n in items]
        try:
            response = provider.chat([
                {'role': 'system', 'content': SUMMARIZE_SYSTEM_PROMPT},
                {'role': 'user', 'content': build_summarize_prompt(items_data)},
            ], temperature=0.3, max_tokens=200)
            return response.strip()
        except Exception as e:
            logger.error(f'AI摘要失败: {e}')
            return None

    @staticmethod
    def poll_news() -> tuple[list[dict], int]:
        """拉取所有源最新快讯并返回新增条目"""
        raw_items = NewsService.fetch_all_sources()
        if not raw_items:
            return [], 0

        new_items = NewsService.save_news_items(raw_items)
        if not new_items:
            return [], 0

        # 异步执行分类流水线（不阻塞返回）
        from app.services.interest_pipeline import InterestPipeline
        item_ids = [n.id for n in new_items]
        _executor.submit(InterestPipeline.process_new_items, item_ids)

        try:
            from app.services.notification import NotificationService
            titles = [n.content[:50] for n in new_items[:3]]
            msg = f"📰 新增 {len(new_items)} 条快讯\n" + "\n".join(f"• {t}" for t in titles)
            if len(new_items) > 3:
                msg += f"\n...等{len(new_items) - 3}条"
            NotificationService.send_slack(msg)
        except Exception:
            pass

        items_data = [NewsService._item_to_dict(n) for n in new_items]
        return items_data, len(new_items)
```

**Step 2: 验证基础功能**

Run: `python -c "from app import create_app; app = create_app(); ctx = app.app_context(); ctx.push(); from app.services.news_service import NewsService; items = NewsService.fetch_all_sources(); print(f'Fetched {len(items)} items from all sources')"`

**Step 3: Commit**

```bash
git add app/services/news_service.py
git commit -m "refactor: NewsService multi-source fetch with parallel execution"
```

---

## Task 5: GLM 分类打分 Prompts

**Files:**
- Create: `app/llm/prompts/news_classify.py`

**Step 1: 创建分类打分 prompt**

```python
"""新闻分类打分 prompts"""

CLASSIFY_SYSTEM_PROMPT = """你是新闻分析助手。对每条新闻评估重要性并提取关键词。
返回严格的JSON数组，每个元素包含:
- index: 新闻序号(从0开始)
- importance: 重要性评分1-5 (1=日常，3=值得关注，5=重大事件)
- keywords: 关键词列表(2-5个，中文)

只返回JSON，不要其他文字。"""


def build_classify_prompt(news_items: list[dict]) -> str:
    lines = []
    for i, item in enumerate(news_items):
        lines.append(f"[{i}] {item['content']}")
    return f"请分析以下{len(news_items)}条新闻：\n\n" + "\n".join(lines)


RECOMMEND_SYSTEM_PROMPT = """你是投资者的个人新闻助手。根据用户最近关注的新闻内容，推荐3-5个新的关键词。
这些关键词应该是用户可能感兴趣但尚未设置的主题。
返回严格的JSON数组，每个元素是一个关键词字符串。只返回JSON。"""


def build_recommend_prompt(recent_contents: list[str], existing_keywords: list[str]) -> str:
    news_text = "\n".join(f"- {c}" for c in recent_contents[:30])
    existing_text = ", ".join(existing_keywords) if existing_keywords else "（无）"
    return f"用户已设置的关键词：{existing_text}\n\n最近关注的新闻：\n{news_text}\n\n请推荐新关键词。"
```

**Step 2: 注册新的 LLM 任务类型**

修改 `app/llm/router.py` 的 `TASK_LAYER_MAP`，添加：

```python
'news_classify': LLMLayer.FLASH,
'news_derivation': LLMLayer.FLASH,
'news_derivation_deep': LLMLayer.PREMIUM,
'news_recommend': LLMLayer.FLASH,
```

**Step 3: Commit**

```bash
git add app/llm/prompts/news_classify.py app/llm/router.py
git commit -m "feat: add GLM prompts for news classification, derivation, and keyword recommendation"
```

---

## Task 6: 兴趣流水线核心逻辑

**Files:**
- Create: `app/services/interest_pipeline.py`

**Step 1: 创建兴趣流水线**

```python
"""新闻兴趣流水线：分类打分 → 关键词匹配 → 衍生搜索"""
import json
import logging
from flask import current_app

from app import db
from app.models.news import NewsItem, InterestKeyword

logger = logging.getLogger(__name__)


class InterestPipeline:

    @staticmethod
    def process_new_items(item_ids: list[int]):
        """处理新入库的新闻条目（在后台线程执行）"""
        from flask import current_app
        try:
            app = current_app._get_current_object()
        except RuntimeError:
            from app import create_app
            app = create_app()

        with app.app_context():
            items = NewsItem.query.filter(NewsItem.id.in_(item_ids)).all()
            if not items:
                return

            # Step 1: GLM 批量分类打分
            classified = InterestPipeline._classify_items(items)

            # Step 2: 关键词匹配
            InterestPipeline._match_keywords(items, classified)

            db.session.commit()

            # Step 3: 高分兴趣条目触发衍生搜索
            from app.services.derivation_service import DerivationService
            interest_items = [n for n in items if n.is_interest and n.importance >= 4]
            DerivationService.process_batch(interest_items[:2])

    @staticmethod
    def _classify_items(items: list[NewsItem]) -> list[dict]:
        """GLM 批量分类打分"""
        from app.llm.router import llm_router
        from app.llm.prompts.news_classify import CLASSIFY_SYSTEM_PROMPT, build_classify_prompt

        provider = llm_router.route('news_classify')
        if not provider:
            return []

        items_data = [{'content': n.content} for n in items]
        try:
            response = provider.chat([
                {'role': 'system', 'content': CLASSIFY_SYSTEM_PROMPT},
                {'role': 'user', 'content': build_classify_prompt(items_data)},
            ], temperature=0.1, max_tokens=500)

            results = json.loads(response.strip())
            for r in results:
                idx = r.get('index', -1)
                if 0 <= idx < len(items):
                    items[idx].importance = r.get('importance', 0)
            return results
        except Exception as e:
            logger.error(f'GLM分类打分失败: {e}')
            return []

    @staticmethod
    def _match_keywords(items: list[NewsItem], classified: list[dict]):
        """将 GLM 提取的关键词与用户兴趣关键词匹配"""
        user_keywords = InterestKeyword.query.filter_by(is_active=True).all()
        if not user_keywords:
            return

        kw_set = {kw.keyword.lower() for kw in user_keywords}

        for r in classified:
            idx = r.get('index', -1)
            if idx < 0 or idx >= len(items):
                continue
            item = items[idx]
            extracted = r.get('keywords', [])

            matched = []
            for ext_kw in extracted:
                ext_lower = ext_kw.lower()
                for user_kw in kw_set:
                    if user_kw in ext_lower or ext_lower in user_kw:
                        matched.append(user_kw)
                        break

            # 也对正文做包含匹配兜底
            if not matched:
                content_lower = item.content.lower()
                for user_kw in kw_set:
                    if user_kw in content_lower:
                        matched.append(user_kw)

            if matched:
                item.is_interest = True
                item.matched_keywords = ','.join(set(matched))

    @staticmethod
    def recommend_keywords():
        """AI 推荐新关键词（每天调用一次）"""
        from flask import current_app
        try:
            app = current_app._get_current_object()
        except RuntimeError:
            from app import create_app
            app = create_app()

        with app.app_context():
            from app.llm.router import llm_router
            from app.llm.prompts.news_classify import RECOMMEND_SYSTEM_PROMPT, build_recommend_prompt
            from datetime import datetime, timedelta

            week_ago = datetime.now() - timedelta(days=7)
            recent = NewsItem.query.filter(
                NewsItem.is_interest == True,
                NewsItem.created_at >= week_ago
            ).order_by(NewsItem.created_at.desc()).limit(50).all()

            if len(recent) < 5:
                return

            existing = InterestKeyword.query.filter_by(is_active=True).all()
            existing_kws = [kw.keyword for kw in existing]

            provider = llm_router.route('news_recommend')
            if not provider:
                return

            contents = [n.content for n in recent]
            try:
                response = provider.chat([
                    {'role': 'system', 'content': RECOMMEND_SYSTEM_PROMPT},
                    {'role': 'user', 'content': build_recommend_prompt(contents, existing_kws)},
                ], temperature=0.3, max_tokens=200)

                suggestions = json.loads(response.strip())
                for kw in suggestions:
                    if isinstance(kw, str) and kw not in existing_kws:
                        db.session.add(InterestKeyword(
                            keyword=kw, source='ai', is_active=False
                        ))
                db.session.commit()
                logger.info(f'[兴趣] AI推荐 {len(suggestions)} 个关键词')
            except Exception as e:
                logger.error(f'AI关键词推荐失败: {e}')
```

**Step 2: Commit**

```bash
git add app/services/interest_pipeline.py
git commit -m "feat: add interest pipeline - GLM classification, keyword matching, AI recommendations"
```

---

## Task 7: 衍生搜索服务

**Files:**
- Create: `app/services/derivation_service.py`

**Step 1: 创建衍生搜索服务**

```python
"""衍生搜索服务：crawl4ai 抓取 + GLM 整理"""
import asyncio
import json
import logging
from concurrent.futures import ThreadPoolExecutor

from app import db
from app.models.news import NewsItem, NewsDerivation
from app.config.news_config import (
    MAX_DERIVATION_PER_POLL, DERIVATION_URL_TIMEOUT, DERIVATION_TOTAL_TIMEOUT
)

logger = logging.getLogger(__name__)

_derivation_executor = ThreadPoolExecutor(max_workers=2)

SEARCH_SYSTEM_PROMPT = """根据这条新闻，生成一组搜索关键词用于查找相关报道。
返回JSON: {"zh": "中文搜索词", "en": "English search terms"}
只返回JSON。"""

SUMMARY_LIGHT_PROMPT = """基于原始新闻和相关文章，写一段扩展摘要（100-200字），补充背景信息。
直接返回摘要文本。"""

SUMMARY_DEEP_PROMPT = """基于原始新闻和相关文章，写一份结构化专题报告（300-500字），格式：
**背景**：（事件背景）
**影响**：（市场/行业影响）
**展望**：（未来趋势）
直接返回报告文本。"""


class DerivationService:

    @staticmethod
    def process_batch(items: list[NewsItem]):
        """批量处理衍生搜索（后台线程调用）"""
        for item in items[:MAX_DERIVATION_PER_POLL]:
            existing = NewsDerivation.query.filter_by(news_item_id=item.id).first()
            if existing:
                continue
            try:
                DerivationService._derive_single(item)
            except Exception as e:
                logger.error(f'衍生搜索失败 [{item.id}]: {e}')

    @staticmethod
    def _derive_single(item: NewsItem):
        """单条新闻衍生搜索"""
        from app.llm.router import llm_router

        # Step 1: 生成搜索关键词
        provider = llm_router.route('news_classify')
        if not provider:
            return

        try:
            resp = provider.chat([
                {'role': 'system', 'content': SEARCH_SYSTEM_PROMPT},
                {'role': 'user', 'content': item.content},
            ], temperature=0.1, max_tokens=100)
            search_terms = json.loads(resp.strip())
            search_query = search_terms.get('zh', item.content[:50])
        except Exception:
            search_query = item.content[:50]

        # Step 2: crawl4ai 搜索
        max_urls = 5 if item.importance >= 5 else 2
        articles = DerivationService._crawl_search(search_query, max_urls)

        # Step 3: GLM 整合
        is_deep = item.importance >= 5
        task_type = 'news_derivation_deep' if is_deep else 'news_derivation'
        prompt_template = SUMMARY_DEEP_PROMPT if is_deep else SUMMARY_LIGHT_PROMPT
        provider = llm_router.route(task_type)

        source_urls = [a['url'] for a in articles]
        article_text = "\n\n".join(
            f"[来源: {a['url']}]\n{a['content'][:1000]}" for a in articles
        )

        summary = None
        if provider and article_text:
            try:
                user_prompt = f"原始新闻：{item.content}\n\n相关文章：\n{article_text}"
                summary = provider.chat([
                    {'role': 'system', 'content': prompt_template},
                    {'role': 'user', 'content': user_prompt},
                ], temperature=0.3, max_tokens=800).strip()
            except Exception as e:
                logger.error(f'GLM衍生整合失败: {e}')

        if not summary and articles:
            summary = articles[0]['content'][:500]

        if not summary:
            return

        derivation = NewsDerivation(
            news_item_id=item.id,
            search_query=search_query,
            sources=source_urls,
            summary=summary,
            importance=item.importance,
        )
        db.session.add(derivation)
        db.session.commit()
        logger.info(f'[衍生] 完成 news_item={item.id}, sources={len(source_urls)}')

    @staticmethod
    def _crawl_search(query: str, max_urls: int) -> list[dict]:
        """用 crawl4ai 搜索并抓取相关文章"""
        try:
            search_url = f"https://www.google.com/search?q={query}&tbm=nws"
            results = asyncio.run(DerivationService._async_crawl(search_url, max_urls))
            return results
        except Exception as e:
            logger.error(f'crawl4ai搜索失败: {e}')
            return []

    @staticmethod
    async def _async_crawl(search_url: str, max_urls: int) -> list[dict]:
        """异步爬取"""
        from crawl4ai import AsyncWebCrawler

        articles = []
        try:
            async with AsyncWebCrawler() as crawler:
                # 先抓搜索结果页提取链接
                search_result = await crawler.arun(
                    url=search_url,
                    timeout=DERIVATION_URL_TIMEOUT,
                )
                # 从 markdown 中提取链接
                urls = DerivationService._extract_urls(search_result.markdown, max_urls)

                # 抓取每个链接的正文
                for url in urls:
                    try:
                        result = await crawler.arun(
                            url=url,
                            timeout=DERIVATION_URL_TIMEOUT,
                        )
                        if result.markdown:
                            articles.append({
                                'url': url,
                                'content': result.markdown[:2000],
                            })
                    except Exception:
                        continue
        except Exception as e:
            logger.error(f'async crawl失败: {e}')
        return articles

    @staticmethod
    def _extract_urls(markdown: str, max_count: int) -> list[str]:
        """从搜索结果 markdown 中提取新闻链接"""
        import re
        url_pattern = re.compile(r'\[.*?\]\((https?://[^)]+)\)')
        urls = []
        skip_domains = {'google.com', 'youtube.com', 'accounts.google'}
        for match in url_pattern.finditer(markdown):
            url = match.group(1)
            if any(d in url for d in skip_domains):
                continue
            urls.append(url)
            if len(urls) >= max_count:
                break
        return urls
```

**Step 2: Commit**

```bash
git add app/services/derivation_service.py
git commit -m "feat: add derivation service - crawl4ai search + GLM summarization"
```

---

## Task 8: 关键词管理 API

**Files:**
- Modify: `app/routes/news.py`

**Step 1: 在 news.py 中添加关键词管理和衍生查询端点**

在现有端点之后追加：

```python
from app.models.news import InterestKeyword, NewsDerivation


@news_bp.route('/keywords')
def get_keywords():
    keywords = InterestKeyword.query.order_by(InterestKeyword.created_at.desc()).all()
    return jsonify({
        'success': True,
        'keywords': [{
            'id': kw.id,
            'keyword': kw.keyword,
            'source': kw.source,
            'is_active': kw.is_active,
        } for kw in keywords]
    })


@news_bp.route('/keywords', methods=['POST'])
def add_keyword():
    from app import db
    data = request.get_json()
    keyword = data.get('keyword', '').strip()
    if not keyword:
        return jsonify({'success': False, 'error': 'keyword required'})
    existing = InterestKeyword.query.filter_by(keyword=keyword).first()
    if existing:
        existing.is_active = True
        existing.source = 'user'
        db.session.commit()
        return jsonify({'success': True, 'id': existing.id})
    kw = InterestKeyword(keyword=keyword, source='user')
    db.session.add(kw)
    db.session.commit()
    return jsonify({'success': True, 'id': kw.id})


@news_bp.route('/keywords/<int:kw_id>', methods=['DELETE'])
def delete_keyword(kw_id):
    from app import db
    kw = InterestKeyword.query.get(kw_id)
    if kw:
        db.session.delete(kw)
        db.session.commit()
    return jsonify({'success': True})


@news_bp.route('/keywords/<int:kw_id>/accept', methods=['POST'])
def accept_keyword(kw_id):
    from app import db
    kw = InterestKeyword.query.get(kw_id)
    if kw:
        kw.is_active = True
        kw.source = 'user'
        db.session.commit()
    return jsonify({'success': True})


@news_bp.route('/derivations/<int:news_id>')
def get_derivation(news_id):
    d = NewsDerivation.query.filter_by(news_item_id=news_id).first()
    if not d:
        return jsonify({'success': False})
    return jsonify({
        'success': True,
        'derivation': {
            'summary': d.summary,
            'sources': d.sources or [],
            'importance': d.importance,
            'search_query': d.search_query,
        }
    })
```

**Step 2: 验证端点可用**

Run: `python -c "from app import create_app; app = create_app(); client = app.test_client(); r = client.get('/news/keywords'); print(r.json)"`

**Step 3: Commit**

```bash
git add app/routes/news.py
git commit -m "feat: add keyword management and derivation query API endpoints"
```

---

## Task 9: 前端 — 兴趣 Tab 和关键词管理

**Files:**
- Modify: `app/templates/news.html`
- Modify: `app/static/js/news.js`

**Step 1: 更新 news.html 模板**

完整重写 `app/templates/news.html`：

```html
{% extends "base.html" %}
{% block title %}新闻看板{% endblock %}

{% block content %}
<style>
.news-item-new {
    background-color: #fff3cd;
    transition: background-color 3s ease;
}
.news-summary-card {
    border-left: 3px solid #0d6efd !important;
}
.importance-stars {
    color: #ffc107;
    font-size: 0.75rem;
    margin-left: 4px;
}
.keyword-tag {
    font-size: 0.7rem;
    padding: 1px 6px;
    margin-left: 4px;
}
.derivation-card {
    background: #f8f9fa;
    border-left: 3px solid #198754;
    padding: 12px;
    margin-top: 8px;
    border-radius: 4px;
    font-size: 0.9rem;
}
.derivation-sources {
    font-size: 0.75rem;
    color: #6c757d;
    margin-top: 8px;
}
.kw-manage-tag {
    display: inline-flex;
    align-items: center;
    padding: 4px 10px;
    margin: 3px;
    border-radius: 16px;
    font-size: 0.85rem;
}
.kw-user { background: #e7f1ff; color: #0d6efd; }
.kw-ai { background: #f0f0f0; color: #6c757d; }
</style>
<div class="container-fluid mt-3">
    <div class="d-flex justify-content-between align-items-center mb-3">
        <div>
            <h4 class="mb-1"><i class="bi bi-newspaper"></i> 新闻看板</h4>
            <small class="text-muted" id="newsStatus">加载中...</small>
        </div>
        <button class="btn btn-outline-secondary btn-sm" onclick="News.showKeywordModal()">
            <i class="bi bi-gear"></i> 关键词管理
        </button>
    </div>

    <ul class="nav nav-tabs mb-3" id="newsTabs">
        <li class="nav-item">
            <a class="nav-link active" data-tab="all" href="#">全部</a>
        </li>
        <li class="nav-item">
            <a class="nav-link" data-tab="interest" href="#">兴趣</a>
        </li>
    </ul>

    <div id="loadingState">
        <div class="skeleton-card mb-2" style="height:60px"></div>
        <div class="skeleton-card mb-2" style="height:60px"></div>
        <div class="skeleton-card mb-2" style="height:60px"></div>
        <div class="skeleton-card mb-2" style="height:60px"></div>
    </div>

    <div id="contentArea" style="display:none">
        <div id="newsList"></div>
        <div class="text-center mt-3">
            <button class="btn btn-outline-secondary btn-sm" id="btnLoadMore" style="display:none">
                加载更多
            </button>
        </div>
    </div>

    <div id="emptyState" style="display:none">
        <div class="text-center py-5 text-muted">
            <i class="bi bi-newspaper" style="font-size:3rem"></i>
            <p class="mt-3">暂无新闻数据</p>
        </div>
    </div>
</div>

<!-- 关键词管理弹窗 -->
<div class="modal fade" id="keywordModal" tabindex="-1">
    <div class="modal-dialog">
        <div class="modal-content">
            <div class="modal-header">
                <h5 class="modal-title">关键词管理</h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
            </div>
            <div class="modal-body">
                <div class="input-group mb-3">
                    <input type="text" class="form-control" id="newKeywordInput" placeholder="输入关键词...">
                    <button class="btn btn-primary" onclick="News.addKeyword()">添加</button>
                </div>
                <div class="mb-3">
                    <strong>我的关键词</strong>
                    <div id="userKeywords" class="mt-2"></div>
                </div>
                <div id="aiRecommendSection" style="display:none">
                    <strong>AI 推荐</strong>
                    <small class="text-muted">（基于你最近关注的新闻）</small>
                    <div id="aiKeywords" class="mt-2"></div>
                </div>
            </div>
        </div>
    </div>
</div>
{% endblock %}

{% block extra_js %}
<script src="{{ url_for('static', filename='js/news.js') }}"></script>
{% endblock %}
```

**Step 2: 重写 news.js**

完整重写 `app/static/js/news.js`，添加关键词管理、兴趣 Tab 增强、衍生内容展示。代码较长，关键变更点：

1. `renderItems()` — 添加 source_name 标签、importance 星级、matched_keywords 标签、衍生内容折叠
2. 新增 `showKeywordModal()` / `addKeyword()` / `deleteKeyword()` / `acceptKeyword()` — 关键词 CRUD
3. 新增 `loadDerivation(newsId)` — 懒加载衍生内容
4. `createItemElement()` — 兴趣条目的增强渲染

```javascript
const NEWS_SOURCE_LABELS = {
    wallstreetcn: { label: '华尔街', color: 'secondary' },
    smolai: { label: 'SmolAI', color: 'info' },
    cls: { label: '财联社', color: 'primary' },
    '36kr': { label: '36kr', color: 'warning' },
};

const News = {
    POLL_SECONDS: 180,
    currentTab: 'all',
    items: [],
    countdown: 0,
    countdownTimer: null,
    keywordModal: null,

    async init() {
        this.keywordModal = new bootstrap.Modal(document.getElementById('keywordModal'));
        this.bindEvents();
        await this.loadData();
        this.resetCountdown();
    },

    bindEvents() {
        document.getElementById('btnLoadMore').addEventListener('click', () => this.loadMore());
        document.querySelectorAll('#newsTabs .nav-link').forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                document.querySelectorAll('#newsTabs .nav-link').forEach(l => l.classList.remove('active'));
                e.target.classList.add('active');
                this.currentTab = e.target.dataset.tab;
                this.items = [];
                this.loadItems();
            });
        });
        document.getElementById('newKeywordInput').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.addKeyword();
        });
    },

    async loadData() {
        try {
            const [itemsResp, pollResp] = await Promise.all([
                fetch(`/news/items?tab=${this.currentTab}&limit=30`),
                fetch('/news/poll'),
            ]);
            const itemsData = await itemsResp.json();
            const pollData = await pollResp.json();
            if (itemsData.success) this.items = itemsData.items;
            if (pollData.success && pollData.new_count > 0) this.mergeNewItems(pollData.new_items);
            this.renderItems();
            this.showContent();
        } catch (e) {
            console.error('加载失败:', e);
            this.items = [];
            this.showContent();
        }
    },

    mergeNewItems(newItems) {
        const existingIds = new Set(this.items.map(i => i.id));
        const unique = newItems.filter(i => !existingIds.has(i.id));
        if (unique.length) this.items = [...unique, ...this.items];
    },

    async loadItems() {
        try {
            const resp = await fetch(`/news/items?tab=${this.currentTab}&limit=30`);
            const data = await resp.json();
            if (data.success) this.items = data.items;
            this.renderItems();
            this.showContent();
        } catch (e) {
            console.error('加载快讯失败:', e);
            this.items = [];
            this.showContent();
        }
    },

    async loadMore() {
        if (!this.items.length) return;
        const lastId = this.items[this.items.length - 1].id;
        try {
            const resp = await fetch(`/news/items?tab=${this.currentTab}&limit=30&before_id=${lastId}`);
            const data = await resp.json();
            if (data.success && data.items.length) {
                this.items = this.items.concat(data.items);
                this.renderItems();
            }
        } catch (e) {
            console.error('加载更多失败:', e);
        }
    },

    resetCountdown() {
        this.countdown = this.POLL_SECONDS;
        if (this.countdownTimer) clearInterval(this.countdownTimer);
        this.updateStatus();
        this.countdownTimer = setInterval(() => this.tick(), 1000);
    },

    async tick() {
        this.countdown--;
        if (this.countdown <= 0) {
            clearInterval(this.countdownTimer);
            await this.poll();
            this.resetCountdown();
            return;
        }
        this.updateStatus();
    },

    async poll() {
        try {
            const resp = await fetch('/news/poll');
            const data = await resp.json();
            if (!data.success || data.new_count === 0) return;
            if (data.new_count <= 3) {
                this.insertNewItems(data.new_items);
            } else {
                await this.insertSummaryCard(data.new_items);
            }
            this.updateStatus();
        } catch (e) {
            console.error('轮询失败:', e);
        }
    },

    insertNewItems(newItems) {
        this.mergeNewItems(newItems);
        const container = document.getElementById('newsList');
        const fragment = document.createDocumentFragment();
        for (const item of newItems) {
            const el = this.createItemElement(item);
            el.classList.add('news-item-new');
            fragment.appendChild(el);
        }
        container.insertBefore(fragment, container.firstChild);
        setTimeout(() => {
            container.querySelectorAll('.news-item-new').forEach(el => el.classList.remove('news-item-new'));
        }, 3000);
    },

    async insertSummaryCard(newItems) {
        this.mergeNewItems(newItems);
        const ids = newItems.map(i => i.id);
        let summary = null;
        try {
            const resp = await fetch('/news/summarize', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ item_ids: ids }),
            });
            const data = await resp.json();
            if (data.success) summary = data.summary;
        } catch (e) {
            console.error('AI摘要失败:', e);
        }
        if (!summary) { this.insertNewItems(newItems); return; }

        const container = document.getElementById('newsList');
        const card = document.createElement('div');
        card.className = 'news-summary-card mb-2 p-3 border rounded bg-light news-item-new';
        card.innerHTML = `
            <div class="d-flex justify-content-between align-items-center mb-1">
                <span class="fw-bold text-primary">
                    <i class="bi bi-clipboard-data"></i> ${newItems.length}条新快讯整理
                </span>
                <button class="btn btn-sm btn-link text-muted p-0" onclick="News.toggleDetail(this)">展开 ▼</button>
            </div>
            <div class="summary-text">${summary}</div>
            <div class="summary-detail" style="display:none">
                ${newItems.map(i => `
                    <div class="small text-muted border-top pt-1 mt-1">
                        <span class="me-1">${i.display_time}</span> ${i.content}
                    </div>
                `).join('')}
            </div>
        `;
        container.insertBefore(card, container.firstChild);
        setTimeout(() => card.classList.remove('news-item-new'), 3000);
    },

    toggleDetail(btn) {
        const card = btn.closest('.news-summary-card, .news-item');
        const detail = card.querySelector('.summary-detail, .derivation-wrap');
        if (!detail) return;
        const isHidden = detail.style.display === 'none';
        detail.style.display = isHidden ? '' : 'none';
        btn.textContent = isHidden ? '收起 ▲' : '展开 ▼';
    },

    createItemElement(item) {
        const src = NEWS_SOURCE_LABELS[item.source_name] || { label: '', color: 'secondary' };
        const scoreIcon = item.score >= 2
            ? '<span class="text-danger me-1">●</span>'
            : '<span class="text-muted me-1">○</span>';
        const srcBadge = src.label
            ? `<span class="badge bg-${src.color} keyword-tag">${src.label}</span>`
            : '';
        const stars = item.importance > 0
            ? `<span class="importance-stars">${'★'.repeat(item.importance)}${'☆'.repeat(5 - item.importance)}</span>`
            : '';
        const kwTags = item.matched_keywords
            ? item.matched_keywords.split(',').map(k => `<span class="badge bg-success keyword-tag">${k.trim()}</span>`).join('')
            : '';

        const hasDerivation = item.is_interest && item.importance >= 4;
        const derivationArea = hasDerivation
            ? `<div class="derivation-wrap" style="display:${item.importance >= 5 ? '' : 'none'}" id="deriv-${item.id}">
                   <div class="derivation-card"><span class="text-muted">加载衍生内容...</span></div>
               </div>`
            : '';
        const derivToggle = hasDerivation
            ? `<button class="btn btn-sm btn-link text-muted p-0 ms-2" onclick="News.toggleDerivation(${item.id}, this)">${item.importance >= 5 ? '收起 ▲' : '▸ 查看衍生'}</button>`
            : '';

        const div = document.createElement('div');
        div.className = 'd-flex align-items-start py-2 border-bottom news-item';
        div.dataset.id = item.id;
        div.innerHTML = `
            <div class="me-2 text-nowrap">
                ${scoreIcon}
                <small class="text-muted">${item.display_time}</small>
            </div>
            <div class="flex-grow-1">
                <div>
                    <span>${item.content}</span>${srcBadge}${stars}${kwTags}${derivToggle}
                </div>
                ${derivationArea}
            </div>
        `;

        if (hasDerivation && item.importance >= 5) {
            this.loadDerivation(item.id, div.querySelector('.derivation-card'));
        }
        return div;
    },

    async toggleDerivation(newsId, btn) {
        const wrap = document.getElementById(`deriv-${newsId}`);
        if (!wrap) return;
        const isHidden = wrap.style.display === 'none';
        wrap.style.display = isHidden ? '' : 'none';
        btn.textContent = isHidden ? '收起 ▲' : '▸ 查看衍生';
        if (isHidden) {
            const card = wrap.querySelector('.derivation-card');
            if (card && card.dataset.loaded !== 'true') {
                await this.loadDerivation(newsId, card);
            }
        }
    },

    async loadDerivation(newsId, container) {
        try {
            const resp = await fetch(`/news/derivations/${newsId}`);
            const data = await resp.json();
            if (!data.success) {
                container.innerHTML = '<span class="text-muted">暂无衍生内容</span>';
                return;
            }
            const d = data.derivation;
            const sources = (d.sources || []).map(s => `<a href="${s}" target="_blank" class="me-2">${new URL(s).hostname}</a>`).join('');
            container.innerHTML = `
                <div>${d.summary.replace(/\n/g, '<br>')}</div>
                ${sources ? `<div class="derivation-sources">来源: ${sources}</div>` : ''}
            `;
            container.dataset.loaded = 'true';
        } catch (e) {
            container.innerHTML = '<span class="text-muted">加载失败</span>';
        }
    },

    renderItems() {
        const container = document.getElementById('newsList');
        if (!this.items.length) {
            container.innerHTML = '<p class="text-muted text-center py-4">暂无快讯</p>';
            document.getElementById('btnLoadMore').style.display = 'none';
            return;
        }
        container.innerHTML = '';
        let lastDate = '';
        for (const item of this.items) {
            if (item.display_date && item.display_date !== lastDate) {
                lastDate = item.display_date;
                const dateDiv = document.createElement('div');
                dateDiv.className = 'text-muted small fw-bold mt-3 mb-2 border-bottom pb-1';
                dateDiv.textContent = lastDate;
                container.appendChild(dateDiv);
            }
            container.appendChild(this.createItemElement(item));
        }
        document.getElementById('btnLoadMore').style.display = 'inline-block';
    },

    showContent() {
        document.getElementById('loadingState').style.display = 'none';
        if (this.items.length) {
            document.getElementById('contentArea').style.display = '';
            document.getElementById('emptyState').style.display = 'none';
        } else {
            document.getElementById('contentArea').style.display = 'none';
            document.getElementById('emptyState').style.display = '';
        }
        this.updateStatus();
    },

    updateStatus() {
        const min = Math.floor(this.countdown / 60);
        const sec = this.countdown % 60;
        const cd = min > 0 ? `${min}:${String(sec).padStart(2, '0')}` : `${sec}s`;
        document.getElementById('newsStatus').textContent = `${this.items.length} 条快讯 · ${cd} 后刷新`;
    },

    // 关键词管理
    async showKeywordModal() {
        this.keywordModal.show();
        await this.loadKeywords();
    },

    async loadKeywords() {
        try {
            const resp = await fetch('/news/keywords');
            const data = await resp.json();
            if (!data.success) return;

            const userKws = data.keywords.filter(k => k.source === 'user' || k.is_active);
            const aiKws = data.keywords.filter(k => k.source === 'ai' && !k.is_active);

            document.getElementById('userKeywords').innerHTML = userKws.length
                ? userKws.map(k => `
                    <span class="kw-manage-tag kw-user">
                        ${k.keyword}
                        <button class="btn-close btn-close-sm ms-1" style="font-size:0.6rem" onclick="News.deleteKeyword(${k.id})"></button>
                    </span>
                `).join('')
                : '<span class="text-muted">暂无关键词，添加你感兴趣的主题</span>';

            const aiSection = document.getElementById('aiRecommendSection');
            if (aiKws.length) {
                aiSection.style.display = '';
                document.getElementById('aiKeywords').innerHTML = aiKws.map(k => `
                    <span class="kw-manage-tag kw-ai">
                        ${k.keyword}
                        <button class="btn btn-sm btn-outline-success py-0 px-1 ms-1" onclick="News.acceptKeyword(${k.id})" title="接受">✓</button>
                        <button class="btn btn-sm btn-outline-danger py-0 px-1 ms-1" onclick="News.deleteKeyword(${k.id})" title="拒绝">✕</button>
                    </span>
                `).join('');
            } else {
                aiSection.style.display = 'none';
            }
        } catch (e) {
            console.error('加载关键词失败:', e);
        }
    },

    async addKeyword() {
        const input = document.getElementById('newKeywordInput');
        const keyword = input.value.trim();
        if (!keyword) return;
        try {
            await fetch('/news/keywords', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ keyword }),
            });
            input.value = '';
            await this.loadKeywords();
        } catch (e) {
            console.error('添加关键词失败:', e);
        }
    },

    async deleteKeyword(id) {
        try {
            await fetch(`/news/keywords/${id}`, { method: 'DELETE' });
            await this.loadKeywords();
        } catch (e) {
            console.error('删除关键词失败:', e);
        }
    },

    async acceptKeyword(id) {
        try {
            await fetch(`/news/keywords/${id}/accept`, { method: 'POST' });
            await this.loadKeywords();
        } catch (e) {
            console.error('接受关键词失败:', e);
        }
    },
};

document.addEventListener('DOMContentLoaded', () => News.init());
```

**Step 3: 验证页面加载**

Run: `python run.py`
打开 http://127.0.0.1:5000/news/ 验证：
- 全部 Tab 正常显示
- 兴趣 Tab 切换正常
- 关键词管理弹窗打开/添加/删除正常
- 来源标签显示正确

**Step 4: Commit**

```bash
git add app/templates/news.html app/static/js/news.js
git commit -m "feat: enhanced news UI - interest tab, keyword management, derivation display, source labels"
```

---

## Task 10: 集成验证与清理

**Files:**
- Modify: `app/llm/prompts/news_briefing.py` (保持不变，已有)
- Verify: 整体流程

**Step 1: 启动应用验证完整流程**

Run: `python run.py`

验证清单：
1. 打开 /news/ — 页面正常加载，骨架屏→内容
2. 多源新闻出现（华尔街、SmolAI、财联社、36kr 标签）
3. 关键词管理 — 添加"AI"、"降息"等关键词
4. 等待下次 poll — 新条目应有 importance 星级
5. 兴趣 Tab — 匹配关键词的条目出现
6. 高分条目 — 衍生内容可展开查看

**Step 2: 清理旧的 INTEREST_CATEGORIES（已不再使用）**

`app/config/news_config.py` 中已在 Task 3 重写时移除了 `INTEREST_CATEGORIES`。

**Step 3: 最终 Commit**

```bash
git add -A
git commit -m "feat: complete news interest module - multi-source, GLM classification, keyword matching, derivation search"
```
