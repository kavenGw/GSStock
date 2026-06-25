# 估值页 theme 筛选 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 `/valuations` 页增加按主题（theme）筛选标的的多选下拉，并为每行展示该股的 theme 标签。

**Architecture:** 主题数据源是个股 buffett 档 frontmatter 的 `themes:` 字段，经现有生成器 `scripts/sync_valuations.py` 回填进 `valuations.yaml`（渲染期零额外 I/O）。路由聚合出现 ≥2 次的主题供下拉，模板用手写 Bootstrap 多选下拉（无新依赖）做 OR 筛选，与现有市场筛选 AND 叠加。

**Tech Stack:** Python / Flask / Jinja2 / PyYAML / Bootstrap 5 bundle（已本地 vendored，含 dropdown）/ 原生 JS / pytest

## Global Constraints

- 响应中文；不写多余注释；不写 backup 文件。
- 所有 git/pytest 命令前加 `rtk`，链式 `&&` 中也要；env 赋值（`PYTHONIOENCODING`/`SCHEDULER_ENABLED`）必须在 `rtk` 之前。
- 测试命令固定：`PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest <path> -v`
- 单测平铺在 `tests/test_*.py`，不建子目录。
- 筛选器只暴露出现 ≥2 次的主题；行内 badge 展示该股全部主题（含单例）。
- 多选主题间 OR；与市场筛选 AND；选中态持久化进现有 `PREF_KEY`（`valuationsSortPref`）。
- `git add` 与 `git commit` 放进同一条 Bash 命令链，精确路径，勿 `git add -A`。

---

### Task 1: 生成器回填 themes（`scripts/sync_valuations.py`）

**Files:**
- Modify: `scripts/sync_valuations.py`（新增 `_clean_themes`；`build_entry` 末尾写入 `themes`）
- Test: `tests/test_sync_valuations.py`

**Interfaces:**
- Produces: `_clean_themes(raw) -> list[str]`（丢弃非 list/空值/`_` 前缀哨兵，去重保序）；`build_entry(fm, source_doc) -> dict` 在 `fm['themes']` 清洗后非空时增加 `entry['themes']: list[str]` 键。

- [ ] **Step 1: 写失败测试**

在 `tests/test_sync_valuations.py` 末尾追加：

```python
def test_clean_themes_drops_empty_sentinel_and_dedups():
    from scripts.sync_valuations import _clean_themes
    assert _clean_themes(['memory', '_excluded', '', 'memory', ' 国产替代 ']) == ['memory', '国产替代']


def test_clean_themes_non_list_returns_empty():
    from scripts.sync_valuations import _clean_themes
    assert _clean_themes(None) == []
    assert _clean_themes('memory') == []


def test_build_entry_includes_cleaned_themes():
    from scripts.sync_valuations import build_entry
    fm = {
        'stock_code': '603986', 'stock_name': 'X', 'sector': 'semiconductor',
        'rating': 'core', 'conviction_date': '2026-05-31',
        'themes': ['memory', '_excluded', 'memory', 'cpu_pcb'],
        'valuation': {'bear': 1.0, 'base': 2.0, 'bull': 3.0, 'currency': 'CNY'},
    }
    e = build_entry(fm, 'foo.md')
    assert e['themes'] == ['memory', 'cpu_pcb']


def test_build_entry_omits_themes_when_empty():
    from scripts.sync_valuations import build_entry
    fm = {
        'stock_code': '603986', 'stock_name': 'X', 'sector': 'semiconductor',
        'rating': 'core', 'conviction_date': '2026-05-31', 'themes': ['_excluded'],
        'valuation': {'bear': 1.0, 'base': 2.0, 'bull': 3.0, 'currency': 'CNY'},
    }
    assert 'themes' not in build_entry(fm, 'foo.md')
```

