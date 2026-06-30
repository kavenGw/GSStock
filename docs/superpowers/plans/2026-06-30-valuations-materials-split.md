# 估值页材料板块打散 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 `/valuations`（价值洼地）页把「材料」一级组打散——有色金属/锂/铜箔 升为独立扁平顶级板块，其余材料子类归入「其余材料」桶。

**Architecture:** 纯展示层改动，全部集中在 `group_by_sector`（Python 分组逻辑）+ `valuations.html`（模板/CSS/JS 渲染）。不动 `valuations.yaml`、docs frontmatter、sector 枚举。板块归属由 `subsector`（`source_doc` 路径派生）驱动。

**Tech Stack:** Flask + Jinja2 模板 + 原生 JS（ECharts 无关）；pytest 单测。

## Global Constraints

- 响应中文；不写多余注释；不写 backup 文件。
- 所有 git/pytest 命令前加 `rtk`，链式 `&&` 中也要。
- `git add` 与 `git commit` 放进**同一条** Bash 命令链（并行 session 抢 index）；中文多行 message 走 `.git/MSG.txt` 文件避免 heredoc 失配。
- 跑 pytest：`PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest ...`（env 赋值在 `rtk` 之前）。
- **改 `app/` 代码前先开独立 git worktree** 隔离 main（见 Task 0）。
- 升顶级集合（verbatim）：`PROMOTE_MATERIALS_SUBSECTORS = {'nonferrous': '有色金属', 'lithium': '锂', 'copper-foil': '铜箔'}`，`MATERIALS_OTHER_KEY = 'materials-other'`，`MATERIALS_OTHER_LABEL = '其余材料'`。

---

## File Structure

- `app/routes/valuations.py` — 新增 promotion 配置常量 + 重构 `group_by_sector` 的一级 key/label 计算，组 dict 增 `flat` 字段。核心逻辑。
- `app/templates/valuations.html` — flat 组隐藏 lvl2 表头（模板条件类 + CSS + `recompute()` 一处 JS 微调）。视图层。
- `tests/test_valuations_grouping.py` — 新建，纯函数单测 `group_by_sector`。
- `.claude/rules/portfolio-valuations.md` — 补「materials 子类升顶级板块」机制文档。

---

## Task 0: 开 worktree 隔离

- [ ] **Step 1: 用 using-git-worktrees skill 建隔离工作树**

REQUIRED SUB-SKILL: superpowers:using-git-worktrees。基于 main，feature 名 `valuations-materials-split`。后续所有 Task 在该 worktree 内进行。

---

## Task 1: `group_by_sector` 升顶级逻辑（核心，纯函数 TDD）

**Files:**
- Modify: `app/routes/valuations.py`（`CARVE_OUT_CATEGORIES` 常量附近加配置；重写 `group_by_sector`，约 104-140 行）
- Test: `tests/test_valuations_grouping.py`（新建）

**Interfaces:**
- Consumes: `group_by_sector(rows: list[dict]) -> list[dict]`，入参为 `_enrich` 后的行（已含 `subsector`/`category`/`margin_base`/`sector`）。
- Produces: 每个 group dict 含 `{'sector': str, 'label': str, 'count': int, 'flat': bool, 'subgroups': [...]}`。`flat=True` 仅当一级 key 以 `mat:` 开头（升顶级的材料子类）。

- [ ] **Step 1: 写失败测试**

新建 `tests/test_valuations_grouping.py`：

```python
from app.routes.valuations import group_by_sector


def _row(code, sector, subsector, base=None, category=None):
    return {
        'stock_code': code,
        'sector': sector,
        'subsector': subsector,
        'category': category,
        'margin_base': base,
    }


def test_nonferrous_promoted_to_flat_toplevel():
    rows = [_row('601899', 'materials', 'nonferrous'),
            _row('000630', 'materials', 'nonferrous')]
    groups = group_by_sector(rows)
    g = next(x for x in groups if x['label'] == '有色金属')
    assert g['sector'] == 'mat:nonferrous'
    assert g['flat'] is True
    assert g['count'] == 2
    assert len(g['subgroups']) == 1


def test_lithium_single_stock_still_promoted():
    rows = [_row('002460', 'materials', 'lithium')]
    groups = group_by_sector(rows)
    g = next(x for x in groups if x['label'] == '锂')
    assert g['sector'] == 'mat:lithium'
    assert g['flat'] is True


def test_copper_foil_promoted():
    rows = [_row('301217', 'materials', 'copper-foil')]
    groups = group_by_sector(rows)
    g = next(x for x in groups if x['label'] == '铜箔')
    assert g['flat'] is True


def test_singleton_subsectors_go_to_materials_other():
    rows = [_row('600309', 'materials', 'chemicals'),
            _row('300224', 'materials', 'ceramics')]
    groups = group_by_sector(rows)
    g = next(x for x in groups if x['sector'] == 'materials-other')
    assert g['label'] == '其余材料'
    assert g['flat'] is False
    assert {sg['label'] for sg in g['subgroups']} == {'化工', '陶瓷'}


def test_non_materials_sector_unaffected():
    rows = [_row('002463', 'electronics', 'pcb')]
    groups = group_by_sector(rows)
    g = next(x for x in groups if x['sector'] == 'electronics')
    assert g['flat'] is False
    assert g['label'] == '电子'


def test_carveout_category_beats_materials_promotion():
    rows = [_row('000729', 'materials', 'nonferrous', category='啤酒')]
    groups = group_by_sector(rows)
    g = next(x for x in groups if x['sector'] == '啤酒')
    assert g['flat'] is False


def test_materials_no_subsector_falls_to_other_unclassified():
    rows = [_row('600309', 'materials', None)]
    groups = group_by_sector(rows)
    g = next(x for x in groups if x['sector'] == 'materials-other')
    assert g['subgroups'][0]['label'] == '未分类'
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_valuations_grouping.py -v`
Expected: FAIL（`KeyError: 'flat'` / `StopIteration`——当前 group dict 无 `flat`，且 materials 未拆）。

