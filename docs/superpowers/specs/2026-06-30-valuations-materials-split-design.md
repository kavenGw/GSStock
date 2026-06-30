# 估值页「材料」板块打散 — 设计

> 状态：已批准（2026-06-30）
> 范围：`/valuations`（价值洼地）页展示分组；纯展示层，零数据迁移

## 背景与目标

`/valuations` 页用 `group_by_sector` 做两级分组（一级 `sector`，二级 `subsector`）。
「材料」(`materials`) 是最大一级组（29 只），分布极不均：

| 子类 | 只数 |
|---|---|
| 有色金属 `nonferrous` | 17 |
| 铜箔 `copper-foil` | 2 |
| 锂 `lithium` | 1 |
| 化工/磁材/陶瓷/小金属/超硬/玻璃/特气/工业气体/光伏银浆 | 各 1（共 9） |

目标：有色金属、锂（用户点名）、铜箔 不应埋在「材料」下，应升为独立顶级板块；其余 9 个单只子类归入一个「其余材料」桶，避免板块栏过碎。

## 决策

- 颗粒度：**抬大的 + 其余材料桶**（非完全打散，避免 10 个单只顶级板块）。
- 升顶级集合：`nonferrous`→有色金属、`lithium`→锂、`copper-foil`→铜箔。锂仅 1 只也单独出（用户点名）。
- 有色金属 17 只**保持扁平**，按安全边际排序，不再按金属（铜/铝/金/钨…）细分——本页目的是按安全边际找洼地，二级金属分组会打断排序。金属二级属未来独立增量（需 `commodity` 字段驱动）。

## 机制与数据流

板块归属藏在 `subsector`（`valuations_helpers.subsector_of` 由 `source_doc` 路径派生）。改动为**纯展示层**：不动 `valuations.yaml`、docs frontmatter、sector 枚举。

`app/routes/valuations.py` 新增配置：
```python
PROMOTE_MATERIALS_SUBSECTORS = {'nonferrous': '有色金属', 'lithium': '锂', 'copper-foil': '铜箔'}
MATERIALS_OTHER_KEY, MATERIALS_OTHER_LABEL = 'materials-other', '其余材料'
```

`group_by_sector` 一级 key 计算扩展（保留现有 carve-out 优先级）：

1. `category ∈ CARVE_OUT_CATEGORIES` → key=分类名（啤酒，不变，**最高优先**）
2. `sector == 'materials'` 且 `subsector ∈ PROMOTE_MATERIALS_SUBSECTORS` → key=`mat:<sub>`，标 `flat=True`，升为扁平顶级板块
3. `sector == 'materials'`（其余，含 subsector=None）→ key=`materials-other`，保留 subsector 二级展示
4. 其它 → key=`sector or '__none__'`（不变）

label 映射：
- key 以 `mat:` 开头 → `PROMOTE_MATERIALS_SUBSECTORS[sub]`
- key == `materials-other` → `其余材料`
- 其余分支不变（CARVE_OUT/`__none__`→未分类/`SECTOR_LABELS`）

每组结构新增 `flat: bool`（默认 False；升顶级的材料子类为 True）。

## 视觉结果（grouped 模式）

顶级板块按只数降序，出现：
`半导体 · 电子 · 有色金属(17) · 消费 · …其它 sector… · 其余材料(9) · 铜箔(2) · 锂(1) · 啤酒`

- 有色金属/锂/铜箔：扁平，标的直接按安全边际列出，无双层表头。
- 其余材料(9)：展开后二级 = 化工/磁材/陶瓷/小金属/超硬/玻璃/特气/工业气体/光伏银浆（各 1）。
- 旧「材料(29)」消失。

## 渲染 / JS 改动（最小侵入）

模板两级结构（lvl1▸lvl2▸行）写死，且 `applySort` 依赖 lvl2 表头存在于 DOM（从 lvl2 表头构建 `subRows`、再 append 行）。因此扁平板块**仍输出一个 lvl2 表头但隐藏**：

- `group_by_sector`：扁平组生成单个 subgroup（`subgroup_id=f'{key}__{sub}'`，行带 `data-subgroup`），组上 `flat=True`。
- 模板 `valuations.html`：`g.flat` 时给 lvl2 表头加 `subgroup-flat` 类。
- CSS：`.group-header.lvl2.subgroup-flat { display:none; }`（首屏 JS 跑前也隐藏）。
- JS `recompute()` lvl2 循环：`subgroup-flat` 表头跳过重显（`h.style.display='none'; return;`），否则 inline style 会把它顶出来。这是**唯一**的 JS 行为改动。
- `applySort` 无需改：照常 append 隐藏的 lvl2 表头 + 行，顺序正确。

兼容性：
- `hiddenSectors`（板块显隐持久化）：新 key（`mat:nonferrous` 等）天然纳入；旧 `materials` 在 localStorage 里被 `loadPref` 的 chip 校验自动丢弃，非破坏。
- 每行 `sector_label` = 所在顶级板块 label（有色金属/锂/铜箔/其余材料），平铺模式徽标随之正确。

## 测试

新增 `tests/test_valuations_grouping.py`（直接调 `group_by_sector`，无需 create_app）：

1. nonferrous/lithium/copper-foil 行各成独立顶级组，`flat=True`，label 正确。
2. 9 个单只子类落入 `materials-other`，`flat=False`，保留各自二级 subgroup。
3. 非 materials sector 行不受影响（仍按 sector 分组）。
4. 啤酒 carve-out（category 命中）仍优先于 materials 升顶级逻辑。
5. materials 行 subsector=None → 落 `materials-other` 的「未分类」二级。

## 文档

更新 `.claude/rules/portfolio-valuations.md` 估值页一节：补「materials 子类升顶级板块」机制，与 `CARVE_OUT_CATEGORIES` 并列说明（一个按 DB 分类 carve、一个按 subsector 升顶级）。

## 非目标 / YAGNI

- 不做有色金属金属类二级细分。
- 不推广到其它 sector（半导体/电子等仍按 sector）。
- 不改 sector 枚举、frontmatter、valuations.yaml。
