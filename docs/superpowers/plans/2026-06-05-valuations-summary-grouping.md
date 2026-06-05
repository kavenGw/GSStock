# 估值汇总页板块分组优化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `/valuations` 估值汇总页从「市场 Tab + 122 行平铺大表」改造为「板块为主轴的分组视图（组按标的数降序、组内按 Base 安全边际降序、可折叠、中文组名），市场降为筛选 chip，exclude 行置灰」。

**Architecture:** 服务端在路由层新增纯函数 `group_by_sector`（分组 + 排序 + 中文标签），`index()` 改为传 `groups` 给模板；模板按组渲染「组头 + 组内行」，去掉行内「板块」列；市场筛选与折叠为纯客户端 JS（切行可见性 + 更新组头计数 + 隐藏空组）。复用现有 `/api/prices`，无 DB / 无数据迁移 / 无新依赖。

**Tech Stack:** Flask + Jinja2 模板 + 原生 JS + Bootstrap5；pytest 单测；数据源 `docs/stock-analytics/valuations.yaml`。

**Conventions:** 测试命令 `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_valuations.py -v`（env 赋值在 `rtk` 之前）。git `add` 与 `commit` 放同一条命令链（防并行 session 抢 index）。响应中文、不写多余注释、不写 backup 文件。

---

## 文件结构

- **Modify** `app/routes/valuations.py` — 新增 `SECTOR_LABELS` 常量 + `group_by_sector()` 纯函数；`index()` 改传 `groups`
- **Modify** `app/templates/valuations.html` — 市场 Tab 改 chip、表格按组渲染、去掉行内板块列、加折叠/置灰/筛选 JS 与 CSS
- **Modify** `tests/test_valuations.py` — 新增 `group_by_sector` 单测 + 组渲染断言；更新 `switchTab`→`switchMarket` 的旧断言

---

## Task 1: 路由层分组函数 `group_by_sector` + `SECTOR_LABELS`

**Files:**
- Modify: `app/routes/valuations.py`（在 `_enrich` 之后、`index()` 之前插入）
- Test: `tests/test_valuations.py`

- [ ] **Step 1: Write the failing tests**

追加到 `tests/test_valuations.py` 末尾：

```python
def test_group_by_sector_orders_groups_by_count_desc():
    from app.routes.valuations import group_by_sector
    rows = [
        {'stock_code': 'a', 'sector': 'electronics', 'margin_base': 0.1},
        {'stock_code': 'b', 'sector': 'semiconductor', 'margin_base': 0.2},
        {'stock_code': 'c', 'sector': 'semiconductor', 'margin_base': 0.3},
        {'stock_code': 'd', 'sector': 'semiconductor', 'margin_base': 0.1},
    ]
    groups = group_by_sector(rows)
    assert [g['sector'] for g in groups] == ['semiconductor', 'electronics']
    assert groups[0]['count'] == 3
    assert groups[0]['label'] == '半导体'
    assert groups[1]['label'] == '电子'


def test_group_by_sector_sorts_rows_within_group_by_base_margin_desc():
    from app.routes.valuations import group_by_sector
    rows = [
        {'stock_code': 'lo', 'sector': 'materials', 'margin_base': 0.05},
        {'stock_code': 'hi', 'sector': 'materials', 'margin_base': 0.50},
        {'stock_code': 'none', 'sector': 'materials', 'margin_base': None},
        {'stock_code': 'mid', 'sector': 'materials', 'margin_base': 0.20},
    ]
    [grp] = group_by_sector(rows)
    assert [r['stock_code'] for r in grp['rows']] == ['hi', 'mid', 'lo', 'none']


def test_group_by_sector_unknown_sector_falls_back_to_raw():
    from app.routes.valuations import group_by_sector
    [grp] = group_by_sector([{'stock_code': 'x', 'sector': 'weird-thing', 'margin_base': 0.1}])
    assert grp['sector'] == 'weird-thing'
    assert grp['label'] == 'weird-thing'


def test_group_by_sector_none_sector_grouped_as_unclassified():
    from app.routes.valuations import group_by_sector
    [grp] = group_by_sector([{'stock_code': 'x', 'sector': None, 'margin_base': 0.1}])
    assert grp['label'] == '未分类'


def test_group_by_sector_empty_returns_empty():
    from app.routes.valuations import group_by_sector
    assert group_by_sector([]) == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_valuations.py -k group_by_sector -v`
Expected: FAIL — `ImportError: cannot import name 'group_by_sector'`

- [ ] **Step 3: Implement `SECTOR_LABELS` + `group_by_sector`**

在 `app/routes/valuations.py` 中 `_enrich` 函数之后、`@valuations_bp.route('/')` 之前插入：

