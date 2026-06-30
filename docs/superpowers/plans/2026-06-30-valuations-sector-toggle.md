# Claude估值页板块显隐 toggle group 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 `/valuations` 估值页加一排板块 chips，多选 toggle 控制每个一级 sector 是否显示，隐藏状态持久化到 localStorage。

**Architecture:** 纯前端单文件改动（`app/templates/valuations.html`）。chips 由服务端已传入模板的 `groups` 渲染，每个 chip 对应一个一级 sector group。前端维护 `hiddenSectors` 集合，复用现有 `recompute()` 的 `filterHidden` 管线把 sector 显隐并入 `fOk` 判断，与市场/主题筛选是 AND 关系。`app/routes/valuations.py` 零改动。

**Tech Stack:** Flask + Jinja2 模板、原生 JS、Bootstrap chips、localStorage；pytest + `app_client` fixture 做 HTML 渲染 smoke 测试。

## Global Constraints

- 响应中文；不写多余注释；不写 backup 文件（git 留痕足够）。
- 所有 git / pytest 命令前加 `rtk`，链式 `&&` 中也要。
- env 赋值必须在 `rtk` 之前：`PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest ...`。
- HTML 渲染测试必须走 `create_app()`（用现有 `app_client` fixture），不能用裸 `Flask()`（base.html 跨 blueprint `url_for` 会 BuildError）。
- pytest 看结果用重定向到文件再读（crawl4ai 进度条走 stdout 会顶掉 `N passed` 摘要）：`pytest ... > out.txt 2>&1; grep -E "passed|failed" out.txt`。
- `git add` 与 `git commit` 放进同一条 Bash 命令链，commit message 中文走 `-m`。
- commit message 末尾加：`Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`。
- 投研/前端写档类改动在 main 分支直接进行（本功能改 `app/` 模板，按 dev-environment 规则属"改 app 代码"，如需隔离可开 worktree；单文件小改可在 main 直接做，提交前 `git show --stat` 自检只含本任务文件）。

参考现有交互（务必先读）：`app/templates/valuations.html` 的 `recompute()`（行 343-385）、`savePref`/`loadPref`（行 158-172）、`initValuations`（行 434-449）、市场 chips 模板（行 47-52）、`group_by_sector` 产出的 `groups` 结构（`g.sector` / `g.label` / `g.count`，见 `app/routes/valuations.py:104-140`）。

---

## File Structure

- `app/templates/valuations.html` — 唯一改动文件。
  - 模板：新增 `#sector-chips` 行（「全部」复位 chip + 每 group 一个 sector chip），插在现有控制行之后、`<div class="table-responsive">` 之前。
  - JS：新增 `hiddenSectors` 状态、`sectorShown()`、`updateSectorChips()`、`toggleSectorVisible()`、`resetSectors()`；改 `recompute()` 的 `fOk`、`repRows`；改 `savePref`/`loadPref`；改 `initValuations`。
- `tests/test_valuations.py` — 新增 2 个渲染 smoke 测试（结构标记 + 持久化代码 wiring）。
- `app/routes/valuations.py` — 无改动。

任务拆分：Task 1 交付「chips 渲染 + 本会话内 toggle 显隐生效（无持久化）」；Task 2 在其上加「持久化（刷新保持）」。两者可独立 review。

---

### Task 1: 板块 chips 渲染 + 会话内显隐 toggle

**Files:**
- Modify: `app/templates/valuations.html`（模板插入 chips 行；JS 加状态/函数/recompute 集成/init）
- Test: `tests/test_valuations.py`（新增 `test_index_renders_sector_chips`）

**Interfaces:**
- Consumes: 模板已有变量 `groups`（list of `{sector, label, count, subgroups}`）；行 `<tr data-code>` 已带 `data-sector` 属性；现有全局 `recompute()`、`initValuations()`、`savePref()`。
- Produces（供 Task 2 依赖）：
  - 全局 `let hiddenSectors = new Set();` — 存被隐藏的 sector key。
  - `function sectorShown(tr)` → `boolean`。
  - `function updateSectorChips()` — 按 `hiddenSectors` 刷新所有 `.chip-sector` 按钮 class。
  - `function toggleSectorVisible(sector)` / `function resetSectors()` — chip 点击入口。
  - DOM：`#sector-chips` 容器，内含 `button.chip-sector[data-sector]`（含 `data-sector="__all__"` 复位 chip）。

