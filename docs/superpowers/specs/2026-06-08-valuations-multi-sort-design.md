# 估值汇总页多排序优化 — 设计文档

> 日期：2026-06-08
> 范围：`/valuations` 估值汇总页，在现有「板块分组视图」基础上增加多维度排序（点列头）+ 分组/平铺模式切换 + 偏好持久化
> 前序：`docs/superpowers/specs/2026-06-05-valuations-summary-grouping-design.md`（板块分组改造）

## 背景与痛点

当前 `/valuations`（`app/routes/valuations.py` + `app/templates/valuations.html`）：

- 服务端按 `sector` 分组渲染，组按标的数降序；**组内固定按 Base 安全边际降序**，无法改排序
- 市场 chip 客户端筛选、板块组头可折叠、刷新实时价
- 痛点：排序写死。想按 Bear（下限保护）或 Bull（上行弹性）边际看时无能为力；想跨板块整体排个序也做不到

## 需求（已与用户确认）

1. **两种模式**：分组（组内排序，组顺序仍按标的数）+ 平铺（打散分组、整表排序）
2. **排序维度**：Bear / Base / Bull 三个场景的安全边际（不含代码/名称/日期/评级/当前价）
3. **交互**：点列头切升/降 + 箭头指示；并把三列从「只显示绝对估值」改为「绝对值 · 边际%」
4. **持久化**：排序列 + 升降序 + 分组/平铺模式存 localStorage，刷新后恢复
5. **列布局**：删独立「Base安全边际」列，边际并入 Bear/Base/Bull 三列；平铺模式下用**独立「板块」列**标注归属

## 实现路径

**纯客户端排序（已选，方案 A）**：

- 服务端照旧渲染分组表，但把每行的 `margin_bear/base/bull` 输出成 `data-*` 属性
- 排序、升降、分组/平铺切换全靠 JS 重排 DOM，零网络、毫秒级
- 复用现有服务端分组模板与 `/api/prices`，改动面最小

**否决备选**：
- 方案 B（服务端 `?sort=&dir=&mode=` 重渲染）：每次排序刷新页面、慢，且给路由加排序/平铺分支，与"实时翻看"冲突
- 方案 C（路由回平铺 JSON、JS 全量建表）：丢掉现成分组模板、改动最大；前序分组设计文档已否决同类路线

## 详细设计

### 1. 页面结构

```
估值汇总                                          [🔄 刷新实时价]
[全部 122][A股 94][港股 18][美股 10]    [▣ 分组 | ▤ 平铺]   ← 市场chip + 模式切换
代码 名称 [板块] 币种 评级 Bear Base▼ Bull 当前价 日期 文档
```

（箭头 ▼ 仅出现在当前排序列，上图示意默认按 Base 降序）

- 市场 chip 行右侧新增**分组/平铺**二态切换控件
- **「板块」列**：始终存在于 `<th>`/`<td>` 结构中，分组模式隐藏（`display:none`，板块在组头）、平铺模式显示
- **Bear/Base/Bull 三列**：由「只显示绝对估值」改为 `绝对值 · 边际%`（如 `25.74 · +12.3%`）；边际部分按正负绿/红着色；列头可点、带排序箭头
- 删除原独立「Base安全边际」列
- 当前价 / 日期 / 文档列不可排序，无箭头

### 2. 列头排序交互

- 点 Bear/Base/Bull 列头 → 按对应 `margin_bear/base/bull` 排序；再点同列头切换升↔降；箭头（▲升/▼降）仅在当前排序列渲染
- **默认**：Base 列、降序（保持现有默认行为）
- **None 边际恒末位**：无估值行（bear/base/bull 为 null，如比亚迪）始终沉底，不随升降翻转，沿用现有 `(margin is None, -margin)` 比较语义
- **分组模式**：在每个板块组内重排标的行；组本身顺序不动（仍按标的数降序）
- **平铺模式**：对全表标的行统一重排，无视板块

### 3. 模式切换（分组 ↔ 平铺）

