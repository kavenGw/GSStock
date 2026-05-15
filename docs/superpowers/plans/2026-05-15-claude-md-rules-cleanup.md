# CLAUDE.md 与 rule 整理 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 CLAUDE.md 硬约束区下沉到对应 rule 文件，去重 / 压缩 / 删过时，CLAUDE.md 瘦身为纯路由。

**Architecture:** 单一权威原则 —— 每条规则只在 1 处保留完整版。CLAUDE.md 只留每会话通用约定 + Rules 路由表。rule 文件保留现有 9 个边界，逐文件做"删/合/补"三类编辑。

**Tech Stack:** 纯 markdown 编辑，无代码改动。所有验证靠 sqlite3 / Grep / wc -l。

**Spec:** `docs/superpowers/specs/2026-05-15-claude-md-rules-cleanup-design.md`

---

## 文件结构

| 文件 | 操作类型 | 预估行数变化 |
|---|---|---:|
| `CLAUDE.md` | 重写 | 63 → ~35 |
| `.claude/rules/data-architecture.md` | 删合补 | 198 → ~150 |
| `.claude/rules/dev-conventions.md` | 删合 | 85 → ~75 |
| `.claude/rules/news-and-research.md` | 合 | 75 → ~70 |
| `.claude/rules/esports.md` | 条件删 | 24 → 23 或 24 |
| `.claude/rules/data-fetch-conventions.md` | 不动 | 26 |
| `.claude/rules/docs-and-portfolio.md` | 不动 | 28 |
| `.claude/rules/llm.md` | 不动 | 15 |
| `.claude/rules/notification-formatting.md` | 不动 | 66 |
| `.claude/rules/watch.md` | 不动 | 23 |

---

### Task 1: 数据收集 spot-grep 验证

为后续任务做决策提供事实依据。一次跑完，结果记入本任务的对话备注。

**Files:** 无修改

- [ ] **Step 1: 查 Stock 表记录数**

Run:
```bash
PYTHONIOENCODING=utf-8 python -c "import sqlite3; c=sqlite3.connect('data/stock.db').cursor(); c.execute('SELECT COUNT(*) FROM stocks'); print('STOCKS_COUNT=', c.fetchone()[0])"
```
Expected: 输出 `STOCKS_COUNT= <N>`，N 为整数。  
决策规则：
- N ≤ 80 → data-architecture.md 保留 "~50 条" 改为 "~{N//10*10} 条"
- N > 80 → 改为 "用户关注池（远小于全 A 股）"，删去具体数字

- [ ] **Step 2: 查 NBA 18:00 调度**

Run（用 Grep 工具）:
```
Grep pattern="0 18 \\* \\* \\*|hour=18|nba.*18|18.*nba" path="app/" -i output_mode="content" -n
```
决策规则：
- 命中含 `nba` / `esports_daily` 的 cron 行 → esports.md 保留该条
- 无命中 → esports.md 删除「NBA晚间调度：每天18:00额外执行一次NBA监控设置，覆盖当晚比赛」整行

- [ ] **Step 3: 验证 data-architecture.md 当前 ASCII 调用链路位置**

Run（用 Grep 工具）:
```
Grep pattern="^### 调用链路$" path=".claude/rules/data-architecture.md" -n
```
Expected: 输出行号 N。该任务记录的 N 用于 Task 3 Step 删除区间起点。

- [ ] **Step 4: 验证 portfolio-shortlist spec 仍存在（spec 已 verify，此处复核）**

Run:
```bash
ls docs/superpowers/specs/2026-05-10-portfolio-shortlist-design.md
```
Expected: 路径存在。不存在则 docs-and-portfolio.md 那段引用需改。

- [ ] **Step 5: 把 4 个决策结果写入下方备注**

在本任务后写一条 `## 决策记录` 短笔记，列出 N（stocks 数）/ NBA cron 是否存在 / 调用链路起始行号 / spec 是否存在。后续任务读这条备注。

无 commit（数据收集任务）。

---

### Task 2: 重写 CLAUDE.md

