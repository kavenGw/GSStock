# 矿产看板页面 `/minerals` — 设计文档

- **日期**：2026-06-24
- **状态**：设计已确认，待写实现计划
- **一句话**：新建一个矿产看板页面，按「铜」「锂」两个板块，各展示期货走势 + 相关股票走势，并用产业链位置标注每只股票对期货价格的影响是正面还是负面。

---

## 1. 背景与目标

现有「走势看板」（`heavy_metals` 路由 / `heavy_metals.html`）已能按分类展示期货 + 股票走势（含铜分类），但：

- 单分类下拉模型，**锂、铜无法同屏并列对比**；
- **没有「股票对期货价格影响正负」的语义**；
- 锂没有独立期货锚，碳酸锂期货未配置。

本页要解决：一屏内并列看「铜」「锂」两大矿产板块，每个板块「期货锚 + 相关股票走势 + 影响正负标注」三位一体。

**影响正负的经济定义**（来自产业分析，非统计相关）：
- **上游资源/矿/锂盐** = 商品卖方 → 期货涨 = 利润涨 = **🟢 正面**（positive）
- **下游加工/铜箔/电池/消费** = 商品买方 → 期货涨 = 成本涨 = **🔴 负面**（negative）

与项目既有约定一致（`docs-conventions.md`：「电池厂是锂买方，锂价涨=成本压力」）。

---

## 2. 范围

### 做
- 新建 `/minerals` 页面（路由 + 模板），不动 `heavy_metals`。
- 股票池来源 = `docs/stock-analytics/valuations.yaml`（与 `/valuations` 同源）。
- 两个板块：**铜**、**锂**。
- 每板块：期货锚走势图 + 相关股票走势 + 影响正负徽章 + 一张「期货 vs 正面股」归一化联动图。
- 给 valuations.yaml 条目 + 对应 doc frontmatter 新增 `commodity` / `commodity_impact` 字段。
- 扩展 `stock-deep-redo` / `buffett` skill，分析时自动产出这两个字段。
- 回填存量 ~12 只锂/铜标的的新字段。

### 不做（YAGNI / 非目标）
- 不算统计相关系数（正负一律来自产业分析）。
- 不动 `heavy_metals` 走势看板。
- 不新建 DB 分类（数据全走 valuations.yaml + frontmatter）。
- 锂/铜之外的矿产（铝/金/钨/银）本期不做，但 `commodity` 字段设计可平滑扩展。

---

## 3. 数据模型：新增两个字段

valuations.yaml 现状：扁平 `list[dict]`，每条有 `sector`（如 `materials`），但 **subsector 只藏在 `source_doc` 路径**（`sectors/materials/nonferrous/...`），且 `nonferrous` 把铜/铝/金/钨/银全混在一起，锂还跨 `materials/lithium` 与 `energy/battery`。**因此光靠 sector + 路径无法把"铜"或"锂"单独拎出来，必须加显式字段。**

新增（写入 valuations.yaml 条目 **与** 对应 buffett doc 的 frontmatter）：

| 字段 | 取值 | 含义 | 缺省行为 |
|---|---|---|---|
| `commodity` | `copper` / `lithium`（未来可加 `aluminum`/`gold`…） | 该标的归属哪个矿产板块 | 无此字段 = 不进矿产页 |
| `commodity_impact` | `positive` / `negative` | 期货价格上涨对该标的的影响方向 | 缺 = 页面显灰色「未标注」徽章，不阻塞 |

- 两个字段都是**可选字段**：linter / 估值页不受影响（valuations.yaml 不被 docs linter 约束；frontmatter 新增字段须在 `scripts/_docs_schema.py` 里登记为可选，避免 lint 报未知字段）。
- `commodity` 与 `sector` 解耦：一只锂电池股 `sector: energy` 仍可 `commodity: lithium`、`commodity_impact: negative`。

### 存量回填清单（本期一次性）

| 板块 | 影响 | 标的 |
|---|---|---|
| copper | positive | 紫金矿业601899、江西铜业00358.HK、云南铜业000878、铜陵有色000630、北方铜业000737、西部矿业601168、盛屯矿业600711、洛阳钼业603993 |
| copper | negative | 铜冠铜箔301217 |
| lithium | positive | 赣锋锂业002460 |
| lithium | negative | 亿纬锂能300014、瑞浦兰钧00666.HK |

