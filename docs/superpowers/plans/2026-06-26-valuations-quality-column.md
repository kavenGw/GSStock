# 估值表「质地」列 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 `/valuations` 估值表新增一列「质地」（★1–5 星），表达抛开当前价格的公司好坏。

**Architecture:** 质地存 `valuations.yaml` 可选整数字段 `quality`；缺失时渲染层按 `rating` 现算星级（core5/config4/watch3/exclude2），手写 `quality:N` 覆写。`sync_valuations.upsert` 把 `quality` 加进保留名单（同 `note`），不被同步冲掉。前端置灰区分「推算」与「手写」，并接入现有排序框架。

**Tech Stack:** Flask + Jinja2 + 原生 JS（无新依赖）；pytest 单测。

## Global Constraints

- 响应中文；不写多余注释；不写 backup 文件。
- 所有 `python/pytest` 命令前加 `rtk`，env 赋值在 `rtk` 之前：`PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest ...`。
- 质地刻度：整数 1–5。映射 `RATING_TO_QUALITY = {'core': 5, 'config': 4, 'watch': 3, 'exclude': 2}`，无/未知 rating 兜底 3。非法 `quality`（非 1–5 整数）回退到 rating 推算。★1 星保留给手动。
- `/api/prices` 不传质地（质地与价格无关）。
- 不批量回填 167 条 yaml；只有手动覆写的条目才出现 `quality` 键。
- 分支策略：本功能改 `app/`，按 dev-environment 约定应在独立 git worktree 进行（执行阶段由 using-git-worktrees 处理）。
- 提交：`git add <精确路径> && git commit` 同一条命令链。

---

### Task 1: 后端 `resolve_quality` + 映射常量

**Files:**
- Modify: `app/services/valuations_helpers.py`（新增常量 + 函数）
- Modify: `app/routes/valuations.py:9-11`（从 helpers 再导出，供测试沿用 `from app.routes.valuations import resolve_quality`）
- Test: `tests/test_valuations.py`（追加）

**Interfaces:**
- Produces:
  - `RATING_TO_QUALITY: dict[str, int]` = `{'core': 5, 'config': 4, 'watch': 3, 'exclude': 2}`
  - `QUALITY_FALLBACK: int = 3`
  - `resolve_quality(row: dict) -> tuple[int, bool]` —— 返回 `(stars, derived)`；`stars∈[1,5]`，`derived=True` 表示来自 rating 推算、`False` 表示来自合法的 `row['quality']` 覆写。

- [ ] **Step 1: 写失败测试**

追加到 `tests/test_valuations.py`：

```python
from app.routes.valuations import resolve_quality


def test_resolve_quality_manual_override():
    assert resolve_quality({'quality': 1, 'rating': 'core'}) == (1, False)
    assert resolve_quality({'quality': 5, 'rating': 'exclude'}) == (5, False)


def test_resolve_quality_derived_from_rating():
    assert resolve_quality({'rating': 'core'}) == (5, True)
    assert resolve_quality({'rating': 'config'}) == (4, True)
    assert resolve_quality({'rating': 'watch'}) == (3, True)
    assert resolve_quality({'rating': 'exclude'}) == (2, True)


def test_resolve_quality_unknown_rating_fallback():
    assert resolve_quality({'rating': None}) == (3, True)
    assert resolve_quality({}) == (3, True)
    assert resolve_quality({'rating': 'mystery'}) == (3, True)


def test_resolve_quality_illegal_value_falls_back():
    assert resolve_quality({'quality': 0, 'rating': 'core'}) == (5, True)
    assert resolve_quality({'quality': 6, 'rating': 'watch'}) == (3, True)
    assert resolve_quality({'quality': 'x', 'rating': 'config'}) == (4, True)
    assert resolve_quality({'quality': 3.5, 'rating': 'core'}) == (5, True)
    assert resolve_quality({'quality': None, 'rating': 'exclude'}) == (2, True)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_valuations.py -k resolve_quality -v`