- [ ] **Step 2: 运行测试确认失败**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_sync_valuations.py -v -k "themes"`
Expected: FAIL，`ImportError: cannot import name '_clean_themes'` 或 `KeyError: 'themes'`

- [ ] **Step 3: 实现**

在 `scripts/sync_valuations.py` 的 `build_entry` 定义之前插入 `_clean_themes`：

```python
def _clean_themes(raw) -> list[str]:
    """frontmatter themes 清洗：丢弃非 list / 空值 / `_` 前缀哨兵（如 _excluded），去重保序。"""
    if not isinstance(raw, list):
        return []
    out, seen = [], set()
    for t in raw:
        s = str(t).strip()
        if not s or s.startswith('_') or s in seen:
            continue
        seen.add(s)
        out.append(s)
    return out
```

在 `build_entry` 内 `entry['source_doc'] = source_doc` 之后、`return entry` 之前插入：

```python
    themes = _clean_themes(fm.get('themes'))
    if themes:
        entry['themes'] = themes
```

- [ ] **Step 4: 运行测试确认通过**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_sync_valuations.py -v`
Expected: PASS（含既有用例，全绿）

- [ ] **Step 5: 提交**

```bash
rtk git add scripts/sync_valuations.py tests/test_sync_valuations.py && rtk git commit -m "feat(valuations): sync_valuations 回填个股 themes 到 yaml"
```

---

### Task 2: 重生成 valuations.yaml（数据产物）

**Files:**
- Modify: `docs/stock-analytics/valuations.yaml`（脚本生成，非手编）

**Interfaces:**
- Consumes: Task 1 的 `build_entry` themes 写入。
- Produces: valuations.yaml 各条目带 `themes:` 列表（除 source 档代码与 yaml code 不一致的 A+H 切口径条目）。

- [ ] **Step 1: 全量重跑生成器**

Run: `PYTHONIOENCODING=utf-8 rtk python scripts/sync_valuations.py`
Expected: 打印 `synced 16x entries into ...valuations.yaml`

- [ ] **Step 2: 校验回填结果**

Run: `PYTHONIOENCODING=utf-8 rtk python -c "import yaml; d=yaml.safe_load(open('docs/stock-analytics/valuations.yaml',encoding='utf-8')); n=sum(1 for r in d if r.get('themes')); print('total',len(d),'with themes',n)"`
Expected: `with themes` 接近 total（约 150+/162；缺失的是 A+H 切 H 口径条目，可接受）

- [ ] **Step 3: 确认无连带脏改**

Run: `rtk git status --short docs/stock-analytics/valuations.yaml`
Expected: 仅该文件 `M`，无其它档被改

- [ ] **Step 4: 提交**

```bash
rtk git add docs/stock-analytics/valuations.yaml && rtk git commit -m "data(valuations): 回填 themes 字段（sync 重生成）"
```

---

### Task 3: 路由聚合主题选项（`app/routes/valuations.py`）

**Files:**
- Modify: `app/routes/valuations.py`（`_enrich` 带 themes；新增 `build_theme_options`；`index()` 传参）
- Test: `tests/test_valuations.py`

**Interfaces:**
- Consumes: 行 dict 的 `themes` 键（Task 2 写入）。
- Produces: `build_theme_options(rows: list[dict]) -> list[dict]`，返回 `[{'name': str, 'count': int}, ...]`，只含出现 ≥2 次的主题，按 `(count desc, name asc)` 排序；`_enrich` 输出行含 `'themes': list`；`index()` 向模板传 `theme_options`。

- [ ] **Step 1: 写失败测试**

在 `tests/test_valuations.py` 末尾追加：

```python
def test_enrich_carries_themes():
    from app.routes.valuations import _enrich
    out = _enrich([{'stock_code': 'x', 'base': 1.0, 'themes': ['memory', 'cpu_pcb']}], {})
    assert out[0]['themes'] == ['memory', 'cpu_pcb']


def test_enrich_themes_default_empty():
    from app.routes.valuations import _enrich
    out = _enrich([{'stock_code': 'x', 'base': 1.0}], {})
    assert out[0]['themes'] == []


def test_build_theme_options_keeps_only_multi_stock_sorted():
    from app.routes.valuations import build_theme_options
    rows = [
        {'themes': ['memory', 'solo']},
        {'themes': ['memory', 'cpu_pcb']},
        {'themes': ['memory', 'cpu_pcb']},
        {'themes': []},
        {'stock_code': 'nokey'},
    ]
    opts = build_theme_options(rows)
    assert opts == [{'name': 'memory', 'count': 3}, {'name': 'cpu_pcb', 'count': 2}]
    assert all(o['count'] >= 2 for o in opts)


def test_index_passes_theme_options(app_client):
    html = app_client.get('/valuations/').data.decode('utf-8')
    assert 'theme-filter' in html, '缺主题筛选下拉容器'
    assert 'data-themes=' in html, '缺行 data-themes 属性'
```

