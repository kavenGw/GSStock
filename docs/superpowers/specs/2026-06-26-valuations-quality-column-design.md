# 估值表新增「质地」列设计

> 日期：2026-06-26
> 范围：`/valuations`（价值洼地）页 —— 在价格相关的安全边际之外，增加一个**抛开当前价格、衡量公司本身好坏**的维度。

## 背景与目标

当前估值表的列为：代码 / 名称 / 板块 / 币种 / 主题 / 评级 / Bear / Base / Bull / 当前价 / 日期。其中 Bear/Base/Bull 及其安全边际全是**价格相关**维度。缺一个价投经典的另一轴——**公司质地（好生意 vs 烂生意），独立于价格便宜与否**。

目标：新增一列「质地」，用 ★1–5 星表达公司好坏，与价格脱钩。

## 关键决策（已与用户确认）

1. **信号来源**：复用现有 `rating` 作为初值，不接财务指标自动算。
2. **拆解方式**：`rating` 仅作初值，另起一个**可覆写**的独立 `quality` 字段（因为 `rating` 是「质地+价格」混合判断，直接当质地会失真）。
3. **刻度**：★ 1–5 星，yaml 存整数。
4. **存储**：存 `valuations.yaml` 可选字段；`sync` 保留不冲掉；渲染缺失时按 `rating` 现算。

## 数据模型

- `docs/stock-analytics/valuations.yaml` 每条新增**可选**字段 `quality`，整数 `1–5`。
- **缺失即现算**：渲染层若条目无 `quality`，按 `rating` 自动推算星级：

  | rating | 推算星级 |
  |--------|---------|
  | core | 5 |
  | config | 4 |
  | watch | 3 |
  | exclude | 2 |
  | （无/未知 rating） | 3（兜底） |

  当前 167 条均有 `rating`，故必有星级。**★1 星保留给手动**标记「质地很差」。映射写成模块级常量 `RATING_TO_QUALITY`，可调。

- **覆写 = 直接改 yaml**：手写 `quality: N`（1–5）即固定该值，不再被 `rating` 推算覆盖。非法值（非 1–5 整数 / 越界 / 非数字）回退到 rating 推算。
- **不批量回填**：不往 167 条物理写星，保持 yaml 干净；只有手动覆写的条目才出现 `quality` 键。

## sync 防冲（关键）

`scripts/sync_valuations.py` 的 `upsert()` 用 buffett 档 frontmatter **整条重建** yaml 条目，当前只显式保留 `note`。

改动：把 `quality` 加进 `upsert()` 的保留逻辑，与 `note` 同款——

```python
for key in ('note', 'quality'):
    if key in e and key not in new_entry:
        new_entry = {**new_entry, key: e[key]}
```

下次 `python scripts/sync_valuations.py [--stock-code X]` 重建条目时，已手写的 `quality` 像 `note` 一样被带过来，不被冲掉。

## 后端

`app/services/valuations_helpers.py`：

- 新增 `RATING_TO_QUALITY = {'core': 5, 'config': 4, 'watch': 3, 'exclude': 2}` 与兜底常量（默认 3）。
- 新增 `resolve_quality(row) -> tuple[int, bool]`：返回 `(stars, derived)`。
  - `row['quality']` 为合法 1–5 整数 → `(值, False)`（手动）。
  - 否则按 `rating` 映射 → `(映射值, True)`（推算）。

`app/routes/valuations.py`：

- `_enrich()` 给每行加 `quality`（最终星级 int）与 `quality_derived`（bool）。
- `/api/prices` **不动**——质地与价格无关，不进价格刷新回包。
- 排序/分组逻辑保持默认按 `margin_base` 降序；质地仅作为可选排序列。

## 前端

`app/templates/valuations.html`：

- 在「评级」列右侧、「Bear」列左侧插入**「质地」列**，显示 `★★★★☆`（实心到 `quality`，其余空心补满 5）。
- **推算 vs 手写视觉区分**：
  - rating 推算（`quality_derived=True`）：星**置灰**（`opacity: .55`）+ `title="由评级推算"`。
  - 手动覆写（`quality_derived=False`）：星**正常色** + `title="手动"`。
  - 一眼看出哪些条目还没人工定过质地。
- 表头可排序：`<th class="sortable" data-sort="quality" onclick="sortBy('quality')">`，行内加 `data-mquality="{{ r.quality }}"`，复用现有 `sortBy` 框架。
- 分组表头 `colspan` 从 12 调整为 13（新增一列）。

## 测试

`tests/test_valuations_quality.py`（或并入现有 valuations 测试）：

- `resolve_quality`：四档 rating 映射正确；yaml 合法 `quality` 覆写优先；非法值（0 / 6 / 'x' / None）回退 rating 推算；缺 rating 走兜底 3。
- `sync_valuations.upsert`：已有 `quality` 的条目被 sync 重建后仍保留 `quality`。
- 路由渲染：含质地列、星级 DOM 正确（沿用现有 valuations 路由测试模式，HTML 测试走 `create_app()`）。

## YAGNI（明确不做）

- 不接 ROE/毛利率等财务指标自动算质地。
- 不批量回填 167 条 yaml。
- 不做质地的历史留痕 / 版本。
- 不在 `/api/prices` 回传质地（非价格相关）。
