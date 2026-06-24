# CLAUDE.md rules 重构 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `.claude/rules/` 三个混轴超载文件按 task-trigger 轴拆成 12 个聚焦文件，消除跨文件重复，同步 CLAUDE.md 路由表与外部深链。

**Architecture:** 纯内容搬迁，无代码改动。每个任务把源文件的指定 `##`/`###` 小节**逐字搬运**到目标文件，源文件相应小节删除；重复内容收敛到唯一源 + `> 见 X` 指针。验证靠 grep 结构校验，非 pytest。

**Tech Stack:** Markdown 文件操作（Write/Edit）；`rtk git` 提交；grep 校验。

## Global Constraints

- 设计依据：`docs/superpowers/specs/2026-06-24-claude-md-rules-重构-design.md`（内容归属/唯一源/外部引用三张表为权威核对表）
- 搬运 = **逐字保留**正文，只改所在文件，不改写措辞（完善仅限新增 header / cross-ref 指针）
- 不发明新规则
- 所有 git 命令加 `rtk`；`git add` 与 `git commit` 必须**同一条命令链**，用精确路径不用 `-A`（并行 session 抢 index 防护）
- 中文多行 commit message 走 `git commit -F - <<'EOF'` heredoc，避免引号失配
- 源文件删除用 `rtk git rm -q .claude/rules/<旧文件>`（与 add/commit 同链）
- 每个任务结束跑该任务的校验 grep，确认通过再 commit

---

## File Structure

新建：`stock-data-cache.md` / `stock-data-model.md` / `notifications.md` / `docs-conventions.md` / `portfolio-valuations.md` / `dev-environment.md`
删除：`data-architecture.md` / `dev-conventions.md` / `docs-and-portfolio.md` / `notification-formatting.md`
保名改内容：`data-fetch-conventions.md` / `news-and-research.md` / `llm.md` / `esports.md` / `watch.md` / `supply-chain.md`
改：`CLAUDE.md`、`.claude/skills/stock-deep-redo/SKILL.md`、两个历史档

**搬迁依赖顺序**（源文件只在内容全部迁出后才删）：
- `data-architecture.md` → 被 Task 1/2/3 消费 → Task 3 末删
- `dev-conventions.md` → 被 Task 2/4 + CLAUDE.md(Task 9) 消费 → Task 4 末删（技术栈已先并入 CLAUDE.md）
- `docs-and-portfolio.md` → 被 Task 5/6 消费 → Task 6 末删

---

## Task 1: stock-data-cache.md（数据架构/缓存主干）

**Files:**
- Create: `.claude/rules/stock-data-cache.md`
- Source: `.claude/rules/data-architecture.md`（读取，本任务不删）

**搬运小节**（从 data-architecture.md 逐字搬到新文件，按原顺序）：
- `_SafeJsonProvider` JSON 安全序列化段（「核心设计」节首段）
- 「统一股票数据API」整节及其全部子节：市场识别 (MarketIdentifier) / 缓存架构（两层缓存、缓存刷新策略区分、TTL 表、缓存日期统一走 SmartCacheStrategy）/ Volume 单位契约（含 VOLUME_UNIT_SCHEMA_VERSION）/ A 股行情数据特征（节假日、一字涨停）/ 数据源 / 策略数据协作 / 核心组件（UnifiedStockDataService / CacheValidator / UnifiedStockCache）/ 统一数据格式（实时价格、OHLC）/ 调用链路

**不搬**（留给 Task 2/3）：数据模型、Stock 表约定、多账户合并、OCR 流程、模块级单例陷阱、失败语义二分、新闻多分支去重、启动数据种子。

- [ ] **Step 1: 新建文件并写 header**

文件首部写入：

```markdown
# 数据架构与缓存

> **何时读**：改 app/services/ 下任何 fetcher、写涉及 Stock/UnifiedStockCache 的 SQL、调试缓存命中率、新增市场支持、修改 Volume / 缓存 TTL
> **不必读**：入库/schema 改动（见 stock-data-model.md）/ 纯前端 / 纯通知格式 / LLM 路由
```

- [ ] **Step 2: 逐字搬运上列小节**

打开 `data-architecture.md`，把上述「搬运小节」内容**逐字复制**到 header 之后，保持原小标题层级与顺序。`_SafeJsonProvider` 段单独成「## 核心设计」下一段或合理小节。

- [ ] **Step 3: 校验内容完整**

