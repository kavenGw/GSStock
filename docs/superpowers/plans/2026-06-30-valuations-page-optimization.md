# 估值页优化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把估值页半导体大板块(74)按子类拆为多个顶级板块，并让实时价首屏秒开后自动补取冷缓存的 HK/US 价格。

**Architecture:** 改动二处，互不依赖。① `app/routes/valuations.py` 新增 `PROMOTE_SEMI_SUBSECTORS`，照搬现有 `PROMOTE_MATERIALS_SUBSECTORS` 机制，把 semiconductor 的 storage/materials/power/equipment 升为扁平顶级板块、其余归「其余半导体」桶（模板零改动，flat 渲染由 `g.flat` 驱动）。② `app/templates/valuations.html` 前端把 `refreshPrices()` 参数化，首屏渲染后自动发一次 `force=0`（按 TTL）后台补取，手动按钮保留 `force=1` 硬刷（后端 `/api/prices` 已支持 force 参数，零改动）。

**Tech Stack:** Flask 路由 + Jinja2 模板 + 原生 JS；pytest 单测；运行约定见 CLAUDE.md（命令前缀 `rtk`，单测 `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest`）。

## Global Constraints

- 响应中文；不写多余注释；不写 backup 文件。
- 所有 git/pytest 命令前加 `rtk`；env 赋值必须在 `rtk` 之前。
- 单测放 `tests/test_*.py` 平铺。
- `group_by_sector` 现有 flat 机制：`flat=True` 的组在模板里被加 `subgroup-flat` 类隐藏 lvl2 表头；本次半导体升顶级复用同一机制，**模板不改**。
- 半导体升顶级子类（决策已定）：`storage`→存储、`materials`→半导体材料、`power`→功率、`equipment`→设备；`design` **不升**，留「其余半导体」桶。
- 后端 `/valuations/api/prices` 已支持 `?force=1`（硬刷）/ 默认 `force=0`（按 TTL）；本次**不改后端路由**。

---

### Task 1: 半导体子类升顶级板块（valuations.py）

**Files:**
- Modify: `app/routes/valuations.py:79-82`（新增配置）、`:108-117`（`_top_key`）、`:120-129`（`_top_label`）、`:159-165`（`group_by_sector` 的 `flat` 判定）
- Test: `tests/test_valuations_grouping.py`（新增半导体用例 + 更新一处已失效用例）

**Interfaces:**
- Consumes: 现有 `group_by_sector(rows: list[dict]) -> list[dict]`、`_top_key(r)`、`_top_label(key)`，行 dict 含 `sector` / `subsector` / `category` / `margin_base`。
- Produces: `group_by_sector` 对 `sector=='semiconductor'` 行，把 `subsector ∈ {storage,materials,power,equipment}` 升为顶级组 `sector='semi:<sub>'`、`flat=True`、label∈{存储,半导体材料,功率,设备}；其余 semiconductor 行归 `sector='semi-other'`、`label='其余半导体'`、`flat=False`、保留 subgroups。

- [ ] **Step 1: 新增/更新失败测试**

在 `tests/test_valuations_grouping.py` 末尾追加（沿用文件顶部已有的 `_row` helper）：

```python
def test_semi_storage_promoted_to_flat_toplevel():
    rows = [_row('603986', 'semiconductor', 'storage'),
            _row('688008', 'semiconductor', 'storage')]
    groups = group_by_sector(rows)
    g = next(x for x in groups if x['label'] == '存储')
    assert g['sector'] == 'semi:storage'
    assert g['flat'] is True
    assert g['count'] == 2


def test_semi_materials_promoted_with_distinct_label():
    rows = [_row('300666', 'semiconductor', 'materials')]
    groups = group_by_sector(rows)
    g = next(x for x in groups if x['sector'] == 'semi:materials')
    assert g['label'] == '半导体材料'
    assert g['flat'] is True


def test_semi_power_and_equipment_promoted():
    rows = [_row('600460', 'semiconductor', 'power'),
            _row('688037', 'semiconductor', 'equipment')]
    groups = group_by_sector(rows)
    labels = {x['sector']: x for x in groups}
    assert labels['semi:power']['label'] == '功率'
    assert labels['semi:power']['flat'] is True
    assert labels['semi:equipment']['label'] == '设备'
    assert labels['semi:equipment']['flat'] is True


def test_semi_design_not_promoted_goes_to_semi_other():
    rows = [_row('300782', 'semiconductor', 'design'),
            _row('688521', 'semiconductor', 'optical')]
    groups = group_by_sector(rows)
    g = next(x for x in groups if x['sector'] == 'semi-other')
    assert g['label'] == '其余半导体'
    assert g['flat'] is False
    assert {sg['label'] for sg in g['subgroups']} == {'设计', '光学'}


def test_semi_no_subsector_falls_to_semi_other_unclassified():
    rows = [_row('688981', 'semiconductor', None)]
    groups = group_by_sector(rows)
    g = next(x for x in groups if x['sector'] == 'semi-other')
    assert g['subgroups'][0]['label'] == '未分类'
```

