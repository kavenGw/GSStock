# LLM 辅助批内新闻去重 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在现有新闻去重系统中增加 LLM Flash 第四通道，对规则未命中的可疑对做语义重复判断。

**Architecture:** 在 `filter_duplicates()` 批内分组阶段，现有三通道规则完成后，对未合并的组代表做预筛选（规则软匹配 OR 通用关键词重叠），可疑对释放锁后调用 LLM Flash 判断，结果合并回组。

**Tech Stack:** Python, 智谱 GLM Flash, difflib, re

**Spec:** `docs/superpowers/specs/2026-03-20-news-dedup-llm-design.md`

---

### Task 1: 新建 LLM 去重 prompt 文件

**Files:**
- Create: `app/llm/prompts/news_dedup.py`

- [ ] **Step 1: 创建 prompt 文件**

```python
"""新闻去重判断 prompt"""

DEDUP_SYSTEM_PROMPT = "你是新闻去重判断器。判断两条新闻是否报道同一事件。只回答 yes 或 no。"


MAX_TEXT_LEN = 500


def build_dedup_prompt(text_a: str, text_b: str) -> str:
    a = text_a[:MAX_TEXT_LEN] if len(text_a) > MAX_TEXT_LEN else text_a
    b = text_b[:MAX_TEXT_LEN] if len(text_b) > MAX_TEXT_LEN else text_b
    return f"新闻A: {a}\n新闻B: {b}"
```

- [ ] **Step 2: Commit**

```bash
git add app/llm/prompts/news_dedup.py
git commit -m "feat: 新增新闻去重LLM prompt"
```

---

### Task 2: 注册 LLM 路由 task_type

**Files:**
- Modify: `app/llm/router.py:9-25`

- [ ] **Step 1: 在 TASK_LAYER_MAP 中增加 news_dedup**

在 `TASK_LAYER_MAP` 字典中 `'company_identify'` 之后添加一行：

```python
    'news_dedup': LLMLayer.FLASH,
```

- [ ] **Step 2: Commit**

```bash
git add app/llm/router.py
git commit -m "feat: 注册news_dedup到LLM路由FLASH层"
```

---

### Task 3: 重构 news_dedup.py — 拆出分数方法 + 通用关键词提取

**Files:**
- Modify: `app/services/news_dedup.py`

- [ ] **Step 1: 添加通用关键词正则和停用词常量**

在类属性区域（`_ENTITY_TTL` 之后）添加：

```python
    _GENERAL_EN_RE = re.compile(r'[A-Za-z]{3,}')
    _GENERAL_CN_ORG_RE = re.compile(r'(?<!该)(?<!上市)(?<!多家)(?<!一家)(?<!这家)(?<!那家)([\u4e00-\u9fa5]{2,6}(?:公司|集团|银行|证券|科技|基金|保险|控股|汽车|电子|医药|能源))')
    _EN_STOPWORDS = frozenset({
        'CEO', 'CFO', 'CTO', 'COO', 'IPO', 'ETF', 'GDP', 'API', 'APP',
        'THE', 'AND', 'FOR', 'WITH', 'FROM', 'THAT', 'THIS', 'WILL',
        'HAS', 'HAD', 'WAS', 'ARE', 'BUT', 'NOT', 'ALL', 'CAN',
    })
```

- [ ] **Step 2: 添加 `_extract_general_keywords` 方法**

在 `_extract_fingerprint` 方法之后添加：

```python
    def _extract_general_keywords(self, text: str) -> set[str]:
        cleaned = self._strip_prefix(text)
        keywords = set()
        for m in self._GENERAL_EN_RE.finditer(cleaned):
            word = m.group().upper()
            if word not in self._EN_STOPWORDS:
                keywords.add(word)
        for m in self._GENERAL_CN_ORG_RE.finditer(cleaned):
            keywords.add(m.group())
        return keywords
```

- [ ] **Step 3: 添加 `_text_similarity_score` 和 `_fingerprint_overlap_count` 方法**

将现有 `_is_text_similar` 和 `_is_fingerprint_match` 的核心计算拆出：

```python
    def _text_similarity_score(self, text_a: str, text_b: str) -> float:
        a = self._normalize(text_a)
        b = self._normalize(text_b)
        if not a or not b:
            return 0.0
        return SequenceMatcher(None, a, b).ratio()

    def _fingerprint_overlap_count(self, fp_a: frozenset, fp_b: frozenset) -> int:
        return len(fp_a & fp_b)
```

然后修改 `_is_text_similar` 和 `_is_fingerprint_match` 复用这两个方法：

```python
    def _is_text_similar(self, text_a: str, text_b: str) -> bool:
        return self._text_similarity_score(text_a, text_b) >= SIMILARITY_THRESHOLD

    def _is_fingerprint_match(self, fp_a: frozenset, fp_b: frozenset) -> bool:
        if len(fp_a) < 2 or len(fp_b) < 2:
            return False
        intersection_count = self._fingerprint_overlap_count(fp_a, fp_b)
        union = fp_a | fp_b
        if len(union) < 3 or intersection_count < 2:
            return False
        return intersection_count / len(union) >= 0.5
```

- [ ] **Step 4: Commit**

```bash
git add app/services/news_dedup.py
git commit -m "refactor: 拆出分数方法，添加通用关键词提取"
```

---

### Task 4: 实现可疑对预筛选 + LLM 调用 + 锁拆分

**Files:**
- Modify: `app/services/news_dedup.py`

- [ ] **Step 1: 添加 `_find_suspect_pairs` 方法**

在 `_is_duplicate` 之后添加：

