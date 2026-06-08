# 估值汇总页多排序优化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 `/valuations` 估值汇总页支持点列头按 Bear/Base/Bull 安全边际排序、分组↔平铺模式切换，并把偏好持久化到 localStorage。

**Architecture:** 纯客户端方案。服务端照旧按板块分组渲染，但每行额外输出 `margin_bear/base/bull` 为 `data-*` 属性、并带 `sector_label`（供平铺模式「板块」列）；排序/升降/模式切换全由前端 JS 重排 DOM，零网络。复用现有 `/api/prices`。

**Tech Stack:** Flask + Jinja2 模板 + 原生 JS + Bootstrap5；pytest（服务端单测 + HTML smoke 断言）。

**设计文档：** `docs/superpowers/specs/2026-06-08-valuations-multi-sort-design.md`

**改动文件：**
- `app/routes/valuations.py` — `group_by_sector` 给每行回填 `sector_label`
- `app/templates/valuations.html` — 列头/列结构 + CSS + 全套排序/模式 JS
- `tests/test_valuations.py` — 新增 1 个单测 + 2 个 smoke + 修 1 个既有 smoke

**测试命令（Windows，env 在 rtk 前）：**
- 单个：`PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_valuations.py::<name> -v`
- 全量：`PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_valuations.py -v`

---

## Task 1: 服务端为每行回填 sector_label

平铺模式要在独立「板块」列显示每只票的板块中文名。`group_by_sector` 已为每组算出中文 `label`，把它写回组内每一行即可。

**Files:**
- Modify: `app/routes/valuations.py:84-87`（`group_by_sector` 的组装循环）
- Test: `tests/test_valuations.py`

- [ ] **Step 1: Write the failing test**

在 `tests/test_valuations.py` 末尾追加：

```python
def test_group_by_sector_assigns_sector_label_to_rows():
    from app.routes.valuations import group_by_sector
    groups = group_by_sector([
        {'stock_code': 'a', 'sector': 'semiconductor', 'margin_base': 0.1},
        {'stock_code': 'b', 'sector': None, 'margin_base': 0.2},
    ])
    by_sector = {g['sector']: g for g in groups}
    assert by_sector['semiconductor']['rows'][0]['sector_label'] == '半导体'
    assert by_sector['__none__']['rows'][0]['sector_label'] == '未分类'
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_valuations.py::test_group_by_sector_assigns_sector_label_to_rows -v`
Expected: FAIL with `KeyError: 'sector_label'`

- [ ] **Step 3: Write minimal implementation**

`app/routes/valuations.py`，把 `group_by_sector` 的循环体（当前 84-87 行）改为：

```python
    for key, items in buckets.items():
        items = sorted(items, key=lambda x: (x.get('margin_base') is None, -(x.get('margin_base') or 0)))
        label = '未分类' if key == '__none__' else SECTOR_LABELS.get(key, key)
        for r in items:
            r['sector_label'] = label
        groups.append({'sector': key, 'label': label, 'count': len(items), 'rows': items})
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_valuations.py::test_group_by_sector_assigns_sector_label_to_rows -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
rtk git add app/routes/valuations.py tests/test_valuations.py && rtk git commit -m "feat(valuations): group_by_sector 回填 sector_label 供平铺模式板块列"
```

---

## Task 2: 模板列结构改造（板块列 + 三列并入边际 + 可排序列头）

把表格改为：新增可隐「板块」列；Bear/Base/Bull 三列由「只显示绝对值」改为「绝对值 + 小号边际 span」并加可排序列头；删除独立「Base安全边际」列。列总数仍为 11，组头 `colspan="11"` 不变。

**Files:**
- Modify: `app/templates/valuations.html:4-17`（CSS）、`:36-72`（table 结构）
- Test: `tests/test_valuations.py`

- [ ] **Step 1: Write the failing smoke tests**

在 `tests/test_valuations.py` 末尾追加：

```python
def test_index_has_sortable_headers_and_sector_column(app_client):
    html = app_client.get('/valuations/').data.decode('utf-8')
    assert 'data-sort="bear"' in html, '缺 Bear 可排序列头'
    assert 'data-sort="base"' in html, '缺 Base 可排序列头'
    assert 'data-sort="bull"' in html, '缺 Bull 可排序列头'
    assert 'data-mbase=' in html, '缺行 base 边际 data 属性'
    assert 'col-sector' in html, '缺板块列'
    assert 'sortBy(' in html, '缺 sortBy 列头绑定'
```