Run: `grep -c "VOLUME_UNIT_SCHEMA_VERSION\|MarketIdentifier\|SmartCacheStrategy\|调用链路\|一字涨停" .claude/rules/stock-data-cache.md`
Expected: ≥ 5（五个锚点全部命中）

- [ ] **Step 4: Commit**

```bash
rtk git add .claude/rules/stock-data-cache.md && rtk git commit -F - <<'EOF'
docs(rules): 新增 stock-data-cache.md-从 data-architecture 切出缓存/统一数据API主干

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
```

---

## Task 2: stock-data-model.md（入库/schema/业务约定）

**Files:**
- Create: `.claude/rules/stock-data-model.md`
- Source: `.claude/rules/data-architecture.md`、`.claude/rules/dev-conventions.md`（读取，本任务不删）

**搬运小节：**
- 从 `data-architecture.md`：数据模型（按日期快照，`(date,stock_code)` 唯一）；Stock 表约定；多账户合并；OCR 流程；模块级单例的 Flask context 陷阱；启动数据种子（seeds 铁律全段，含 StockCategory 唯一约束）
- 从 `dev-conventions.md`：「数据存储」整节（stock.db / private.db 双 DB + `__bind_key__` 模型清单 + memory_cache + uploads）；「股票代码配置」整节（FUTURES_CODES / INDEX_CODES / CATEGORY_CODES / CATEGORY_NAMES + Stock/StockCategory 表来源说明）

- [ ] **Step 1: 新建文件并写 header**

```markdown
# 数据模型与入库

> **何时读**：改 schema、Stock/StockCategory 表、写 seeds、多账户合并、OCR 入库流程、双 DB（stock.db/private.db）选型、股票/期货/指数代码配置
> **不必读**：缓存/统一数据API（见 stock-data-cache.md）/ 取数源坑（见 data-fetch-conventions.md）
```

- [ ] **Step 2: 逐字搬运 data-architecture.md 的 model 小节**

把上列 6 个 data-architecture 小节逐字复制到 header 后，保持顺序。

- [ ] **Step 3: 逐字搬运 dev-conventions.md 的「数据存储」「股票代码配置」两节**

追加到文件，归入「## 存储与代码配置」或保持原小标题。

- [ ] **Step 4: 校验**

Run: `grep -c "多账户合并\|OCR\|seeds\|private.db\|FUTURES_CODES\|Flask context" .claude/rules/stock-data-model.md`
Expected: ≥ 6

- [ ] **Step 5: Commit**

```bash
rtk git add .claude/rules/stock-data-model.md && rtk git commit -F - <<'EOF'
docs(rules): 新增 stock-data-model.md-入库/schema/双DB/代码配置归并

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
```

---

## Task 3: notifications.md（推送格式 + 推送语义归位）+ 删 data-architecture.md

**Files:**
- Create: `.claude/rules/notifications.md`
- Source: `.claude/rules/notification-formatting.md`（全量搬运后删）、`.claude/rules/data-architecture.md`（取 2 段后删）

**搬运小节：**
- `notification-formatting.md` 全文（Slack 推送配置 / 频道路由表 / 盯盘告警推送格式 / Slack 推送排版规范）逐字搬入
- 从 `data-architecture.md`：「数据获取服务失败语义二分」整段（None vs 空 dict + exc_info 要求 + esports 参考）；「新闻推送多分支去重」整段（InterestPipeline）

- [ ] **Step 1: 新建 notifications.md，写 header + 搬 notification-formatting 全文**

```markdown
# Slack 推送、告警格式与推送语义

> **何时读**：改 app/services/notification.py、新增推送策略、改盯盘告警格式/排版、调 Slack 频道路由、改 _fetch_* 失败语义或新闻推送去重
> **不必读**：数据获取 / 调度配置 / 数据库变更
```

header 后逐字粘入 `notification-formatting.md` 的全部正文（去掉其原 header 行）。

- [ ] **Step 2: 追加两段推送语义**

在文件末新增「## 数据获取失败语义与去重」节，逐字粘入 data-architecture 的「失败语义二分」+「新闻多分支去重」两段。

- [ ] **Step 3: 校验**

Run: `grep -c "频道\|盯盘告警\|失败语义\|InterestPipeline\|exc_info" .claude/rules/notifications.md`
Expected: ≥ 5

- [ ] **Step 4: 删除 data-architecture.md 与 notification-formatting.md（内容已全部迁出）**

先确认 Task 1/2 已迁完 data-architecture 的全部小节（缓存→cache、model→model、推送语义→本任务），再删。