- [ ] **Step 1: 写失败的渲染测试**

在 `tests/test_valuations.py` 末尾追加：

```python
def test_index_renders_sector_chips(app_client):
    html = app_client.get('/valuations/').data.decode('utf-8')
    assert 'id="sector-chips"' in html, '缺板块 chips 容器'
    assert 'data-sector="__all__"' in html, '缺全部复位 chip'
    assert 'resetSectors' in html, '缺 resetSectors JS'
    # toggleSectorVisible( 出现在 JS 定义 + 每个 group 的 onclick；非空 yaml → 至少 2 次
    assert html.count('toggleSectorVisible(') >= 2, '板块 chip 未按 groups 渲染'
```

- [ ] **Step 2: 跑测试确认失败**

Run:
```bash
PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_valuations.py::test_index_renders_sector_chips -v > out.txt 2>&1; rtk grep -E "PASSED|FAILED|assert" out.txt
```
Expected: FAILED（`缺板块 chips 容器` —— `#sector-chips` 尚未存在）

- [ ] **Step 3: 模板加 chips 行**

在 `app/templates/valuations.html` 中，定位现有控制行的结束 `</div>`（市场 chips / 主题 / 模式那个 flex 容器，紧接其后是 `<div class="table-responsive">`）。在这两行之间插入：

```html
<div id="sector-chips" class="mb-3 d-flex flex-wrap gap-1 align-items-center">
  <span class="text-muted small me-1">板块</span>
  <button class="btn btn-sm btn-outline-secondary chip-sector" data-sector="__all__"
          onclick="resetSectors()">全部</button>
  {% for g in groups %}
  <button class="btn btn-sm btn-primary chip-sector" data-sector="{{ g.sector }}"
          onclick="toggleSectorVisible('{{ g.sector }}')">{{ g.label }} <span class="badge bg-light text-dark">{{ g.count }}</span></button>
  {% endfor %}
</div>
```

注意：此块必须在 `{% if not groups %}...{% else %} ... {% endif %}` 的 `{% else %}` 分支内（与表格同属有数据分支），groups 为空时不渲染。

- [ ] **Step 4: JS 加状态与函数**

在 `app/templates/valuations.html` 的 `<script>` 内，找到 `let selectedThemes = new Set();`（约行 153），在其后加一行：

```javascript
let hiddenSectors = new Set();
```

在 `themeMatches` 函数定义之后（约行 199 之后）加入三个函数：

```javascript
function sectorShown(tr) {
  return !hiddenSectors.has(tr.dataset.sector);
}

function updateSectorChips() {
  document.querySelectorAll('#sector-chips .chip-sector').forEach(b => {
    const sec = b.dataset.sector;
    if (sec === '__all__') return;
    const shown = !hiddenSectors.has(sec);
    b.classList.toggle('btn-primary', shown);
    b.classList.toggle('btn-outline-secondary', !shown);
  });
}

function toggleSectorVisible(sector) {
  if (hiddenSectors.has(sector)) hiddenSectors.delete(sector);
  else hiddenSectors.add(sector);
  updateSectorChips();
  savePref();
  recompute();
}

function resetSectors() {
  hiddenSectors.clear();
  updateSectorChips();
  savePref();
  recompute();
}
```

- [ ] **Step 5: 把 sector 显隐并入 recompute 与 repRows**

在 `recompute()` 里，把（约行 351）：

```javascript
    const fOk = rowMatchesMarket(tr) && themeMatches(tr);
```

改为：

```javascript
    const fOk = rowMatchesMarket(tr) && themeMatches(tr) && sectorShown(tr);
```

在 `repRows(rows)` 里，把（约行 235）：

```javascript
    if (rowMatchesMarket(tr) && themeMatches(tr)) return marginOf(tr, sortKey);
```

改为：

```javascript
    if (rowMatchesMarket(tr) && themeMatches(tr) && sectorShown(tr)) return marginOf(tr, sortKey);
```

- [ ] **Step 6: init 时刷新 chip 态**