并把既有的 `test_index_has_table_headers_and_refresh`（约 126-131 行）整体替换为（去掉已删除的 `安全边际` 断言）：

```python
def test_index_has_table_headers_and_refresh(app_client):
    resp = app_client.get('/valuations/')
    html = resp.data.decode('utf-8')
    for col in ('Bear', 'Base', 'Bull', '当前价'):
        assert col in html, f'缺列头 {col}'
    assert 'id="refresh-btn"' in html
```

- [ ] **Step 2: Run tests to verify new one fails**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_valuations.py::test_index_has_sortable_headers_and_sector_column -v`
Expected: FAIL（`data-sort="bear"` 不在 html）

- [ ] **Step 3: 改 CSS**

`app/templates/valuations.html`，在 `{% block extra_css %}` 的 `<style>` 内（现 16 行 `#market-chips .chip` 之后）追加：

```css
.val-table th.sortable { cursor: pointer; user-select: none; }
.val-table th.sortable:hover { background: #e9ecef; }
.sort-arrow { display: inline-block; width: 1em; text-align: left; }
.mg { font-size: 11px; margin-left: 4px; }
table.mode-grouped .col-sector { display: none; }
table.mode-flat .group-header { display: none; }
#mode-toggle .btn { padding: .15rem .55rem; }
```

- [ ] **Step 4: 改市场 chip 行 + table 结构**

把现有 `<div class="mb-3" id="market-chips"> ... </div>`（30-35 行）替换为一个 flex 容器，右侧加模式切换：

```html
<div class="mb-3 d-flex justify-content-between align-items-center flex-wrap gap-2">
  <div id="market-chips">
    <button class="btn btn-sm btn-primary chip" data-market="all" onclick="switchMarket(event,'all')">全部 ({{ total }})</button>
    <button class="btn btn-sm btn-outline-primary chip" data-market="A" onclick="switchMarket(event,'A')">A股 ({{ market_counts.get('A', 0) }})</button>
    <button class="btn btn-sm btn-outline-primary chip" data-market="HK" onclick="switchMarket(event,'HK')">港股 ({{ market_counts.get('HK', 0) }})</button>
    <button class="btn btn-sm btn-outline-primary chip" data-market="US" onclick="switchMarket(event,'US')">美股 ({{ market_counts.get('US', 0) }})</button>
  </div>
  <div id="mode-toggle" class="btn-group btn-group-sm">
    <button class="btn btn-primary" data-mode="grouped" onclick="setMode('grouped')">▣ 分组</button>
    <button class="btn btn-outline-primary" data-mode="flat" onclick="setMode('flat')">▤ 平铺</button>
  </div>
</div>
```

把 `<table class="table table-sm table-hover val-table">`（37 行）替换为：

```html
<table id="val-table" class="table table-sm table-hover val-table mode-grouped">
```

把 `<thead>...</thead>`（38-45 行）替换为：

```html
  <thead class="table-light">
    <tr>
      <th>代码</th><th>名称</th><th class="col-sector">板块</th><th>币种</th><th>评级</th>
      <th class="text-end sortable" data-sort="bear" onclick="sortBy('bear')">Bear<span class="sort-arrow"></span></th>
      <th class="text-end sortable" data-sort="base" onclick="sortBy('base')">Base<span class="sort-arrow"></span></th>
      <th class="text-end sortable" data-sort="bull" onclick="sortBy('bull')">Bull<span class="sort-arrow"></span></th>
      <th class="text-end">当前价</th>
      <th>日期</th><th>文档</th>
    </tr>
  </thead>
```

把标的行 `<tr data-code=...>...</tr>`（52-67 行）整体替换为（新增 3 个 `data-m*` 属性 + 板块列 + 三列并入边际、删独立边际列）：