> 紫金/洛阳钼业为铜金/铜钴多金属矿，本期按"铜"板块归入（其主要价格弹性来自铜）；以后做金/钴板块时一只标的可能需要多 commodity 归属——设计上 `commodity` 预留为「单值，本期足够」，多归属是明确的未来扩展点，不在本期。

---

## 4. 数据源与期货锚

### 期货锚（已确认口径）
- **铜**：COMEX 铜 `HG=F`（已在 `FUTURES_CODES`，走 yfinance，稳定）。
- **锂**：碳酸锂期货主连（广期所，**当前完全未配置**，yfinance 无对应 ticker）。

### 锂期货数据风险（本设计最大未知，需实现期先 spike）
现有 `FUTURES_CODES` 里的"沪铜/沪金"实为 yfinance 代理（`CU0` 的 `yf_code` = `HG=F`），即系统从不真取 A 股期货。碳酸锂在 yfinance 无对应物，**必须新增 akshare 取数路径**：
- 候选接口：`ak.futures_main_sina(symbol="LC0")`（碳酸锂主连日线）/ `ak.futures_zh_realtime` / `ak.futures_zh_minute_sina`。实现第一步先 spike 确认接口名、返回字段、单位。
- 封装为独立 fetch（不污染 UnifiedStockDataService 的 A/US/HK 三市场语义），失败降级。
- **Fallback**：碳酸锂取数失败 → 用锂矿/锂电指数或 ETF 作代理锚，页面显式标注「碳酸锂期货数据暂缺，当前为代理指数」。

### 股票走势
复用 `UnifiedStockDataService.get_trend_data` / `get_realtime_prices`，与 `/valuations` 同样用 `cache_only=True` 首屏秒开 + `force_refresh` 手动刷新。港股代码（00358.HK / 00666.HK）走 `_fetch_code` 同款 4 位补零归一（参考 `app/routes/valuations.py`）。

---

## 5. 路由与服务

- `app/routes/minerals.py`：`minerals_bp`，注册到 app。
  - `GET /minerals` → 渲染 `minerals.html`（首屏 `cache_only`）。
  - `GET /minerals/api/board/<commodity>` → 返回该板块 JSON：期货锚走势 + 股票列表（含 `commodity_impact`、现价、Base 安全边际、走势序列）。
  - `GET /minerals/api/prices?force=1` → 强刷现价（同 valuations `api_prices` 模式）。
- 板块配置 `MINERAL_BOARDS`（放 `app/config/stock_codes.py` 或新建 `app/config/minerals.py`）：
  ```python
  MINERAL_BOARDS = {
      'copper':  {'name': '铜', 'futures': 'HG=F', 'futures_name': 'COMEX铜'},
      'lithium': {'name': '锂', 'futures': 'LC0',  'futures_name': '碳酸锂主连',
                  'futures_fallback': None},  # 代理ETF/指数代码由实现期 spike 选定后填入
  }
  ```
- 股票池：读 valuations.yaml → 过滤 `commodity in MINERAL_BOARDS` → 按 `commodity` 分板块、板块内按 `commodity_impact`（正面在前）+ Base 安全边际排序。复用 `load_valuations` / `_enrich` / `compute_margin`（考虑从 valuations.py 抽公共函数，避免复制）。

---

## 6. 页面布局（上下堆叠，每板块一行）

```
┌─ 矿产看板 ───────────────────────────── [7d|30d] [刷新] ─┐
│ ▌铜  COMEX铜 HG=F  4.82 ▲+1.2%                            │
│ ┌── 期货走势图（ECharts 折线，全宽）──────────────────┐ │
│ └──────────────────────────────────────────────────────┘ │
│ ┌── 期货 vs 正面股 归一化联动图 ───────────────────────┐ │
│ └──────────────────────────────────────────────────────┘ │
│  相关股票（影响分组，正面在前）                            │
│  🟢正面  紫金矿业601899  ▁▂▃▅  18.2  Base+12% [上游铜矿]  │
│  🟢正面  江西铜业00358   ▁▃▂▄  41.1  Base-56% [上游冶炼]  │
│  🔴负面  铜冠铜箔301217  ▅▃▂▁  ...   Base...  [下游铜箔]  │
│─────────────────────────────────────────────────────────│
│ ▌锂  碳酸锂主连 LC  68,500 ▼-0.8%  (或：代理指数·期货暂缺) │
│  ...（同结构：期货图 + 归一化叠图 + 股票列表）            │
└──────────────────────────────────────────────────────────┘
```