```bash
rtk git rm -q .claude/rules/data-architecture.md .claude/rules/notification-formatting.md && rtk git add .claude/rules/notifications.md && rtk git commit -F - <<'EOF'
docs(rules): 新增 notifications.md-推送格式+失败语义/去重归位；删 data-architecture/notification-formatting

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
```

- [ ] **Step 5: 验证 data-architecture 无残留引用（仅 graphify 缓存可命中）**

Run: `grep -rn "data-architecture\|notification-formatting" .claude/ CLAUDE.md`
Expected: 仅命中 `CLAUDE.md` 路由表旧行（Task 9 修）；`.claude/` 下零命中。若 `.claude/skills/` 命中需记录待 Task 8 修。

---

## Task 4: dev-environment.md + 技术栈并入 CLAUDE.md + 删 dev-conventions.md

**Files:**
- Create: `.claude/rules/dev-environment.md`
- Modify: `CLAUDE.md`（项目概述补技术栈细节）
- Source: `.claude/rules/dev-conventions.md`（剩余内容迁出后删）

**搬运小节（dev-conventions.md → dev-environment.md）：**
- 「常用命令的 Windows 坑点」整节全部子条（脚本查 DB / PYTHONIOENCODING / 作用域限制 / 管道吞 stdout / 后台 bash 日志 / crawl4ai 进度条 / create_app 开销 / 只读 DB 巡检 / sqlite_master 查表名 / wc-l / heredoc / rtk env 顺序 / Bash cwd 持久）
- 「开发规范」整节（测试目录布局 / 一次性脚本不入库 / sys.path / 配置变更同步三处 / amend 重验 HEAD / 并行 session 抢 git index）
- 「安装第三方仓库时」条 → **改写为 cross-ref**：`> 装第三方仓库后同步 GITHUB_RELEASE_REPOS，见 news-and-research.md`

**并入 CLAUDE.md：** dev-conventions 的「技术栈」段细节（RapidOCR(ONNX) / Twelve Data / Polygon / 可选 PyTorch app/ml）补进 CLAUDE.md「## 项目概述」，不单独成段。

- [ ] **Step 1: 新建 dev-environment.md，header + 搬运**

```markdown
# 开发环境与工作流

> **何时读**：跑脚本/查 DB、提 commit、踩 Windows 编码/heredoc/管道吞 stdout/create_app 副作用、git 协议（amend 重验、并行 session 抢 index）、测试布局
> **不必读**：纯业务逻辑实现（除非需 commit）
```

逐字搬入「Windows 坑点」+「开发规范」两节；「安装第三方仓库时」替换为上述 cross-ref 行。

- [ ] **Step 2: CLAUDE.md 项目概述补技术栈细节**

在 `CLAUDE.md` 「## 项目概述」首段技术栈描述后补充（一句话并入，不新增段落）：RapidOCR(ONNX) OCR、Twelve Data / Polygon 数据源、可选 PyTorch（app/ml AI 走势预测）。

- [ ] **Step 3: 校验 dev-environment 内容 + 技术栈已并入**

Run: `grep -c "PYTHONIOENCODING\|create_app\|并行 session\|sys.path\|heredoc" .claude/rules/dev-environment.md`
Expected: ≥ 5
Run: `grep -c "RapidOCR\|Polygon" CLAUDE.md`
Expected: ≥ 1

- [ ] **Step 4: 删 dev-conventions.md + commit**

确认 Task 2 已迁走「数据存储」「股票代码配置」、本任务已迁走其余、技术栈已并入 CLAUDE.md，再删。

```bash
rtk git rm -q .claude/rules/dev-conventions.md && rtk git add .claude/rules/dev-environment.md CLAUDE.md && rtk git commit -F - <<'EOF'
docs(rules): 新增 dev-environment.md-Windows坑/git协议/测试；技术栈并入CLAUDE.md；删 dev-conventions

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
```

---

## Task 5: docs-conventions.md（文档写作规范）

**Files:**
- Create: `.claude/rules/docs-conventions.md`
- Source: `.claude/rules/docs-and-portfolio.md`（取写作规范部分，本任务不删）

**搬运小节（docs-and-portfolio.md → docs-conventions.md）：**
- 「文档目录约定（docs/stock-analytics/）」整节（含一级 sector 枚举、跨板块 sector 归属准则、锂电/储能归 energy）
- 「Frontmatter 约定（5 类 doc_type）」整节（含强制规则、conviction_date 解析为 date 对象坑）
- 「跨文档引用：frontmatter.related_docs 唯一源」整节
- 「Lint 脚本（手动 run）」整节（含 Windows + 并发坑）→ 其中 PYTHONIOENCODING 编码坑改为 `> 编码坑见 dev-environment.md` 指针（保留 lint 特有的 `--check-orphans`/`--rewrite-blocks`/`symmetric` 描述）