将硬约束区整段删除，仅保留 #1 #2 通用约定；保留启动命令、Rules 索引、graphify 区。

**Files:**
- Modify: `CLAUDE.md` (整体重写)

- [ ] **Step 1: 写入新版 CLAUDE.md**

用 Write 工具覆写。内容：

```markdown
# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

个人股票管理工具（Flask + SQLAlchemy + SQLite + akshare/yfinance + 智谱GLM/Gemini + APScheduler）。
管理多个证券账户的持仓情况，支持上传持仓截图自动识别、多账户合并、操作建议记录。
访问地址：http://127.0.0.1:5000

**通用约定**：响应中文；不写多余注释；不写 backup 文件（git 留痕足够）；所有 git/cargo/npm/pytest 命令前加 `rtk`，链式 `&&` 中也要。

## 常用命令

```bash
# 启动应用
python run.py
# 一键启动（启动并打开浏览器）
start.bat
# Linux 部署（拉取代码 + 更新依赖 + 重启）
./update_and_run.sh
# 安装依赖
pip install -r requirements.txt
# 单测（禁用调度器 + UTF-8 编码）
rtk PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 python -m pytest tests/ -v
# 只读 DB 巡检（不走 create_app —— 会启 17 任务 + crawl4ai + LLM）
PYTHONIOENCODING=utf-8 python -c "import sqlite3; c=sqlite3.connect('data/stock.db').cursor(); c.execute('SELECT ...'); ..."
```

## Rules（按需 Read，路径用反引号、不用 @ 触发自动 import）

- `.claude/rules/data-architecture.md` — 数据/缓存/Volume/A 股特征/产业链图谱 — 改 services/ 或写 SQL 前
- `.claude/rules/notification-formatting.md` — Slack 频道/盯盘告警 7 类格式/排版规范 — 改推送前
- `.claude/rules/news-and-research.md` — 新闻/公司/华尔街/野村/博客/Trending/Release 配置 — 调轮询或加新源前
- `.claude/rules/esports.md` — NBA/LoL 推送 + 失败重试队列 — 改 esports_service.py 前
- `.claude/rules/watch.md` — 盯盘前端架构 + AI 分析调度（realtime/7d/30d）— 改 watch 模块前
- `.claude/rules/llm.md` — 智谱/Gemini/llama-server 环境变量 — 改 llm/ 前
- `.claude/rules/data-fetch-conventions.md` — akshare/PDF/股票名查询坑 — 写新数据脚本前
- `.claude/rules/docs-and-portfolio.md` — docs 命名 + frontmatter + portfolio skill — 写分析或调 portfolio 前
- `.claude/rules/dev-conventions.md` — 技术栈/双 DB/测试布局/commit 协议/第三方仓库监控 — 改 schema 或提 commit 前

## graphify

This project has a graphify knowledge graph at graphify-out/.

Rules:
- Before answering architecture or codebase questions, read graphify-out/GRAPH_REPORT.md for god nodes and community structure
- If graphify-out/wiki/index.md exists, navigate it instead of reading raw files
- After modifying code files in this session, run `python3 -c "from graphify.watch import _rebuild_code; from pathlib import Path; _rebuild_code(Path('.'))"` to keep the graph current
- Top god nodes are minified vendor bundles (echarts.min.js / chart.umd.min.js — `E()`, `T()`, `js()` etc.); skip them. Real architectural cores are `Stock`, `MarketIdentifier`, `UnifiedStockCache`, `UnifiedStockDataService`.
```

- [ ] **Step 2: 验证行数**

Run:
```bash
wc -l CLAUDE.md
```
Expected: 35-45 行（含空行）。如 > 50 行，检查是否有多余内容。

- [ ] **Step 3: 验证无硬约束残留关键字**

Run（用 Grep）:
```
Grep pattern="硬约束|VOLUME_UNIT_SCHEMA_VERSION|__bind_key__|has_app_context|stock_name LIKE|rev-parse HEAD" path="CLAUDE.md"
```
Expected: 无输出（全部不应出现在新 CLAUDE.md）。

- [ ] **Step 4: Commit**

