# Claude估值页 二级板块嵌套分组 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 `/valuations`（Claude估值）页在现有一级板块分组下再嵌套一层二级板块分组（一级→二级→个股，三层可折叠）。

**Architecture:** 二级板块 slug 从每条 `source_doc` 路径 `sectors/<sector>/<subsector>/...` 自动提取（数据已存在，yaml 不改）。后端 `group_by_sector` 由单层改为两级嵌套结构；新增 `SUBSECTOR_LABELS` 中文映射兑底。前端模板渲染两级 header，JS 重写折叠/筛选/排序为两级联动。

**Tech Stack:** Flask + Jinja2 + 原生 JS（无构建）；pytest。

## Global Constraints

- 响应/注释中文；不写多余注释；不写 backup 文件。
- 所有 git/pytest 命令前加 `rtk`，env 赋值在 `rtk` 之前。
- 测试单文件 `tests/test_*.py` 平铺。
- 单测命令：`PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest <node-id> -v`
- `valuations.yaml` 不新增字段；`/api/prices` 接口、刷新逻辑、市场 chips、分组/平铺切换、排序偏好 localStorage 全部保留。
- 二级组复合 id 统一格式 `f"{sector_key}__{subsector_key}"`；DOM class 用 `sub-<复合id>`，JS 选择器侧用 `CSS.escape`。
- `subsector` 缺失（无 doc / 路径不符）归 `__none__`，标签「未分类」。

---

### Task 1: `subsector_of` 解析二级 slug

**Files:**
- Modify: `app/services/valuations_helpers.py`（文件末尾追加函数）
- Modify: `app/routes/valuations.py:9-11`（import 增列 `subsector_of`，使其可经 `app.routes.valuations.subsector_of` 访问，与现有 `compute_margin` 等一致）
- Test: `tests/test_valuations.py`（追加）

**Interfaces:**
- Produces: `subsector_of(row: dict) -> Optional[str]` — `source_doc` 形如 `sectors/<sec>/<sub>/<file>` 时返回 `parts[2]`，否则 `None`。

- [ ] **Step 1: 写失败测试**（追加到 `tests/test_valuations.py` 末尾）

```python
def test_subsector_of_extracts_from_source_doc():
    from app.routes.valuations import subsector_of
    assert subsector_of({'source_doc': 'sectors/semiconductor/storage/2026-x.md'}) == 'storage'


def test_subsector_of_missing_doc_returns_none():
    from app.routes.valuations import subsector_of
    assert subsector_of({}) is None


def test_subsector_of_short_path_returns_none():
    from app.routes.valuations import subsector_of
    assert subsector_of({'source_doc': 'sectors/semiconductor'}) is None


def test_subsector_of_non_sectors_path_returns_none():
    from app.routes.valuations import subsector_of
    assert subsector_of({'source_doc': 'cross-sector/2026-x.md'}) is None
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_valuations.py -k subsector_of -v`
Expected: FAIL（`ImportError: cannot import name 'subsector_of'`）

- [ ] **Step 3: 实现 `subsector_of`**（追加到 `app/services/valuations_helpers.py` 末尾）

```python
def subsector_of(row: dict) -> Optional[str]:
    """从 source_doc 路径提取二级 slug：sectors/<sector>/<subsector>/<file> → parts[2]，否则 None。"""
    parts = (row.get('source_doc') or '').split('/')
    if len(parts) >= 4 and parts[0] == 'sectors':
        return parts[2]
    return None
```

- [ ] **Step 4: 在路由 import 中暴露**（`app/routes/valuations.py:9-11`）

把：

```python
from app.services.valuations_helpers import (
    VALUATIONS_PATH, load_valuations, _fetch_code, _extract_price, compute_margin,
)
```

改为：

```python
from app.services.valuations_helpers import (
    VALUATIONS_PATH, load_valuations, _fetch_code, _extract_price, compute_margin, subsector_of,
)
```

- [ ] **Step 5: 跑测试确认通过**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_valuations.py -k subsector_of -v`
Expected: PASS（4 passed）

- [ ] **Step 6: 提交**

```bash
rtk git add app/services/valuations_helpers.py app/routes/valuations.py tests/test_valuations.py && rtk git commit -m "feat(valuations): subsector_of 从 source_doc 提取二级 slug"
```

---

### Task 2: `SUBSECTOR_LABELS` 映射 + `_enrich` 补 subsector

**Files:**
- Modify: `app/routes/valuations.py`（在 `CARVE_OUT_CATEGORIES`（约 line 73）之后新增 `SUBSECTOR_LABELS`；`_enrich`（line 39-56）补 `subsector` 字段）
- Test: `tests/test_valuations.py`（追加）

**Interfaces:**
- Consumes: `subsector_of`（Task 1）
- Produces: `SUBSECTOR_LABELS: dict[str, str]`；`_enrich` 输出每行新增 `'subsector'`（slug 或 None）。

- [ ] **Step 1: 写失败测试**（追加到 `tests/test_valuations.py`）

```python
def test_subsector_labels_maps_common_slugs():
    from app.routes.valuations import SUBSECTOR_LABELS
    assert SUBSECTOR_LABELS['storage'] == '存储'
    assert SUBSECTOR_LABELS['nonferrous'] == '有色'


