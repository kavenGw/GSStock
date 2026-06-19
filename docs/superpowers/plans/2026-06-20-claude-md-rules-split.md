# CLAUDE.md 与 rules 精准外科拆分 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 163 行的 `data-architecture.md` 按域外科拆分——产业链图谱→新建 `supply-chain.md`，腾讯HTTP/港股/A+H 取数坑→并入 `data-fetch-conventions.md`，保留架构内核；4 处跨引用同步改向；CLAUDE.md 路由表更新。

**Architecture:** 纯 markdown 搬运，无代码改动。搬运顺序铁律：**先把内容加到新归属（Task 1、2），再从 `data-architecture.md` 删（Task 3）**——任何时刻内容至少存在于一处，绝不出现"删了还没加"的丢失窗口。中间任务只改工作树 + Grep 校验，**不 commit**；全部落定后 Task 5 单次原子 commit。

**Tech Stack:** Markdown。验证靠 Grep 工具 + python 行数统计（Windows `wc -l` 对中文不可靠，一律 `python -c "print(sum(1 for _ in open(path, encoding='utf-8')))"`）。

## Global Constraints

- **搬运 verbatim**：移动的内容（产业链图谱约定、tag同步、腾讯HTTP整节）从源文件**逐字复制，不改写、不压缩、不重排句子**。本轮"压缩"只靠拆分达成，不动文字。
- **单原子 commit**：Task 1–4 全程 **不 commit**，只改工作树。仅 Task 5 一次性 `git add <精确路径> && git commit -F <msg文件>` 同链执行（防并行 session 抢 index；中文 message 走文件防 heredoc 失配）。命令前缀一律 `rtk`。
- **不动 frozen 记录**：历史 plan/spec（`2026-05-15-*`、`2026-06-04-*`）指向旧路径但属不可变记录，**保持原样**。
- **spec 已单独提交**（commit 4924d4c），本 plan 的 commit **不含 spec**。
- 源文件当前行锚（执行前用 Read 复核，并发可能微移）：产业链+tag 块 = `data-architecture.md` 行 26–28；腾讯HTTP数据源 = 行 94–107。

---

### Task 1: 新建 supply-chain.md（搬入产业链图谱 + tag 同步）

纯追加操作，安全（不动任何现存内容）。

**Files:**
- Create: `.claude/rules/supply-chain.md`
- Read (源): `.claude/rules/data-architecture.md` 行 26–28

**Interfaces:**
- Produces: 新 rule 文件 `.claude/rules/supply-chain.md`，含 `> **何时读**` 路由头 + 两段 verbatim 内容。Task 4 的 CLAUDE.md 路由表会新增指向它的条目。

- [ ] **Step 1: 从源文件复制两段 verbatim**

用 Read 读 `.claude/rules/data-architecture.md` 行 26 与行 28（`**产业链图谱约定**：…` 整段、`**tag 与分析档同步**：…` 整段），原文照抄到剪贴区，**勿改一字**。

- [ ] **Step 2: 用 Write 创建 supply-chain.md**

文件头 + 结构如下（头部为本任务新撰写；两段正文用 Step 1 复制的 verbatim 内容替换占位）：

```markdown
# 产业链图谱与 tag 同步

> **何时读**：改 app/config/supply_chain.py、新增/修改 `SUPPLY_CHAIN_GRAPHS` 图谱、调 `/supply-chain` 渲染、回写标的 tag 反映分析结论
> **不必读**：数据获取 / 缓存 / 通知格式 / 盯盘 / 纯前端

## 产业链图谱约定

<<行 26 的「**产业链图谱约定**：…」整段 verbatim>>

## tag 与分析档同步

<<行 28 的「**tag 与分析档同步**：…」整段 verbatim>>

> 关联：tag 与 docs/stock-analytics 评级的同步细节见 `docs-and-portfolio.md`。
```

- [ ] **Step 3: 校验新文件内容完整**

用 Grep：`pattern="SUPPLY_CHAIN_GRAPHS|not_analyzed|何时读"` `path=".claude/rules/supply-chain.md"` `output_mode="count"`
Expected: count ≥ 3（图谱配置、tag 取值、路由头都在）。

- [ ] **Step 4: 校验行数**

