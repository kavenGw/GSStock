# 估值汇总页板块分组优化 — 设计文档

> 日期：2026-06-05
> 范围：`/valuations` 估值汇总页，由「市场 Tab + 122 行平铺大表」改造为「板块为主轴的分组视图 + 市场筛选器」

## 背景与痛点

当前 `/valuations` 页（`app/routes/valuations.py` + `app/templates/valuations.html`）：

- 数据源 `docs/stock-analytics/valuations.yaml`，122 条记录，含字段 `sector`（10 个一级板块）、`rating`（config/watch/exclude/core/空）、`market`、bear/base/bull、`conviction_date`、`source_doc`
- 仅按**市场**分 Tab（全部/A/港/美），下面一张大平铺表按 Base 安全边际降序
- 痛点：122 行单表，板块和评级只是普通列、不能分组也不能筛选；板块分布极不均（半导体 45、电子 19、材料 15、消费 14…），同板块标的散落在大表各处，无法横向对比

## 设计决策（已与用户确认）

1. **分类形态**：按板块（sector）分组展示
2. **主轴**：板块为主轴，市场降为筛选器
3. **组头与排序**：组头显示「名称 + 数量」，组之间按标的数降序；组内仍按 Base 安全边际降序
4. **评级处理**：全部显示，`exclude` 行置灰弱化（不加评级筛选）
5. **折叠**：板块组头可折叠（用户确认要加，收纳半导体等大组）
6. **组头名称**：英→中映射（用户确认要加）

## 实现路径

**服务端分组渲染 + 客户端市场筛选**（已选）：

- 路由层 `_enrich` 计算 margin 后，按 sector 分组 → 组按标的数降序 → 组内按 Base 安全边际降序（None 末位）→ 传给模板渲染成「板块组头 + 组内行」DOM
- 市场筛选纯客户端：chip 切换行可见性 + 动态更新组头计数 + 隐藏空组，不重新请求后端
- 复用现有 `/api/prices`（仍按 stock_code 更新单元格，分组结构不影响刷新）

**否决备选**：纯客户端渲染（路由回平铺数据、JS 负责分组排序）——市场筛选时重算更灵活，但要重写整段渲染 JS，复杂度不划算。

## 详细设计

### 1. 页面结构

```
估值汇总                                    [🔄 刷新实时价]
[全部 122] [A股 94] [港股 18] [美股 10]   ← 市场筛选 chip（单选，由原 Tab 改造）

▼ 半导体 (45)        ← 板块组头，可点击折叠
  代码 名称 币种 评级 Bear Base Bull 当前价 Base安全边际 日期 文档
  ...45 行，按 Base 安全边际降序，exclude 行置灰...
▼ 电子 (19)
  ...
（组按标的数降序：半导体45 → 电子19 → 材料15 → 消费14 → 其他8 → 工业7 → 媒体6 → AI应用4 → 能源3 → 医疗1）
```

### 2. 路由层（`app/routes/valuations.py`）

- 新增 `SECTOR_LABELS` 字典：英文 enum → 中文名（覆盖 docs 11 个一级 sector）
  - `semiconductor→半导体`、`electronics→电子`、`consumer→消费`、`materials→材料`、`energy→能源`、`healthcare→医疗`、`media→媒体`、`financial→金融`、`industrial→工业`、`ai-application→AI应用`、`other→其他`
  - 无映射时回退原始 sector 值；`sector` 为空归入一个「未分类」组
- 新增分组函数：输入 enriched rows，输出有序 `list[dict]`，每组形如
  ```python
  {'sector': 'semiconductor', 'label': '半导体', 'count': 45, 'rows': [...]}
  ```
  - 组排序：`count` 降序（并列时按 sector 名稳定排序）
  - 组内排序：沿用现有 `_enrich` 的 `(margin_base is None, -margin_base)` 规则
- `index()` 改为传 `groups`（替代 `rows`），保留 `market_counts`、`total`

### 3. 模板（`app/templates/valuations.html`）

- 市场 Tab 改造为筛选 chip 行（单选）：`全部/A股/港股/美股`，沿用 `market_counts` 显示数量
- 表格按 `groups` 渲染：每组先输出一个组头行（`<tr class="group-header">` 或独立 thead），含折叠箭头 + 中文名 + 计数徽章；随后输出该组的标的行
- 组内行去掉「板块」列（已在组头），其余列与字段不变；行保留 `data-code`、`data-market`、`data-sector`
- `rating=='exclude'` 的行加 `.row-muted` 类（淡灰文字）

### 4. 前端 JS

- `switchMarket(market)`：遍历所有标的行按 `data-market` 显隐 → 每组重算可见行数、更新组头计数徽章、可见数为 0 的整组隐藏
- `toggleGroup(sector)`：点组头折叠/展开该组标的行
- `refreshPrices()`：保持不变（按 `data-code` 更新 `.cell-price` / `.cell-margin`）

### 5. 不改动

- `valuations.yaml` 数据结构与字段
- `/api/prices` 接口契约
- margin 计算逻辑（`compute_margin` / `_extract_price`）

## 影响面

- **改动文件**：`app/routes/valuations.py`、`app/templates/valuations.html`
- **无**：新依赖、DB 变更、数据迁移、其他路由/模板联动

## 验证

- 启动后访问 `/valuations`：确认按板块分组、组按标的数降序、组内按 Base 安全边际降序
- 点市场 chip：确认行过滤、组头计数更新、空组隐藏
- 点组头：确认折叠/展开
- 点刷新实时价：确认价格与安全边际单元格正常更新
- `exclude` 行确认置灰
- 单测层：`load_valuations` / `compute_margin` 既有行为不回归；新增分组函数可加轻量单测（组排序 + 组内排序）
