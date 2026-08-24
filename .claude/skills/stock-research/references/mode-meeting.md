# 模式 4 · 投资者会议纪要

一份业绩说明会 / 调研 / 投资者交流的 Q&A 或纪要 → 提炼管理层口径对该股旧 thesis 的**增量信息**，
落 `quarterly/<NNqN>/` 点评档并与个股档对称链接。不重算估值，不改评级。

## 何时用 / 何时不用

**用**：输入是单只股票的会议记录（交易所互动平台、公司 IR 纪要、券商整理稿、用户手记）。
**不用**：行业会议 / 多家路演 / 论坛（主体多家）→ 降级模式 3；用户问的是"这会上的口径对其他票有什么影响" → 模式 3；
纪要里含财报数字且用户要点评财报本体 → 模式 2。

## 默认参数

| 维度 | 默认 |
|------|------|
| 产出 | `docs/stock-analytics/quarterly/<NNqN>/YYYY-MM-DD-<股票名>-<会议名>纪要.md`，`doc_type: quarterly`，≤200 行 |
| `period` | 业绩说明会 = 该期财报季度（26Q2 说明会 → `26q2`）；非财报会议 = 召开日所在季度。目录不存在则新建 |
| `date` | 今天 |
| 核实 | 交易所/公司 IR 来源 → 1 家确认；券商整理稿/用户手记 → 交叉 1 家官方或媒体口径，对不上的标「未核实」 |
| 估值 | 不重算；指引变化只写"对 §9 假设的方向性影响"，不给数字 |
| 语言 | 中文 |

## 流程（控制者本人，不派 subagent）

### 1. 核实来源 + 判主体

- 纪要来源分层核实（见默认参数）。区分管理层原话 / 整理者转述 / 提问者观点，后两者不当口径用。
- 主体一家 → 继续；多家 → 降模式 3。

### 2. 读旧档

Glob `docs/stock-analytics/**/*<股票名>*`：
- 文件夹档 → Read `index.md`（frontmatter `thesis` / `rating` / `watch_reason` + §10/§11）与 `thesis.md`；
- 平铺档 → Read 最新 buffett 档的 §0/§6-§8/§11；
- 无档 → 跳过，汇报时提示"该股未建档，深度分析另起模式 1"。

抽三张清单备用：旧 thesis 核心论点（多空各列）、§11 监控指标与硬阈值、`events.md` 里未消化事件。

### 3. 写档

```yaml
---
doc_type: quarterly
stock_code: '<代码，字符串引号>'
stock_name: <股票名>
sector: <sector>
subsector: <subsector>
period: <NNqN>
date: '<YYYY-MM-DD>'
tags:
- <会议名>
related_docs:
  - path: ../../sectors/<sector>/<subsector>/<股票名>/index.md   # 平铺档则指向该 .md
    note: <一句话：口径对旧 thesis 的净效果>
    symmetric: true
---
# <股票名> — <会议名>纪要（<会议日期>）

<!-- BEGIN related_docs (auto-generated from frontmatter, do not edit) -->
<!-- END related_docs -->
```

正文四节，按倒金字塔：
1. **会议要素**：时间 / 形式 / 出席高管 / 来源链接 / 核实结论（含"未核实"项）。
2. **管理层关键口径**（核心）：表格逐条——原话摘要 | 对应旧 thesis 变量或 §11 指标 | `证实 / 动摇 / 无信息` | 置信度。
   只收有增量的口径，客套与重复公告内容不收。数字口径（产能 / 出货 / 毛利指引）写出原话数字与时间窗。
3. **§11 监控指标对账**：旧档每个硬阈值 → 本次口径给出的现状 → 是否触发。
4. **操作含义**：口径对旧 thesis 的净效果一句话；是否建议升模式 1（主论点被动摇）或模式 2（会上披露了完整财报数字）；
   对 `watch_reason` / `exclude_reason` 的影响方向。

### 4. 反向链 + lint

给被链个股档补反向条目（文件夹 → `related.md` frontmatter `related_docs`（结构性引用）；平铺 → 该档 frontmatter），
path 按相对目录算（`sectors/<s>/<ss>/<股票名>/index.md` → `../../../../quarterly/<NNqN>/<档名>.md`），`symmetric: true`。然后：

```bash
python scripts/lint_docs_refs.py --rewrite-blocks
python scripts/lint_docs_frontmatter.py
python scripts/lint_docs_refs.py
```

双 exit 0 后按 `finalize.md` 的并行 session 安全协议提交（`git add <精确路径...> && git commit -F .git/MSG.txt` 同链）。

### 5. 汇报

一句话：核实结论 + 口径对旧 thesis 的净效果 + 触发的 §11 指标 + 是否建议升级模式 1/2 + 档路径与行数 + lint 是否通过。
预估 10-20min。

## 维护规则

流程变化改本文件；频繁出现的纪要来源核实坑可追加到 `lessons.md`（共用编号）并在此引用 `[Ln]`。