Run: `python -c "print(sum(1 for _ in open('.claude/rules/supply-chain.md', encoding='utf-8')))"`
Expected: 14–22 行。

不 commit（见 Global Constraints）。

---

### Task 2: data-fetch-conventions.md 接收腾讯HTTP取数坑

纯追加操作，安全。把腾讯整节插到 `## yfinance 港股代码格式` 之后、`## 研究取数约定` 之前，使所有港股取数坑相邻。

**Files:**
- Modify: `.claude/rules/data-fetch-conventions.md`
- Read (源): `.claude/rules/data-architecture.md` 行 94–107（`### 腾讯HTTP数据源` 整节）

**Interfaces:**
- Consumes: 无（独立追加）。
- Produces: `data-fetch-conventions.md` 新增 `## 腾讯 HTTP 行情源取数坑` 一节，含腾讯字段索引 / XD失真 / `[41][42]`失真 / 港股 `q=hk` 字段 / A+H 市值自洽校验 / 一次性脚本直连优先。Task 3 的指针、Task 4 的 3 处跨引用都指向本节。

- [ ] **Step 1: 复制腾讯整节 verbatim**

用 Read 读 `.claude/rules/data-architecture.md` 行 94–107（从 `### 腾讯HTTP数据源` 到 `### 策略数据协作` 之前的最后一行），原文照抄，**勿改一字**。注意保留其中所有子项缩进、`q=` 字段索引、A+H 校验公式。

- [ ] **Step 2: 用 Edit 在 data-fetch-conventions.md 插入新节**

用 Edit。`old_string` 为现有分节边界（`## yfinance 港股代码格式` 节的最后一行 + 紧随的 `## 研究取数约定` 行）；在两者之间插入新节。新节 heading 为 `## 腾讯 HTTP 行情源取数坑`，body = Step 1 复制的 verbatim（把原 `### 腾讯HTTP数据源` 降级为本节正文，去掉那一行 `### 腾讯HTTP数据源` 标题，因为已有新 `##` 标题）。

执行细节：先 Read `.claude/rules/data-fetch-conventions.md` 定位 `## 研究取数约定` 的精确前一行，以该锚点构造 Edit 的 old_string（含上下文确保唯一）。

- [ ] **Step 3: 校验插入成功且位置正确**

用 Grep：`pattern="腾讯 HTTP 行情源取数坑|q=hk|市值自洽校验|\\[46\\]"` `path=".claude/rules/data-fetch-conventions.md"` `output_mode="count"`
Expected: count ≥ 4。

用 Grep 确认顺序（港股节在腾讯节之前、研究取数在最后）：`pattern="^## "` `path=".claude/rules/data-fetch-conventions.md"` `output_mode="content"` `-n=true`
Expected: 看到 `## yfinance 港股代码格式` → `## 腾讯 HTTP 行情源取数坑` → `## 研究取数约定` 顺序。

- [ ] **Step 4: 更新路由头**

用 Edit 改 `data-fetch-conventions.md` 顶部 `> **何时读**` 行，句末追加触发条件。
old_string（当前头，执行前 Read 确认精确文本）:
```
> **何时读**：写新数据获取脚本、首次调用 akshare 某接口、抓 PDF 调研纪要、按 stock_name 反查代码、新浪/cninfo/巨潮源切换
```
new_string:
```
> **何时读**：写新数据获取脚本、首次调用 akshare 某接口、抓 PDF 调研纪要、按 stock_name 反查代码、新浪/cninfo/巨潮源切换、腾讯 HTTP 行情字段 / 港股 q=hk 取数 / A+H 市值自洽校验
```

不 commit。

---

### Task 3: data-architecture.md 删 2 块 + 留指针 + 改路由头

此刻内容已存在于新归属（Task 1、2），现在安全删除源。

**Files:**
- Modify: `.claude/rules/data-architecture.md`

**Interfaces:**
- Consumes: Task 1、2 已落地的新归属文件（删除前提）。
- Produces: `data-architecture.md` 收缩至 ~105 行，腾讯节位置留一行 `### 数据源` 指针指向 `data-fetch-conventions.md`。

- [ ] **Step 1: 删除产业链 + tag 两段（行 26–28）**