- [ ] **Step 3: 加配置常量**

在 `app/routes/valuations.py` 的 `CARVE_OUT_CATEGORIES = {'啤酒'}` 之后插入：

```python
PROMOTE_MATERIALS_SUBSECTORS = {'nonferrous': '有色金属', 'lithium': '锂', 'copper-foil': '铜箔'}
MATERIALS_OTHER_KEY = 'materials-other'
MATERIALS_OTHER_LABEL = '其余材料'
```

- [ ] **Step 4: 重写 `group_by_sector`**

把现有 `group_by_sector`（约 104-140 行）整体替换为：

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
    return r.get('sector') or '__none__'


def _top_label(key: str) -> str:
    if key in CARVE_OUT_CATEGORIES:
        return key
    if key.startswith('mat:'):
        return PROMOTE_MATERIALS_SUBSECTORS[key[4:]]
    if key == MATERIALS_OTHER_KEY:
        return MATERIALS_OTHER_LABEL
    if key == '__none__':
        return '未分类'
    return SECTOR_LABELS.get(key, key)


def group_by_sector(rows: list[dict]) -> list[dict]:
    """两级分组：一级 key 走 _top_key（啤酒 carve-out > materials 子类升顶级 > sector）；
    升顶级的材料子类（mat:*）标 flat=True 供模板隐藏 lvl2 表头。一级内按 subsector 分二级组
    （None→未分类）。一级/二级均按标的数降序（key 兜底），行内按 Base 安全边际降序（None 末位）。"""
    buckets: dict[str, list] = {}
    for r in rows:
        buckets.setdefault(_top_key(r), []).append(r)
    groups = []
    for key, items in buckets.items():
        label = _top_label(key)
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
        groups.append({
            'sector': key,
            'label': label,
            'count': len(items),
            'flat': key.startswith('mat:'),
            'subgroups': subgroups,
        })
    groups.sort(key=lambda g: (-g['count'], g['sector']))
    return groups
```

- [ ] **Step 5: 跑测试确认通过**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_valuations_grouping.py -v`
Expected: 7 passed。