```html
    <tr data-code="{{ r.stock_code }}" data-market="{{ r.market }}" data-sector="{{ g.sector }}"
        data-mbear="{{ r.margin_bear if r.margin_bear is not none else '' }}"
        data-mbase="{{ r.margin_base if r.margin_base is not none else '' }}"
        data-mbull="{{ r.margin_bull if r.margin_bull is not none else '' }}"
        class="grp-{{ g.sector }}{% if r.rating == 'exclude' %} row-muted{% endif %}">
      <td>{{ r.stock_code }}</td>
      <td>{{ r.stock_name }}</td>
      <td class="col-sector"><span class="badge bg-light text-secondary">{{ r.sector_label }}</span></td>
      <td>{{ r.currency or '—' }}</td>
      <td><span class="badge bg-secondary rating-badge">{{ r.rating or '—' }}</span></td>
      <td class="text-end">
        {{ '%.2f'|format(r.bear) if r.bear is not none else '—' }}
        <span class="mg cell-mbear {% if r.margin_bear is not none and r.margin_bear >= 0 %}margin-pos{% elif r.margin_bear is not none %}margin-neg{% endif %}">{{ '%+.1f%%'|format(r.margin_bear * 100) if r.margin_bear is not none else '' }}</span>
      </td>
      <td class="text-end">
        {{ '%.2f'|format(r.base) if r.base is not none else '—' }}
        <span class="mg cell-mbase {% if r.margin_base is not none and r.margin_base >= 0 %}margin-pos{% elif r.margin_base is not none %}margin-neg{% endif %}">{{ '%+.1f%%'|format(r.margin_base * 100) if r.margin_base is not none else '' }}</span>
      </td>
      <td class="text-end">
        {{ '%.2f'|format(r.bull) if r.bull is not none else '—' }}
        <span class="mg cell-mbull {% if r.margin_bull is not none and r.margin_bull >= 0 %}margin-pos{% elif r.margin_bull is not none %}margin-neg{% endif %}">{{ '%+.1f%%'|format(r.margin_bull * 100) if r.margin_bull is not none else '' }}</span>
      </td>
      <td class="text-end cell-price">{{ '%.2f'|format(r.current_price) if r.current_price is not none else '—' }}</td>
      <td>{{ r.conviction_date or '—' }}</td>
      <td>{% if r.source_doc %}<span title="{{ r.source_doc }}" style="cursor:help">📄</span>{% else %}—{% endif %}</td>
    </tr>
```

> 组头行 `<th colspan="11">`（49 行）保持不变：列数 11→（删边际列 +加板块列）仍为 11。

- [ ] **Step 5: Run tests to verify they pass**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_valuations.py::test_index_has_sortable_headers_and_sector_column tests/test_valuations.py::test_index_has_table_headers_and_refresh -v`
Expected: 两个都 PASS

- [ ] **Step 6: Commit**

```bash
rtk git add app/templates/valuations.html tests/test_valuations.py && rtk git commit -m "feat(valuations): 列头可排序 + 板块列 + 三列并入安全边际"
```

---

## Task 3: 前端排序/模式/持久化 JS

替换模板内 `<script>` 全块，加入排序（点列头切升降）、分组↔平铺切换、localStorage 持久化，并扩展 `refreshPrices` 同步刷新三列边际。

**Files:**
- Modify: `app/templates/valuations.html:75-145`（`<script>...</script>` 整块）
- Test: `tests/test_valuations.py`

- [ ] **Step 1: Write the failing smoke test**

在 `tests/test_valuations.py` 末尾追加：

```python
def test_index_has_sort_and_mode_js(app_client):
    html = app_client.get('/valuations/').data.decode('utf-8')
    assert 'function sortBy' in html, '缺 sortBy'
    assert 'function applySort' in html, '缺 applySort'
    assert 'function setMode' in html, '缺 setMode'
    assert 'valuationsSortPref' in html, '缺 localStorage 键'
    assert "setMode('flat')" in html, '缺平铺模式按钮绑定'
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_valuations.py::test_index_has_sort_and_mode_js -v`
Expected: FAIL（`function sortBy` 不在 html）

- [ ] **Step 3: 替换整个 `<script>` 块**

把 `app/templates/valuations.html` 的 `<script> ... </script>`（75-145 行）整体替换为：

```html
<script>
function fmtPrice(v) { return v === null || v === undefined ? '—' : v.toFixed(2); }
function fmtMargin(v) { return v === null || v === undefined ? '' : (v >= 0 ? '+' : '') + (v * 100).toFixed(1) + '%'; }

const PREF_KEY = 'valuationsSortPref';
let sortKey = 'base';
let sortDir = 'desc';
let mode = 'grouped';
let currentMarket = 'all';