在 `initValuations()` 里找到 `updateThemeButton();`（约行 447），在其后加一行：

```javascript
  updateSectorChips();
```

（此时 `hiddenSectors` 为空集，全部 chip 显示为 `btn-primary`；持久化在 Task 2 接入。）

- [ ] **Step 7: 跑测试确认通过**

Run:
```bash
PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_valuations.py::test_index_renders_sector_chips -v > out.txt 2>&1; rtk grep -E "passed|failed" out.txt
```
Expected: `1 passed`

- [ ] **Step 8: 全量回归（确保未破坏现有估值页测试）**

Run:
```bash
PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_valuations.py -v > out.txt 2>&1; rtk grep -E "passed|failed" out.txt
```
Expected: 全部 passed（含原有 `test_index_route_smoke` / `test_index_has_currency_column_and_data_market` 等）

- [ ] **Step 9: 手工浏览器冒烟（本会话内显隐）**

启动 `python run.py`，打开 http://127.0.0.1:5000/valuations/ ，确认：
1. 控制行下方出现「板块」chips 一排，含「全部」+ 每个板块一个 chip（带数量徽标），默认全亮（`btn-primary`）。
2. 点某板块 chip → 该板块 lvl1/lvl2 表头与所有行消失，chip 变暗（`btn-outline-secondary`）；其它板块不受影响。
3. 平铺模式下点板块 chip 同样隐藏该板块的行。
4. 点「全部」→ 所有板块恢复显示、chips 全亮。
5. 板块隐藏 + 市场筛选 + 主题筛选三者叠加为 AND（被任一过滤即不显示）。
6. （本任务暂不持久化）刷新页面后隐藏状态丢失、全部恢复显示 —— 这是 Task 1 的预期，Task 2 修复。

- [ ] **Step 10: 提交**

```bash
cd /d/Git/stock && rtk git add app/templates/valuations.html tests/test_valuations.py && rtk git commit -m "feat(valuations): 板块 chips 显隐 toggle（会话内生效）

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>" && rtk git show --stat HEAD | head -15
```
Expected: 仅含 `app/templates/valuations.html` 与 `tests/test_valuations.py` 两文件。

---

### Task 2: 隐藏状态持久化到 localStorage

**Files:**
- Modify: `app/templates/valuations.html`（`savePref` / `loadPref` 增 `hiddenSectors` 字段）
- Test: `tests/test_valuations.py`（新增 `test_index_sector_pref_persistence_wired`）

**Interfaces:**
- Consumes: Task 1 产出的 `hiddenSectors`、`updateSectorChips()`、`#sector-chips .chip-sector[data-sector]`；现有 `PREF_KEY = 'valuationsSortPref'`、`loadPref()`、`savePref()`、`initValuations()`。
- Produces: 刷新/重开页面后 `hiddenSectors` 从 `valuationsSortPref.hiddenSectors` 恢复，并经 `updateSectorChips()` + `recompute()` 反映到视图。

- [ ] **Step 1: 写失败的持久化 wiring 测试**

在 `tests/test_valuations.py` 末尾追加（纯前端 localStorage 行为无 JS runtime，改静态校验 wiring 代码存在）：

```python
def test_index_sector_pref_persistence_wired(app_client):
    html = app_client.get('/valuations/').data.decode('utf-8')
    assert 'hiddenSectors: [...hiddenSectors]' in html, 'savePref 未持久化 hiddenSectors'
    assert 'p.hiddenSectors' in html, 'loadPref 未读取 hiddenSectors'
```

- [ ] **Step 2: 跑测试确认失败**

Run:
```bash
PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_valuations.py::test_index_sector_pref_persistence_wired -v > out.txt 2>&1; rtk grep -E "PASSED|FAILED|assert" out.txt
```
Expected: FAILED（`savePref 未持久化 hiddenSectors`）

- [ ] **Step 3: savePref 写入 hiddenSectors**

把 `savePref`（约行 170-172）：

```javascript
function savePref() {
  localStorage.setItem(PREF_KEY, JSON.stringify({ sortKey, dir: sortDir, mode, themes: [...selectedThemes] }));
}
```

改为：

