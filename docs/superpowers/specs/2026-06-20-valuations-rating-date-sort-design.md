# Claude估值页 评级 / 日期 列排序

## 目标

让 `/valuations`（Claude估值，"价值洼地"）页的**评级**列和**日期**列像 Bear/Base/Bull 列一样支持点表头排序，行为完全一致：升降序切换、▲▼ 箭头、localStorage 记忆偏好、grouped/flat 两模式都生效。

## 现状

`app/templates/valuations.html` 已有数值排序通路：
- Bear/Base/Bull 表头带 `class="sortable" data-sort="..."`，点击走 `sortBy(key)`。
- `marginOf(tr, key)` 读 `tr.dataset['m' + key]`（即 `data-m{key}`）并 `parseFloat`。
- `sortRows` 对 null/空值恒置末位；`updateArrows` 遍历所有 `.sortable` 表头自动渲染箭头。
- `loadPref` 用白名单 `['bear','base','bull']` 校验持久化的 sortKey。

评级列（`core`/`config`/`watch`/`exclude`/`null`）和日期列（`conviction_date`，`YYYY-MM-DD`）当前均不可排序。

## 方案

核心思路：把分类评级与日期都**归一成数字** rank，塞进 `data-m{key}` 属性，复用现有数值排序通路，零新增排序逻辑。

### 后端 `app/routes/valuations.py`

- 新增常量 `RATING_RANK = {'core': 4, 'config': 3, 'watch': 2, 'exclude': 1}`（数字越大优先级越高，对应用户选定顺序 core>config>watch>exclude>null）。`null`/未知 → `None`。
- 新增 `_date_rank(d)`：`str(d or '')` 后去掉 `-` 取前 8 位；若为 8 位纯数字返回 `int(YYYYMMDD)`，否则 `None`。兼容 yaml 解析出的 `datetime.date` 与字符串两种形态。YYYYMMDD 数值大小天然等于时间先后。
- `_enrich()` 每行追加 `'rating_rank': RATING_RANK.get(r.get('rating'))` 和 `'date_rank': _date_rank(r.get('conviction_date'))`。

### 模板 `app/templates/valuations.html`

- `<tr>` 增加 `data-mrating="{{ r.rating_rank if r.rating_rank is not none else '' }}"` 和 `data-mdate="{{ r.date_rank if r.date_rank is not none else '' }}"`。
- 评级 `<th>` 与日期 `<th>` 改为 `class="... sortable" data-sort="rating"/"date" onclick="sortBy('rating')"/sortBy('date')`，各加 `<span class="sort-arrow"></span>`。
- JS `loadPref` 白名单 `['bear','base','bull']` → `['bear','base','bull','rating','date']`。

## 不需要改动

- `sortRows` / `marginOf` / `updateArrows` / `applySort` —— key=`rating`/`date` 时自动读 `data-mrating`/`data-mdate`。
- `refreshPrices` —— 刷新实时价不影响评级/日期，无需更新这两个属性。
- 默认排序保持 `base` 不变。

## 行为预期

- 点「评级」表头：降序 core 在最前，再点切升序；无评级（null）恒末位。
- 点「日期」表头：降序最新在前，升序最早在前；无日期恒末位。
- 箭头、localStorage 记忆、grouped/flat、市场筛选全部自动继承，与 Bear 列一致。

## 范围

无 schema 变更、无新接口、无新依赖。改动 2 个文件：1 个常量 + 1 个函数 + 1 处 enrich（路由），评级/日期两列属性与表头 + 1 处白名单（模板）。