- [ ] **Step 1: 新建 docs-conventions.md，header**

```markdown
# 文档写作与 lint 规范

> **何时读**：写 docs/stock-analytics/ 新文档、改 frontmatter、跑 lint_docs_*、维护 related_docs、判 sector 归属
> **不必读**：portfolio/valuations skill 行为（见 portfolio-valuations.md）/ 纯代码 / 通知 / 数据获取
```

- [ ] **Step 2: 逐字搬运四节**

按上列顺序搬入；Lint 节的 Windows 编码坑替换为指针行，其余 lint 坑（orphans/rewrite-blocks/symmetric 并发）保留。

- [ ] **Step 3: 校验**

Run: `grep -c "doc_type\|related_docs\|一级 sector\|conviction_date\|rewrite-blocks" .claude/rules/docs-conventions.md`
Expected: ≥ 5

- [ ] **Step 4: Commit**

```bash
rtk git add .claude/rules/docs-conventions.md && rtk git commit -F - <<'EOF'
docs(rules): 新增 docs-conventions.md-从 docs-and-portfolio 切出文档/frontmatter/lint 规范

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
```

---

## Task 6: portfolio-valuations.md（skill 行为 + A+H 唯一源）+ 删 docs-and-portfolio.md

**Files:**
- Create: `.claude/rules/portfolio-valuations.md`
- Source: `.claude/rules/docs-and-portfolio.md`（取剩余 skill 部分后删）

**搬运小节（docs-and-portfolio.md → portfolio-valuations.md）：**
- 「持仓再平衡报告输出」整节（入口、HTML 输出目录、文件名、写库表、StockWeight.weight float、shares 计算吸收 FP 噪声）
- 「docs/stock-analytics/ 是 portfolio skill 的隐式选股池」整节
- 「估值汇总页（/valuations，即"价值洼地"）」整节（含 CARVE_OUT_CATEGORIES、新增分组、A+H 取较低估值口径铁律、A+H valuations.yaml H 口径代码形态、ADR+港股 fungible 对比）—— 即 A+H 口径**唯一源**

- [ ] **Step 1: 新建 portfolio-valuations.md，header**

```markdown
# Portfolio / Valuations skill 行为与 A+H 口径

> **何时读**：跑 /portfolio-init 或 /portfolio-rebalance、改 RebalanceConfig/StockWeight/PositionPlan、改 /valuations 页或 valuations.yaml、裁定 A+H 双重上市口径
> **不必读**：文档写作/frontmatter/lint（见 docs-conventions.md）
```

- [ ] **Step 2: 逐字搬运三节**

- [ ] **Step 3: 校验 A+H 唯一源在此**

Run: `grep -c "RebalanceConfig\|CARVE_OUT_CATEGORIES\|A+H\|fungible\|价值洼地" .claude/rules/portfolio-valuations.md`
Expected: ≥ 5

- [ ] **Step 4: 删 docs-and-portfolio.md（Task 5+6 已迁完）+ commit**

```bash
rtk git rm -q .claude/rules/docs-and-portfolio.md && rtk git add .claude/rules/portfolio-valuations.md && rtk git commit -F - <<'EOF'
docs(rules): 新增 portfolio-valuations.md-再平衡/选股池/valuations/A+H唯一源；删 docs-and-portfolio

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
```

- [ ] **Step 5: 验证 docs-and-portfolio 无 .claude 内残留**

Run: `grep -rn "docs-and-portfolio" .claude/rules/ CLAUDE.md`
Expected: 仅 CLAUDE.md 路由表旧行（Task 9 修）；`.claude/rules/` 零命中。`.claude/skills/SKILL.md` 命中留 Task 8 修。

---

## Task 7: data-fetch-conventions.md + news-and-research.md 消重

**Files:**
- Modify: `.claude/rules/data-fetch-conventions.md`
- Modify: `.claude/rules/news-and-research.md`

- [ ] **Step 1: data-fetch A+H 段消重**