```javascript
function savePref() {
  localStorage.setItem(PREF_KEY, JSON.stringify({ sortKey, dir: sortDir, mode, themes: [...selectedThemes], hiddenSectors: [...hiddenSectors] }));
}
```

- [ ] **Step 4: loadPref 读取并校验 hiddenSectors**

在 `loadPref()` 内，现有 themes 恢复块之后（`if (Array.isArray(p.themes)) { ... }` 闭合 `}` 之后，约行 167）插入：

```javascript
    if (Array.isArray(p.hiddenSectors)) {
      const validSec = new Set(
        [...document.querySelectorAll('#sector-chips .chip-sector')]
          .map(b => b.dataset.sector).filter(s => s !== '__all__')
      );
      p.hiddenSectors.forEach(s => { if (validSec.has(s)) hiddenSectors.add(s); });
    }
```

（按当前实际渲染的 chips 校验、丢弃失效 key；`initValuations` 已在 Task 1 调 `updateSectorChips()`，`setMode(mode)` 链路触发 `recompute()`，首屏即按持久化状态显隐，无需额外改 init。）

- [ ] **Step 5: 跑测试确认通过**

Run:
```bash
PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_valuations.py::test_index_sector_pref_persistence_wired -v > out.txt 2>&1; rtk grep -E "passed|failed" out.txt
```
Expected: `1 passed`

- [ ] **Step 6: 全量回归**

Run:
```bash
PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_valuations.py -v > out.txt 2>&1; rtk grep -E "passed|failed" out.txt
```
Expected: 全部 passed

- [ ] **Step 7: 手工浏览器冒烟（持久化）**

打开 http://127.0.0.1:5000/valuations/ ：
1. 隐藏 2-3 个板块（chip 变暗）。
2. 刷新页面（F5）→ 这些板块仍隐藏、对应 chip 仍为暗态、表格不显示它们。
3. 点「全部」→ 恢复并刷新页面 → 全部仍显示。
4. 「刷新实时价」按钮点击后，隐藏状态不丢（`refreshPrices` 末尾调 `recompute()`）。
5. 打开浏览器 DevTools → Application → localStorage → `valuationsSortPref`，确认 JSON 含 `hiddenSectors` 数组。

- [ ] **Step 8: 提交**

```bash
cd /d/Git/stock && rtk git add app/templates/valuations.html tests/test_valuations.py && rtk git commit -m "feat(valuations): 板块显隐状态持久化到 localStorage

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>" && rtk git show --stat HEAD | head -15
```
Expected: 仅含 `app/templates/valuations.html` 与 `tests/test_valuations.py`。

---

## 自检对照（Self-Review）

- **Spec 覆盖**：
  - 一级 sector 粒度 → Task 1 Step 3 模板 `{% for g in groups %}` 每 group 一 chip ✓
  - 一排 chips 仿市场 → Task 1 Step 3 `#sector-chips` flex 行 ✓
  - 多选 toggle + 默认全显 → Task 1 Step 4 `toggleSectorVisible` + 默认空集 ✓
  - 「全部」复位 chip → Task 1 Step 3 `data-sector="__all__"` + Step 4 `resetSectors` ✓
  - 存「隐藏集合」非「显示集合」→ `hiddenSectors`（Task 1 Step 4）+ loadPref 仅恢复 hidden（Task 2 Step 4）✓
  - 并入现有 PREF 对象不新开 key → Task 2 Step 3/4 改 `valuationsSortPref` ✓
  - load 校验丢弃失效 key → Task 2 Step 4 `validSec` ✓
  - 与市场/主题 AND、复用 recompute filterHidden → Task 1 Step 5 `fOk` 并入 `sectorShown` ✓
  - 分组/平铺/排序/刷新协同 → Task 1 Step 9 + Task 2 Step 7 冒烟点覆盖 ✓
  - `valuations.py` 零改动 → 计划无 route 改动 ✓
- **占位符扫描**：无 TBD/TODO；每个改码步骤均给完整代码块 ✓
- **类型/命名一致**：`hiddenSectors` / `sectorShown` / `updateSectorChips` / `toggleSectorVisible` / `resetSectors` / `chip-sector` / `data-sector="__all__"` 全计划统一 ✓