用 Edit。执行前 Read 行 24–30 复核锚点。old_string = 行 26 `**产业链图谱约定**：…` 整段 + 行 27 空行 + 行 28 `**tag 与分析档同步**：…` 整段（连同其前导空行，使 行24 启动种子段 与 行30 `## 统一股票数据API` 之间只留一个空行）。new_string = 空（即 `**启动数据种子**：…` 段后直接接一个空行再接 `## 统一股票数据API`）。

- [ ] **Step 2: 删除腾讯HTTP整节，替换为指针**

用 Edit。old_string = `### 腾讯HTTP数据源` 整节（原 行 94–107，到 `### 策略数据协作` 之前）。new_string：
```
### 数据源

A股实时价/分时K线优先腾讯 `qt.gtimg.cn`（并发安全、无需限速），美股/港股走 yfinance；选源与负载均衡见下方「核心组件」。腾讯字段索引 / XD除息失真 / `[41][42]`年高低失真 / 港股 `q=hk` 字段 / A+H 市值自洽校验等取数坑见 `data-fetch-conventions.md`。
```

- [ ] **Step 3: 更新路由头去掉「产业链图谱」**

用 Edit 改顶部 `> **何时读**` 行。
old_string（执行前 Read 确认）:
```
> **何时读**：改 app/services/ 下任何 fetcher、写涉及 Stock/UnifiedStockCache 的 SQL、调试缓存命中率、新增市场支持、修改 Volume / OCR / 多账户合并 / 产业链图谱
```
new_string:
```
> **何时读**：改 app/services/ 下任何 fetcher、写涉及 Stock/UnifiedStockCache 的 SQL、调试缓存命中率、新增市场支持、修改 Volume / OCR / 多账户合并
```

- [ ] **Step 4: 校验删除干净 + 指针在位**

用 Grep：`pattern="SUPPLY_CHAIN_GRAPHS|q=hk|XD除息|tag 与分析档|产业链图谱约定"` `path=".claude/rules/data-architecture.md"` `output_mode="count"`
Expected: count = 0（两块已彻底移出）。

用 Grep：`pattern="qt.gtimg.cn|data-fetch-conventions.md"` `path=".claude/rules/data-architecture.md"` `output_mode="count"`
Expected: count ≥ 1（指针在位）。

- [ ] **Step 5: 校验架构内核未误删**

用 Grep：`pattern="VOLUME_UNIT_SCHEMA_VERSION|MarketIdentifier|缓存架构|调用链路|失败语义|多账户合并"` `path=".claude/rules/data-architecture.md"` `output_mode="count"`
Expected: count ≥ 6。

- [ ] **Step 6: 校验行数**

Run: `python -c "print(sum(1 for _ in open('.claude/rules/data-architecture.md', encoding='utf-8')))"`
Expected: 95–118 行。

不 commit。

---

### Task 4: 4 处跨引用同步 + CLAUDE.md 路由表

修复所有指向旧位置的引用，避免断链。

**Files:**
- Modify: `.claude/skills/stock-deep-redo/SKILL.md`（2 处）
- Modify: `.claude/skills/stock-deep-redo/references/playbook.md`（1 处）
- Modify: `.claude/rules/docs-and-portfolio.md`（1 处）
- Modify: `CLAUDE.md`（路由表 3 改）

- [ ] **Step 1: stock-deep-redo/SKILL.md 第 39 行（A+H 口径）**

用 Edit。把该行内 `` `.claude/rules/data-architecture.md` 港股节 `` 改为 `` `.claude/rules/data-fetch-conventions.md` 港股节 ``。
old_string: `H 口径市值自洽校验见 `.claude/rules/data-architecture.md` 港股节`
new_string: `H 口径市值自洽校验见 `.claude/rules/data-fetch-conventions.md` 港股节`

- [ ] **Step 2: stock-deep-redo/SKILL.md 第 126 行（rules 清单）**

用 Edit。
old_string: `` `.claude/rules/data-fetch-conventions.md`（akshare/实时价坑）、`.claude/rules/data-architecture.md`（qt.gtimg.cn/缓存）、 ``
new_string: `` `.claude/rules/data-fetch-conventions.md`（akshare/实时价/qt.gtimg.cn 字段坑）、`.claude/rules/data-architecture.md`（缓存）、 ``