```bash
rtk git add CLAUDE.md
rtk git commit -m "docs(claude-md): 硬约束区下沉到 rule，CLAUDE.md 瘦身为纯路由"
```

---

### Task 3: 改 data-architecture.md（删调用链路 + 补缓存时区 + 合并单例声明）

**Files:**
- Modify: `.claude/rules/data-architecture.md`

- [ ] **Step 1: 删除"服务层模式"整段**

用 Edit 工具删除以下内容：
```
**服务层模式**：业务逻辑放在 `services/`，路由保持简洁
```
（替换为空字符串；前后的空行也删一行）

- [ ] **Step 2: 删除调用链路 ASCII 树**

用 Edit 工具，old_string 为从 `### 调用链路\n\n所有服务统一通过 UnifiedStockDataService 获取数据：\n\n` 开始到 `TDSequentialService.calculate()\n    ← watch.py chart-data 接口调用（复用60日趋势数据）\n` 的整段（约 35 行 ASCII 树 + 标题）。

new_string 替换为：
```
### 调用链路

所有持仓 / 期货 / 盯盘 / 预加载 / 季报 / TD九转服务统一走 `UnifiedStockDataService` 的 `get_trend_data` / `get_realtime_prices` / `get_indices_data` / `get_intraday_data` 入口，缓存命中率与 force_refresh 语义由该服务统一裁决。`WatchAnalysisService` 是聚合层（不直连数据源），其余服务均直接消费 unified 入口。
```

- [ ] **Step 3: 合并 UnifiedStockDataService 单例声明**

Grep 文件内 `单例模式` 出现次数：
```
Grep pattern="单例模式" path=".claude/rules/data-architecture.md" -n
```
若 2 次出现，保留 `### 核心组件` 章节首个 `- **UnifiedStockDataService** - 统一数据获取入口（单例模式）` 不动，删除其他重复。

- [ ] **Step 4: 补"禁用 date.today()"明示警告**

在「缓存架构」章节末尾（"季度财报 quarterly_earnings 7天" 表格之后、"Volume 单位契约" 之前）补一段：

```markdown
**缓存日期统一走 SmartCacheStrategy**：所有缓存 lookup/save 用 `SmartCacheStrategy.get_effective_cache_date(code)` 替代 `date.today()`；批量场景用 `_get_effective_cache_dates(codes)` 按市场分组。理由：处理跨市场时区错位（A 股 vs 美股），让缓存"今日"语义跟随该股票所属市场的有效交易日。API 查询日期范围（start_date/end_date）仍用 `date.today()`，API 自动截断。
```

- [ ] **Step 5: 处理 Stock 表数字**

根据 Task 1 决策记录：
- 若 N ≤ 80：Edit `~50 条` 为 `~{N//10*10} 条`
- 若 N > 80：Edit `~50 条` 为 `远小于全 A 股`，移除括号

old_string: `；库只存用户关注池（~50 条），不是全 A 股`  
new_string（举 N>80 例）: `；库只存用户关注池（远小于全 A 股），不是全市场快照`

- [ ] **Step 6: 验证行数**

Run:
```bash
wc -l .claude/rules/data-architecture.md
```
Expected: 130-165 行。

- [ ] **Step 7: 验证关键内容未误删**

Run（用 Grep）:
```
Grep pattern="VOLUME_UNIT_SCHEMA_VERSION|腾讯HTTP|MarketIdentifier|cache_type|data_json|节假日" path=".claude/rules/data-architecture.md" -c
```
Expected: 至少 6 行命中（每个关键词 ≥1 次）。

- [ ] **Step 8: Commit**

```bash
rtk git add .claude/rules/data-architecture.md
rtk git commit -m "docs(rule): data-architecture 压缩调用链路 + 补缓存时区明示警告"
```

---

### Task 4: 改 dev-conventions.md（删测试命令重复 + 压缩技术栈）

**Files:**
- Modify: `.claude/rules/dev-conventions.md`

- [ ] **Step 1: 压缩技术栈列表**