function loadPref() {
  try {
    const p = JSON.parse(localStorage.getItem(PREF_KEY) || '{}');
    if (['bear', 'base', 'bull'].includes(p.sortKey)) sortKey = p.sortKey;
    if (['asc', 'desc'].includes(p.dir)) sortDir = p.dir;
    if (['grouped', 'flat'].includes(p.mode)) mode = p.mode;
  } catch (e) {}
}
function savePref() {
  localStorage.setItem(PREF_KEY, JSON.stringify({ sortKey, dir: sortDir, mode }));
}

function marginOf(tr, key) {
  const v = tr.dataset['m' + key];
  return (v === '' || v === undefined) ? null : parseFloat(v);
}

function sortRows(rows) {
  const dir = sortDir === 'asc' ? 1 : -1;
  return rows.slice().sort((a, b) => {
    const va = marginOf(a, sortKey), vb = marginOf(b, sortKey);
    if (va === null && vb === null) return 0;
    if (va === null) return 1;   // null 边际恒末位
    if (vb === null) return -1;
    return (va - vb) * dir;
  });
}

function updateArrows() {
  document.querySelectorAll('#val-table th.sortable').forEach(th => {
    const arrow = th.querySelector('.sort-arrow');
    arrow.textContent = (th.dataset.sort === sortKey) ? (sortDir === 'asc' ? '▲' : '▼') : '';
  });
}

function applySort() {
  updateArrows();
  const tbody = document.querySelector('#val-table tbody');
  if (mode === 'flat') {
    sortRows([...tbody.querySelectorAll('tr[data-code]')]).forEach(r => tbody.appendChild(r));
  } else {
    document.querySelectorAll('#val-table .group-header').forEach(header => {
      const sector = header.dataset.sector;
      const rows = sortRows([...tbody.querySelectorAll('tr.grp-' + CSS.escape(sector) + '[data-code]')]);
      let ref = header;
      rows.forEach(r => { ref.after(r); ref = r; });
    });
  }
}

function sortBy(key) {
  if (sortKey === key) {
    sortDir = sortDir === 'asc' ? 'desc' : 'asc';
  } else {
    sortKey = key;
    sortDir = 'desc';
  }
  savePref();
  applySort();
}

function setMode(m) {
  mode = m;
  const table = document.getElementById('val-table');
  table.classList.toggle('mode-grouped', m === 'grouped');
  table.classList.toggle('mode-flat', m === 'flat');
  document.querySelectorAll('#mode-toggle .btn').forEach(b => {
    const on = b.dataset.mode === m;
    b.classList.toggle('btn-primary', on);
    b.classList.toggle('btn-outline-primary', !on);
  });
  if (m === 'flat') {
    document.querySelectorAll('#val-table tr[data-code]').forEach(tr => tr.classList.remove('hidden-by-group'));
    document.querySelectorAll('#val-table .group-header').forEach(h => h.classList.remove('collapsed'));
  }
  savePref();
  applySort();
  applyMarketFilter();
}

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
  document.querySelectorAll('#val-table tr[data-code]').forEach(tr => {
    const mOk = currentMarket === 'all' || tr.dataset.market === currentMarket;
    const collapsed = tr.classList.contains('hidden-by-group');
    tr.style.display = (mOk && !collapsed) ? '' : 'none';
    tr.dataset.marketHidden = mOk ? '' : '1';
  });
  if (mode === 'grouped') {
    document.querySelectorAll('#val-table .group-header').forEach(h => {
      const sector = h.dataset.sector;
      const rows = document.querySelectorAll('#val-table tr.grp-' + CSS.escape(sector) + '[data-code]');
      let visible = 0;
      rows.forEach(r => { if (r.dataset.marketHidden !== '1') visible++; });
      h.style.display = visible > 0 ? '' : 'none';
      const badge = h.querySelector('.group-count');
      if (badge) badge.textContent = visible;
    });
  }
}

function toggleGroup(sector) {
  if (mode !== 'grouped') return;
  const header = document.querySelector('#val-table .group-header[data-sector="' + sector + '"]');
  const collapsed = header.classList.toggle('collapsed');
  document.querySelectorAll('#val-table tr.grp-' + CSS.escape(sector) + '[data-code]').forEach(tr => {
    tr.classList.toggle('hidden-by-group', collapsed);
  });
  applyMarketFilter();
}