- [ ] **Step 3: playbook.md 第 126 行（港股/美股行情）**

用 Edit。把 `` 详见 `.claude/rules/data-architecture.md` 腾讯HTTP节 `` 改为 `` 详见 `.claude/rules/data-fetch-conventions.md` 腾讯HTTP节 ``。
old_string: `详见 `.claude/rules/data-architecture.md` 腾讯HTTP节`
new_string: `详见 `.claude/rules/data-fetch-conventions.md` 腾讯HTTP节`

- [ ] **Step 4: docs-and-portfolio.md 第 89 行**

执行前 Read 第 89 行确认精确措辞（该行较长被省略过）。把其中 `` `data-architecture.md` 港股节 `` 改为 `` `data-fetch-conventions.md` 港股节 ``（若带 `.claude/rules/` 前缀则一并保留前缀只换文件名）。用 Edit，old_string 取含该引用的唯一上下文片段。

- [ ] **Step 5: CLAUDE.md 路由表 3 改**

用 Edit 改 3 行。

5a — data-architecture 描述去掉「产业链图谱」：
old_string: `- `.claude/rules/data-architecture.md` — 数据/缓存/Volume/A 股特征/产业链图谱 — 改 services/ 或写 SQL 前`
new_string: `- `.claude/rules/data-architecture.md` — 数据/缓存/Volume/A 股特征/统一数据 API — 改 services/ 或写 SQL 前`

5b — data-fetch 描述加腾讯/港股/A+H：
old_string: `- `.claude/rules/data-fetch-conventions.md` — akshare/PDF/股票名查询坑 — 写新数据脚本前`
new_string: `- `.claude/rules/data-fetch-conventions.md` — akshare/PDF/股票名查询坑/腾讯HTTP/港股/A+H 取数 — 写新数据脚本前`

5c — 新增 supply-chain 条目（插在 data-architecture 行之后）：
用 Edit，old_string = data-architecture 那行（5a 改后的新文本）；new_string = 该行 + 换行 + `- `.claude/rules/supply-chain.md` — 产业链图谱 SUPPLY_CHAIN_GRAPHS 配置 + tag 同步 — 改 supply_chain.py 或加图谱前`。

- [ ] **Step 6: 校验再无指向 data-architecture 的港股/腾讯引用**

用 Grep（全仓，排除 frozen 历史档）：`pattern="data-architecture\\.md` （港股|腾讯)|data-architecture.md.{0,12}(qt.gtimg|腾讯HTTP)"` `glob="*.md"` `output_mode="content"` `-n=true`
人工核对：命中只应出现在 `docs/superpowers/plans/` 与 `specs/` 的本任务/历史文档里，**不得**出现在 `.claude/skills/` 或 `.claude/rules/`。

- [ ] **Step 7: 校验 CLAUDE.md 路由表完整**

用 Grep：`pattern="\\.claude/rules/[a-z-]+\\.md"` `path="CLAUDE.md"` `output_mode="content"` `-o=true`
Expected: 10 行（原 9 + 新增 supply-chain）。

不 commit。

---

### Task 5: 全局验证 + 单原子 commit

**Files:** 无新修改，仅校验 + 提交。

- [ ] **Step 1: 文件数校验**

Run: `ls .claude/rules/*.md | wc -l`（或 Glob `.claude/rules/*.md` 数条目）
Expected: 10。

- [ ] **Step 2: 每个 rule 仍有路由头**

用 Grep：`pattern="^> \\*\\*何时读"` `path=".claude/rules/"` `glob="*.md"` `output_mode="files_with_matches"`
Expected: 10 个文件全命中。

- [ ] **Step 3: 内容唯一归属（无丢失、无重复）**

用 Grep（限 `.claude/rules/`，`glob="*.md"`，逐条）：
- `SUPPLY_CHAIN_GRAPHS` → 只命中 `supply-chain.md`
- `市值自洽校验` 的港股节 / `q=hk` → 只命中 `data-fetch-conventions.md`
- `\[46\]PB`（腾讯字段索引）→ 只命中 `data-fetch-conventions.md`
- `XD除息` → 只命中 `data-fetch-conventions.md`

任一条命中 0 次（丢失）或命中 2 个文件（重复）即为失败，回 Task 1–3 修。

