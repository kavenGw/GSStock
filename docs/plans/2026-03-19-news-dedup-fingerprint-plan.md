# 新闻去重指纹优化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在现有 SequenceMatcher 去重基础上，新增关键特征指纹通道，捕获同一事件不同措辞的重复新闻。

**Architecture:** 改造 `news_dedup.py` 单文件，新增文本清洗、特征提取（实体名/金额/日期）、Jaccard 指纹比较三层逻辑。实体名从 DB 懒加载+TTL 缓存。双通道 OR 判定：SequenceMatcher >= 0.4 或指纹 Jaccard 满足三重条件。

**Tech Stack:** Python stdlib（re, difflib, NamedTuple），SQLAlchemy 查询（CompanyKeyword, Stock）

**Spec:** `docs/plans/2026-03-19-news-dedup-fingerprint-design.md`

---

### Task 1: PushedRecord NamedTuple + 缓冲区结构迁移

**Files:**
- Modify: `app/services/news_dedup.py:1-82`

- [ ] **Step 1: 定义 PushedRecord 并替换缓冲区类型**

在文件顶部 import 区域新增 `NamedTuple`，定义 `PushedRecord`，修改 `__init__` 和 `filter_duplicates` 中的缓冲区操作：

```python
from typing import NamedTuple

class PushedRecord(NamedTuple):
    timestamp: datetime
    content: str
    fingerprint: frozenset

# __init__ 中:
self._pushed_buffer: list[PushedRecord] = []

# filter_duplicates 中清理窗口:
self._pushed_buffer = [r for r in self._pushed_buffer if r.timestamp > cutoff]

# 历史比较:
is_dup = any(self._is_similar(content, r.content)
             for r in self._pushed_buffer)

# 追加记录（指纹暂时传空，Task 3 填充）:
self._pushed_buffer.append(PushedRecord(now, content, frozenset()))
```

- [ ] **Step 2: 验证应用正常启动，新闻推送不受影响**

Run: `python run.py`，触发一次新闻轮询确认日志正常，无报错。

- [ ] **Step 3: Commit**

```bash
git add app/services/news_dedup.py
git commit -m "refactor: news_dedup 缓冲区改用 PushedRecord NamedTuple"
```

---

### Task 2: 文本预处理 + 特征提取函数

**Files:**
- Modify: `app/services/news_dedup.py`

- [ ] **Step 1: 新增文本清洗函数 `_strip_prefix`**

在 `NewsDeduplicator` 类中新增：

```python
_PREFIX_PATTERNS = [
    re.compile(r'^(财联社|每经|证券时报|新华社|央视)\d{1,2}月\d{1,2}日(电|讯|消息)[，,\s]*'),
    re.compile(r'^据.{2,10}(报道|消息|透露)[，,\s]*'),
    re.compile(r'^【[^】]+】\s*'),
]

@classmethod
def _strip_prefix(cls, text: str) -> str:
    for pat in cls._PREFIX_PATTERNS:
        text = pat.sub('', text)
    return text
```

- [ ] **Step 2: 新增数字+日期特征提取正则**

```python
_AMOUNT_RE = re.compile(r'\d+\.?\d*\s*[百千万亿]+[美韩日欧]?[元圆币]|\$[\d.]+[BMK]?')
_DATE_RE = re.compile(r'\d{4}年|[一二三四1-4]季[度报]|Q[1-4]|[上下]半年|半年报|年报')
```

- [ ] **Step 3: 新增实体名缓存机制**

在 `__init__` 中初始化缓存变量：

```python
self._entity_re: re.Pattern | None = None
self._entity_cache_time: datetime | None = None
```

类级常量（与 `_PREFIX_PATTERNS` 同级）：

```python
_ENTITY_TTL = timedelta(hours=1)
```

新增加载方法：

```python
def _get_entity_re(self) -> re.Pattern | None:
    now = datetime.now()
    if self._entity_re is not None and self._entity_cache_time and now - self._entity_cache_time < self._ENTITY_TTL:
        return self._entity_re
    try:
        from app.models.news import CompanyKeyword
        from app.models.stock import Stock
        names = set()
        for c in CompanyKeyword.query.filter_by(is_active=True).all():
            if len(c.name) >= 2:
                names.add(c.name)
        for s in Stock.query.all():
            if len(s.stock_name) >= 2:
                names.add(s.stock_name)
        if names:
            pattern = '|'.join(re.escape(n) for n in sorted(names, key=len, reverse=True))
            self._entity_re = re.compile(pattern)
        else:
            self._entity_re = None
        self._entity_cache_time = now
    except Exception:
        logger.debug('[去重] 实体名加载失败，跳过实体匹配')
        self._entity_re = None
    return self._entity_re
```

- [ ] **Step 4: 新增 `_extract_fingerprint` 方法**

```python
def _extract_fingerprint(self, text: str) -> frozenset:
    cleaned = self._strip_prefix(text)
    features = set()
    # 实体名
    entity_re = self._get_entity_re()
    if entity_re:
        features.update(entity_re.findall(cleaned))
    # 金额
    features.update(self._AMOUNT_RE.findall(cleaned))
    # 日期
    features.update(self._DATE_RE.findall(cleaned))
    return frozenset(features)
```

- [ ] **Step 5: 手动验证特征提取**

Run: `PYTHONIOENCODING=utf-8 python -c "..."`，用三星新闻样本验证提取结果包含预期特征。

- [ ] **Step 6: Commit**

```bash
git add app/services/news_dedup.py
git commit -m "feat: 新增新闻文本清洗和关键特征指纹提取"
```

---

