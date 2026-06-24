# 估值页 theme 筛选 — 设计

> 日期：2026-06-25
> 目标：在 Claude估值页（`/valuations`）增加按主题（theme）筛选标的的能力，并在每行展示该股的 theme 标签。

## 背景

- 估值页 `app/routes/valuations.py` + `app/templates/valuations.html` 从 `docs/stock-analytics/valuations.yaml` 读 162 条目，按 sector 分组渲染，已有「市场 chips（全部/A/HK/US）」「分组/平铺切换」「列排序」「刷新实时价」。
- valuations.yaml 由 `scripts/sync_valuations.py` 扫各个股 buffett 档 frontmatter 生成；当前条目**不含** themes。
- 每个个股 buffett 档 frontmatter 自带 `themes:` 列表（161 档，与 stock_code 1:1）。这是最自然的 per-stock 主题源。
- 全量 themes 取值很碎：350 个不同 theme，其中 273 个是单例（只挂 1 只股），≥2 只的 77 个，≥3 只的 37 个。

## 决策

| 维度 | 选择 |
|------|------|
| 主题数据源 | 个股 buffett 档 `themes:` 字段，经 `sync_valuations.py` 回填进 valuations.yaml |
| 筛选器暴露范围 | 只暴露 ≥2 只股的主题（77 个）；单例不进筛选器 |
| 筛选控件 | 手写 Bootstrap 多选下拉（含搜索框），无新依赖 |
| 多选语义 | 选中多个主题间 OR；与市场筛选 AND 叠加 |
| 行内展示 | 新增一列「主题」，展示该股**全部** themes（含单例）为小 badge |

## 数据链路

### 1. 生成器（`scripts/sync_valuations.py`）

- `build_entry()` 增加：从 `fm.get('themes')` 提取 themes 写入 `entry['themes']`。
- 清洗规则：丢弃非 list / 空值；丢弃 `_` 开头的哨兵（如 `_excluded`）；`str()` 归一；去重保序。结果为空列表时不写该字段（保持 yaml 精简）。
- 全量重跑 `python scripts/sync_valuations.py` 回填所有条目。

**边界**：A+H 切 H 口径导致 valuations.yaml 的 `stock_code` 与 buffett 档代码不一致的条目（如 688234→02631），sync 按 code 匹配不上 → 该条 `themes` 缺省为空，不进任何主题、行内无标签。可接受，本期不特殊处理。

## 路由层（`app/routes/valuations.py`）

- `_enrich()`：每行带上 `themes`（`r.get('themes') or []`）。
- 新增 `build_theme_options(rows) -> list[dict]`：统计全体行 theme 频次，只留 ≥2 的，按 `(频次 desc, 名称 asc)` 排序，返回 `[{'name': str, 'count': int}, ...]`。
- `index()`：把 `theme_options` 传入模板。
- `api/prices` 不改（只管价格/边际）。

## 前端（`app/templates/valuations.html`）

### 筛选控件
- 位置：现有市场 chips 与「分组/平铺」切换之间，同一行 flex。
- 结构：`btn` 触发 `.dropdown-menu`；菜单内顶部搜索 `input`（实时过滤复选项）+ 复选框列表（`主题名 (股数)`，如 `memory (12)`）+ 底部「清除」。
- 按钮文案随选中数变化：`主题` / `主题 (N)`。

### 行内 theme 列
- 新增表头「主题」（在「文档」前或「板块」后，择一不破坏排序列 data-sort 对齐）。
- 表头 `colspan` 由 11 → 12 同步改（group-header `<th colspan>`）。
- 行渲染该股全部 themes 为小 badge（`badge bg-light text-secondary`，与 sector_label 同风格）。
- 行上加 `data-themes`，用 Jinja `| tojson` 存 JSON 数组（单引号包属性），JS `JSON.parse` 后精确匹配——避免分隔符与含空格主题冲突。

### 筛选逻辑整合
- 现有 `applyMarketFilter()` 泛化为 `applyFilters()`：一行显示 = 市场命中 **AND** 主题命中（未选主题=不限）**AND** 未被分组折叠。
- 主题命中：行 themes 与选中主题集合有交集（OR）。
- 分组头可见股数 badge 按上述双条件重算（沿用现有重算逻辑，加入主题条件）。
- `switchMarket` / 主题下拉变更 / `toggleGroup` / `setMode` 都收敛到 `applyFilters()`。
- 选中主题持久化进现有 `PREF_KEY`（localStorage，与 sortKey/mode 一致）；`loadPref()` 恢复时校验仍存在于当前 theme_options 的项。

### 不受影响
- `refreshPrices()` 只改价格/边际 cell，不碰行显隐与主题。
- `applySort()` 逻辑不变（排序与筛选正交）。

## YAGNI（不做）

- 不引入 select2/tom-select 等外部库（项目全本地 vendored）。
- 不做主题层级/分组、不做主题×板块交叉透视。
- 不改 `themes/` 专题档数据；本期只用个股档 `themes`，不并入 theme 专题档的 `related_codes`。

## 涉及文件

- `scripts/sync_valuations.py` — build_entry 加 themes + 清洗
- `docs/stock-analytics/valuations.yaml` — 重生成（数据产物）
- `app/routes/valuations.py` — _enrich 带 themes + build_theme_options + index 传参
- `app/templates/valuations.html` — 下拉控件 + 主题列 + applyFilters

## 验证

- 重跑 sync 后 `grep -c "themes:" valuations.yaml` 应接近 162（除匹配不上的 A+H 切口径条目）。
- 启动应用，访问 `/valuations`：下拉列出 77 个 ≥2 主题（带股数）；选 1~多个主题行数收敛且与市场筛选 AND 正确；行内 badge 显示；分组头股数随筛选更新；刷新实时价不破坏筛选态；reload 后筛选态恢复。