Edit old_string:
```
## 技术栈

- Flask + SQLAlchemy + SQLite
- RapidOCR (ONNX Runtime)
- Bootstrap 5 + 原生 JavaScript
- akshare（A股数据）+ yfinance（美股/港股/期货数据）+ Twelve Data + Polygon
- 智谱 GLM（LITE 层免费 glm-4-flash）+ Google Gemini（FLASH/PREMIUM 层主力）
- APScheduler（策略调度）
- PyTorch（AI走势预测，可选）— `app/ml/` 模块，未安装 torch 时自动跳过
```

new_string:
```
## 技术栈

Flask + SQLAlchemy + SQLite + RapidOCR(ONNX) + Bootstrap5 + 原生 JS。数据：akshare（A股）+ yfinance（美股/港股/期货）+ Twelve Data + Polygon。LLM：智谱 GLM（LITE 免费 glm-4-flash）+ Google Gemini（FLASH/PREMIUM 主力）。调度：APScheduler。可选 PyTorch（`app/ml/` AI 走势预测，未安装自动跳过）。
```

- [ ] **Step 2: 压缩股票代码配置常量罗列**

Edit old_string:
```
**配置项**：
- `FUTURES_CODES` - 期货代码映射（yfinance格式）
- `INDEX_CODES` - 指数代码映射
- `CATEGORY_CODES` - 分类代码列表
- `CATEGORY_NAMES` - 分类显示名称
```

new_string:
```
**配置项**：期货 / 指数 / 分类代码常量见 `app/config/stock_codes.py`（`FUTURES_CODES` / `INDEX_CODES` / `CATEGORY_CODES` / `CATEGORY_NAMES`）。
```

- [ ] **Step 3: 删除"运行单测"重复区块**

Edit old_string:
```
**运行单测**（禁用调度器 + UTF-8 编码）：

```bash
PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 python -m pytest tests/ -v
```

```

new_string: 空字符串（连带前后一个空行）。

理由：与 CLAUDE.md "常用命令" 区重复。

- [ ] **Step 4: 验证行数**

Run:
```bash
wc -l .claude/rules/dev-conventions.md
```
Expected: 60-80 行。

- [ ] **Step 5: 验证关键内容未误删**

Run（用 Grep）:
```
Grep pattern="commit --amend|rev-parse HEAD|GITHUB_RELEASE_REPOS|create_app|heredoc|cp950" path=".claude/rules/dev-conventions.md" -c
```
Expected: ≥6 行命中。

- [ ] **Step 6: Commit**

```bash
rtk git add .claude/rules/dev-conventions.md
rtk git commit -m "docs(rule): dev-conventions 压缩技术栈/股票代码常量罗列，删测试命令重复"
```

---

### Task 5: 改 news-and-research.md（压缩动态发现实现细节）

**Files:**
- Modify: `.claude/rules/news-and-research.md`

- [ ] **Step 1: 压缩 plugin discovery 实现细节**

Edit old_string:
```
动态发现逻辑（`app/services/plugin_discovery.py`）：
- 读取 `$CLAUDE_PLUGINS_DIR/installed_plugins.json` 提取已装插件所属的 marketplace 名
- 在 `known_marketplaces.json` 查每个 marketplace 的 `source`，支持 `{source: 'github', repo: ...}` 和 `{source: 'git', url: 'https://github.com/.../.git'}`
- 非 github.com 源、目录不存在、JSON 损坏均安全降级为空列表（只用静态配置）
- 动态条目 `key` 统一加 `marketplace_` 前缀避免与静态 key 冲突
```

new_string:
```
动态发现逻辑见 `app/services/plugin_discovery.py`：读 `$CLAUDE_PLUGINS_DIR/installed_plugins.json` → 查 marketplace `source`（支持 github/git 两种）→ 动态条目 `key` 加 `marketplace_` 前缀避免冲突。非 github 源 / 目录缺失 / JSON 损坏均静默降级为空列表（只用静态配置）。
```

- [ ] **Step 2: 验证行数**

Run:
```bash
wc -l .claude/rules/news-and-research.md
```
Expected: 65-72 行。