### Task 3: 双通道判定逻辑

**Files:**
- Modify: `app/services/news_dedup.py`

- [ ] **Step 1: 新增指纹相似度判定方法 `_is_fingerprint_match`**

```python
def _is_fingerprint_match(self, fp_a: frozenset, fp_b: frozenset) -> bool:
    if len(fp_a) < 2 or len(fp_b) < 2:
        return False
    intersection = fp_a & fp_b
    union = fp_a | fp_b
    if len(union) < 3 or len(intersection) < 2:
        return False
    jaccard = len(intersection) / len(union)
    return jaccard >= 0.5
```

- [ ] **Step 2: 修改 `_is_similar` 改名为 `_is_text_similar`，新增 `_is_duplicate` 统一入口**

```python
def _is_text_similar(self, text_a: str, text_b: str) -> bool:
    a = self._normalize(text_a)
    b = self._normalize(text_b)
    if not a or not b:
        return False
    return SequenceMatcher(None, a, b).ratio() >= SIMILARITY_THRESHOLD

def _is_duplicate(self, text_a: str, fp_a: frozenset,
                  text_b: str, fp_b: frozenset) -> tuple[bool, str]:
    """返回 (是否重复, 匹配方式: 'text'|'fingerprint'|'')"""
    if self._is_text_similar(text_a, text_b):
        return True, 'text'
    if self._is_fingerprint_match(fp_a, fp_b):
        return True, 'fingerprint'
    return False, ''
```

- [ ] **Step 3: 改造 `filter_duplicates` 使用双通道**

完整替换 `filter_duplicates` 方法体：

```python
def filter_duplicates(self, items: list, content_key) -> list:
    with self._lock:
        now = datetime.now()
        cutoff = now - timedelta(minutes=DEDUP_WINDOW_MINUTES)
        self._pushed_buffer = [r for r in self._pushed_buffer if r.timestamp > cutoff]

        # 为每个 item 提取内容和指纹
        item_data = []
        for item in items:
            content = content_key(item)
            fp = self._extract_fingerprint(content)
            item_data.append((item, content, fp))

        # 批内分组去重
        groups: list[list[tuple]] = []
        for entry in item_data:
            _, content, fp = entry
            merged = False
            for group in groups:
                _, rep_content, rep_fp = group[0]
                is_dup, _ = self._is_duplicate(content, fp, rep_content, rep_fp)
                if is_dup:
                    group.append(entry)
                    merged = True
                    break
            if not merged:
                groups.append([entry])

        # 每组取最长
        deduplicated = []
        for group in groups:
            best = max(group, key=lambda e: len(e[1]))
            deduplicated.append(best)

        # 跨历史去重
        result = []
        text_filtered = 0
        fp_filtered = 0
        for item, content, fp in deduplicated:
            is_dup = False
            for r in self._pushed_buffer:
                dup, method = self._is_duplicate(content, fp, r.content, r.fingerprint)
                if dup:
                    is_dup = True
                    if method == 'text':
                        text_filtered += 1
                    else:
                        fp_filtered += 1
                    logger.debug(f'[去重] {method}命中: {fp} ↔ {r.fingerprint}')
                    break
            if not is_dup:
                result.append(item)
                self._pushed_buffer.append(PushedRecord(now, content, fp))

        # 批内去重的统计
        batch_filtered = len(items) - len(deduplicated)
        total_filtered = len(items) - len(result)
        if total_filtered > 0:
            logger.info(
                f'[去重] 输入 {len(items)} 条，过滤 {total_filtered} 条'
                f'（批内合并{batch_filtered}，文本相似{text_filtered}，指纹匹配{fp_filtered}），'
                f'推送 {len(result)} 条'
            )

        return result
```

- [ ] **Step 4: 验证应用启动 + 新闻轮询正常**

Run: `python run.py`，观察日志中出现新的去重统计格式。

- [ ] **Step 5: Commit**

```bash
git add app/services/news_dedup.py
git commit -m "feat: 新闻去重新增关键特征指纹双通道判定"
```

---

### Task 4: 端到端验证

**Files:**
- 无代码改动，纯验证

- [ ] **Step 1: 用 Python 脚本模拟三星新闻去重场景**

```python
# 在项目根目录运行
PYTHONIOENCODING=utf-8 python -c "
import re, sys
sys.path.insert(0, '.')
from datetime import datetime
from app.services.news_dedup import news_deduplicator

# 手动注入实体名（绕过 DB 查询）
news_deduplicator._entity_re = re.compile('三星电子')
news_deduplicator._entity_cache_time = datetime.now()

items = [
    '财联社3月19日电，三星电子计划在2026年至少投入110万亿韩元（约732亿美元）用于研发与设施建设。',
    '三星电子：计划2026年在研发与设施方面投资至少110万亿韩元。计划2026年派发9.8万亿韩元常规股息。',
    '国家外汇管理局召开党组扩大会议，强调深化外汇领域模优结构。',
]

# 清空历史缓冲区确保干净测试
news_deduplicator._pushed_buffer = []

result = news_deduplicator.filter_duplicates(items, content_key=lambda x: x)
print(f'输入 {len(items)} 条，输出 {len(result)} 条')
for r in result:
    fp = news_deduplicator._extract_fingerprint(r)
    print(f'  -> {r[:50]}...')
    print(f'     指纹: {set(fp)}')
"
```

预期：输入 3 条，输出 2 条（两条三星新闻合并为 1 条，外汇新闻保留）。三星新闻指纹应包含 `{三星电子, 110万亿韩元, 2026年}` 等特征。

- [ ] **Step 2: 确认无误后完成**