Expected: FAIL —— `ImportError: cannot import name 'resolve_quality'`

- [ ] **Step 3: 实现**

在 `app/services/valuations_helpers.py` 末尾追加：

```python
RATING_TO_QUALITY = {'core': 5, 'config': 4, 'watch': 3, 'exclude': 2}
QUALITY_FALLBACK = 3


def resolve_quality(row: dict) -> tuple[int, bool]:
    """返回 (星级 1-5, 是否由 rating 推算)。row['quality'] 为合法 1-5 整数→手动覆写；
    否则按 rating 映射，未知 rating 兜底 QUALITY_FALLBACK。"""
    q = row.get('quality')
    if isinstance(q, int) and not isinstance(q, bool) and 1 <= q <= 5:
        return q, False
    return RATING_TO_QUALITY.get(row.get('rating'), QUALITY_FALLBACK), True
```

在 `app/routes/valuations.py` 的 import 块（第 9–11 行）把 `resolve_quality` 加入从 helpers 的导入：

```python
from app.services.valuations_helpers import (
    VALUATIONS_PATH, load_valuations, _fetch_code, _extract_price, compute_margin, subsector_of,
    resolve_quality,
)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_valuations.py -k resolve_quality -v`
Expected: PASS（5 个用例全过）

- [ ] **Step 5: 提交**

```bash
git add app/services/valuations_helpers.py app/routes/valuations.py tests/test_valuations.py && git commit -m "feat(valuations): resolve_quality 质地星级解析(rating 现算 + quality 覆写)"
```

---

### Task 2: `_enrich` 注入 `quality` / `quality_derived`

**Files:**
- Modify: `app/routes/valuations.py:39-58`（`_enrich`）
- Test: `tests/test_valuations.py`（追加）

**Interfaces:**
- Consumes: `resolve_quality`（Task 1）
- Produces: `_enrich` 返回的每行新增两键 —— `quality: int`、`quality_derived: bool`。

- [ ] **Step 1: 写失败测试**

追加到 `tests/test_valuations.py`：

```python
from app.routes.valuations import _enrich


def test_enrich_adds_quality_derived_from_rating():
    rows = [{'stock_code': '600519', 'rating': 'core'}]
    out = _enrich(rows, prices={}, cat_map={})
    assert out[0]['quality'] == 5
    assert out[0]['quality_derived'] is True


def test_enrich_quality_manual_override():
    rows = [{'stock_code': '600519', 'rating': 'watch', 'quality': 5}]
    out = _enrich(rows, prices={}, cat_map={})
    assert out[0]['quality'] == 5
    assert out[0]['quality_derived'] is False
```

- [ ] **Step 2: 运行测试确认失败**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_valuations.py -k enrich_adds_quality -v`
Expected: FAIL —— `KeyError: 'quality'`

- [ ] **Step 3: 实现**

在 `app/routes/valuations.py` 的 `_enrich` 循环里，构造 `out.append({...})` 的字典内加入两行（与 `'rating_rank'` 等同级）。先在 append 前算出：

```python
    for r in rows:
        data = prices.get(r['stock_code']) or {}
        price = _extract_price(data)
        quality, quality_derived = resolve_quality(r)
        out.append({
            **r,
            'category': cat_map.get(r['stock_code']),
            'themes': r.get('themes') or [],
            'subsector': subsector_of(r),
            'current_price': price,
            'rating_rank': RATING_RANK.get(r.get('rating')),
            'date_rank': _date_rank(r.get('conviction_date')),
            'quality': quality,
            'quality_derived': quality_derived,
            'margin_bear': compute_margin(r.get('bear'), price),
            'margin_base': compute_margin(r.get('base'), price),
            'margin_bull': compute_margin(r.get('bull'), price),
        })