- [ ] **Step 3: 验证关键内容未误删**

Run（用 Grep）:
```
Grep pattern="GITHUB_RELEASE_REPOS|NOMURA|WALLSTREET|BLOG_MONITOR|GITHUB_TRENDING|smoke test" path=".claude/rules/news-and-research.md" -c
```
Expected: ≥5 行命中。

- [ ] **Step 4: Commit**

```bash
rtk git add .claude/rules/news-and-research.md
rtk git commit -m "docs(rule): news-and-research 压缩 plugin_discovery 实现细节"
```

---

### Task 6: 条件改 esports.md（按 Task 1 决策）

**Files:**
- Modify: `.claude/rules/esports.md`（条件性）

- [ ] **Step 1: 根据 Task 1 决策记录处理**

若 Task 1 Step 2 结果显示**无 NBA 18:00 cron 命中**：

Edit old_string:
```
- 比赛结束：自动检测并推送最终比分
- NBA晚间调度：每天18:00额外执行一次NBA监控设置，覆盖当晚比赛
- 失败重试：单联赛
```

new_string:
```
- 比赛结束：自动检测并推送最终比分
- 失败重试：单联赛
```

若有命中 → 跳过本任务。

- [ ] **Step 2: 验证行数**

Run:
```bash
wc -l .claude/rules/esports.md
```
Expected: 22-25 行。

- [ ] **Step 3: Commit（仅当 Step 1 实际修改时）**

```bash
rtk git add .claude/rules/esports.md
rtk git commit -m "docs(rule): esports 删除已失效的 NBA 18:00 调度描述"
```

---

### Task 7: 最终全局校验

**Files:** 无修改

- [ ] **Step 1: 验证总行数变化**

Run:
```bash
wc -l CLAUDE.md .claude/rules/*.md
```
Expected: 总计 430-470 行（spec 预估 ~443）。

- [ ] **Step 2: 校验 CLAUDE.md 没引用不存在的 rule**

Run（用 Grep）:
```
Grep pattern="\\.claude/rules/[a-z-]+\\.md" path="CLAUDE.md" output_mode="content" -o
```
Expected: 9 行输出，每行一个 rule 路径。

逐路径核对存在（已有 9 个文件，无新增/删除）：
```bash
ls .claude/rules/*.md | wc -l
```
Expected: `9`。

- [ ] **Step 3: 校验各 rule 文件「何时读 / 不必读」头存在**

Run（用 Grep）:
```
Grep pattern="^> \\*\\*何时读" path=".claude/rules/" glob="*.md" -l
```
Expected: 9 个文件均命中（未误删格式）。

- [ ] **Step 4: 校验 git log 干净**

Run:
```bash
rtk git log --oneline -10
```
Expected: 看到 6 个新 commit（docs(claude-md) + 5 个 docs(rule)，其中 esports 视决策可能没有），无意外文件。

Run:
```bash
rtk git status
```
Expected: working tree clean。

- [ ] **Step 5: 收尾报告**

写一段总结，含：
- CLAUDE.md 实际行数
- 各 rule 实际行数变化（before/after 对照）
- 总行数节省
- Task 1 决策结果
- 哪些 spot-grep 命中 / 未命中

无 commit。

---

## Self-Review 记录

**Spec coverage**:
- §1 目标态结构 → Task 2
- §2 硬约束 10 条下沉映射 → Task 2 (#1 #2 保留)，Task 3-6 (#3-#10 在各 rule 已有，无需补；#5 缓存时区在 Task 3 Step 4 补)
- §3 各 rule 清理 → Task 3-6
- §4 验证步骤 → Task 1 + Task 7
- §5 行数预估 → Task 7 Step 1
- §7 风险（覆盖度不够）→ Task 3 Step 4（仅 #5 实际需要补）

**Placeholder scan**: 无 TBD/TODO；每个 Edit 都有具体 old/new；每个 Run 都有 expected。

**Type consistency**: 文件路径 `.claude/rules/*.md` 全程一致；commit 信息前缀 `docs(rule):` / `docs(claude-md):` 一致。