- 每只股票一行：影响徽章 + 名称代码 + 迷你走势 sparkline + 现价 + Base 安全边际（复用 valuations 口径）+ 角色 tooltip。
- 图表库沿用项目既有 ECharts。
- 时间框架切换 7d / 30d（与 heavy_metals 一致）。

---

## 7. 影响可视化

- 🟢 正面 = 绿、🔴 负面 = 红；徽章 + 一句产业链解释文案（hover tooltip，如「上游铜矿，铜价↑→利润↑→正面」）。
- **归一化联动图**（已确认要做）：把期货锚与该板块「正面」股票走势按起点归一化（各序列首值=100）叠在同一张图，直观验证「同涨同跌」（正相关）。负面股可用虚线另叠或省略，避免图过密。

---

## 8. skill 扩展（本期含）

- 扩展 `stock-deep-redo` 与 `buffett` skill 的收尾流程：当标的属于某矿产/商品板块时，由产业分析判定并写入 `commodity` + `commodity_impact` 到 frontmatter 与 valuations.yaml。
- 判定准则写进 skill：上游资源/矿/锂盐 = positive；下游加工/电池/消费 = negative；非矿产标的不写该字段。
- `scripts/_docs_schema.py` 登记两个新可选 frontmatter 字段。

---

## 9. 边界与错误处理

- 锂期货取数失败 → 代理指数 + 页面标注，不报错、不空页。
- 股票缺 `commodity` → 不进矿产页（静默）。
- 股票缺 `commodity_impact` → 灰色「未标注」徽章，列表仍展示。
- 现价缺失（cache miss）→ 前端显「—」，与 valuations 同款防御。
- 港股代码归一化失败 → 跳过该股取价，不挂整页。

---

## 10. 涉及文件清单

| 文件 | 改动 |
|---|---|
| `app/routes/minerals.py` | 新建 Blueprint + 3 个端点 |
| `app/templates/minerals.html` | 新建模板（ECharts + 影响徽章 + 归一化叠图） |
| `app/config/stock_codes.py` 或新建 `app/config/minerals.py` | `MINERAL_BOARDS` 配置 + 碳酸锂 `LC0` 代码 |
| `app/__init__.py` / 路由注册处 | 注册 `minerals_bp` + 导航入口 |
| 数据层（akshare 碳酸锂 fetch） | 新增碳酸锂期货取数 + 降级 |
| `docs/stock-analytics/valuations.yaml` | 回填 ~12 条 `commodity` / `commodity_impact` |
| 对应 ~12 个 buffett doc frontmatter | 同步回填两字段 |
| `scripts/_docs_schema.py` | 登记两个新可选字段 |
| `stock-deep-redo` / `buffett` skill | 收尾流程产出新字段 |

---

## 11. 验收标准

1. 访问 `/minerals` 一屏看到「铜」「锂」两板块，各含期货走势图 + 股票列表 + 归一化叠图。
2. 每只锂/铜股票显示正确的 🟢/🔴 影响徽章（与回填清单一致）。
3. 铜板块期货锚为 COMEX HG=F 实时/历史走势。
4. 锂板块期货锚取到碳酸锂走势；取不到则显代理 + 标注，页面不报错。
5. 现价 / Base 安全边际与 `/valuations` 口径一致。
6. 跑 `stock-deep-redo` 对一只新矿产标的，frontmatter + valuations.yaml 自动带出 `commodity` / `commodity_impact`。
7. `pytest tests/` 通过；docs lint（frontmatter）通过。

---

## 12. 风险

- **锂期货数据源**（最高）：akshare 碳酸锂接口可用性、字段、单位需 spike 确认；最坏退化为代理指数。
- **多金属矿归属**（中）：紫金/洛阳钼业铜金/铜钴双属性，本期按铜单归属，金/钴板块为未来扩展。
- **公共逻辑复用**（低）：valuations.py 的 `load_valuations`/`_enrich`/`_fetch_code` 应抽为共享，避免 minerals 复制漂移。
