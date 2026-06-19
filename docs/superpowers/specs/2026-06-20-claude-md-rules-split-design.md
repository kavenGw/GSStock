# CLAUDE.md 与 rules 精准外科拆分 Design

**Date:** 2026-06-20
**Status:** Approved (design)
**Topic:** 把 163 行杂货铺 `data-architecture.md` 按域拆开，收拢取数坑，独立产业链图谱，改进路由

## 背景

2026-05-15 做过一轮清理（CLAUDE.md 瘦成纯路由、9 个 rule 各守边界、单一权威去重，见 `docs/superpowers/specs/2026-05-15-claude-md-rules-cleanup-design.md`）。之后文件又长回来：`data-architecture.md` 当时压到 ~150，现 163；新增了 A+H 估值校验、产业链 tag 同步等内容。

本轮目标（用户确认）：**拆大文件 + 压缩瘦身 + 改进路由**。不做内容纠错（过时项如 worldcup 临时内容这轮不碰）。

`data-architecture.md` 是唯一痛点文件，混了 4 个域：① DB模型/缓存/统一API/Volume（数据架构核心）② 产业链图谱+tag同步（对应 `app/config/supply_chain.py` + `/supply-chain` 路由）③ 腾讯HTTP/港股/A+H 取数坑（本质"数据源取数坑"，与 `data-fetch-conventions.md` 同域）④ A股行情特征。按需 Read 时被迫吞整文件。

## 方案：精准外科（保留 data-architecture.md 名字，只切走 2 块）

选此方案因其少破坏 skill 引用（文件名不变），并把分散两处的港股/取数坑收拢到一处。

### 目标文件结构（9 → 10）

| 文件 | 行数(前→后) | 动作 |
|------|------|------|
| `CLAUDE.md` | 52→~53 | 路由表更新 3 条 |
| `.claude/rules/data-architecture.md` | 163→~105 | 切走 2 块，留架构核心 |
| `.claude/rules/data-fetch-conventions.md` | 33→~75 | 并入腾讯HTTP/港股/A+H 取数坑 |
| `.claude/rules/supply-chain.md` | **新 ~28** | 产业链图谱 + tag同步 |
| 其余 6 个 rule | 不变 | 仅必要时改路由头 |

> 注：data-fetch-conventions 当前实测 33 行（spec 表用此为准）；移入后约 70–80 行。

## 详细设计

### 1. data-architecture.md — 切走 2 块，保留架构内核

**切走 → supply-chain.md：**
- `产业链图谱约定` 整段（SUPPLY_CHAIN_GRAPHS 配置 / 渲染路由 `/supply-chain/api/<name>` / upstream-midstream-downstream / tag 取值 `frontEC`·`don_buy`·`keep_watching`·`not_analyzed` / 主题型图谱虚拟 slug / 新增图谱零改动 / 跨链复用标注）
- `tag 与分析档同步` 整段

**切走 → data-fetch-conventions.md：**
- `### 腾讯HTTP数据源` 整个子节（实时价格批量 endpoint + 字段索引 `[1]name[3]price…[46]PB`、分钟K线/日K线 endpoint、`[datetime,open,close,high,low,volume]` 字段顺序、XD除息日字段失真、`[41]/[42]` 非除息日失真、只取实时价一次性脚本直连HTTP优先、港股 `q=hk` 字段不同、A+H 标的 H 口径市值自洽校验）

**保留（架构内核）：** JSON安全序列化 / 数据模型 / Stock表约定 / 多账户合并 / OCR流程 / 模块级单例Flask陷阱 / 数据获取失败语义二分 / 新闻推送多分支去重 / 启动数据种子 / 市场识别 / 缓存架构 / Volume单位契约 / A股行情数据特征 / 策略数据协作 / 核心组件 / 统一数据格式 / 调用链路

**架构事实不丢：** `核心组件` 节已写明 "get_realtime_prices A股用腾讯HTTP批量+akshare负载均衡"，架构层已捕获。切走腾讯子节后，在「缓存架构」或「核心组件」附近留一行指针：
> 腾讯 `qt.gtimg.cn` 行情源字段索引 / XD失真 / 港股 `q=hk` 字段 / A+H 市值自洽校验等取数坑见 `data-fetch-conventions.md`。

**路由头更新：** `何时读` 去掉 "产业链图谱"；不再涉及腾讯字段（已由 data-fetch 接管，但 data-architecture 仍管"缓存/市场支持/Volume/OCR/多账户合并"，保留这些触发条件）。

### 2. data-fetch-conventions.md — 接收取数坑

新增一节 `## 腾讯 HTTP 行情源取数坑`，装载从 data-architecture 移入的全部腾讯/港股/A+H 内容，原文照搬（仅去掉与本文件已有内容重复的句子，如无则不删）。

**收益：** 现有 `## yfinance 港股代码格式` 与移入的 `港股 q=hk 字段坑` 并排——所有港股取数坑收拢一处。

**路由头更新：** `何时读` 增加 "腾讯HTTP行情字段 / 港股 q=hk 取数 / A+H 市值自洽校验"。