同文件内**更新**已失效用例 `test_materials_subsector_under_other_sector_stays_put`（line 60-67）—— 旧行为是 semiconductor 的 materials 子类留在「半导体」组；新行为是升为 `semi:materials`。整体替换为：

```python
def test_semiconductor_no_longer_single_bucket():
    rows = [_row('300666', 'semiconductor', 'materials'),
            _row('603986', 'semiconductor', 'storage'),
            _row('300782', 'semiconductor', 'design')]
    groups = group_by_sector(rows)
    # 不再有单一「半导体」顶级组
    assert all(x['sector'] != 'semiconductor' for x in groups)
    sectors = {x['sector'] for x in groups}
    assert {'semi:materials', 'semi:storage', 'semi-other'} <= sectors
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_valuations_grouping.py -v`
Expected: 新增 5 个用例 FAIL（`semi:*`/`semi-other` 尚未产生，命中 `StopIteration` 或断言失败）；`test_semiconductor_no_longer_single_bucket` FAIL。

- [ ] **Step 3: 新增配置常量**

在 `app/routes/valuations.py` 的 `PROMOTE_MATERIALS_SUBSECTORS` / `MATERIALS_OTHER_*` 块后（line 80-82 之后）追加：

```python
PROMOTE_SEMI_SUBSECTORS = {'storage': '存储', 'materials': '半导体材料',
                           'power': '功率', 'equipment': '设备'}
SEMI_OTHER_KEY = 'semi-other'
SEMI_OTHER_LABEL = '其余半导体'
```

- [ ] **Step 4: 扩展 `_top_key`**

把 `app/routes/valuations.py:108-117` 的 `_top_key` 改为（在 materials 分支后加对称 semiconductor 分支）：

```python
def _top_key(r: dict) -> str:
    cat = r.get('category')
    if cat in CARVE_OUT_CATEGORIES:
        return cat
    if r.get('sector') == 'materials':
        sub = r.get('subsector')
        if sub in PROMOTE_MATERIALS_SUBSECTORS:
            return f'mat:{sub}'
        return MATERIALS_OTHER_KEY
    if r.get('sector') == 'semiconductor':
        sub = r.get('subsector')
        if sub in PROMOTE_SEMI_SUBSECTORS:
            return f'semi:{sub}'
        return SEMI_OTHER_KEY
    return r.get('sector') or '__none__'
```

- [ ] **Step 5: 扩展 `_top_label`**

把 `app/routes/valuations.py:120-129` 的 `_top_label` 改为：

```python
def _top_label(key: str) -> str:
    if key in CARVE_OUT_CATEGORIES:
        return key
    if key.startswith('mat:'):
        return PROMOTE_MATERIALS_SUBSECTORS[key[4:]]
    if key == MATERIALS_OTHER_KEY:
        return MATERIALS_OTHER_LABEL
    if key.startswith('semi:'):
        return PROMOTE_SEMI_SUBSECTORS[key[5:]]
    if key == SEMI_OTHER_KEY:
        return SEMI_OTHER_LABEL
    if key == '__none__':
        return '未分类'
    return SECTOR_LABELS.get(key, key)
```

- [ ] **Step 6: 扩展 `group_by_sector` 的 flat 判定**

把 `app/routes/valuations.py` 中 `groups.append({...})` 内的（约 line 163）：

```python
            'flat': key.startswith('mat:'),
```

改为：

```python
            'flat': key.startswith(('mat:', 'semi:')),
```

- [ ] **Step 7: 运行测试，确认通过**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_valuations_grouping.py -v`
Expected: 全部 PASS（含原 materials 用例 + 新增半导体用例 + 改写后的 `test_semiconductor_no_longer_single_bucket`）。

- [ ] **Step 8: 跑全量 valuations 测试防回归**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_valuations.py tests/test_valuations_grouping.py tests/test_sync_valuations.py -v`
Expected: 全部 PASS。

- [ ] **Step 9: Commit**

