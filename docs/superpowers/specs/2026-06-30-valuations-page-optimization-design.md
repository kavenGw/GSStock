# 估值页优化设计：半导体子类升顶级 + 实时价缓存补取

> 日期：2026-06-30
> 范围：`app/routes/valuations.py`、`app/templates/valuations.html`

## 背景与问题

估值页（`/valuations`，"价值洼地"）当前有两个体验问题：

1. **半导体板块过大（74 只）**：单一顶级板块塞 74 只，子类繁多但都挤在一个折叠组下，浏览困难。
2. **实时价缓存不一致**：首屏 `cache_only=True` 纯读缓存，冷缓存的 HK/US 永远显「—」；手动刷新按钮固定 `force=1` 无条件全量打 API（慢，把刚缓存的 A 股也重取），缺「按 TTL 只刷过期」的中间档与自动补取。

## 现状事实

- 半导体子类分布（按数量）：`materials` 15（实为半导体材料：光刻胶/电子化学品/靶材/石英）、`storage` 12、`design` 9、`power` 6、`equipment` 6、`optical` 4、`wafer` 3、`mcu` 2，其余十余个均为单只。
- 已有两套 carve 机制：`CARVE_OUT_CATEGORIES`（按 DB 分类 carve，如啤酒）、`PROMOTE_MATERIALS_SUBSECTORS`（仅对 `sector=='materials'` 把有色/锂/铜箔升为顶级 flat 板块，其余归「其余材料」桶）。
- 模板 flat 渲染完全由 `g.flat` 驱动：`flat=True` 的组给 lvl2 表头加 `subgroup-flat` 类隐藏，`recompute()` 跳过其重显。
- `/valuations/api/prices` 路由已支持 `force` 参数：`force=request.args.get('force')=='1'`；默认 `force=0` → `get_realtime_prices(codes, force_refresh=False)`，即三层缓存按 TTL（新鲜读缓存、过期/缺失才打 API）。

## 决策

- 拆分机制：**只针对半导体**新增 `PROMOTE_SEMI_SUBSECTORS`，照搬 materials 那套（不做通用化 / 不做阈值自动升级）。
- 升顶级子类：**存储、半导体材料、功率、设备**；**design 不升**，留在「其余半导体」桶。
- 缓存策略：**首屏秒开 + 自动补取冷缓存**（首屏 `cache_only` 不变，前端首屏渲染后自动发一次 `force=0` 后台补取；手动按钮保留 `force=1` 硬刷）。

## 改动一：半导体子类升顶级板块（`app/routes/valuations.py`）

新增配置（与 `PROMOTE_MATERIALS_SUBSECTORS` 并列）：

```python
PROMOTE_SEMI_SUBSECTORS = {'storage': '存储', 'materials': '半导体材料',
                           'power': '功率', 'equipment': '设备'}
SEMI_OTHER_KEY = 'semi-other'
SEMI_OTHER_LABEL = '其余半导体'
```

- **`_top_key`**：在 materials 分支后加对称 semiconductor 分支 —— `sector=='semiconductor'` 时，`subsector ∈ PROMOTE_SEMI_SUBSECTORS` → 返回 `f'semi:{sub}'`（升顶级），否则 → `SEMI_OTHER_KEY`。
- **`_top_label`**：增加 `semi:` 前缀（查 `PROMOTE_SEMI_SUBSECTORS[key[5:]]`）与 `SEMI_OTHER_KEY`（→ `SEMI_OTHER_LABEL`）两个分支。
- **`group_by_sector`** 的 flat 判定：`'flat': key.startswith('mat:')` → `key.startswith(('mat:', 'semi:'))`。

**模板零改动**（flat 渲染由 `g.flat` 驱动）。

### 预期效果

半导体由 1 个顶级板块（74）拆为 5 个：

| 顶级板块 | 数量 | 形态 |
|---------|------|------|
| 半导体材料 | 15 | 扁平顶级（隐藏 lvl2） |
| 存储 | 12 | 扁平顶级 |
| 功率 | 6 | 扁平顶级 |
| 设备 | 6 | 扁平顶级 |
| 其余半导体 | ~35 | 顶级 + 保留 lvl2 子类折叠（design/optical/wafer/mcu/单票） |

已知取舍：design(9) 未升，「其余半导体」桶约 35 只，仍是较大单板块，但内部按二级子类折叠可导航（与「其余材料」同款）。后续如需可只改 `PROMOTE_SEMI_SUBSECTORS` dict 一行把 design 升顶级。

## 改动二：实时价缓存——首屏秒开 + 自动补取冷缓存（`app/templates/valuations.html`）

**后端零改动**（`/api/prices` 已支持 `force=0` 默认按 TTL）。仅改前端 JS：

- `refreshPrices()` → `refreshPrices(force)`；fetch URL 改为 `'/valuations/api/prices' + (force ? '?force=1' : '')`。
- 手动刷新按钮 `onclick` → `refreshPrices(true)`（硬刷，全量重取，保留现状）。
- `initValuations()` 末尾（首屏 `cache_only` 渲染完成后）自动调用 `refreshPrices(false)` —— 后台按 TTL 补取冷缓存的 HK/US、刷新过期项；A 股新鲜则读缓存不重取。
- 状态栏文案区分自动补取（如「自动更新 HH:MM:SS」）与手动硬刷（「已更新 HH:MM:SS」）。

### 预期效果

- 首屏仍 `cache_only` 秒开。
- 冷的 HK/US 不再永远显「—」、无需手点即在首屏后自动填入。
- TTL 内再次访问读缓存不打 API；仅冷/过期项走 API。

## 测试

- **半导体分组**（`app/routes/valuations.py`）：单测 `group_by_sector` —— 喂入含 semiconductor 各子类的 rows，断言 storage/materials/power/equipment 升为独立顶级组且 `flat=True`、label 正确（materials→「半导体材料」），其余 semi 子类归入 `semi-other` 组且 `flat=False`、保留 subgroups。沿用现有 valuations 测试布局（`tests/test_*.py` 平铺）。
- **前端取价**：手动验证首屏 cache_only 秒开 + 首屏后冷 HK/US 自动填入；手动按钮仍硬刷。前端逻辑不强制单测。

## 非目标（YAGNI）

- 不做通用 `PROMOTE_SUBSECTORS`（仅半导体）。
- 不做阈值自动升顶级。
- 不升 design（保留单行可改）。
- 不加定时轮询 / 不加「轻刷」第三档按钮。
- 后端 `/api/prices` 不改。