- [ ] **Step 6: 全量回归（确认没打挂其它 valuations 测试）**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/ -k valuations -v`
Expected: 全 passed（含本新文件 + 任何既有 valuations 相关测试）。

- [ ] **Step 7: 提交**

```bash
printf '%s\n' 'feat(valuations): 材料子类有色/锂/铜箔升顶级板块' '' '其余材料子类归 materials-other 桶；group_by_sector 增 flat 标志' '' 'Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>' > .git/MSG.txt && rtk git add app/routes/valuations.py tests/test_valuations_grouping.py && rtk git commit -F .git/MSG.txt && rm -f .git/MSG.txt
```

---

## Task 2: 扁平板块隐藏 lvl2 表头（模板 + CSS + JS）

**Files:**
- Modify: `app/templates/valuations.html`（CSS 块、lvl2 表头模板行 ~107、`recompute()` lvl2 循环 ~419-424）

**Interfaces:**
- Consumes: group dict 的 `g.flat`（Task 1 产出）。
- Produces: 无下游消费（终端视图层）。

视图层交互（DOM 重排 + 折叠）无浏览器测试框架，验证以**人工浏览器核对**为准；逻辑正确性已由 Task 1 的 `flat` 单测兜底。

- [ ] **Step 1: 加 CSS——隐藏 flat 子组表头**

在 `valuations.html` 的 `<style>` 块内，`.group-header.lvl2:hover { background: #eef1f4; }`（约 20 行）之后加一行：

```css
.group-header.lvl2.subgroup-flat { display: none; }
```

- [ ] **Step 2: 模板——flat 组的 lvl2 表头加 `subgroup-flat` 类**

把 lvl2 表头行（约 107 行）：

```html
    <tr class="group-header lvl2" data-sector="{{ g.sector }}" data-subgroup="{{ sg.subgroup_id }}" onclick="toggleSub('{{ sg.subgroup_id }}')">
```

改为：

```html
    <tr class="group-header lvl2{% if g.flat %} subgroup-flat{% endif %}" data-sector="{{ g.sector }}" data-subgroup="{{ sg.subgroup_id }}" onclick="toggleSub('{{ sg.subgroup_id }}')">
```

- [ ] **Step 3: JS——`recompute()` 跳过 flat 子组表头重显**

`recompute()` 里的 lvl2 表头循环（约 419-424 行）：

```javascript
  tbody.querySelectorAll('.group-header.lvl2').forEach(h => {
    const v = subVisible[h.dataset.subgroup] || 0;
    h.style.display = (v > 0 && !collapsedSec.has(h.dataset.sector)) ? '' : 'none';
    const badge = h.querySelector('.subgroup-count');
    if (badge) badge.textContent = v;
  });
```

改为（开头加一行守卫，flat 表头恒隐藏，否则下方 inline `display=''` 会盖掉 CSS 把它顶出来）：

```javascript
  tbody.querySelectorAll('.group-header.lvl2').forEach(h => {
    if (h.classList.contains('subgroup-flat')) { h.style.display = 'none'; return; }
    const v = subVisible[h.dataset.subgroup] || 0;
    h.style.display = (v > 0 && !collapsedSec.has(h.dataset.sector)) ? '' : 'none';
    const badge = h.querySelector('.subgroup-count');
    if (badge) badge.textContent = v;
  });
```

- [ ] **Step 4: 起应用人工核对**

Run: `SCHEDULER_ENABLED=0 python run.py`（后台），浏览器开 `http://127.0.0.1:5000/valuations`。

核对清单（grouped 分组模式）：
- 出现顶级板块「有色金属」(17)，其下 17 只直接平铺、**无**「▸有色」二级表头。
- 出现「锂」(1)、「铜箔」(2) 独立扁平板块。
- 出现「其余材料」(9)，展开后二级仍是 化工/磁材/陶瓷/小金属/超硬/玻璃/特气/工业气体/光伏银浆。
- 旧「材料」(29) 板块消失。
- 点「有色金属」lvl1 表头可整组折叠/展开。
- 切「平铺」模式：各行板块徽标显示对应顶级 label（有色金属/锂/铜箔/其余材料）。
- 板块 chip 栏点「有色金属」可隐藏该组，刷新页面后保持隐藏（localStorage）。
- 按 Bear/Base/Bull 排序：有色金属组内 17 只随之重排，组顺序也随代表值变化。

核对通过后停掉 `run.py`。

- [ ] **Step 5: 提交**

```bash
printf '%s\n' 'feat(valuations): 扁平顶级板块隐藏冗余 lvl2 表头' '' 'flat 组 lvl2 加 subgroup-flat 类 + CSS 隐藏；recompute 跳过其重显' '' 'Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>' > .git/MSG.txt && rtk git add app/templates/valuations.html && rtk git commit -F .git/MSG.txt && rm -f .git/MSG.txt
```

---

## Task 3: 文档——补 rule 机制说明

**Files:**
- Modify: `.claude/rules/portfolio-valuations.md`（「估值汇总页（/valuations…）」一节）

- [ ] **Step 1: 在 valuations 节补「子类升顶级」机制**

在 `.claude/rules/portfolio-valuations.md` 里「**新增一个主题/二级板块分组**」段落之后，加一段：

```markdown
**materials 子类升顶级板块（与 CARVE_OUT_CATEGORIES 并列的第二条 carve 机制）**：`group_by_sector` 对 `sector=='materials'` 的行特殊处理——`subsector ∈ PROMOTE_MATERIALS_SUBSECTORS`（有色 `nonferrous`/锂 `lithium`/铜箔 `copper-foil`）升为**扁平顶级板块**（组 `flat=True`），其余材料子类归入 `materials-other`（「其余材料」桶，保留 subsector 二级）。区别于 CARVE_OUT_CATEGORIES（按 DB 分类 carve），此机制**按 subsector（source_doc 路径派生）driven**、仅作用于 materials、零数据改动。扁平组在模板里给 lvl2 表头加 `subgroup-flat` 类隐藏，`recompute()` 跳过其重显。新增升顶级子类只改 `PROMOTE_MATERIALS_SUBSECTORS` dict。
```

- [ ] **Step 2: 提交**

```bash
printf '%s\n' 'docs(rules): 补 valuations materials 子类升顶级板块机制' '' 'Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>' > .git/MSG.txt && rtk git add .claude/rules/portfolio-valuations.md && rtk git commit -F .git/MSG.txt && rm -f .git/MSG.txt
```

---

## Task 4: 收尾——合回 main

- [ ] **Step 1: 用 finishing-a-development-branch skill 收口**

REQUIRED SUB-SKILL: superpowers:finishing-a-development-branch。全量 pytest 绿后，把 worktree 合回 main（本仓 valuations 改动无跨档 lint 依赖，直接 merge）。