- [ ] **Step 2: 运行测试确认失败**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_valuations.py -v -k "themes or theme_options"`
Expected: FAIL（`build_theme_options` 未定义 / `_enrich` 无 themes / HTML 无 `theme-filter`）

- [ ] **Step 3: 实现路由**

在 `app/routes/valuations.py` 的 `_enrich` 内，append 的 dict 中加入 `themes` 键。把现有：

```python
        out.append({
            **r,
            'category': cat_map.get(r['stock_code']),
```

改为：

```python
        out.append({
            **r,
            'category': cat_map.get(r['stock_code']),
            'themes': r.get('themes') or [],
```

在 `group_by_sector` 之后、`index()` 之前新增：

```python
def build_theme_options(rows: list[dict]) -> list[dict]:
    """聚合出现 ≥2 次的主题，按 (出现次数 desc, 名称 asc) 排序，供筛选下拉渲染。"""
    c = Counter()
    for r in rows:
        for t in (r.get('themes') or []):
            c[t] += 1
    opts = [{'name': name, 'count': n} for name, n in c.items() if n >= 2]
    opts.sort(key=lambda o: (-o['count'], o['name']))
    return opts
```

在 `index()` 内 `groups = group_by_sector(enriched)` 之后加：

```python
    theme_options = build_theme_options(enriched)
```

并在 `render_template(...)` 调用里加入 `theme_options=theme_options,`（与 `groups=groups,` 同级）。

（`Counter` 已在文件顶部 `from collections import Counter` 导入，无需新增。）

- [ ] **Step 4: 运行测试确认通过**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_valuations.py -v`
Expected: PASS（含既有用例全绿；注意 `test_index_passes_theme_options` 需要 Task 4 的模板改动才会过——见下方说明）

> **执行顺序提示**：`test_index_passes_theme_options` 断言 HTML 含 `theme-filter` / `data-themes`，依赖 Task 4 模板。若按 TDD 严格分任务，可先让该用例在 Task 3 标记预期失败，Task 4 完成后转绿；或把该用例移到 Task 4 一并提交。推荐后者：本 Step 4 先只跑 `-k "themes and not index"` 确认路由层逻辑，HTML 断言留 Task 4。

Run（路由层）: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_valuations.py -v -k "(themes or theme_options) and not index"`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
rtk git add app/routes/valuations.py tests/test_valuations.py && rtk git commit -m "feat(valuations): _enrich 带 themes + build_theme_options 聚合多股主题"
```

---

### Task 4: 模板主题列 + 多选下拉 + 双条件筛选（`app/templates/valuations.html`）

**Files:**
- Modify: `app/templates/valuations.html`（表头 + 主题列 + 下拉控件 + JS）
- Test: `tests/test_valuations.py`（HTML 断言）

**Interfaces:**
- Consumes: 模板上下文 `theme_options`（Task 3）、行 `r.themes`（Task 2/3）。
- Produces: 行 `data-themes`（JSON 数组）；下拉容器 `#theme-filter`；JS `themeMatches()` / `onThemeToggle()` / `clearThemes()` / `filterThemeSearch()`；主题筛选并入既有 `recompute()` 与 `repRows()`（本页过滤核心函数是 `recompute`，**不是** applyFilters）。

> **本任务针对当前嵌套两级分组模板**（sector→subsector）：有 **两条** group-header（lvl1/lvl2，各 `colspan="11"`），过滤/计数函数是 `recompute()`，分组排序代表值函数是 `repRows()`。下方编辑均按此结构给出。

- [ ] **Step 1: 写失败测试**

在 `tests/test_valuations.py` 末尾追加（`test_index_passes_theme_options` 已在 Task 3 写好，这里补 JS/列断言）：

```python
def test_index_has_theme_dropdown_and_column(app_client):
    html = app_client.get('/valuations/').data.decode('utf-8')
    assert 'id="theme-filter"' in html, '缺主题下拉'
    assert 'id="theme-search"' in html, '缺主题搜索框'
    assert 'col-theme' in html, '缺主题列'
    assert 'function themeMatches' in html, '缺 themeMatches'
    assert 'onThemeToggle' in html, '缺主题勾选回调'


def test_index_group_headers_colspan_updated(app_client):
    html = app_client.get('/valuations/').data.decode('utf-8')
    # 两级组头（lvl1 sector + lvl2 subgroup）都要随主题列扩到 12
    assert html.count('colspan="12"') >= 2, '两级组头 colspan 未都改为 12'
    assert 'colspan="11"' not in html, '仍有未更新的 colspan=11'


def test_recompute_integrates_theme_filter(app_client):
    html = app_client.get('/valuations/').data.decode('utf-8')
    assert 'themeMatches(tr)' in html, 'recompute/repRows 未并入主题筛选'
    assert 'filterHidden' in html, '未改用合并筛选标记 filterHidden'
```

- [ ] **Step 2: 运行测试确认失败**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_valuations.py -v -k "theme_dropdown or colspan or recompute_integrates"`
Expected: FAIL（HTML 无下拉 / 无 themeMatches / colspan 仍 11）

- [ ] **Step 3a: 加主题筛选下拉控件**

在 `app/templates/valuations.html` 的 `#mode-toggle` 那个 `<div class="btn-group ...">` **之前**（同一 flex 行内），插入：

```html
  <div class="dropdown" id="theme-filter">
    <button class="btn btn-sm btn-outline-secondary dropdown-toggle" type="button"
            id="theme-filter-btn" data-bs-toggle="dropdown" data-bs-auto-close="outside" aria-expanded="false">主题</button>
    <div class="dropdown-menu p-2" style="max-height:340px;overflow-y:auto;min-width:260px">
      <input type="text" class="form-control form-control-sm mb-2" id="theme-search"
             placeholder="搜索主题…" oninput="filterThemeSearch(this.value)">
      <div id="theme-options">
        {% for t in theme_options %}
        <div class="form-check theme-option" data-theme="{{ t.name }}">
          <input class="form-check-input" type="checkbox" value="{{ t.name }}"
                 id="th-{{ loop.index }}" onchange="onThemeToggle()">
          <label class="form-check-label" for="th-{{ loop.index }}">{{ t.name }} <span class="text-muted">({{ t.count }})</span></label>
        </div>
        {% endfor %}
      </div>
      <div class="border-top mt-2 pt-1">
        <button type="button" class="btn btn-sm btn-link px-0 text-decoration-none" onclick="clearThemes()">清除</button>
      </div>
    </div>
  </div>
```

- [ ] **Step 3b: 加主题列（表头 + 单元格 + 行 data 属性 + 组头 colspan）**

表头行：在 `<th>币种</th>` 之后插入 `<th class="col-theme">主题</th>`：

```html
      <th>代码</th><th>名称</th><th class="col-sector">板块</th><th>币种</th><th class="col-theme">主题</th>
```

组头 `colspan`：**两条** group-header 的 `<th colspan="11">` 都改为 `<th colspan="12">`——lvl1（sector，`{{ g.label }}`）与 lvl2（subgroup，`{{ sg.label }}`）各一处：

```html
      <th colspan="12"><span class="caret">▼</span> {{ g.label }} <span class="badge bg-secondary group-count">{{ g.count }}</span></th>
```
```html
      <th colspan="12"><span class="caret">▼</span> {{ sg.label }} <span class="badge bg-light text-secondary subgroup-count">{{ sg.count }}</span></th>
```

数据行 `<tr ...>` 上加 `data-themes` 属性（在 `data-subgroup="{{ sg.subgroup_id }}"` 之后）：

```html
        data-themes='{{ r.themes | tojson }}'
```

在 `<td class="col-sector">…</td>` 与 `<td>{{ r.currency or '—' }}</td>` 之间——即币种单元格之后——插入主题单元格：

```html
      <td class="col-theme">
        {% for t in r.themes %}<span class="badge bg-light text-secondary me-1" style="font-weight:400">{{ t }}</span>{% endfor %}
      </td>
```

> 顺序须与表头一致：代码/名称/板块/币种/**主题**/评级/Bear/Bull…。币种单元格 `<td>{{ r.currency or '—' }}</td>` 保持原位，主题列紧随其后。

- [ ] **Step 3c: JS——筛选态 + 主题过滤并入 recompute/repRows + 搜索 + 持久化**

> 本页过滤/计数核心函数是 **`recompute()`**，分组排序代表值函数是 **`repRows()`**（无 applyFilters / 无 grp- 扁平类）。主题筛选并入这两个函数，与现有市场筛选 AND。

在 `<script>` 内 `let currentMarket = 'all';` 之后加：

```javascript
let selectedThemes = new Set();
```

将 `savePref` 改为带 themes：

```javascript
function savePref() {
  localStorage.setItem(PREF_KEY, JSON.stringify({ sortKey, dir: sortDir, mode, themes: [...selectedThemes] }));
}
```

在 `loadPref` 内 `if (['grouped', 'flat'].includes(p.mode)) mode = p.mode;` 之后补恢复 themes：

```javascript
    if (Array.isArray(p.themes)) p.themes.forEach(t => selectedThemes.add(t));
```

新增主题相关函数（放在 `recompute` 函数定义之前）。注意 `onThemeToggle`/`clearThemes` 调 `applySort(); recompute();`（与 `switchMarket` 同款，先重排分组再重算可见/计数）：

```javascript
function themeMatches(tr) {
  if (selectedThemes.size === 0) return true;
  let arr = [];
  try { arr = JSON.parse(tr.dataset.themes || '[]'); } catch (e) {}
  return arr.some(t => selectedThemes.has(t));
}

function updateThemeButton() {
  const btn = document.getElementById('theme-filter-btn');
  if (btn) btn.textContent = selectedThemes.size ? '主题 (' + selectedThemes.size + ')' : '主题';
}

function onThemeToggle() {
  selectedThemes = new Set(
    [...document.querySelectorAll('#theme-options input:checked')].map(c => c.value)
  );
  updateThemeButton();
  savePref();
  applySort();
  recompute();
}

function clearThemes() {
  document.querySelectorAll('#theme-options input:checked').forEach(c => { c.checked = false; });
  selectedThemes.clear();
  updateThemeButton();
  savePref();
  applySort();
  recompute();
}

function filterThemeSearch(q) {
  const kw = (q || '').trim().toLowerCase();
  document.querySelectorAll('#theme-options .theme-option').forEach(el => {
    const name = (el.dataset.theme || '').toLowerCase();
    el.style.display = (!kw || name.includes(kw)) ? '' : 'none';
  });
}
```

让分组排序代表值函数 `repRows` 也尊重主题筛选。把：

```javascript
function repRows(rows) {
  for (const tr of rows) {
    if (rowMatchesMarket(tr)) return marginOf(tr, sortKey);
  }
  return null;
}
```

改为：

```javascript
function repRows(rows) {
  for (const tr of rows) {
    if (rowMatchesMarket(tr) && themeMatches(tr)) return marginOf(tr, sortKey);
  }
  return null;
}
```

把 `recompute()` 内市场单条件改为市场 AND 主题，并把标记 `marketHidden` 统一改名 `filterHidden`。两处精确替换：

**（1）行可见性主循环**——把：

```javascript
    const mOk = rowMatchesMarket(tr);
    tr.dataset.marketHidden = mOk ? '' : '1';
    let show;
    if (mode === 'flat') {
      show = mOk;
    } else {
      show = mOk && !collapsedSec.has(tr.dataset.sector) && !collapsedSub.has(tr.dataset.subgroup);
    }
```

改为：

```javascript
    const fOk = rowMatchesMarket(tr) && themeMatches(tr);
    tr.dataset.filterHidden = fOk ? '' : '1';
    let show;
    if (mode === 'flat') {
      show = fOk;
    } else {
      show = fOk && !collapsedSec.has(tr.dataset.sector) && !collapsedSub.has(tr.dataset.subgroup);
    }
```

**（2）可见计数循环**——把 `if (tr.dataset.marketHidden === '1') return;` 改为 `if (tr.dataset.filterHidden === '1') return;`

（改完后 `recompute` 内不应再出现 `marketHidden` 或 `mOk`。）

在 `initValuations()` 内 `setMode(mode);` **之前**补：恢复勾选态 + 按钮文案：

```javascript
  selectedThemes.forEach(t => {
    const cb = document.querySelector('#theme-options input[value="' + CSS.escape(t) + '"]');
    if (cb) cb.checked = true;
  });
  updateThemeButton();
```

> `setMode` 末尾已调用 `applySort()` + `recompute()`，故 init 里无需再单独调。

- [ ] **Step 3d: 加列显隐 CSS（与现有 col-sector 一致，平铺模式可见、不被模式切换隐藏）**

在 `{% block extra_css %}` 的 `<style>` 内补一行（主题列始终显示，无需随分组/平铺切换隐藏，故不必加 mode 规则；仅确保 badge 不挤压换行时可读）：

```css
.col-theme { max-width: 320px; white-space: normal; }
```

> 注：`.val-table th, .val-table td { white-space: nowrap; }` 会让主题 badge 不换行，长主题列会很宽；用 `.col-theme { white-space: normal; }` 覆盖允许换行。

- [ ] **Step 4: 运行测试确认通过**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_valuations.py -v`
Expected: PASS（全绿，含 Task 3 的 `test_index_passes_theme_options` 与本任务新增 HTML 断言）

- [ ] **Step 5: 全量回归 + 手验**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_valuations.py tests/test_sync_valuations.py -v`
Expected: PASS

手验（可选，需起服务）：`rtk python run.py` → 访问 `http://127.0.0.1:5000/valuations` → 下拉列出 ≥2 主题（带股数）；勾选多个主题行数收敛、与市场 chips AND 正确；行内 badge 显示；分组头股数随筛选更新；刷新实时价不破坏筛选态；reload 后勾选态恢复。

- [ ] **Step 6: 提交**

```bash
rtk git add app/templates/valuations.html tests/test_valuations.py && rtk git commit -m "feat(valuations): 主题多选下拉 + 行内 theme 列 + 双条件筛选"
```

---

## 自检（Self-Review）记录

- **结构对齐（关键修订）**：本计划最初按估值页**扁平单层**分组编写；执行前发现当前 main 已合入**嵌套两级分组**（sector→subsector，过滤核心函数 `recompute()`、排序代表值 `repRows()`、两条 `colspan="11"` 组头）。Task 4 已整体改写为针对嵌套结构：主题筛选并入 `recompute()`/`repRows()`（非 applyFilters），两条组头 colspan 同改 12，`marketHidden`→`filterHidden`。Task 1–3（后端）与结构无关，不受影响。
- **Spec 覆盖**：数据源回填（Task 1/2）✓；≥2 主题聚合（Task 3 `build_theme_options`）✓；可搜索多选下拉（Task 4 Step 3a/3c）✓；OR + 市场 AND（`recompute`/`themeMatches`）✓；行内全部主题 badge（Task 4 Step 3b）✓；持久化（`savePref`/`loadPref`/init 恢复）✓；A+H 切口径边界（Task 2 Step 2 校验说明）✓。
- **占位符**：无 TBD/TODO；每个改码步骤均给完整代码。
- **类型一致**：`build_theme_options` 返回 `[{'name','count'}]` 与模板 `t.name`/`t.count` 一致；`themeMatches`/`onThemeToggle`/`clearThemes`/`filterThemeSearch`/`updateThemeButton` 命名前后一致；dataset `filterHidden` 统一替换 `recompute` 内旧 `marketHidden`（赋值 + 计数循环 2 处）；`repRows` 同步并入主题条件。
- **执行顺序注意**：`test_index_passes_theme_options`（Task 3 写）的 HTML 断言依赖 Task 4 模板，Task 3 Step 4 只跑路由层子集，完整 HTML 断言在 Task 4 Step 4 转绿。