```python
SECTOR_LABELS = {
    'semiconductor': '半导体',
    'electronics': '电子',
    'consumer': '消费',
    'materials': '材料',
    'energy': '能源',
    'healthcare': '医疗',
    'media': '媒体',
    'financial': '金融',
    'industrial': '工业',
    'ai-application': 'AI应用',
    'other': '其他',
}


def group_by_sector(rows: list[dict]) -> list[dict]:
    """按 sector 分组：组按标的数降序（并列按 sector 名稳定），组内按 Base 安全边际降序（None 末位）。
    sector 缺失归入「未分类」组；未知 sector 回退原始值。"""
    buckets: dict[str, list] = {}
    for r in rows:
        key = r.get('sector') or '__none__'
        buckets.setdefault(key, []).append(r)
    groups = []
    for key, items in buckets.items():
        items = sorted(items, key=lambda x: (x.get('margin_base') is None, -(x.get('margin_base') or 0)))
        label = '未分类' if key == '__none__' else SECTOR_LABELS.get(key, key)
        groups.append({'sector': key, 'label': label, 'count': len(items), 'rows': items})
    groups.sort(key=lambda g: (-g['count'], g['sector']))
    return groups
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_valuations.py -k group_by_sector -v`
Expected: PASS（5 passed）

- [ ] **Step 5: Commit**

```bash
rtk git add app/routes/valuations.py tests/test_valuations.py && rtk git commit -m "feat(valuations): 新增 group_by_sector 分组函数与板块中文映射"
```

---

## Task 2: `index()` 传 groups + 模板按组渲染

**Files:**
- Modify: `app/routes/valuations.py:61-78`（`index()`）
- Modify: `app/templates/valuations.html:28-60`（thead/tbody）
- Test: `tests/test_valuations.py`

- [ ] **Step 1: Write the failing test**

追加到 `tests/test_valuations.py` 末尾：

```python
def test_index_renders_sector_group_headers(app_client):
    html = app_client.get('/valuations/').data.decode('utf-8')
    assert 'group-header' in html, '缺板块组头'
    assert 'data-sector=' in html, '缺行/组头 data-sector 属性'
    # valuations.yaml 实际含半导体板块 → 组头中文名应出现
    assert '半导体' in html
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_valuations.py::test_index_renders_sector_group_headers -v`
Expected: FAIL — `assert 'group-header' in html`

- [ ] **Step 3: Update `index()` to pass groups**

替换 `app/routes/valuations.py` 的 `index()` 函数体（第 61-78 行）为：

```python
@valuations_bp.route('/')
def index():
    rows = load_valuations()
    codes = [r['stock_code'] for r in rows]
    prices = {}
    if codes:
        try:
            prices = unified_stock_data_service.get_realtime_prices(codes)
        except Exception as e:
            logger.warning(f'[估值页] 取实时价失败，降级渲染: {type(e).__name__}: {e}', exc_info=True)
    enriched = _enrich(rows, prices)
    groups = group_by_sector(enriched)
    market_counts = Counter(r.get('market') for r in enriched)
    return render_template(
        'valuations.html',
        groups=groups,
        market_counts=market_counts,
        total=len(enriched),
    )
```

- [ ] **Step 4: Replace template thead/tbody (the `{% else %}` table block)**

替换 `app/templates/valuations.html` 中第 22-59 行（从 `<ul class="nav nav-tabs...` 到 `</div>` 表格容器结束）为：