```

- [ ] **Step 4: 运行测试确认通过**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_valuations.py -k "enrich_adds_quality or enrich_quality_manual" -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add app/routes/valuations.py tests/test_valuations.py && git commit -m "feat(valuations): _enrich 注入 quality/quality_derived"
```

---

### Task 3: `sync_valuations.upsert` 保留 `quality`

**Files:**
- Modify: `scripts/sync_valuations.py:99-108`（`upsert`）
- Test: `tests/test_sync_valuations.py`（追加）

**Interfaces:**
- Consumes: 既有 `upsert(entries, new_entry)`
- Produces: 行为变更 —— 旧条目里的 `quality`（连同已有的 `note`）在 upsert 重建后保留。

- [ ] **Step 1: 写失败测试**

追加到 `tests/test_sync_valuations.py`：

```python
def test_upsert_preserves_quality():
    from scripts.sync_valuations import upsert
    entries = [{'stock_code': '600519', 'rating': 'core', 'quality': 5, 'note': '老笔记'}]
    upsert(entries, {'stock_code': '600519', 'rating': 'watch'})
    assert entries[0]['quality'] == 5
    assert entries[0]['note'] == '老笔记'
    assert entries[0]['rating'] == 'watch'


def test_upsert_new_entry_has_no_quality():
    from scripts.sync_valuations import upsert
    entries = []
    upsert(entries, {'stock_code': '000001', 'rating': 'config'})
    assert 'quality' not in entries[0]
```

- [ ] **Step 2: 运行测试确认失败**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_sync_valuations.py -k upsert_preserves_quality -v`
Expected: FAIL —— `AssertionError`（`quality` 被丢弃，KeyError 或断言失败）

- [ ] **Step 3: 实现**

把 `scripts/sync_valuations.py` 的 `upsert` 改为保留多键：

```python
def upsert(entries: list[dict], new_entry: dict) -> list[dict]:
    """按 stock_code 原地替换已有条目，不存在则追加；保留旧条目手工字段（note / quality）。"""
    for i, e in enumerate(entries):
        if e.get('stock_code') == new_entry['stock_code']:
            for key in ('note', 'quality'):
                if key in e and key not in new_entry:
                    new_entry = {**new_entry, key: e[key]}
            entries[i] = new_entry
            return entries
    entries.append(new_entry)
    return entries
```

- [ ] **Step 4: 运行测试确认通过**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_sync_valuations.py -k "upsert_preserves_quality or upsert_new_entry_has_no_quality" -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add scripts/sync_valuations.py tests/test_sync_valuations.py && git commit -m "feat(valuations): sync upsert 保留手写 quality 不被冲掉"
```

---

### Task 4: 前端「质地」列（模板 + CSS + 排序）

**Files:**
- Modify: `app/templates/valuations.html`（表头、行单元格、两处 group-header `colspan`、CSS、JS 排序白名单）
- Test: `tests/test_valuations.py`（扩展路由 smoke 测试）

**Interfaces:**
- Consumes: 行字段 `r.quality`（int 1–5）、`r.quality_derived`（bool）（Task 2）

- [ ] **Step 1: 写失败测试**

在 `tests/test_valuations.py` 末尾追加（与现有 `test_index_route_smoke` 同款用 `app_client`）：

```python
def test_index_route_renders_quality_column(app_client):
    resp = app_client.get('/valuations/')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert '质地' in html
    assert 'data-sort="quality"' in html
    assert '★' in html
```

- [ ] **Step 2: 运行测试确认失败**

Run（HTML 路由要走 create_app，输出有 crawl4ai 噪音，重定向到文件再看结果）：
`PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_valuations.py -k renders_quality_column -v > /tmp/q.txt 2>&1; grep -E "passed|failed|PASSED|FAILED" /tmp/q.txt`
Expected: FAIL（`'质地' not in html`）

- [ ] **Step 3: 实现**

**(a) 表头** —— 在 `app/templates/valuations.html` 第 79 行「评级」`<th>` 之后插入一列：