async function refreshPrices() {
  const btn = document.getElementById('refresh-btn');
  const status = document.getElementById('refresh-status');
  btn.disabled = true; status.textContent = '刷新中…';
  try {
    const resp = await fetch('/valuations/api/prices?force=1');
    if (!resp.ok) throw new Error('http ' + resp.status);
    const data = await resp.json();
    document.querySelectorAll('#val-table tr[data-code]').forEach(tr => {
      const row = data[tr.dataset.code];
      if (!row) return;
      tr.querySelector('.cell-price').textContent = fmtPrice(row.current_price);
      [['bear', 'margin_bear'], ['base', 'margin_base'], ['bull', 'margin_bull']].forEach(([k, mk]) => {
        const span = tr.querySelector('.cell-m' + k);
        const v = row[mk];
        span.textContent = fmtMargin(v);
        span.classList.remove('margin-pos', 'margin-neg');
        if (v !== null && v !== undefined) span.classList.add(v >= 0 ? 'margin-pos' : 'margin-neg');
        tr.dataset['m' + k] = (v === null || v === undefined) ? '' : v;
      });
    });
    applySort();
    status.textContent = '已更新 ' + new Date().toLocaleTimeString();
  } catch (e) {
    status.textContent = '刷新失败';
  } finally {
    btn.disabled = false;
  }
}

function initValuations() {
  loadPref();
  setMode(mode);  // 应用 table class + 模式按钮态 + applySort + applyMarketFilter
}
document.addEventListener('DOMContentLoaded', initValuations);
</script>
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_valuations.py::test_index_has_sort_and_mode_js -v`
Expected: PASS

- [ ] **Step 5: 全量回归**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_valuations.py -v`
Expected: 全 PASS（含既有 30+ 测试与 3 个新测试，无回归）

- [ ] **Step 6: Commit**

```bash
rtk git add app/templates/valuations.html tests/test_valuations.py && rtk git commit -m "feat(valuations): 列头排序/分组平铺切换/localStorage 持久化 JS"
```

---

## Task 4: 手动验证

服务端单测无法覆盖 DOM 交互，需启动应用人工核对。

**Files:** 无（仅验证）

- [ ] **Step 1: 启动应用**

Run: `python run.py`，浏览器访问 `http://127.0.0.1:5000/valuations/`

- [ ] **Step 2: 逐项核对**

- [ ] Bear/Base/Bull 三列每格显示「绝对值 · 边际%」，边际正绿负红
- [ ] 默认按 Base 降序，箭头 ▼ 只在 Base 列头
- [ ] 点 Bear 列头 → 按 Bear 边际降序、箭头移到 Bear；再点 → 升序、箭头变 ▲
- [ ] 点「▤ 平铺」→ 板块组头消失、「板块」列出现、整表按当前键有序
- [ ] 点「▣ 分组」→ 组头回来、「板块」列隐藏、组内有序且组顺序按数量不变
- [ ] 无估值行（如比亚迪 002594）在两模式、升降下恒在末位
- [ ] 点市场 chip（A股/港股/美股）在两模式下都正确筛选；分组模式空组隐藏、组头计数更新
- [ ] 点「🔄 刷新实时价」→ 当前价与三列边际同步更新、着色正确、刷新后顺序仍按当前排序
- [ ] 调整排序/模式后刷新浏览器（F5）→ 排序列、升降、分组/平铺自动恢复（localStorage）
- [ ] 分组模式点组头可折叠/展开；平铺模式点组头无效（已隐藏）

- [ ] **Step 3:** 全部通过即完成；任一项异常回到对应 Task 修复。

---

## Self-Review（计划作者自检记录）

- **Spec 覆盖**：① 两种模式→Task3 `setMode`；② Bear/Base/Bull 边际排序→Task3 `sortBy/sortRows`；③ 点列头+箭头+三列并入边际→Task2 列头 + Task3 `updateArrows`；④ localStorage→Task3 `loadPref/savePref`；⑤ 平铺独立「板块」列→Task1 `sector_label` + Task2 col-sector；⑥ None 末位→Task3 `sortRows`；⑦ 市场筛选两模式协作→Task3 `applyMarketFilter` 守卫；⑧ 刷新同步三列→Task3 `refreshPrices`。无遗漏。
- **占位符扫描**：无 TBD/TODO，所有代码步含完整代码。
- **命名一致性**：`data-mbear/mbase/mbull` ↔ `dataset['m'+key]`（key∈bear/base/bull）；`.cell-mbear/mbase/mbull` 三处（模板渲染 + refreshPrices querySelector）一致；`sector_label`（Task1 写 / Task2 模板读）一致；`#val-table`/`#mode-toggle`/`PREF_KEY='valuationsSortPref'` 全文一致。
