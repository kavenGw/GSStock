# cross-sector buffett 对比档拆分为独立个股档 — 设计

> 日期：2026-06-21
> 类型：文档重组（非重新分析）
> 范围：`docs/stock-analytics/cross-sector/` 下的 6 篇纯 buffett 双标的对比档

## 目标与原则

- **重组而非重析**：忠实拆分对比档内容，不抓新数据、不重做估值、保留原"数据待填入"占位。
- 6 篇 buffett 对比档拆完后**全部删除**。
- 每只标的最终有自己的独立 buffett 档（带 `rating`），可独立维护。
- 删档不留断链：所有反向链接、`valuations.yaml`、related_docs 同步修复。

## 范围内 / 范围外

**范围内（A 类，6 篇 buffett 对比）：**
- `2026-05-08-AMD-Intel-buffett对比分析.md`
- `2026-05-08-立昂微-沪硅产业-buffett对比分析.md`
- `2026-05-08-立讯精密-歌尔股份-buffett对比分析.md`
- `2026-05-28-中兴通讯-思科-buffett对比分析.md`
- `2026-05-29-戴尔-工业富联-buffett对比分析.md`
- `2026-05-31-青岛啤酒-燕京啤酒-buffett对比.md`

**范围外（不动）：**
- B 类相关性/事件专题：`2026-05-06-通富微电-AMD26Q1财报联动专题.md`、`2026-05-09-工业富联-甲骨文-走势相关性专题.md`（两股关系本身即内容，拆开无意义）
- C 类材料对比：`2026-05-26-宏和科技-味之素-AI算力链材料对比.md`
- 不抓行情/财报、不算新估值、不写 valuations 新数字。

## 逐档处理矩阵

| 对比档 | 标的 | 动作 |
|---|---|---|
| AMD-Intel | AMD / Intel | **新建两档**（都无独立档） |
| 立昂微-沪硅产业 | 立昂微 / 沪硅产业 | 立昂微保留既有档；**新建沪硅产业** |
| 立讯-歌尔 | 立讯 / 歌尔 | 立讯保留既有档；**新建歌尔** |
| 中兴-思科 | 中兴 / 思科 | 两者都有既有档，**仅删对比档** |
| 戴尔-富联 | 戴尔 / 富联 | 两者都有既有档，**仅删对比档** |
| 青啤-燕京 | 青啤 / 燕京 | 两者都有既有档，**仅删对比档** |

**关键约束**：已有独立档的标的（多为更新的全量重做）**不做提取**——提取对比档里的薄内容只会覆盖更好的现有档。只有真正缺档的 **4 只（AMD / Intel / 沪硅产业 / 歌尔）** 才从对比档提取建新档。

## 新建 4 档的规格（忠实提取对比档对应栏）

| 标的 | 路径 | conviction_date | rating | reason 字段 |
|---|---|---|---|---|
| 歌尔股份 002241 | `sectors/electronics/ems/2026-05-08-歌尔股份-buffett分析.md` | 2026-05-08 | `exclude` | exclude_reason：护城河已被 22 年丢单证伪，Don't Buy |
| 沪硅产业 688126 | `sectors/semiconductor/wafer/2026-05-08-沪硅产业-buffett分析.md` | 2026-05-08 | `exclude` | exclude_reason：8/9 年扣非为负，2025 毛利率 -17% |
| AMD | `sectors/semiconductor/design/2026-05-08-AMD-buffett分析.md` | 2026-05-08 | `watch` | watch_reason：业务质量 OK，估值无安全边际，回调再看 |
| Intel | `sectors/semiconductor/design/2026-05-08-Intel-buffett分析.md` | 2026-05-08 | `exclude` | exclude_reason：价值陷阱，Foundry 持续负 FCF |

**已拍板判断点：**
- 歌尔归 `electronics/ems`（与对比伙伴立讯一致），非 consumer-electronics。
- AMD 评级 `watch`（业务质量 OK、仅估值贵），其余三只按对比档结论 `exclude`。

**frontmatter 必填**（buffett 类）：`doc_type, stock_code, stock_name, sector, subsector, themes, rating, conviction_date, thesis`。
- `stock_code` 必须字符串引号（`'002241'`、`'688126'`）。
- `thesis` 由对比档该股 Conclusion 提炼为单标的一句话。
- `exclude`→必填 `exclude_reason`；`watch`→必填 `watch_reason`（见上表）。