- [ ] **Step 4: 无悬空 rule 引用**

用 Grep 全仓 `pattern="\\.claude/rules/([a-z-]+)\\.md"` `output_mode="content"` `-o=true`，对去重后的每个文件名核对 `.claude/rules/` 下存在该文件。
Expected: 被引用文件名 ⊆ {data-architecture, data-fetch-conventions, supply-chain, dev-conventions, docs-and-portfolio, esports, llm, news-and-research, notification-formatting, watch}，无 `data-model-and-cache` / `data-sources` 等不存在名。

- [ ] **Step 5: 总行数 sanity**

Run（逐文件 python 行数；Windows wc 不可靠）:
```bash
for f in CLAUDE.md .claude/rules/*.md; do python -c "print(sum(1 for _ in open('$f', encoding='utf-8')), '$f')"; done
```
Expected: data-architecture ~95–118、data-fetch ~70–90、supply-chain ~14–22、CLAUDE.md ≤ 56；总行数较拆分前（~628）基本持平（搬运不删字）。

- [ ] **Step 6: 写 commit message 文件**

用 Write 创建 `.git/MSG_split.txt`：
```
docs(rules): data-architecture 按域外科拆分

163 行杂货铺拆为三：产业链图谱+tag同步→新建 supply-chain.md；
腾讯HTTP/港股q=hk/A+H 市值自洽校验取数坑→并入 data-fetch-conventions.md；
data-architecture 保留架构内核(~105行)并留指针。CLAUDE.md 路由表 +1 条、
4 处跨引用(stock-deep-redo SKILL×2/playbook/docs-and-portfolio)同步改向。
搬运 verbatim 无文字改写。spec/plan: 2026-06-20-claude-md-rules-split。

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
```

- [ ] **Step 7: 原子 add + commit（同链，防抢 index）**

Run:
```bash
rtk git add CLAUDE.md .claude/rules/data-architecture.md .claude/rules/data-fetch-conventions.md .claude/rules/supply-chain.md .claude/rules/docs-and-portfolio.md .claude/skills/stock-deep-redo/SKILL.md .claude/skills/stock-deep-redo/references/playbook.md docs/superpowers/plans/2026-06-20-claude-md-rules-split.md && rtk git commit -F .git/MSG_split.txt && rm .git/MSG_split.txt
```

- [ ] **Step 8: 提交后复核只含本任务文件**

Run: `rtk git show --stat HEAD`
Expected: 恰好 8 个文件（上列 7 个 rule/skill/CLAUDE + 本 plan），无他人在写档裹挟。若多出文件，`git reset --soft HEAD~1` 重做精确 add。

- [ ] **Step 9: 收尾报告**

写一段总结：各文件 before/after 行数、4 处跨引用确认、唯一归属校验结果、commit SHA。无 commit。

---

## Self-Review 记录

**Spec coverage**：
- §1 data-architecture 切走 2 块 → Task 1（产业链）+ Task 2（腾讯）+ Task 3（删源+指针）
- §2 data-fetch 接收 → Task 2
- §3 supply-chain 新文件 → Task 1
- §4 4 处跨引用 → Task 4 Step 1–4
- §5 CLAUDE.md 路由表 3 改 → Task 4 Step 5
- §6 压缩=仅靠拆分、不动他文件 → Global Constraints「搬运 verbatim」
- §7 单原子 commit → Task 5 Step 6–7
- §8 验证 6 条 → Task 5 Step 1–5、8（悬空引用/唯一归属/路由头/行数/文件数/git干净）
- §风险（断链/丢失/抢index）→ Task 4 Step 6、Task 5 Step 3、Task 5 Step 7+8

**Placeholder scan**：无 TBD/TODO。搬运内容因「verbatim 不可转写」用行锚 + 源文件复制指令替代内联（转写 40 行中文坑点反而引入错误）——每个 Edit 给了 old/new 或唯一锚点，每个校验给了 expected。

**Type consistency**：文件名全程一致（`supply-chain.md` / `data-fetch-conventions.md` / `data-architecture.md`）；新节标题 `## 腾讯 HTTP 行情源取数坑`、指针 heading `### 数据源` 在 Task 2/3/5 间一致；commit 前缀 `docs(rules):`。
