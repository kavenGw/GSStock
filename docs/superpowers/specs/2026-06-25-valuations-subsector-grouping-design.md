# Claude估值页 — 二级板块嵌套分组 设计

- 日期：2026-06-25
- 范围：`/valuations`（Claude估值 / "价值洼地"）页新增二级板块分组
- 状态：已确认，待 writing-plans

## 背景

`/valuations` 页当前数据源 `docs/stock-analytics/valuations.yaml`（162 条），每条有 `sector`（一级，11 枚举）但**无二级板块字段**。二级板块实际藏在 `source_doc` 路径 `sectors/<sector>/<subsector>/...` 中（如 `storage` / `design` / `nonferrous`）。

页面现状：按一级 `sector` 单层分组（可折叠）+ 市场筛选 chips + 边际排序 + 分组/平铺切换 + 排序偏好 localStorage 持久化。

共约 80 个二级 slug，分布碎（半导体下 18 个、约半数仅 1 只股），且为英文 slug、无中文映射，部分 slug 跨一级板块重名（`pcb` 同时在 semiconductor / electronics；`materials` 既是一级又是半导体下二级）。

## 决策汇总

| 维度 | 选定方案 |
|------|---------|
| 呈现形态 | 一级板块组 → 二级板块子组 → 个股行（三层嵌套折叠） |
| 数据来源 | 从 `source_doc` 路径自动提取二级 slug，零维护；无 doc 的归"未分类" |
| 中文标签 | 新增 `SUBSECTOR_LABELS` 映射表，未命中回退原 slug |
| 碎片化 | 忠实全展，每个二级 slug 独立成组（含单例），靠折叠控噪 |

未选方案：加二级列（改动最小但不符"嵌套"语义）、切换分组维度（slug 跨板块重名需消歧，复杂）。

## 改动点

### 1. `app/services/valuations_helpers.py`

新增纯函数：

```python
def subsector_of(row: dict) -> Optional[str]:
    """从 source_doc 路径提取二级 slug。
    路径形如 sectors/<sector>/<subsector>/<file> 时返回 parts[2]，否则 None。"""
    sd = row.get('source_doc') or ''
    parts = sd.split('/')
    if len(parts) >= 4 and parts[0] == 'sectors':
        return parts[2]
    return None
```

### 2. `app/routes/valuations.py`

- 新增 `SUBSECTOR_LABELS` 字典（覆盖现有 ~80 个 slug，见附录），消费处 `SUBSECTOR_LABELS.get(slug, slug)` 兑底。同一 slug 跨板块语义一致（`pcb→PCB`、`networking→网络`、`power-electronics→功率电子`），扁平映射无冲突。
- `_enrich`：每行补 `subsector`（slug，来自 `subsector_of`）+ `subsector_label`。
- `group_by_sector` 改为两级：
  - 一级 key 逻辑不变：`category in CARVE_OUT_CATEGORIES` → 分类名；否则 `sector or '__none__'`。
  - 每个一级桶内再按 `subsector` 分子组，`None → '__none__'`（标签"未分类"）。
  - 每行加稳定复合 id `subgroup_id = f"{sec_key}__{sub_key}"`（防 `pcb` 跨板块碰撞）；复合 id 与 sec_key 都做 DOM-安全处理（仅用作 class/data 属性，CSS 选择器侧用 `CSS.escape`）。
  - 返回结构：
    ```python
    [{'sector': key, 'label': ..., 'count': N,
      'subgroups': [{'key': sub_key, 'subgroup_id': ..., 'label': ..., 'count': m, 'rows': [...]}]}]
    ```
  - 排序：一级按 `count` 降序（key 稳定兜底）；二级组内按 `count` 降序；行内按 Base 边际降序（None 末位）。

### 3. `app/templates/valuations.html`

