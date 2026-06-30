# Claude估值页 — 板块显隐 toggle group 设计

- 日期：2026-06-30
- 范围：`app/templates/valuations.html` 纯前端单文件；`app/routes/valuations.py` 零改动
- 目标：在估值页加一排板块 chips，多选 toggle 控制每个一级 sector 是否显示，状态持久化

## 背景

估值页（`/valuations`）当前有三组交互：

- 市场 chips（全部/A股/港股/美股，单选过滤，**不持久化**，刷新回到「全部」）
- 主题下拉（多选过滤，**持久化**于 `valuationsSortPref`）
- 分组/平铺模式切换

表格分两级组：lvl1 = sector（半导体/电子/消费… 共 11 类 + 啤酒等 carve-out 分类），lvl2 = subsector。已有逐板块折叠（`toggleSector`），但折叠只收起行、表头还在，无法把整个板块从视图里移除，也不能一次聚焦某几个板块。

本设计新增「板块显隐」开关，与折叠是两回事：开关直接把整个板块（含表头与所有行）从视图移除。

## 需求确认（已与用户敲定）

1. **粒度**：仅一级 sector（lvl1），不含二级 subsector 单独开关。
2. **UI 形态**：一排 chips，仿市场 chips 样式，多选 toggle。
3. **持久化**：隐藏状态存 localStorage，刷新/重开页面保持。

## 设计

### 1. chips 渲染（模板）

- 新增一排板块 chips，**独立成行**放在现有控制行（市场/主题/模式）下方。理由：一级 sector 有 8-12 个，挤进现有行会换行错乱。
- chips 数据源 = 服务端已算好的 `groups`（`index()` 已传入模板）。每个 chip 对应一个 group：
  - key = `g.sector`（如 `semiconductor`、carve-out 为分类名如 `啤酒`、未分类为 `__none__`）
  - 文案 = `g.label`
  - 数量徽标 = `g.count`（**静态**，与市场 chips 一致，不随市场/主题筛选变化）
- carve-out 分类（如「啤酒」）在 `groups` 里就是顶级 group，因此也是一个独立 chip。
- 最前面加一个「全部」复位 chip（`data-sector="__all__"`）：点击清空隐藏集合、恢复全部显示。
- 仅在 `groups` 非空时渲染（页面顶层已有 `{% if not groups %}` 守卫，chips 行放进 `{% else %}` 分支）。

### 2. 状态模型（JS）

- 维护一个 `hiddenSectors`（`Set`），**存被隐藏的 sector key，而非显示的**。
  - 关键取舍：将来 `valuations.yaml` 新增板块时，新板块不在隐藏集合里 → 默认显示；只有用户明确关掉的才保持隐藏。若反过来存「显示集合」，新板块会因不在集合里被莫名隐藏。
- 默认全显示（`hiddenSectors` 为空）。
- chip 视觉：显示 = `btn-primary`，隐藏 = `btn-outline-secondary`（与市场 chips 的 `btn-outline-primary` 区分，避免混淆单选/多选语义）。

### 3. 持久化

- 并入现有 `valuationsSortPref` 这个 PREF 对象，新增字段 `hiddenSectors: [...]`，复用 `loadPref()` / `savePref()`，**不新开 localStorage key**。
- `loadPref()` 读取时按当前实际渲染的 chips 校验、丢弃失效 key（参照现有 themes 的 `valid` 集合做法）。

### 4. 与现有筛选/模式协同（复用现有管线）

板块显隐与市场、主题筛选是 **AND** 关系，复用 `recompute()` 现有的 `filterHidden` 机制：

- 把「sector 是否被隐藏」并进现有 `fOk` 判断：`rowMatchesMarket(tr) && themeMatches(tr) && sectorShown(tr)`，其中 `sectorShown(tr)` = `!hiddenSectors.has(tr.dataset.sector)`。
- 分组模式：被隐藏板块的 lvl1 表头、lvl2 表头、行全部消失（现有 `secVisible`/`subVisible` 计数变 0 → 表头自动隐藏，零额外逻辑）。
- 平铺模式：行上本来就有 `data-sector`，同样按 sector 过滤生效，无表头不受影响。
- 排序：不受影响。隐藏行只是 `display:none`，排序仍对全集排。
- 刷新实时价：`refreshPrices()` 末尾已调 `recompute()`，隐藏状态自然保持。

### 5. 事件与初始化

- chip 点击：
  - 「全部」chip → 清空 `hiddenSectors`，所有板块 chip 置为显示态。
  - 普通 sector chip → 在 `hiddenSectors` 里 toggle 该 key，更新该 chip class。
  - 之后统一 `savePref()` + `recompute()`（无需 `applySort()`，显隐不改变排序）。
- `initValuations()` 末尾：根据 `hiddenSectors` 初始化每个 chip 的 class，然后 `recompute()` 已在 `setMode(mode)` 链路里触发，确保首屏按持久化状态显隐。

## 改动清单

- `app/templates/valuations.html`
  - 模板：新增板块 chips 行（含「全部」复位 chip + 每 group 一个 chip）。
  - JS：新增 `hiddenSectors` 状态、`sectorShown()`、chip 点击事件、`loadPref`/`savePref` 增字段、`recompute()` 的 `fOk` 并入 sector 判断、`initValuations()` 初始化 chip class。
- `app/routes/valuations.py`：无改动。

## 验证

- 单测层不易覆盖纯前端交互；以手工冒烟为准（渲染 HTML 路由需走 `create_app()`，见 dev-environment 规则）。
- 冒烟点：
  1. 默认全显示，chips 全亮。
  2. 点某板块 chip → 该板块表头+行消失，chip 变暗；其它板块不受影响。
  3. 点「全部」→ 恢复全显示。
  4. 隐藏后刷新页面 → 隐藏状态保持。
  5. 板块隐藏 + 市场筛选 + 主题筛选三者叠加为 AND。
  6. 平铺模式下板块隐藏同样生效。
  7. 「刷新实时价」后隐藏状态不丢。

## 不做（YAGNI）

- 二级 subsector 单独开关。
- 板块顺序拖拽 / 自定义排序。
- 服务端按隐藏集合裁剪数据（纯前端 display 切换即可，数据量小）。