```html
<div class="mb-3" id="market-chips">
  <button class="btn btn-sm btn-primary chip" data-market="all" onclick="switchMarket(event,'all')">全部 ({{ total }})</button>
  <button class="btn btn-sm btn-outline-primary chip" data-market="A" onclick="switchMarket(event,'A')">A股 ({{ market_counts.get('A', 0) }})</button>
  <button class="btn btn-sm btn-outline-primary chip" data-market="HK" onclick="switchMarket(event,'HK')">港股 ({{ market_counts.get('HK', 0) }})</button>
  <button class="btn btn-sm btn-outline-primary chip" data-market="US" onclick="switchMarket(event,'US')">美股 ({{ market_counts.get('US', 0) }})</button>
</div>
<div class="table-responsive">
<table class="table table-sm table-hover val-table">
  <thead class="table-light">
    <tr>
      <th>代码</th><th>名称</th><th>币种</th><th>评级</th>
      <th class="text-end">Bear</th><th class="text-end">Base</th><th class="text-end">Bull</th>
      <th class="text-end">当前价</th><th class="text-end">Base安全边际</th>
      <th>日期</th><th>文档</th>
    </tr>
  </thead>
  <tbody>
  {% for g in groups %}
    <tr class="group-header" data-sector="{{ g.sector }}" onclick="toggleGroup('{{ g.sector }}')">
      <th colspan="11"><span class="caret">▼</span> {{ g.label }} <span class="badge bg-secondary group-count">{{ g.count }}</span></th>
    </tr>
    {% for r in g.rows %}
    <tr data-code="{{ r.stock_code }}" data-market="{{ r.market }}" data-sector="{{ g.sector }}"
        class="grp-{{ g.sector }}{% if r.rating == 'exclude' %} row-muted{% endif %}">
      <td>{{ r.stock_code }}</td>
      <td>{{ r.stock_name }}</td>
      <td>{{ r.currency or '—' }}</td>
      <td><span class="badge bg-secondary rating-badge">{{ r.rating or '—' }}</span></td>
      <td class="text-end">{{ '%.2f'|format(r.bear) if r.bear is not none else '—' }}</td>
      <td class="text-end">{{ '%.2f'|format(r.base) if r.base is not none else '—' }}</td>
      <td class="text-end">{{ '%.2f'|format(r.bull) if r.bull is not none else '—' }}</td>
      <td class="text-end cell-price">{{ '%.2f'|format(r.current_price) if r.current_price is not none else '—' }}</td>
      <td class="text-end cell-margin {% if r.margin_base is not none and r.margin_base >= 0 %}margin-pos{% elif r.margin_base is not none %}margin-neg{% endif %}">
        {{ '%+.1f%%'|format(r.margin_base * 100) if r.margin_base is not none else '—' }}
      </td>
      <td>{{ r.conviction_date or '—' }}</td>
      <td>{% if r.source_doc %}<span title="{{ r.source_doc }}" style="cursor:help">📄</span>{% else %}—{% endif %}</td>
    </tr>
    {% endfor %}
  {% endfor %}
  </tbody>
</table>
</div>
```

注意：① 行内去掉了「板块」列（已在组头）；② 顶部 `{% if not rows %}` 仍依赖变量——下一步修正。

- [ ] **Step 5: Fix the empty-guard variable**

`index()` 不再传 `rows`，模板第 19 行 `{% if not rows %}` 改判 `groups`。在 `app/templates/valuations.html` 中替换：

```html
{% if not groups %}
<div class="alert alert-warning">暂无估值数据（docs/stock-analytics/valuations.yaml 为空或缺失）。</div>
{% else %}
```

- [ ] **Step 6: Run the new + smoke tests**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_valuations.py::test_index_renders_sector_group_headers tests/test_valuations.py::test_index_route_smoke tests/test_valuations.py::test_index_has_table_headers_and_refresh -v`
Expected: PASS（3 passed）

- [ ] **Step 7: Commit**

```bash
rtk git add app/routes/valuations.py app/templates/valuations.html tests/test_valuations.py && rtk git commit -m "feat(valuations): index 传 groups，模板按板块分组渲染，行内去板块列"
```

---

## Task 3: 前端 JS（市场 chip 筛选 + 折叠 + exclude 置灰）

**Files:**
- Modify: `app/templates/valuations.html`（`{% block extra_css %}` 加样式；`<script>` 段重写 `switchTab`→`switchMarket` + 新增 `toggleGroup`）
- Test: `tests/test_valuations.py:170-175`（更新旧断言）

- [ ] **Step 1: Update the existing test that asserts the old JS name**

把 `tests/test_valuations.py` 中 `test_index_has_currency_column_and_data_market`（第 170-175 行）整体替换为：

```python
def test_index_has_currency_column_and_data_market(app_client):
    html = app_client.get('/valuations/').data.decode('utf-8')
    assert '币种' in html, '缺币种列头'
    assert 'data-market=' in html, '缺行 data-market 属性'
    assert 'switchMarket' in html, '缺 switchMarket JS'
    assert 'toggleGroup' in html, '缺 toggleGroup JS'
```

- [ ] **Step 2: Run it to verify it fails**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_valuations.py::test_index_has_currency_column_and_data_market -v`
Expected: FAIL — `assert 'switchMarket' in html`（当前仍是 switchTab）

- [ ] **Step 3: Add CSS for muted rows / group header / chips**

在 `app/templates/valuations.html` 的 `{% block extra_css %}` `<style>` 内追加：

```css
.row-muted td { color: #adb5bd; }
.row-muted .rating-badge { opacity: .6; }
.group-header { cursor: pointer; background: #f1f3f5; }
.group-header:hover { background: #e9ecef; }
.group-header th { font-size: 13px; }
.group-header .caret { display: inline-block; width: 1em; transition: transform .15s; }
.group-header.collapsed .caret { transform: rotate(-90deg); }
#market-chips .chip { margin-right: 6px; }
```