### 3. supply-chain.md — 新文件（~28 行）

结构：
```
# 产业链图谱与 tag 同步
> **何时读**：改 app/config/supply_chain.py、新增/修改 SUPPLY_CHAIN_GRAPHS 图谱、调 /supply-chain 渲染、回写标的 tag
> **不必读**：数据获取 / 缓存 / 通知 / 纯前端

## 产业链图谱约定   （从 data-architecture 原样移入）
## tag 与分析档同步  （从 data-architecture 原样移入，交叉链到 docs-and-portfolio.md）
```

### 4. 跨引用同步（4 处，断链风险点）

| 文件:行 | 现状措辞 | 改为 |
|---------|---------|------|
| `.claude/skills/stock-deep-redo/SKILL.md`:39 | `data-architecture.md` 港股节 | `data-fetch-conventions.md` |
| `.claude/skills/stock-deep-redo/SKILL.md`:126 | `data-architecture.md`（qt.gtimg.cn/缓存） | `data-fetch-conventions.md`（qt.gtimg.cn 字段坑）+ `data-architecture.md`（缓存） |
| `.claude/skills/stock-deep-redo/references/playbook.md`:126 | `data-architecture.md` 腾讯HTTP节 | `data-fetch-conventions.md` 腾讯HTTP节 |
| `.claude/rules/docs-and-portfolio.md`:89 | `data-architecture.md` 港股节 | `data-fetch-conventions.md` |

**不动：** 历史 plan/spec（`2026-05-15-claude-md-rules-cleanup.md`、`2026-06-04-估值汇总页.md`）指向旧路径，但属 frozen 记录，保持原样。

### 5. CLAUDE.md 路由表更新（3 条）

- `data-architecture.md` 描述：删 "产业链图谱"，保留 "数据/缓存/Volume/A 股特征"
- `data-fetch-conventions.md` 描述：加 "腾讯HTTP/港股字段/A+H"
- 新增条目：`.claude/rules/supply-chain.md` — 产业链图谱 SUPPLY_CHAIN_GRAPHS 配置 + tag同步 — 改 supply_chain.py 或加图谱前

### 6. 压缩说明（避免过度 churn）

本轮"压缩瘦身"主要由**拆分本身**达成（data-architecture 163→~105）。**不**对无关 6 个文件做激进重写，仅在搬运时顺手去掉明显重复句。保证 diff 干净、风险可控。

## 提交策略

搬运是原子的（一处减、一处增、引用同步）。**单个 commit** 一次性落地全部移动 + 4 处引用更新 + CLAUDE.md，避免中间态内容丢失/重复。

`git add <精确路径...> && git commit -F <msg文件>` 同链执行（防并行 session 抢 index，中文 message 走文件防 heredoc 失配）。涉及文件：
```
CLAUDE.md
.claude/rules/data-architecture.md
.claude/rules/data-fetch-conventions.md
.claude/rules/supply-chain.md          (新增)
.claude/rules/docs-and-portfolio.md
.claude/skills/stock-deep-redo/SKILL.md
.claude/skills/stock-deep-redo/references/playbook.md
docs/superpowers/specs/2026-06-20-claude-md-rules-split-design.md  (本 spec)
docs/superpowers/plans/2026-06-20-claude-md-rules-split.md          (plan)
```

## 验证（纯 markdown，无代码改动）

靠 Grep + 行数：

1. **无悬空引用**：Grep 全仓 `\.claude/rules/[a-z-]+\.md`，每个被引路径对应文件存在；`ls .claude/rules/*.md` 应为 10。
2. **跨引用已改**：Grep `data-architecture\.md` 在 4 个目标文件中再无 "港股|腾讯|qt|HTTP" 同行；3 处 skill/docs 引用已指向 data-fetch。
3. **内容唯一归属**：
   - `SUPPLY_CHAIN_GRAPHS` 仅在 supply-chain.md（rules 内）出现
   - `A+H` / `市值自洽校验` 的港股节仅在 data-fetch-conventions.md（rules 内）
   - 腾讯字段索引 `\[46\]PB` 仅在 data-fetch-conventions.md（rules 内）
   - data-architecture.md 内不再含 `SUPPLY_CHAIN_GRAPHS` / `q=hk` / `XD除息`
4. **路由头完整**：每个 rule 文件（含新 supply-chain.md）仍有 `> **何时读**` 行，共 10 命中。
5. **行数区间**：data-architecture ~95–115、data-fetch ~70–85、supply-chain ~24–32、CLAUDE.md ≤ 56。
6. **git 干净**：`git show --stat <sha>` 仅含上述清单文件，未裹挟他人在写档。

## 风险

- **断链**：4 处跨引用必须随移动一并改，否则 skill 运行时指向空内容节。验证步骤 2 强制兜底。
- **内容丢失**：原子单 commit + 验证步骤 3（唯一归属）双保险。
- **并行 session 抢 index**：add+commit 同链、提交后 `git show --stat` 复核。
