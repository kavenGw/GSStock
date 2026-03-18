# 新闻推送去重 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 Slack 推送前增加跨源文本相似度去重，30分钟窗口内同一事件只推送内容最长的一条。

**Architecture:** 新建 `NewsDeduplicator` 单例，维护内存已推送缓冲区，两处推送方法（兴趣新闻、公司新闻）在发送前统一过滤。

**Tech Stack:** Python 标准库 `difflib.SequenceMatcher`、`threading.Lock`

---

### Task 1: 创建 NewsDeduplicator 核心组件

**Files:**
- Create: `app/services/news_dedup.py`

- [ ] **Step 1: 创建 `app/services/news_dedup.py`**

```python
"""新闻推送去重：跨源文本相似度过滤"""
import logging
import re
import threading
from datetime import datetime, timedelta
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)

DEDUP_WINDOW_MINUTES = 30
SIMILARITY_THRESHOLD = 0.4


class NewsDeduplicator:
    _instance = None
    _init_guard = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._init_guard:
            return
        self._init_guard = True
        self._pushed_buffer: list[tuple[datetime, str]] = []
        self._lock = threading.Lock()

    @staticmethod
    def _normalize(text: str) -> str:
        return re.sub(r'[\s\W]+', '', text)

    def _is_similar(self, text_a: str, text_b: str) -> bool:
        a = self._normalize(text_a)
        b = self._normalize(text_b)
        if not a or not b:
            return False
        return SequenceMatcher(None, a, b).ratio() >= SIMILARITY_THRESHOLD

    def filter_duplicates(self, items: list, content_key) -> list:
        with self._lock:
            now = datetime.now()
            cutoff = now - timedelta(minutes=DEDUP_WINDOW_MINUTES)
            self._pushed_buffer = [(t, c) for t, c in self._pushed_buffer if t > cutoff]

            # 批内贪心分组，每组保留内容最长的
            groups: list[list] = []
            for item in items:
                content = content_key(item)
                merged = False
                for group in groups:
                    representative = content_key(group[0])
                    if self._is_similar(content, representative):
                        group.append(item)
                        merged = True
                        break
                if not merged:
                    groups.append([item])

            deduplicated = []
            for group in groups:
                best = max(group, key=lambda x: len(content_key(x)))
                deduplicated.append(best)

            # 与已推送缓冲区比较
            result = []
            for item in deduplicated:
                content = content_key(item)
                is_dup = any(self._is_similar(content, pushed_content)
                            for _, pushed_content in self._pushed_buffer)
                if not is_dup:
                    result.append(item)
                    self._pushed_buffer.append((now, content))

            filtered_count = len(items) - len(result)
            if filtered_count > 0:
                logger.info(f'[去重] 输入 {len(items)} 条，过滤 {filtered_count} 条重复，推送 {len(result)} 条')

            return result


news_deduplicator = NewsDeduplicator()
```

- [ ] **Step 2: 验证模块可导入**

Run: `cd D:/Git/stock && python -c "from app.services.news_dedup import news_deduplicator; print('OK')"`
Expected: `OK`

---

### Task 2: 集成到兴趣新闻推送

**Files:**
- Modify: `app/services/interest_pipeline.py:306-333` (`_notify_interest_slack` 方法)

- [ ] **Step 1: 修改 `_notify_interest_slack`，推送前调用去重过滤**

在 `_notify_interest_slack` 方法开头，stock_name_map 构建之前，插入去重过滤：

```python
@staticmethod
def _notify_interest_slack(items: list[NewsItem]):
    from app.services.notification import NotificationService
    from app.services.news_dedup import news_deduplicator
    try:
        items = news_deduplicator.filter_duplicates(items, content_key=lambda n: n.content)
        if not items:
            return

        # 预加载关联股票名称（以下为原有代码，不变）
        all_codes = set()
        ...
```

关键变更：在方法入口处加两行（导入 + 过滤），过滤后为空则直接 return。其余代码不变。

---

### Task 3: 集成到公司新闻推送

**Files:**
- Modify: `app/services/company_news_service.py:262-269` (`_notify_company_slack` 方法)

- [ ] **Step 1: 修改 `_notify_company_slack`，推送前调用去重过滤**

```python
@staticmethod
def _notify_company_slack(items: list[tuple[str, str]]):
    from app.services.notification import NotificationService
    from app.services.news_dedup import news_deduplicator
    try:
        items = news_deduplicator.filter_duplicates(items, content_key=lambda t: t[1])
        if not items:
            return

        for company, content in items:
            NotificationService.send_slack(f"🏢 [{company}] {content}")
    except Exception as e:
        logger.error(f'[公司新闻] Slack通知失败: {e}')
```

---