- [ ] **Step 4: Replace the `<script>` body**

替换 `app/templates/valuations.html` 中 `switchTab` 函数（第 93-101 行）为 `switchMarket` + `toggleGroup`，并保留 `refreshPrices`/`fmtPrice`/`fmtMargin` 不变。新函数：

```javascript
let currentMarket = 'all';

function switchMarket(ev, market) {
  ev.preventDefault();
  currentMarket = market;
  document.querySelectorAll('#market-chips .chip').forEach(b => {
    const on = b.dataset.market === market;
    b.classList.toggle('btn-primary', on);
    b.classList.toggle('btn-outline-primary', !on);
  });
  applyMarketFilter();
}

function applyMarketFilter() {
  document.querySelectorAll('tr[data-code]').forEach(tr => {
    const mOk = currentMarket === 'all' || tr.dataset.market === currentMarket;
    const collapsed = tr.classList.contains('hidden-by-group');
    tr.style.display = (mOk && !collapsed) ? '' : 'none';
    tr.dataset.marketHidden = mOk ? '' : '1';
  });
  document.querySelectorAll('.group-header').forEach(h => {
    const sector = h.dataset.sector;
    const rows = document.querySelectorAll('tr.grp-' + CSS.escape(sector) + '[data-code]');
    let visible = 0;
    rows.forEach(r => { if (r.dataset.marketHidden !== '1') visible++; });
    h.style.display = visible > 0 ? '' : 'none';
    const badge = h.querySelector('.group-count');
    if (badge) badge.textContent = visible;
  });
}

function toggleGroup(sector) {
  const header = document.querySelector('.group-header[data-sector="' + sector + '"]');
  const collapsed = header.classList.toggle('collapsed');
  document.querySelectorAll('tr.grp-' + CSS.escape(sector) + '[data-code]').forEach(tr => {
    tr.classList.toggle('hidden-by-group', collapsed);
  });
  applyMarketFilter();
}
```

说明：`hidden-by-group`（折叠态）与 `marketHidden`（市场过滤态）两个维度共同决定行 `display`；组头计数只数「未被市场过滤」的行，折叠不改计数。

- [ ] **Step 5: Run the full valuations test file**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_valuations.py -v`
Expected: PASS（全部，含旧测试 + 新增 group_by_sector 5 项 + 组渲染 + JS 断言）

- [ ] **Step 6: Manual smoke (启动 app 目测)**

Run: `python run.py`，浏览器开 `http://127.0.0.1:5000/valuations`
检查清单：
- 按板块分组、组头中文名 + 计数，组按标的数降序（半导体在最上）
- 组内按 Base 安全边际降序
- 点市场 chip（A股/港股/美股）：行过滤、组头计数更新、空组隐藏；再点「全部」恢复
- 点组头：折叠/展开，箭头转向
- exclude 行置灰
- 点「🔄 刷新实时价」：当前价/安全边际单元格更新
关掉 `run.py`。

- [ ] **Step 7: Commit**

```bash
rtk git add app/templates/valuations.html tests/test_valuations.py && rtk git commit -m "feat(valuations): 市场 chip 筛选 + 板块折叠 + exclude 行置灰"
```

---

## Self-Review 记录

- **Spec 覆盖**：① 板块分组（Task 1+2）② 板块主轴/市场降筛选器（Task 2 chip + Task 3 switchMarket）③ 组头名称+数量、组按数降序、组内 Base 边际降序（Task 1）④ exclude 置灰（Task 2 row-muted + Task 3 CSS）⑤ 折叠（Task 3 toggleGroup）⑥ 中文组名（Task 1 SECTOR_LABELS）。全覆盖。
- **Placeholder 扫描**：无 TBD/TODO，所有代码步给出完整代码块。
- **类型/命名一致性**：`group_by_sector` 返回 `{'sector','label','count','rows'}` 在 Task 1 定义、Task 2 模板按这些键访问（`g.sector`/`g.label`/`g.count`/`g.rows`）；JS `grp-{sector}` class 与 `data-sector` 在 Task 2 模板与 Task 3 JS 一致；`switchMarket`/`toggleGroup` 在模板 onclick 与 JS 定义一致。
- **旧测试回归**：`test_index_renders_market_tabs_with_counts` 仍要求 `全部 (N)`/`A股 (N)` 文案与计数——chip 保留同文案同格式，不回归；`test_index_has_currency_column_and_data_market` 在 Task 3 Step 1 同步更新为 `switchMarket`/`toggleGroup`。