def test_enrich_attaches_subsector_from_source_doc():
    from app.routes.valuations import _enrich
    out = _enrich([{'stock_code': 'a', 'base': 1.0, 'source_doc': 'sectors/materials/nonferrous/x.md'}], {})
    assert out[0]['subsector'] == 'nonferrous'


def test_enrich_subsector_none_without_doc():
    from app.routes.valuations import _enrich
    out = _enrich([{'stock_code': 'a', 'base': 1.0}], {})
    assert out[0]['subsector'] is None
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_valuations.py -k "subsector_labels or enrich_attaches_subsector or enrich_subsector" -v`
Expected: FAIL（`ImportError: SUBSECTOR_LABELS` / `KeyError: 'subsector'`）

- [ ] **Step 3: 新增 `SUBSECTOR_LABELS`**（在 `app/routes/valuations.py` 的 `CARVE_OUT_CATEGORIES = {'啤酒'}` 这一行之后插入）

```python
SUBSECTOR_LABELS = {
    'storage': '存储', 'design': '设计', 'equipment': '设备', 'optical': '光学',
    'power': '功率', 'mcu': 'MCU', 'optical-components': '光学元件', 'wafer': '晶圆',
    'pcb': 'PCB', 'packaging': '封装', 'sic-substrate': '碳化硅衬底', 'mems': 'MEMS',
    'photonics': '光子', 'foundry': '晶圆代工', 'laser-chip': '激光芯片', 'networking': '网络',
    'advanced-packaging': '先进封装', 'materials': '材料', 'components': '元器件', 'ems': 'EMS',
    'display': '显示', 'servers': '服务器', 'pc-server': 'PC服务器', 'power-electronics': '功率电子',
    'functional-materials': '功能材料', 'display-glass': '显示玻璃', 'precision-manufacturing': '精密制造',
    'pcb-equipment': 'PCB设备', 'thermal-management': '热管理', 'nonferrous': '有色',
    'copper-foil': '铜箔', 'chemicals': '化工', 'magnetic-materials': '磁材', 'ceramics': '陶瓷',
    'minor-metals': '小金属', 'superhard': '超硬材料', 'lithium': '锂', 'consumer-electronics': '消费电子',
    'sportswear': '运动服饰', 'beer': '啤酒', 'home-appliance': '家电', 'mobility': '出行',
    'local-services': '本地生活', 'restaurant': '餐饮', 'designer-toy': '潮玩', 'auto': '汽车',
    'furniture': '家居', 'auto-ev': '新能源车', 'ev': '电动车', 'power-equipment': '电力设备',
    'cable': '线缆', 'auto-parts': '汽车零部件', 'precision-components': '精密零件',
    'cleanroom-epc': '洁净室EPC', 'defense': '国防军工', 'music-streaming': '音乐流媒体',
    'digital-marketing': '数字营销', 'short-video': '短视频', 'online-literature': '网络文学',
    'shopping-guide': '导购', 'internet-platform': '互联网平台', 'solar': '光伏', 'battery': '电池',
    'waste-to-energy': '垃圾发电', 'cloud': '云计算', 'software': '软件', 'database': '数据库',
    'exchange': '交易所', 'securities': '证券', 'cro': 'CRO',
}
```

- [ ] **Step 4: `_enrich` 补 subsector 字段**（`app/routes/valuations.py` 的 `_enrich`，`out.append({...})` 块内）

把：

```python
        out.append({
            **r,
            'category': cat_map.get(r['stock_code']),
            'current_price': price,
```

改为：

```python
        out.append({
            **r,
            'category': cat_map.get(r['stock_code']),
            'subsector': subsector_of(r),
            'current_price': price,
```

- [ ] **Step 5: 跑测试确认通过**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_valuations.py -k "subsector_labels or enrich_attaches_subsector or enrich_subsector" -v`
Expected: PASS（3 passed）

- [ ] **Step 6: 提交**

```bash
rtk git add app/routes/valuations.py tests/test_valuations.py && rtk git commit -m "feat(valuations): SUBSECTOR_LABELS 映射 + _enrich 补 subsector 字段"
```

---

### Task 3: `group_by_sector` 改两级嵌套

**Files:**
- Modify: `app/routes/valuations.py`（替换 `group_by_sector`，line 76-98）
- Test: `tests/test_valuations.py`（更新 4 个失效测试 + 追加新测试）

**Interfaces:**
- Consumes: `SECTOR_LABELS`、`SUBSECTOR_LABELS`、`CARVE_OUT_CATEGORIES`；每行的 `category` / `sector` / `subsector` / `margin_base`。
- Produces: `group_by_sector(rows) -> list[dict]`，元素结构：
  ```python
  {'sector': str, 'label': str, 'count': int,
   'subgroups': [{'key': str, 'subgroup_id': str, 'label': str, 'count': int, 'rows': list[dict]}]}
  ```
  一级按 `count` 降序（key 兜底）；二级按 `count` 降序（key 兜底）；行内按 `margin_base` 降序（None 末位）。每行写入 `sector_label`。`subgroup_id == f"{sector}__{subsector_key}"`。

- [ ] **Step 1: 更新 4 个失效测试 + 写新测试**

更新 `tests/test_valuations.py` 中这 4 个现存测试（返回结构由 `rows` 改 `subgroups`）：

`test_group_by_sector_sorts_rows_within_group_by_base_margin_desc` 改名并改体：

```python
def test_group_by_sector_sorts_rows_within_subgroup_by_base_margin_desc():
    from app.routes.valuations import group_by_sector
    rows = [
        {'stock_code': 'lo', 'sector': 'materials', 'subsector': 'nonferrous', 'margin_base': 0.05},
        {'stock_code': 'hi', 'sector': 'materials', 'subsector': 'nonferrous', 'margin_base': 0.50},
        {'stock_code': 'none', 'sector': 'materials', 'subsector': 'nonferrous', 'margin_base': None},
        {'stock_code': 'mid', 'sector': 'materials', 'subsector': 'nonferrous', 'margin_base': 0.20},
    ]
    [grp] = group_by_sector(rows)
    [sg] = grp['subgroups']
    assert [r['stock_code'] for r in sg['rows']] == ['hi', 'mid', 'lo', 'none']
```

`test_group_by_sector_carves_out_whitelisted_category` 改体：

```python
def test_group_by_sector_carves_out_whitelisted_category():
    from app.routes.valuations import group_by_sector
    rows = [
        {'stock_code': '600600', 'sector': 'other', 'category': '啤酒', 'subsector': 'beer', 'margin_base': 0.1},
        {'stock_code': '600132', 'sector': 'consumer', 'category': '啤酒', 'subsector': 'beer', 'margin_base': 0.3},
        {'stock_code': '000001', 'sector': 'consumer', 'category': None, 'subsector': None, 'margin_base': 0.2},
    ]
    groups = {g['sector']: g for g in group_by_sector(rows)}
    assert '啤酒' in groups
    beer = groups['啤酒']
    assert beer['label'] == '啤酒'
    assert beer['count'] == 2
    [beer_sg] = beer['subgroups']
    assert [r['stock_code'] for r in beer_sg['rows']] == ['600132', '600600']
    [cons_sg] = groups['consumer']['subgroups']
    assert [r['stock_code'] for r in cons_sg['rows']] == ['000001']
```

`test_group_by_sector_carveout_row_gets_category_label` 改体：

```python
def test_group_by_sector_carveout_row_gets_category_label():
    from app.routes.valuations import group_by_sector
    [grp] = group_by_sector([{'stock_code': '600132', 'sector': 'consumer', 'category': '啤酒', 'subsector': 'beer', 'margin_base': 0.1}])
    assert grp['subgroups'][0]['rows'][0]['sector_label'] == '啤酒'
```

`test_group_by_sector_assigns_sector_label_to_rows` 改体：

```python
def test_group_by_sector_assigns_sector_label_to_rows():
    from app.routes.valuations import group_by_sector
    groups = group_by_sector([
        {'stock_code': 'a', 'sector': 'semiconductor', 'subsector': 'storage', 'margin_base': 0.1},
        {'stock_code': 'b', 'sector': None, 'subsector': None, 'margin_base': 0.2},
    ])
    by_sector = {g['sector']: g for g in groups}
    assert by_sector['semiconductor']['subgroups'][0]['rows'][0]['sector_label'] == '半导体'
    assert by_sector['__none__']['subgroups'][0]['rows'][0]['sector_label'] == '未分类'
```

追加 4 个新测试到末尾：

```python
def test_group_by_sector_builds_subgroups_by_subsector():
    from app.routes.valuations import group_by_sector
    rows = [
        {'stock_code': 'a', 'sector': 'semiconductor', 'subsector': 'storage', 'margin_base': 0.1},
        {'stock_code': 'b', 'sector': 'semiconductor', 'subsector': 'storage', 'margin_base': 0.2},
        {'stock_code': 'c', 'sector': 'semiconductor', 'subsector': 'design', 'margin_base': 0.3},
    ]
    [grp] = group_by_sector(rows)
    assert grp['count'] == 3
    subs = {sg['key']: sg for sg in grp['subgroups']}
    assert subs['storage']['count'] == 2
    assert subs['storage']['label'] == '存储'
    assert subs['design']['count'] == 1
    assert [sg['key'] for sg in grp['subgroups']] == ['storage', 'design']


def test_group_by_sector_none_subsector_is_unclassified_subgroup():
    from app.routes.valuations import group_by_sector
    [grp] = group_by_sector([{'stock_code': 'a', 'sector': 'energy', 'subsector': None, 'margin_base': 0.1}])
    [sg] = grp['subgroups']
    assert sg['key'] == '__none__'
    assert sg['label'] == '未分类'


def test_group_by_sector_subgroup_id_is_sector_scoped():
    from app.routes.valuations import group_by_sector
    rows = [
        {'stock_code': 'a', 'sector': 'semiconductor', 'subsector': 'pcb', 'margin_base': 0.1},
        {'stock_code': 'b', 'sector': 'electronics', 'subsector': 'pcb', 'margin_base': 0.2},
    ]
    groups = {g['sector']: g for g in group_by_sector(rows)}
    sem_id = groups['semiconductor']['subgroups'][0]['subgroup_id']
    ele_id = groups['electronics']['subgroups'][0]['subgroup_id']
    assert sem_id == 'semiconductor__pcb'
    assert ele_id == 'electronics__pcb'
    assert sem_id != ele_id


def test_group_by_sector_subgroups_tiebreak_by_key():
    from app.routes.valuations import group_by_sector
    rows = [
        {'stock_code': 'a', 'sector': 'media', 'subsector': 'short-video', 'margin_base': 0.1},
        {'stock_code': 'b', 'sector': 'media', 'subsector': 'digital-marketing', 'margin_base': 0.2},
    ]
    [grp] = group_by_sector(rows)
    assert [sg['key'] for sg in grp['subgroups']] == ['digital-marketing', 'short-video']
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_valuations.py -k group_by_sector -v`
Expected: FAIL（旧实现无 `subgroups` 键 → `KeyError`）

- [ ] **Step 3: 替换 `group_by_sector`**（`app/routes/valuations.py:76-98` 整段替换）

```python
def group_by_sector(rows: list[dict]) -> list[dict]:
    """两级分组：一级 category 命中 CARVE_OUT_CATEGORIES 用分类名，否则按 sector；
    一级内再按 subsector 分二级组（None→未分类）。一级/二级均按标的数降序（key 兜底），
    行内按 Base 安全边际降序（None 末位）。每行写 sector_label。"""
    buckets: dict[str, list] = {}
    for r in rows:
        cat = r.get('category')
        key = cat if cat in CARVE_OUT_CATEGORIES else (r.get('sector') or '__none__')
        buckets.setdefault(key, []).append(r)
    groups = []
    for key, items in buckets.items():
        if key in CARVE_OUT_CATEGORIES:
            label = key
        elif key == '__none__':
            label = '未分类'
        else:
            label = SECTOR_LABELS.get(key, key)
        for r in items:
            r['sector_label'] = label
        sub_buckets: dict[str, list] = {}
        for r in items:
            sub_buckets.setdefault(r.get('subsector') or '__none__', []).append(r)
        subgroups = []
        for sub_key, sub_items in sub_buckets.items():
            sub_items = sorted(sub_items, key=lambda x: (x.get('margin_base') is None, -(x.get('margin_base') or 0)))
            sub_label = '未分类' if sub_key == '__none__' else SUBSECTOR_LABELS.get(sub_key, sub_key)
            subgroups.append({
                'key': sub_key,
                'subgroup_id': f"{key}__{sub_key}",
                'label': sub_label,
                'count': len(sub_items),
                'rows': sub_items,
            })
        subgroups.sort(key=lambda sg: (-sg['count'], sg['key']))
        groups.append({'sector': key, 'label': label, 'count': len(items), 'subgroups': subgroups})
    groups.sort(key=lambda g: (-g['count'], g['sector']))
    return groups
```

- [ ] **Step 4: 跑测试确认通过**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_valuations.py -k group_by_sector -v`
Expected: PASS（含改名后共 11 个 group_by_sector 测试全过）

- [ ] **Step 5: 提交**

```bash
rtk git add app/routes/valuations.py tests/test_valuations.py && rtk git commit -m "feat(valuations): group_by_sector 改两级嵌套(一级板块→二级板块)"
```

---

### Task 4: 模板 + CSS + JS 两级渲染与联动

**Files:**
- Modify: `app/templates/valuations.html`（整文件替换为下方内容）
- Test: `tests/test_valuations.py`（更新 2 个 JS 断言测试 + 追加渲染测试）

**Interfaces:**
- Consumes: `groups`（Task 3 结构，含 `subgroups`/`subgroup_id`）、`market_counts`、`total`。
- Produces（供测试断言）：HTML 含 `group-header lvl1` / `group-header lvl2` / `data-subgroup=`；JS 含 `function toggleSector` / `function toggleSub` / `function recompute` / `function repRows` / `defaultSectorOrder` / `defaultSubOrder` / `MARGIN_SORT_KEYS`；`switchMarket` 函数体调用 `applySort()`。

- [ ] **Step 1: 更新 2 个 JS 断言测试 + 写渲染测试**

更新 `test_index_has_currency_column_and_data_market`（line 155-160）—— 把 `toggleGroup` 改为两级函数：

```python
def test_index_has_currency_column_and_data_market(app_client):
    html = app_client.get('/valuations/').data.decode('utf-8')
    assert '币种' in html, '缺币种列头'
    assert 'data-market=' in html, '缺行 data-market 属性'
    assert 'switchMarket' in html, '缺 switchMarket JS'
    assert 'toggleSector' in html, '缺 toggleSector JS'
    assert 'toggleSub' in html, '缺 toggleSub JS'
```

更新 `test_index_has_group_reorder_js`（line 376-380）—— 改为新函数/变量名：

```python
def test_index_has_group_reorder_js(app_client):
    html = app_client.get('/valuations/').data.decode('utf-8')
    assert 'MARGIN_SORT_KEYS' in html, '缺组联动触发列常量'
    assert 'defaultSectorOrder' in html, '缺默认一级组顺序捕获'
    assert 'defaultSubOrder' in html, '缺默认二级组顺序捕获'
    assert 'function repRows' in html, '缺组代表值函数'
```

追加渲染测试到末尾：

```python
def test_index_renders_nested_subgroup_headers(app_client):
    html = app_client.get('/valuations/').data.decode('utf-8')
    assert 'group-header lvl1' in html, '缺一级组头'
    assert 'group-header lvl2' in html, '缺二级组头'
    assert 'data-subgroup=' in html, '缺二级组头/行 data-subgroup'
    assert 'function recompute' in html, '缺统一可见性重算函数'


def test_index_subgroup_id_is_sector_scoped_in_html(app_client):
    import re
    html = app_client.get('/valuations/').data.decode('utf-8')
    ids = set(re.findall(r'data-subgroup="([^"]+)"', html))
    assert ids, '页面无 data-subgroup'
    assert all('__' in i for i in ids), 'subgroup_id 应为 sector__sub 形态'
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_valuations.py -k "currency_column or group_reorder or nested_subgroup or subgroup_id_is_sector_scoped_in_html" -v`
Expected: FAIL（旧模板无 `toggleSector` / `lvl2` / `data-subgroup`）

- [ ] **Step 3: 整文件替换 `app/templates/valuations.html`**

```html
{% extends "base.html" %}
{% block title %}Claude估值 - 股票管理{% endblock %}
{% block extra_css %}
<style>
.margin-pos { color: #198754; font-weight: 600; }
.margin-neg { color: #dc3545; font-weight: 600; }
.val-table th, .val-table td { font-size: 13px; white-space: nowrap; vertical-align: middle; }
.rating-badge { font-size: 11px; }
.row-muted td { color: #adb5bd; }
.row-muted .rating-badge { opacity: .6; }
.group-header { cursor: pointer; }
.group-header .caret { display: inline-block; width: 1em; transition: transform .15s; }
.group-header.collapsed .caret { transform: rotate(-90deg); }
.group-header.lvl1 { background: #e9ecef; }
.group-header.lvl1:hover { background: #dee2e6; }
.group-header.lvl1 th { font-size: 13px; }
.group-header.lvl2 { background: #f8f9fa; }
.group-header.lvl2:hover { background: #eef1f4; }
.group-header.lvl2 th { font-size: 12px; font-weight: 500; padding-left: 2.4rem; }
#market-chips .chip { margin-right: 6px; }
.val-table th.sortable { cursor: pointer; user-select: none; }
.val-table th.sortable:hover { background: #e9ecef; }
.sort-arrow { display: inline-block; width: 1em; text-align: left; }
.mg { font-size: 11px; margin-left: 4px; }
table.mode-grouped .col-sector { display: none; }
table.mode-flat .group-header { display: none; }
#mode-toggle .btn { padding: .15rem .55rem; }
</style>
{% endblock %}
{% block content %}
<div class="d-flex justify-content-between align-items-center mb-3">
  <h4 class="mb-0"><i class="bi bi-cash-stack"></i> Claude估值</h4>
  <div>
    <span id="refresh-status" class="text-muted small me-2"></span>
    <button id="refresh-btn" class="btn btn-sm btn-primary" onclick="refreshPrices()">🔄 刷新实时价</button>
  </div>
</div>
{% if not groups %}
<div class="alert alert-warning">暂无估值数据（docs/stock-analytics/valuations.yaml 为空或缺失）。</div>
{% else %}
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
<div class="table-responsive">
<table id="val-table" class="table table-sm table-hover val-table mode-grouped">
  <thead class="table-light">
    <tr>
      <th>代码</th><th>名称</th><th class="col-sector">板块</th><th>币种</th>
      <th class="sortable" data-sort="rating" onclick="sortBy('rating')">评级<span class="sort-arrow"></span></th>
      <th class="text-end sortable" data-sort="bear" onclick="sortBy('bear')">Bear<span class="sort-arrow"></span></th>
      <th class="text-end sortable" data-sort="base" onclick="sortBy('base')">Base<span class="sort-arrow"></span></th>
      <th class="text-end sortable" data-sort="bull" onclick="sortBy('bull')">Bull<span class="sort-arrow"></span></th>
      <th class="text-end">当前价</th>
      <th class="sortable" data-sort="date" onclick="sortBy('date')">日期<span class="sort-arrow"></span></th><th>文档</th>
    </tr>
  </thead>
  <tbody>
  {% for g in groups %}
    <tr class="group-header lvl1" data-sector="{{ g.sector }}" onclick="toggleSector('{{ g.sector }}')">
      <th colspan="11"><span class="caret">▼</span> {{ g.label }} <span class="badge bg-secondary group-count">{{ g.count }}</span></th>
    </tr>
    {% for sg in g.subgroups %}
    <tr class="group-header lvl2" data-sector="{{ g.sector }}" data-subgroup="{{ sg.subgroup_id }}" onclick="toggleSub('{{ sg.subgroup_id }}')">
      <th colspan="11"><span class="caret">▼</span> {{ sg.label }} <span class="badge bg-light text-secondary subgroup-count">{{ sg.count }}</span></th>
    </tr>
      {% for r in sg.rows %}
      <tr data-code="{{ r.stock_code }}" data-market="{{ r.market }}" data-sector="{{ g.sector }}" data-subgroup="{{ sg.subgroup_id }}"
          data-mrating="{{ r.rating_rank if r.rating_rank is not none else '' }}"
          data-mdate="{{ r.date_rank if r.date_rank is not none else '' }}"
          data-mbear="{{ r.margin_bear if r.margin_bear is not none else '' }}"
          data-mbase="{{ r.margin_base if r.margin_base is not none else '' }}"
          data-mbull="{{ r.margin_bull if r.margin_bull is not none else '' }}"
          class="sub-{{ sg.subgroup_id }}{% if r.rating == 'exclude' %} row-muted{% endif %}">
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
      {% endfor %}
    {% endfor %}
  {% endfor %}
  </tbody>
</table>
</div>
{% endif %}

<script>
function fmtPrice(v) { return v === null || v === undefined ? '—' : v.toFixed(2); }
function fmtMargin(v) { return v === null || v === undefined ? '' : (v >= 0 ? '+' : '') + (v * 100).toFixed(1) + '%'; }

const PREF_KEY = 'valuationsSortPref';
let sortKey = 'base';
let sortDir = 'desc';
let mode = 'grouped';
let currentMarket = 'all';
let defaultSectorOrder = [];
let defaultSubOrder = {};
const MARGIN_SORT_KEYS = ['bear', 'base', 'bull'];

function loadPref() {
  try {
    const p = JSON.parse(localStorage.getItem(PREF_KEY) || '{}');
    if (['bear', 'base', 'bull', 'rating', 'date'].includes(p.sortKey)) sortKey = p.sortKey;
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

function rowMatchesMarket(tr) {
  return currentMarket === 'all' || tr.dataset.market === currentMarket;
}

function sortRows(rows) {
  const dir = sortDir === 'asc' ? 1 : -1;
  return rows.slice().sort((a, b) => {
    const va = marginOf(a, sortKey), vb = marginOf(b, sortKey);
    if (va === null && vb === null) return 0;
    if (va === null) return 1;
    if (vb === null) return -1;
    return (va - vb) * dir;
  });
}

// 取一组已排序行中首个「当前市场可见」行的边际，作为组代表值
function repRows(rows) {
  for (const tr of rows) {
    if (rowMatchesMarket(tr)) return marginOf(tr, sortKey);
  }
  return null;
}

function cmpRep(va, vb, dir) {
  if (va === null && vb === null) return 0;
  if (va === null) return 1;
  if (vb === null) return -1;
  return (va - vb) * dir;
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
    return;
  }
  const isMargin = MARGIN_SORT_KEYS.includes(sortKey);
  const dir = sortDir === 'asc' ? 1 : -1;
  const lvl1 = new Map([...tbody.querySelectorAll('.group-header.lvl1')].map(h => [h.dataset.sector, h]));
  const lvl2 = new Map([...tbody.querySelectorAll('.group-header.lvl2')].map(h => [h.dataset.subgroup, h]));
  const subRows = new Map();
  lvl2.forEach((h, subId) => {
    subRows.set(subId, sortRows([...tbody.querySelectorAll('tr.sub-' + CSS.escape(subId) + '[data-code]')]));
  });
  const subOrderBySector = {};
  Object.keys(defaultSubOrder).forEach(sec => {
    let order = defaultSubOrder[sec].slice();
    if (isMargin) {
      order.sort((a, b) => cmpRep(repRows(subRows.get(a) || []), repRows(subRows.get(b) || []), dir));
    }
    subOrderBySector[sec] = order;
  });
  function repSector(sec) {
    for (const subId of (subOrderBySector[sec] || [])) {
      const r = repRows(subRows.get(subId) || []);
      if (r !== null) return r;
    }
    return null;
  }
  let sectorOrder = defaultSectorOrder.slice();
  if (isMargin) {
    sectorOrder.sort((a, b) => cmpRep(repSector(a), repSector(b), dir));
  }
  sectorOrder.forEach(sec => {
    const h1 = lvl1.get(sec);
    if (!h1) return;
    tbody.appendChild(h1);
    (subOrderBySector[sec] || []).forEach(subId => {
      const h2 = lvl2.get(subId);
      if (!h2) return;
      tbody.appendChild(h2);
      (subRows.get(subId) || []).forEach(r => tbody.appendChild(r));
    });
  });
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
  recompute();
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
    document.querySelectorAll('#val-table .group-header').forEach(h => h.classList.remove('collapsed'));
  }
  savePref();
  applySort();
  recompute();
}

function switchMarket(ev, market) {
  ev.preventDefault();
  currentMarket = market;
  document.querySelectorAll('#market-chips .chip').forEach(b => {
    const on = b.dataset.market === market;
    b.classList.toggle('btn-primary', on);
    b.classList.toggle('btn-outline-primary', !on);
  });
  applySort();
  recompute();
}

// 统一可见性 + 计数重算：市场筛选 × 一级折叠 × 二级折叠
function recompute() {
  const tbody = document.querySelector('#val-table tbody');
  const collapsedSec = new Set();
  tbody.querySelectorAll('.group-header.lvl1.collapsed').forEach(h => collapsedSec.add(h.dataset.sector));
  const collapsedSub = new Set();
  tbody.querySelectorAll('.group-header.lvl2.collapsed').forEach(h => collapsedSub.add(h.dataset.subgroup));

  tbody.querySelectorAll('tr[data-code]').forEach(tr => {
    const mOk = rowMatchesMarket(tr);
    tr.dataset.marketHidden = mOk ? '' : '1';
    let show;
    if (mode === 'flat') {
      show = mOk;
    } else {
      show = mOk && !collapsedSec.has(tr.dataset.sector) && !collapsedSub.has(tr.dataset.subgroup);
    }
    tr.style.display = show ? '' : 'none';
  });

  if (mode === 'flat') {
    tbody.querySelectorAll('.group-header').forEach(h => { h.style.display = 'none'; });
    return;
  }

  const subVisible = {}, secVisible = {};
  tbody.querySelectorAll('tr[data-code]').forEach(tr => {
    if (tr.dataset.marketHidden === '1') return;
    subVisible[tr.dataset.subgroup] = (subVisible[tr.dataset.subgroup] || 0) + 1;
    secVisible[tr.dataset.sector] = (secVisible[tr.dataset.sector] || 0) + 1;
  });
  tbody.querySelectorAll('.group-header.lvl2').forEach(h => {
    const v = subVisible[h.dataset.subgroup] || 0;
    h.style.display = (v > 0 && !collapsedSec.has(h.dataset.sector)) ? '' : 'none';
    const badge = h.querySelector('.subgroup-count');
    if (badge) badge.textContent = v;
  });
  tbody.querySelectorAll('.group-header.lvl1').forEach(h => {
    const v = secVisible[h.dataset.sector] || 0;
    h.style.display = v > 0 ? '' : 'none';
    const badge = h.querySelector('.group-count');
    if (badge) badge.textContent = v;
  });
}

function toggleSector(sector) {
  if (mode !== 'grouped') return;
  const h = [...document.querySelectorAll('#val-table .group-header.lvl1')].find(x => x.dataset.sector === sector);
  if (!h) return;
  h.classList.toggle('collapsed');
  recompute();
}

function toggleSub(subId) {
  if (mode !== 'grouped') return;
  const h = [...document.querySelectorAll('#val-table .group-header.lvl2')].find(x => x.dataset.subgroup === subId);
  if (!h) return;
  h.classList.toggle('collapsed');
  recompute();
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
    recompute();
    status.textContent = '已更新 ' + new Date().toLocaleTimeString();
  } catch (e) {
    status.textContent = '刷新失败';
  } finally {
    btn.disabled = false;
  }
}

function initValuations() {
  loadPref();
  const tbody = document.querySelector('#val-table tbody');
  if (!tbody) return;
  defaultSectorOrder = [...tbody.querySelectorAll('.group-header.lvl1')].map(h => h.dataset.sector);
  defaultSubOrder = {};
  tbody.querySelectorAll('.group-header.lvl2').forEach(h => {
    (defaultSubOrder[h.dataset.sector] = defaultSubOrder[h.dataset.sector] || []).push(h.dataset.subgroup);
  });
  setMode(mode);
}
document.addEventListener('DOMContentLoaded', initValuations);
</script>
{% endblock %}
```

- [ ] **Step 4: 跑测试确认通过**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_valuations.py -k "currency_column or group_reorder or nested_subgroup or subgroup_id_is_sector_scoped_in_html or switch_market_triggers or renders_sector_group_headers" -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
rtk git add app/templates/valuations.html tests/test_valuations.py && rtk git commit -m "feat(valuations): 模板/JS 两级嵌套渲染+折叠+排序联动"
```

---

### Task 5: 全量回归与人工核对

**Files:** 无新增（验证收尾）

- [ ] **Step 1: 跑整个估值测试文件**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_valuations.py > .omc/artifacts/val_test.log 2>&1; rtk python -c "print(open('.omc/artifacts/val_test.log').read()[-2000:])"`
Expected: 末尾出现 `N passed`（含本次新增约 13 个 + 改写 6 个），无 failed。（按 dev-environment 约定：create_app 触发的 crawl4ai 进度走 stdout，故写文件再读末段，勿用管道）

- [ ] **Step 2: 跑相邻回归（同步脚本测试，确认未误伤）**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_sync_valuations.py -v`
Expected: PASS（本次未改 sync 逻辑，应全绿）

- [ ] **Step 3: 人工核对页面（启动应用，浏览器看 /valuations）**

Run: `python run.py`（另开终端）→ 浏览器 http://127.0.0.1:5000/valuations
核对清单：
- 一级板块组下出现二级板块子组（缩进、可折叠），子组数与计数正确。
- 点一级组头折叠：其全部二级组头 + 个股行隐藏；再点展开恢复（此前单独折叠的二级组保持折叠态）。
- 点二级组头：仅该子组个股行折叠。
- 切市场（A/HK/US）：空二级组、空一级组隐藏，计数随之更新。
- 点 Base/Bear/Bull 列头：行内→二级组→一级组三层重排；点评级/日期：保持默认序。
- 切「平铺」：无组头、全部行平铺排序；切回「分组」正常。
- 「🔄 刷新实时价」：价格/边际更新后排序仍生效。

- [ ] **Step 4: （可选）刷新 graphify 图谱**

仅当上述全过。小改动可跳过。

---

## 自检记录（写计划时）

- **Spec 覆盖**：呈现形态（Task 3/4）、数据来源 subsector_of（Task 1）、SUBSECTOR_LABELS 兑底（Task 2）、忠实全展（Task 3 不合并单例）、边界 other/啤酒/None（Task 3 测试）、不变项 api/刷新/切换/localStorage（Task 4 保留）、测试（各 Task + Task 5）—— 全覆盖。
- **占位符**：无 TODO/TBD；每步含完整代码或精确命令。
- **类型一致**：`group_by_sector` 产出 `subgroups[].{key,subgroup_id,label,count,rows}` 在 Task 3 定义、Task 4 模板与 JS 消费一致；`subgroup_id == f"{sector}__{sub}"` 三处一致；JS 函数名 `toggleSector/toggleSub/recompute/repRows/applySort` 与测试断言一致；移除的旧名 `toggleGroup/groupRepresentative/defaultGroupOrder` 已在 Task 4 同步更新对应测试。