- 渲染：一级 header 行（colspan，caret，count badge）→ 其下每个二级 header 行（缩进 + caret + count badge）→ 个股行。个股行带 `data-sector="<sec_key>"`、`data-subgroup="<subgroup_id>"`，class 含 `grp-<sec_key>` 与 `sub-<subgroup_id>`。
- JS 两级化：
  - `toggleGroup` 拆为一级/二级：一级折叠隐藏其全部二级 header + 个股行；二级折叠仅隐藏本子组个股行。
  - `applyMarketFilter`：两级重算可见数（更新一级、二级 count badge），可见数为 0 的二级子组、一级组整体隐藏。
  - `applySort`：边际排序键（bear/base/bull）时三层重排——行内排序 → 子组按代表边际排序 → 一级组按代表边际排序；非边际键（rating/date）保持默认序（与现状一致）。
  - `initValuations` 的 `defaultGroupOrder` 扩展为记录一级与二级默认序。
  - **平铺模式（flat）逻辑不变**：无分组，所有行直接排序。
- CSS：二级 header 缩进（如左 padding）、嵌套 caret 复用现有 `.caret` 旋转动画。

## 边界与不变项

- `other` 板块 4 条无 doc → 一级"其他" / 二级"未分类"。
- `啤酒`（CARVE_OUT）仍只影响一级分组；其下二级照常从 doc 取（`beer→啤酒`）。
- `valuations.yaml` 不动（不新增字段）。
- `/api/prices` 接口、刷新逻辑、市场筛选 chips、分组/平铺切换、排序偏好 localStorage 全部保留。
- 个股行的"板块"列（`col-sector`）保留现状显示一级 `sector_label`。

## 测试

纯函数单测（无需 app context，置于 `tests/test_*.py` 平铺）：

- `subsector_of`：正常路径、缺 `source_doc`、路径段不足、非 `sectors/` 开头 → 各自预期。
- `group_by_sector`：两级计数正确、一级/二级/行内三级排序、CARVE_OUT 仍在一级、`subsector=None → 未分类`、跨板块同名 slug（`pcb`）不串组（复合 id 区分）。

HTML 渲染：因 `base.html` 跨 blueprint `url_for` 需 `create_app()`，做一条 smoke（页面 200 + 含二级 header 文案）即可。

## 附录：SUBSECTOR_LABELS（初始覆盖）

```
storage 存储 | design 设计 | equipment 设备 | optical 光学 | power 功率 | mcu MCU
optical-components 光学元件 | wafer 晶圆 | pcb PCB | packaging 封装 | sic-substrate 碳化硅衬底
mems MEMS | photonics 光子 | foundry 晶圆代工 | laser-chip 激光芯片 | networking 网络
advanced-packaging 先进封装 | materials 材料 | components 元器件 | ems EMS | display 显示
servers 服务器 | pc-server PC服务器 | power-electronics 功率电子 | functional-materials 功能材料
display-glass 显示玻璃 | precision-manufacturing 精密制造 | pcb-equipment PCB设备
thermal-management 热管理 | nonferrous 有色 | copper-foil 铜箔 | chemicals 化工
magnetic-materials 磁材 | ceramics 陶瓷 | minor-metals 小金属 | superhard 超硬材料 | lithium 锂
consumer-electronics 消费电子 | sportswear 运动服饰 | beer 啤酒 | home-appliance 家电
mobility 出行 | local-services 本地生活 | restaurant 餐饮 | designer-toy 潮玩 | auto 汽车
furniture 家居 | auto-ev 新能源车 | ev 电动车 | power-equipment 电力设备 | cable 线缆
auto-parts 汽车零部件 | precision-components 精密零件 | cleanroom-epc 洁净室EPC | defense 国防军工
music-streaming 音乐流媒体 | digital-marketing 数字营销 | short-video 短视频
online-literature 网络文学 | shopping-guide 导购 | internet-platform 互联网平台
solar 光伏 | battery 电池 | waste-to-energy 垃圾发电 | cloud 云计算 | software 软件
database 数据库 | exchange 交易所 | securities 证券 | cro CRO
```

未在表中的 slug（后续新增 doc 引入）显示原文，不报错。