在 `data-fetch-conventions.md` 的「腾讯 HTTP 行情源取数坑」节内 A+H 部分：**保留**「A+H 标的 H 口径市值自洽校验」的**算法细节**（A 股总市值÷A 股价反推总股本×H 股现价、AH 折价公式、腾讯 q=hk 取价），在该小段**开头加一行**：
```markdown
> A+H 选哪一地口径作跟踪主体的**决策铁律**见 portfolio-valuations.md；此处只讲 H 口径市值的取数自洽校验。
```
不删算法，仅加指针明确分工。

- [ ] **Step 2: news-and-research GITHUB_RELEASE_REPOS 确认为唯一源**

确认 `news-and-research.md` 的「GitHub Release 监控配置」节已含「监控仓库列表 = 静态配置 ∪ 本地已装插件」与 GITHUB_RELEASE_REPOS 说明（已是唯一源，无需改）。若该节缺少「装新仓库后加到 GITHUB_RELEASE_REPOS」的动作描述，补一行：
```markdown
> 安装任何第三方仓库（skill/plugin/工具）后，需把对应 marketplace 仓库加入 `GITHUB_RELEASE_REPOS`。
```

- [ ] **Step 3: 校验**

Run: `grep -c "决策铁律见 portfolio-valuations\|自洽校验" .claude/rules/data-fetch-conventions.md`
Expected: ≥ 2

- [ ] **Step 4: Commit**

```bash
rtk git add .claude/rules/data-fetch-conventions.md .claude/rules/news-and-research.md && rtk git commit -F - <<'EOF'
docs(rules): data-fetch A+H 段消重指向 portfolio-valuations；GITHUB_RELEASE_REPOS 收为唯一源

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
```

---

## Task 8: 小文件 header 归一化 + esports cross-ref + 外部 SKILL 深链同步

**Files:**
- Modify: `.claude/rules/llm.md`（补 header）
- Modify: `.claude/rules/esports.md`（补失败语义 cross-ref）
- Modify: `.claude/skills/stock-deep-redo/SKILL.md`（4 处深链改名）

- [ ] **Step 1: llm.md 补 header**

在 `llm.md`「# LLM 配置」标题下补：
```markdown
> **何时读**：改 app/llm/、调 LLM 模型路由、改限流/超时、配 llama-server、调日预算
> **不必读**：非 LLM 相关
```
（确认 esports.md / watch.md / supply-chain.md 已有 header；如缺同样补齐，格式对齐其余文件。）

- [ ] **Step 2: esports.md 补失败语义 cross-ref**

在 esports.md「失败重试」相关段落补一行：
```markdown
> `_fetch_*` 返回 None vs 空 dict 的失败语义、exc_info 日志要求见 notifications.md。
```

- [ ] **Step 3: SKILL.md 4 处深链改名**

`.claude/skills/stock-deep-redo/SKILL.md` 逐处 Edit：
- L43 `docs-and-portfolio.md` → `docs-conventions.md`（归属准则）
- L106 `docs-and-portfolio.md` → `docs-conventions.md`（电池厂是锂买方）
- L133 `docs-and-portfolio.md`（目录/frontmatter/lint/related_docs）→ `docs-conventions.md`
- L134 `data-architecture.md`（缓存）→ `stock-data-cache.md`
- L135 `dev-conventions.md`（Windows…）→ `dev-environment.md`
- L39 `data-fetch-conventions.md 港股节` → **不改**（保名；A+H 自洽校验仍在该文件）

- [ ] **Step 4: 校验外部深链无旧名**

Run: `grep -rn "data-architecture\|dev-conventions\.md\|docs-and-portfolio\|notification-formatting" .claude/skills/`
Expected: 零命中

- [ ] **Step 5: Commit**

```bash
rtk git add .claude/rules/llm.md .claude/rules/esports.md .claude/skills/stock-deep-redo/SKILL.md && rtk git commit -F - <<'EOF'
docs(rules): llm.md 补 header；esports cross-ref；stock-deep-redo SKILL 深链改名同步

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
```

---

## Task 9: CLAUDE.md 路由表重写 + 历史档 path-only 修正

**Files:**
- Modify: `CLAUDE.md`（路由表）
- Modify: `docs/superpowers/specs/2026-06-21-估值页板块排序联动-design.md`
- Modify: `docs/superpowers/plans/2026-06-24-minerals-page.md`

- [ ] **Step 1: 重写 CLAUDE.md 路由表为 12 条**

替换 `CLAUDE.md` 「## Rules（按需 Read…）」下的清单为以下 12 条（触发描述露出高频坑）：