```python
    SOFT_SIMILARITY_THRESHOLD = 0.2

    def _find_suspect_pairs(self, groups: list[list[tuple]]) -> list[tuple[int, int]]:
        """在未合并的组代表之间，找出需要 LLM 判断的可疑对"""
        reps = []
        for i, group in enumerate(groups):
            _, content, fp = group[0]
            keywords = self._extract_general_keywords(content)
            reps.append((i, content, fp, keywords))

        pairs = []
        for ai in range(len(reps)):
            for bi in range(ai + 1, len(reps)):
                i_idx, i_content, i_fp, i_kw = reps[ai]
                j_idx, j_content, j_fp, j_kw = reps[bi]

                # 规则软匹配
                sim_score = self._text_similarity_score(i_content, j_content)
                if self.SOFT_SIMILARITY_THRESHOLD <= sim_score < SIMILARITY_THRESHOLD:
                    pairs.append((i_idx, j_idx))
                    continue
                fp_overlap = self._fingerprint_overlap_count(i_fp, j_fp)
                if fp_overlap == 1:
                    pairs.append((i_idx, j_idx))
                    continue

                # 通用关键词重叠
                common = i_kw & j_kw
                if len(common) >= 2:
                    pairs.append((i_idx, j_idx))

        return pairs
```

- [ ] **Step 2: 添加 `_llm_check_duplicate` 方法**

```python
    def _llm_check_duplicate(self, text_a: str, text_b: str) -> bool:
        """调用 LLM Flash 判断两条新闻是否同一事件，失败时返回 False（放行）"""
        try:
            from app.llm.router import llm_router
            from app.llm.prompts.news_dedup import DEDUP_SYSTEM_PROMPT, build_dedup_prompt

            provider = llm_router.route('news_dedup')
            if not provider:
                return False

            messages = [
                {'role': 'system', 'content': DEDUP_SYSTEM_PROMPT},
                {'role': 'user', 'content': build_dedup_prompt(text_a, text_b)},
            ]
            response = provider.chat(messages, temperature=0.1, max_tokens=10)
            is_dup = response.strip().lower().startswith('yes')
            if is_dup:
                logger.debug(f'[去重] LLM判定重复: {text_a[:30]}... ↔ {text_b[:30]}...')
            return is_dup
        except Exception as e:
            logger.warning(f'[去重] LLM调用失败，放行: {e}')
            return False
```

- [ ] **Step 3: 重写 `filter_duplicates` 方法，拆分锁段**

替换整个 `filter_duplicates` 方法：

```python
    def filter_duplicates(self, items: list, content_key) -> list:
        # 阶段 1：锁内完成规则分组 + 收集可疑对
        with self._lock:
            now = datetime.now()
            cutoff = now - timedelta(minutes=DEDUP_WINDOW_MINUTES)
            self._pushed_buffer = [r for r in self._pushed_buffer if r.timestamp > cutoff]

            item_data = []
            for item in items:
                content = content_key(item)
                fp = self._extract_fingerprint(content)
                item_data.append((item, content, fp))

            # 批内规则分组
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

            # 收集可疑对（仅多组时才需要）
            suspect_pairs = self._find_suspect_pairs(groups) if len(groups) > 1 else []

        # 阶段 2：锁外调用 LLM 判断可疑对
        llm_merges = []
        for i_idx, j_idx in suspect_pairs:
            _, i_content, _ = groups[i_idx][0]
            _, j_content, _ = groups[j_idx][0]
            if self._llm_check_duplicate(i_content, j_content):
                llm_merges.append((i_idx, j_idx))

        # 阶段 3：锁内执行 LLM 合并 + 跨历史去重
        with self._lock:
            # 执行 LLM 合并（将 j 组并入 i 组）
            merged_into = {}  # j_idx -> i_idx
            for i_idx, j_idx in llm_merges:
                # 找到实际目标（处理链式合并）
                target = i_idx
                while target in merged_into:
                    target = merged_into[target]
                if target != j_idx and j_idx not in merged_into:
                    merged_into[j_idx] = target
                    groups[target].extend(groups[j_idx])

            llm_filtered = len(merged_into)

            # 构建去重后的列表
            deduplicated = []
            for i, group in enumerate(groups):
                if i in merged_into:
                    continue
                best = max(group, key=lambda e: len(e[1]))
                deduplicated.append(best)

            # 跨历史去重
            result = []
            text_filtered = 0
            fp_filtered = 0
            contain_filtered = 0
            for item, content, fp in deduplicated:
                is_dup = False
                for r in self._pushed_buffer:
                    dup, method = self._is_duplicate(content, fp, r.content, r.fingerprint)
                    if dup:
                        is_dup = True
                        if method == 'text':
                            text_filtered += 1
                        elif method == 'containment':
                            contain_filtered += 1
                        else:
                            fp_filtered += 1
                        logger.debug(f'[去重] {method}命中: {fp} ↔ {r.fingerprint}')
                        break
                if not is_dup:
                    result.append(item)
                    self._pushed_buffer.append(PushedRecord(now, content, fp))

            batch_filtered = len(items) - len(deduplicated)
            total_filtered = len(items) - len(result)
            if total_filtered > 0:
                logger.info(
                    f'[去重] 输入 {len(items)} 条，过滤 {total_filtered} 条'
                    f'（批内合并{batch_filtered - llm_filtered}，LLM合并{llm_filtered}，'
                    f'文本相似{text_filtered}，指纹匹配{fp_filtered}，包含度{contain_filtered}），'
                    f'推送 {len(result)} 条'
                )

            return result
```

- [ ] **Step 4: Commit**

```bash
git add app/services/news_dedup.py
git commit -m "feat: 批内去重增加LLM第四通道（可疑对预筛选+锁拆分）"
```