- **分组模式（默认）**：显示板块组头行、隐藏「板块」列；组头可折叠；排序作用于组内
- **平铺模式**：隐藏所有板块组头行（含折叠态一并展开）、显示「板块」列；排序作用于全表
- DOM 重排实现：JS 持有全部 `tr[data-code]` 引用；切平铺时把所有标的行按当前排序键整体排序后顺次 append 进 tbody，组头行 `display:none`；切分组时按 `data-sector` 归位到各自组头之后

### 4. 市场筛选与两模式协作

- 市场 chip 在两模式下都生效（按 `data-market` 显隐行）
- 分组模式下沿用现有逻辑：重算每组可见数、更新组头计数徽章、空组隐藏
- 平铺模式下：仅按市场显隐行，无组头计数
- 市场筛选状态**不持久化**（保持每次默认"全部"），仅排序/分组持久化

### 5. localStorage 持久化

- 键 `valuationsSortPref`，值 `{ sortKey: 'base'|'bear'|'bull', dir: 'asc'|'desc', mode: 'grouped'|'flat' }`
- 页面加载：读取并恢复排序列、箭头、模式（组头/板块列显隐）；无记录或解析失败回退默认 `{base, desc, grouped}`
- 任一排序/模式变更后写回
- 与盯盘页 `WatchStore` 一致的本地持久化思路（参考 `.claude/rules/watch.md`）

### 6. 服务端改动（`app/routes/valuations.py`，最小）

- 每行渲染补 `data-mbear / data-mbase / data-mbull`（把已算的 `margin_bear/base/bull` 输出成属性，无值留空字符串）
- `group_by_sector` 给每行带 `sector_label`（供平铺「板块」列单元格），其余分组/排序逻辑不动
- `index()` 传参不变（仍传 `groups`/`market_counts`/`total`）；平铺有序列表纯前端算，不新增后端数据

### 7. 模板与前端 JS（`app/templates/valuations.html`）

- `<thead>`：Bear/Base/Bull 三 `<th>` 加 `data-sort` 标识、点击绑定 `sortBy(key)`；新增可隐「板块」`<th class="col-sector">`；删「Base安全边际」`<th>`
- 每行新增 `<td class="col-sector">{{ r.sector_label }}</td>`（默认隐藏）；Bear/Base/Bull 单元格改为「绝对值 + 小号边际 span」结构，便于刷新时单独改边际
- 新增 JS：
  - `sortBy(key)`：定排序键/翻升降 → 写 localStorage → `applySort()`
  - `applySort()`：按 mode 在组内或全表重排 DOM、更新列头箭头
  - `setMode(mode)`：切组头/板块列显隐 → 写 localStorage → `applySort()` + `applyMarketFilter()`
  - `restorePref()`：加载时读 localStorage 恢复
  - 扩展 `refreshPrices()`：按 `data-code` 同时刷新三列边际 span 文本+着色（不再只刷单一 margin 列）
  - 保留 `switchMarket`/`applyMarketFilter`/`toggleGroup`（折叠仅分组模式可用）

### 8. 不改动

- `valuations.yaml` 数据结构与字段
- `/api/prices` 接口契约（仍按 stock_code 返回 margin_bear/base/bull，前端消费方式微调）
- `compute_margin` / `_extract_price` / margin 计算口径
- 无新依赖、无 DB 变更、无数据迁移

## 影响面

- **改动文件**：`app/routes/valuations.py`、`app/templates/valuations.html`、`tests/test_valuations.py`
- **无**：新依赖、DB、迁移、其他路由/模板联动

## 验证

- **单测**（`tests/test_valuations.py`）：
  - `group_by_sector` 输出每组每行含 `sector_label`；行携带 `margin_bear/base/bull`（不回归）
  - `compute_margin` / `load_valuations` 行为不变
- **手测**：
  - 点 Bear/Base/Bull 三个列头分别排序，再点切升降，箭头只在当前列
  - 分组 ↔ 平铺切换：组头/「板块」列显隐正确、平铺整表有序、分组组内有序且组顺序不变
  - None 边际行（比亚迪）两模式、升降下恒末位
  - market chip 在两模式下都正确筛选
  - 刷新实时价后三列边际文本与着色同步更新
  - localStorage：调整后刷新页面，排序列/升降/模式自动恢复