```markdown
- `.claude/rules/stock-data-cache.md` — 缓存/统一数据API/Volume/SmartCacheStrategy/A股特征 — 改 services/ fetcher 或调缓存前
- `.claude/rules/stock-data-model.md` — schema/Stock表/seeds/多账户合并/OCR入库/双DB/代码配置 — 改 schema 或写入库逻辑前
- `.claude/rules/data-fetch-conventions.md` — akshare/腾讯HTTP/yfinance港股/PDF/A+H市值自洽校验 — 写新取数脚本前
- `.claude/rules/notifications.md` — Slack频道/盯盘告警7类格式/排版/失败语义二分/推送去重 — 改推送前
- `.claude/rules/news-and-research.md` — 新闻轮询/公司/华尔街/野村/博客/Trending/Release(GITHUB_RELEASE_REPOS) — 调轮询或加新源前
- `.claude/rules/esports.md` — NBA/LoL/worldcup(2026并入) 推送 + 失败重试队列 — 改 esports_service.py 前
- `.claude/rules/watch.md` — 盯盘前端架构 + AI 分析调度（realtime/7d/30d）— 改 watch 模块前
- `.claude/rules/supply-chain.md` — 产业链图谱 SUPPLY_CHAIN_GRAPHS + tag 同步 — 改 supply_chain.py 或加图谱前
- `.claude/rules/docs-conventions.md` — docs目录/frontmatter/lint/related_docs/sector归属 — 写分析文档、改 frontmatter、跑 lint 前
- `.claude/rules/portfolio-valuations.md` — portfolio-init/rebalance/valuations页/A+H口径铁律 — 跑 portfolio 或改 RebalanceConfig 前
- `.claude/rules/dev-environment.md` — Windows编码/heredoc/create_app副作用/commit协议(并行session抢index)/测试布局 — 跑脚本或提 commit 前
- `.claude/rules/llm.md` — 智谱/Gemini/llama-server 环境变量 — 改 llm/ 前
```

- [ ] **Step 2: 历史档 path-only 修正**

- `docs/superpowers/specs/2026-06-21-估值页板块排序联动-design.md`：`docs-and-portfolio.md`（估值汇总页一节）→ `portfolio-valuations.md`（估值汇总页一节）
- `docs/superpowers/plans/2026-06-24-minerals-page.md`：`docs-and-portfolio.md`「电池厂是锂买方」→ `docs-conventions.md`「电池厂是锂买方」

仅改路径，正文叙述不动。

- [ ] **Step 3: 全仓验收 grep（核心验收闸）**

Run: `grep -rn "data-architecture\|dev-conventions\.md\|docs-and-portfolio\|notification-formatting" .claude/ docs/ CLAUDE.md`
Expected: 零命中（graphify-out/*.json 不在搜索范围；如误纳入，仅那些缓存命中可接受）

- [ ] **Step 4: 12 文件清单核对**

Run: `ls .claude/rules/`
Expected: 恰好 12 个 .md：stock-data-cache / stock-data-model / data-fetch-conventions / notifications / news-and-research / esports / watch / supply-chain / docs-conventions / portfolio-valuations / dev-environment / llm

- [ ] **Step 5: Commit**

```bash
rtk git add CLAUDE.md "docs/superpowers/specs/2026-06-21-估值页板块排序联动-design.md" "docs/superpowers/plans/2026-06-24-minerals-page.md" && rtk git commit -F - <<'EOF'
docs: CLAUDE.md 路由表重写为12条+触发描述优化；历史档深链 path-only 修正

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
```

---

## Self-Review（计划对 spec 的覆盖核对）

- **拆分**：Task 1/2/3（data-architecture）、Task 4（dev-conventions）、Task 5/6（docs-and-portfolio）✓
- **整理/消重**：A+H→Task 6 唯一源 + Task 7 指针；GITHUB_REPOS→Task 7；PYTHONIOENCODING→Task 5 指针；失败语义→Task 3 + Task 8 cross-ref ✓
- **完善/归一化**：header→Task 8（llm 等）+ 各 Task header；触发描述→Task 9 ✓
- **修路由+外链**：SKILL→Task 8；CLAUDE.md→Task 9；历史档→Task 9 ✓
- **验收标准**：Task 9 Step 3/4 兜底 grep + 文件清单 ✓
- **内容守恒**：每个搬运 Task 有锚点 grep 校验，源文件删除前依赖顺序已锁（Task 3/4/6 删前确认上游已迁）✓
- **风险（搬运漏段）**：每个 Task 列明搬运小节清单 + 锚点 grep；建议执行时对照 spec「内容归属」表逐节勾。