```html
      <th class="sortable text-center" data-sort="quality" onclick="sortBy('quality')">质地<span class="sort-arrow"></span></th>
```

**(b) 行单元格** —— 在第 112 行「评级」`<td>...rating...</td>` 之后插入：

```html
        <td class="text-center"><span class="stars{% if r.quality_derived %} q-derived{% endif %}" title="{{ '由评级推算' if r.quality_derived else '手动' }}">{{ '★' * r.quality }}{{ '☆' * (5 - r.quality) }}</span></td>
```

**(c) 行 `data-mquality`** —— 在第 98 行 `data-mrating=...` 之后插入（供排序）：

```html
          data-mquality="{{ r.quality }}"
```

**(d) group-header colspan** —— 把第 90、94 行的 `colspan="12"` 改为 `colspan="13"`（共两处）。

**(e) CSS** —— 在 `<style>` 块内（第 8 行 `.rating-badge` 附近）追加：

```css
.stars { color: #f0ad4e; letter-spacing: 1px; }
.q-derived { opacity: .55; }
```

**(f) JS 排序白名单** —— 第 154 行把 `'quality'` 加入合法 sortKey 列表，使持久化生效：

```javascript
    if (['bear', 'base', 'bull', 'rating', 'date', 'quality'].includes(p.sortKey)) sortKey = p.sortKey;
```

（`sortRows`/`marginOf` 已是泛型读 `data-m<key>`，`data-mquality` 自动接入，无需改排序算法。）

- [ ] **Step 4: 运行测试确认通过**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_valuations.py -k renders_quality_column -v > /tmp/q.txt 2>&1; grep -E "passed|failed" /tmp/q.txt`
Expected: PASS

- [ ] **Step 5: 人工目检（可选但建议）**

`rtk python run.py` 后浏览器开 `http://127.0.0.1:5000/valuations/`：确认质地列在评级右侧、星级显示、推算行置灰、点表头「质地」可排序。看完 `Ctrl+C`。

- [ ] **Step 6: 提交**

```bash
git add app/templates/valuations.html tests/test_valuations.py && git commit -m "feat(valuations): 前端质地列(★1-5/推算置灰/可排序)"
```

---

### Task 5: 全量回归

- [ ] **Step 1: 跑全套 valuations 相关测试**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_valuations.py tests/test_sync_valuations.py -v > /tmp/all.txt 2>&1; grep -E "passed|failed" /tmp/all.txt`
Expected: 全 PASS，无 FAIL

- [ ] **Step 2: 若上一步全绿，无需提交（无代码变更）；若发现回归，按 systematic-debugging 修复后再补提交。**

---

## Self-Review

**1. Spec coverage：**
- 数据模型（quality 可选字段 + 缺失现算 + 非法回退）→ Task 1 ✓
- 不批量回填（只现算）→ Task 1/2（无 yaml 写入）✓
- sync 防冲 → Task 3 ✓
- 后端 resolve_quality / _enrich / `/api/prices` 不动 → Task 1、2（`/api/prices` 全程未触碰）✓
- 前端列 / 置灰区分 / 可排序 / colspan +1 → Task 4 ✓
- 测试（resolve_quality 四档+覆写+越界、upsert 保留、路由渲染）→ Task 1、3、4 ✓

**2. Placeholder scan：** 无 TBD/TODO/“add error handling”等占位；每个代码步均给出完整代码。✓

**3. Type consistency：** `resolve_quality(row)->tuple[int,bool]` 在 Task 1 定义，Task 2 解包 `quality, quality_derived` 一致；行字段 `quality`/`quality_derived` 在 Task 2 产出、Task 4 模板消费一致；`data-mquality` ↔ JS `marginOf(tr,'quality')` 读 `dataset.mquality` 一致；`RATING_TO_QUALITY` 键 `core/config/watch/exclude` 与 spec 映射表一致。✓