```bash
rtk git add app/routes/valuations.py tests/test_valuations_grouping.py && rtk git commit -m "feat(valuations): 半导体子类升顶级板块（存储/半导体材料/功率/设备）

照搬 PROMOTE_MATERIALS_SUBSECTORS 机制新增 PROMOTE_SEMI_SUBSECTORS，
semiconductor(74) 拆为 4 扁平顶级 + 其余半导体桶（保留 lvl2）。

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: 实时价首屏秒开 + 自动补取冷缓存（valuations.html 前端）

**Files:**
- Modify: `app/templates/valuations.html:41`（按钮 onclick）、`:451-456`（`refreshPrices` 签名 + fetch URL）、`:474`（状态文案）、`:497`（init 末尾自动补取）

**Interfaces:**
- Consumes: 后端 `GET /valuations/api/prices`（默认 `force=0` 按 TTL；`?force=1` 硬刷），返回 `{code: {current_price, margin_bear, margin_base, margin_bull}}`。
- Produces: `refreshPrices(force: boolean)`；按钮调 `refreshPrices(true)`；`initValuations()` 首屏后调 `refreshPrices(false)`。

> 纯前端 JS 行为，无单测；以手动验证为准（Step 4）。

- [ ] **Step 1: 参数化 `refreshPrices` 并区分状态文案**

把 `app/templates/valuations.html:451` 的函数签名 `async function refreshPrices() {` 改为 `async function refreshPrices(force) {`。

把 `:456` 的：

```javascript
    const resp = await fetch('/valuations/api/prices?force=1');
```

改为：

```javascript
    const resp = await fetch('/valuations/api/prices' + (force ? '?force=1' : ''));
```

把 `:454` 的初始状态文案 `status.textContent = '刷新中…';` 改为：

```javascript
    btn.disabled = true; status.textContent = force ? '刷新中…' : '更新中…';
```

把 `:474` 的成功文案：

```javascript
    status.textContent = '已更新 ' + new Date().toLocaleTimeString();
```

改为：

```javascript
    status.textContent = (force ? '已更新 ' : '自动更新 ') + new Date().toLocaleTimeString();
```

- [ ] **Step 2: 按钮 onclick 传 true**

把 `app/templates/valuations.html:41`：

```html
    <button id="refresh-btn" class="btn btn-sm btn-primary" onclick="refreshPrices()">🔄 刷新实时价</button>
```

改为：

```html
    <button id="refresh-btn" class="btn btn-sm btn-primary" onclick="refreshPrices(true)">🔄 刷新实时价</button>
```

- [ ] **Step 3: 首屏渲染后自动补取**

把 `app/templates/valuations.html:497` `initValuations()` 内末行 `setMode(mode);` 之后追加一行（在 `setMode(mode);` 与函数结束 `}` 之间）：

```javascript
  setMode(mode);
  refreshPrices(false);
```

- [ ] **Step 4: 手动验证**

启动应用：`rtk python run.py`（或已运行实例），浏览器开 `http://127.0.0.1:5000/valuations/`。
Expected:
1. 首屏即时渲染（A股 有价、冷的 HK/US 初始可能「—」）。
2. 顶部状态栏短暂显「更新中…」→「自动更新 HH:MM:SS」；原显「—」的 HK/US 自动填入价格与安全边际。
3. 点「🔄 刷新实时价」按钮，状态显「刷新中…」→「已更新 HH:MM:SS」（硬刷全量）。
4. 半导体不再是单一大板块，出现 `存储`/`半导体材料`/`功率`/`设备` 扁平顶级板块 + `其余半导体`（可展开 design/光学 等二级）。

- [ ] **Step 5: Commit**

```bash
rtk git add app/templates/valuations.html && rtk git commit -m "feat(valuations): 实时价首屏秒开后自动按 TTL 补取冷缓存

refreshPrices 参数化：手动按钮 force=1 硬刷，首屏渲染后自动 force=0 补取
冷缓存的 HK/US；状态文案区分自动更新/已更新。后端零改动。

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Self-Review

- **Spec 覆盖**：
  - 改动一（半导体升顶级）→ Task 1 全覆盖（配置 + `_top_key`/`_top_label`/`group_by_sector` + 测试）。
  - 改动二（实时价首屏秒开 + 自动补取）→ Task 2 全覆盖（参数化 + 按钮 + init 自动补取 + 手动验证）。
  - 决策点「design 不升」→ Task 1 Step 1 `test_semi_design_not_promoted_goes_to_semi_other` 显式断言。
  - 「半导体材料」区分标签 → Task 1 Step 1 `test_semi_materials_promoted_with_distinct_label` + Step 3 配置。
  - 非目标（不改后端 / 不做通用化 / 不加轮询）→ 计划内无相关任务，符合。
- **Placeholder 扫描**：无 TBD/TODO；所有代码步骤含完整代码。
- **类型一致性**：`semi:<sub>` / `semi-other` / `PROMOTE_SEMI_SUBSECTORS` / `refreshPrices(force)` 在任务间命名一致；flat 判定 `startswith(('mat:', 'semi:'))` 与 `_top_label` 的 `semi:` 前缀切片 `key[5:]` 对齐。
- **已知回归**：Task 1 Step 1 已显式改写 `test_materials_subsector_under_other_sector_stays_put`（旧用例断言 semi materials 留在半导体组，与新行为冲突），避免遗漏。