**正文构成**：
- 对比档中该股**独有**的段落（Business Quality 单栏、专项 Monitoring Indicators、专项 Key Risks）。
- 共用段落（Circle of Competence / Key Assumptions / Owner Earnings 洞察 / Overall Assessment 等）改写为单标的口径，删去对手栏与"两家"措辞。
- 双栏对比表（8 问、Financial Snapshot、Valuation）拆为该股单列；保留原"定性框架，需后续抓数据细化""框架，待数据填入"占位，不补数据。

## 配对互链（保留对比价值）

删除对比档后，每对标的之间加 **symmetric related_docs 互链**，让"曾被对比"的关系仍可导航：
- 立讯 ↔ 歌尔
- AMD ↔ Intel
- 立昂微 ↔ 沪硅产业
- 中兴 ↔ 思科
- 戴尔 ↔ 工业富联
- 青啤 ↔ 燕京

对已有既有档的标的，若原 related_docs 只指向对比档，删档后改为指向配对个股档。

## 断链与 valuations 修复

**valuations.yaml**（6 条 `source_doc` 指向待删对比档，需重指）：

| 行 | stock | 当前 source_doc | 重指到 |
|---|---|---|---|
| ~785 | 燕京 | 青啤-燕京对比 | 既有燕京个股档 |
| ~797 | 歌尔 002241 | 立讯-歌尔对比 | 新建歌尔档 |
| ~855 | 工业富联 601138 | 戴尔-富联对比 | 既有工业富联个股档 |
| ~880 | 沪硅产业 688126 | 立昂微-沪硅对比 | 新建沪硅产业档 |
| ~892 | AMD | AMD-Intel对比 | 新建 AMD 档 |
| ~904 | Intel | AMD-Intel对比 | 新建 Intel 档 |

- 估值数字（bear/base/bull/note）保持原样。
- 重指后按 `stock_code` 去重：若工业富联/燕京已另有指向既有个股档的条目，保留权威档那条，删冗余。

**反向链接清理**：从所有引用 6 篇对比档的文档移除指向对比档的 related_docs 条目。已知引用方：
- 立昂微-沪硅对比：`sectors/semiconductor/wafer/.../立昂微`、`themes/2026-06-19-立昂微涨价-硅基功率链影响.md`
- 立讯-歌尔对比：`quarterly/26q1/.../立讯精密-汽车线束二曲线专题.md`、`sectors/electronics/ems/.../工业富联`、`sectors/electronics/ems/.../立讯精密`、`sectors/semiconductor/optical/.../源杰科技`
- 中兴-思科对比：`sectors/electronics/networking/.../思科`、`.../中兴通讯`
- 戴尔-富联对比：`sectors/electronics/ems/.../工业富联`、`sectors/electronics/servers/.../戴尔科技`、`themes/2026-05-29-Rubin-VR200-BOM拆解-价值分配.md`
- 青啤-燕京对比：`quarterly/26q1/.../燕京啤酒-26Q1季报点评.md`、`sectors/consumer/beer/.../燕京啤酒`、`sectors/consumer/beer/.../青岛啤酒`

> related_docs 块由 `<!-- BEGIN/END related_docs -->` 自动生成，只改 frontmatter 的 `related_docs:`，不手编块体。

## 校验与提交

1. `PYTHONIOENCODING=utf-8 python scripts/lint_docs_frontmatter.py` → exit 0
2. `PYTHONIOENCODING=utf-8 python scripts/lint_docs_refs.py` → exit 0（含反向对称）
3. `python scripts/lint_docs_refs.py --rewrite-blocks` 重生块后，**只精确 `git add` 本任务涉及的档**，勿 `git add -A`（避免裹挟并行 session 半成品）。
4. `git add` 与 `git commit` 同一条命令链（防并行 session 抢 index）；删档用 `git rm`。

## YAGNI（明确不做）

- 不抓行情/财报、不算新估值、不写 valuations 新数字。
- 不碰 B 类相关性专题、C 类材料对比。
- supply_chain tag 不动（评级态未实质变化）。
