# stock-deep-redo 成长轴优化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 给 stock-deep-redo skill 加一条"成长轴"——新增成长/扩产/客户增长横切 lens + playbook bull 情景的增长证据包门控，让 AI/存储/PCB 成长股不只看估值。

**Architecture:** 纯文档改动，仅追加/微调，不删除现有任何 lens 或红线。改 3 个文件：`references/sector-lenses.md`（加横切 lens 节 + 头部说明）、`references/playbook.md`（§3 加门控铁律 + §2 节说明微调 + §4 指针）、`SKILL.md`（选 lens 步骤 + 红线第 8 条 + 两段式审查各加一项）。

**Tech Stack:** Markdown skill 文件（Claude Code skill 约定，五段式 lens 注册表）。无代码、无 schema、无 lint 脚本改动。

**验证手段:** 每个文件改完用 Grep 确认插入内容存在；最后跑 `lint_docs_frontmatter.py` 确认未误伤 `docs/stock-analytics`（预期零影响，因为只改 `.claude/skills/` 下文件）。

**前置 Spec:** `docs/superpowers/specs/2026-05-31-stock-deep-redo-growth-axis-design.md`

---

## File Structure

| 文件 | 责任 | 本次改动 |
|------|------|---------|
| `.claude/skills/stock-deep-redo/references/sector-lenses.md` | 板块视角注册表（五段式 lens） | 头部说明改两横切 lens；AI 节后追加「成长」横切 lens 节 |
| `.claude/skills/stock-deep-redo/references/playbook.md` | 13 节模板 + 估值机制 + 采证清单 | §3 加门控铁律；§2 节说明补跑道/增长质量；§4 加成长 lens 指针 |
| `.claude/skills/stock-deep-redo/SKILL.md` | 总编排 + 质量红线 + 审查清单 | 选 lens 步骤提两横切；红线加第 8 条；两段式审查各加一项 |

任务顺序：先改被引用的 references（lens + playbook），再改引用方 SKILL.md，最后整体验证。三个任务各自独立可提交。

---

### Task 1: sector-lenses.md — 头部说明 + 新增成长横切 lens 节

**Files:**
- Modify: `.claude/skills/stock-deep-redo/references/sector-lenses.md`（头部第 4 行附近 + AI 节末尾 47 行后）

- [ ] **Step 1: 改头部说明（两个横切 lens）**

用 Edit 把这一行：

```
> **可叠加多选**：一只股可同时命中多套（如 PCB + AI）。AI 是横切 lens，默认对每只股都跑识别。
```

替换为：

```
> **可叠加多选**：一只股可同时命中多套（如 PCB + AI + 成长）。**AI 与 成长是两个横切 lens，默认对每只股都跑识别。**
```

- [ ] **Step 2: 在 AI 节之后插入成长横切 lens 节**

AI 节以第 46 行 `- 终端（AI 服务器等）出货/资本开支指引下修。` 结尾，其后是第 47 行的 `---` 分隔线。
用 Edit 把这段（AI 节监控指标末行 + 其后的 `---`）：

```
- 终端（AI 服务器等）出货/资本开支指引下修。

---
```

替换为（在 `---` 后插入完整成长节，再接 PCB 节原有的 `---`）：

```
- 终端（AI 服务器等）出货/资本开支指引下修。

---

## 成长 / 扩产 / 客户增长（横切 · 默认对每只股跑识别）

### 【识别信号】
- 任何标的都先判：是否处在**产能扩张 / 营收高增**轨道（区别于纯周期股 / 价值股）。
- 强信号：在建产线 / 扩产 capex 公告；近年营收 CAGR 显著；AI 基建 / 存储 / PCB 等高增赛道；
  管理层 / 财报把增长归因到扩产达产或大客户放量。
- 判为纯周期 / 价值股（无扩产、纯靠涨价弹性）→ 一句话带过，不强跑全清单。

### 【必查清单（采证 face）】
- **标的自身扩产**：在建 / 规划产线、capex 金额与节奏、投产时间表、达产率爬坡曲线、对应增量营收 / 产能
  （量化，带公告 URL + 日期）。
- **客户增长预期（分层兑证）**：
  - ① 先具名——识别 Top-N 大客户，逐个找其自身 capex / 出货 / 营收 guidance（如沪电→英伟达 / 北美服务器
    ODM capex 指引）。
  - ② 客户保密 / 过于分散 → 降级到终端市场总量（北美 CSP capex、AI 服务器出货预测、AMOLED 面板出货等
    第三方机构口径），**明写这是终端兑底而非具名**。
  - ③ 每条标【硬】（客户 / 机构公开 guidance）/【软】（媒体推测）/【缺】。
- **历史增长质量**：近 3 年营收 / 净利 CAGR、增长拆量价、是否伴随毛利改善（有质量增长 vs 烧钱扩张）。
- **跑道长度（TAM 渗透）**：标的当前在赛道的渗透率 / 份额，距天花板还有多远。

### 【撰写落点（撰写 face）】
- §2 市场规模：补「跑道长度」——标的在 TAM 中的当前渗透与剩余空间。
- §3 盈利能力：增长拆量价 + 增长是否伴随毛利改善（增长质量）。
- §6 核心新论点：扩产达产逻辑（结构性增量 vs 周期性补涨二分判定）。
- §9 估值：**成长持续性证据包**（扩产达产确定性 + 客户 capex 能见度 + TAM 跑道）作为 bull 情景赋权依据
  （门控机制见 playbook.md §3）。

### 【双面必答】
- 扩产是**结构性需求支撑**，还是**赌行业景气**（同业一起扩 → 未来产能过剩 / 价格战）？最强反驳前置。
- 客户增长预期是**已锁定订单 / capex 指引**，还是**框架意向 / 卖方一致预期**（容易证伪）？
- 高增长是否**已被股价 price-in**（高 PE / PB）——增长再好也要算安全边际，不许用「成长空间」稀释「贵」。

### 【监控指标模板】
- 在建产能达产率 miss 进度 / 稼动率连续 N 季下滑（扩产证伪）。
- 大客户 capex / 出货指引下修，或终端市场（AI 服务器 / CSP capex / AMOLED）增速预测下调。
- 营收增速连续 N 季放缓且毛利率同步走弱（增长质量恶化）。
- 同业扩产产能集中释放窗口临近（供给过剩前瞻信号）。

---
```

- [ ] **Step 3: Grep 验证插入成功**

Run:
```bash
rtk grep -n "成长 / 扩产 / 客户增长（横切" ".claude/skills/stock-deep-redo/references/sector-lenses.md"
rtk grep -n "AI 与 成长是两个横切 lens" ".claude/skills/stock-deep-redo/references/sector-lenses.md"
```
Expected: 两条都各命中 1 行。

- [ ] **Step 4: 确认未写死会过时的事实**

Run:
```bash
rtk grep -nE "[0-9]{4}年|Q[1-4]|\\$[0-9]" ".claude/skills/stock-deep-redo/references/sector-lenses.md"
```
Expected: 新增成长节内**无**命中（铁律：lens 只写必查清单不写死事实；"3 年 CAGR""Top-N""N 季"是模板占位不算）。若命中具体年份/报价即是 bug，删除该具体值改回模板措辞。

- [ ] **Step 5: Commit**

```bash
rtk git add .claude/skills/stock-deep-redo/references/sector-lenses.md
rtk git commit -m "feat(stock-deep-redo): sector-lenses 加成长/扩产/客户增长横切lens(默认对每股识别)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: playbook.md — §3 门控铁律 + §2 节说明 + §4 指针

**Files:**
- Modify: `.claude/skills/stock-deep-redo/references/playbook.md`（§2 第 57/64 行、§3 第 80-85 行铁律块、§4 第 87-91 行）

- [ ] **Step 1: §3 场景加权——追加「增长证据包门控 bull」铁律**

§3 铁律是第 80-85 行的列表，末条为第 84-85 行：

```
- 安全边际 = (期望内在价值 − 实时市值) / 实时市值。必要时对最乐观 bull 单独再算一次安全边际做压力测试。
- 实时市值用 Phase A 采证的真实值，不用估。
```

用 Edit 在「- 实时市值用 Phase A 采证的真实值，不用估。」这一行**之后**追加：

```
- 实时市值用 Phase A 采证的真实值，不用估。
- **bull 情景增长证据包门控**（命中成长横切 lens 时必算）：bull 的概率与倍数上修必须由「成长持续性
  证据包」三要素支撑——(a) **扩产达产确定性**（产线已开工 / 设备到位 / 达产路线清晰=硬；仅规划=软）、
  (b) **客户 capex / 出货能见度**（具名客户公开 guidance=硬；终端市场总量=中；卖方一致预期=软）、
  (c) **TAM 跑道**（渗透率低、空间大）。三项里硬证据越少，bull 概率越要封顶（如三项全软 → bull 概率
  ≤ 20%）。这是「拒绝周期顶定价」的**对偶约束**：既不许用周期顶利润定价（防高估），也不许在缺乏增长
  证据时给 bull 高权重（防被叙事拔高）。**反过来**：三项全硬的结构性成长股，base 情景也可适度脱离纯
  周期均值（用穿越周期的成长中枢），避免系统性低估真成长。
```

- [ ] **Step 2: §2 13 节说明——补跑道长度 + 增长质量**

§2 中 §2/§3 两节的描述行（第 56-57 行）：

```
- **§2 市场规模**（各业务线 TAM/SAM/SOM）
- **§3 盈利能力**（最新季报兑现 + 毛利率·ROIC 周期分析 + 涨价/需求弹性精算）
```

用 Edit 替换为：

```
- **§2 市场规模**（各业务线 TAM/SAM/SOM + 跑道长度：标的当前渗透率/份额距天花板多远）
- **§3 盈利能力**（最新季报兑现 + 毛利率·ROIC 周期分析 + 涨价/需求弹性精算 + 增长拆量价与增长质量：高增长是否伴随毛利改善）
```

- [ ] **Step 3: §4 指针——补成长 lens 指引**

§4 标题与正文是第 87-91 行，标题为：

```
## 4. AI 维度标签法 → 见 sector-lenses.md「AI」节
```

用 Edit 在该 §4 段落末尾（第 91 行 `未兑现的概念不许进 §9 估值的 owner earnings 基础。命中 AI lens 时撰写 subagent 读该节的【撰写落点】。`）之后追加一行：

```
未兑现的概念不许进 §9 估值的 owner earnings 基础。命中 AI lens 时撰写 subagent 读该节的【撰写落点】。
**成长横切 lens 同理**：命中时读 sector-lenses.md「成长 / 扩产 / 客户增长」节的【必查清单】【撰写落点】，
其【撰写落点】§9 的「成长持续性证据包」对应本文件 §3 的 bull 门控铁律。
```

- [ ] **Step 4: Grep 验证三处插入**

Run:
```bash
rtk grep -n "bull 情景增长证据包门控" ".claude/skills/stock-deep-redo/references/playbook.md"
rtk grep -n "跑道长度：标的当前渗透率" ".claude/skills/stock-deep-redo/references/playbook.md"
rtk grep -n "成长横切 lens 同理" ".claude/skills/stock-deep-redo/references/playbook.md"
```
Expected: 三条各命中 1 行。

- [ ] **Step 5: 确认 13 节结构未新增节号**

Run:
```bash
rtk grep -nE "^- \\*\\*§1[0-9]" ".claude/skills/stock-deep-redo/references/playbook.md"
```
Expected: 仍只有 §10/§11/§12（无 §13 及以上新节）；成长内容并入既有节，不新增节号。

- [ ] **Step 6: Commit**

```bash
rtk git add .claude/skills/stock-deep-redo/references/playbook.md
rtk git commit -m "feat(stock-deep-redo): playbook §3 加增长证据包门控bull(对偶约束)+§2跑道/增长质量

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: SKILL.md — 选 lens 步骤 + 红线第 8 条 + 两段式审查

**Files:**
- Modify: `.claude/skills/stock-deep-redo/SKILL.md`（选 lens 第 58-59 行、规格审查第 82-83 行、质量审查第 84 行、红线第 110 行后）

- [ ] **Step 1: "选 sector-lens" 步骤提两个横切 lens**

第 58-59 行当前为：

```
4. **选 sector-lens**：按 subsector 从 `references/sector-lenses.md` 挑命中的 lens 节（**可叠加**：主 lens
   如 PCB/存储 + 横切 AI lens 默认跑识别）。把命中节的【必查清单】【撰写落点】摘出，分别注入 Phase A / Phase B 提示。
```

用 Edit 替换为：

```
4. **选 sector-lens**：按 subsector 从 `references/sector-lenses.md` 挑命中的 lens 节（**可叠加**：主 lens
   如 PCB/存储 + **两个横切 lens（AI、成长）默认对每只股跑识别**）。把命中节的【必查清单】【撰写落点】摘出，分别注入 Phase A / Phase B 提示。
```

- [ ] **Step 2: 规格审查清单加成长项**

第 81-83 行规格审查项当前为：

```
1. **规格符合性**：13 节齐全？frontmatter 合规？三情景概率 Σ=100% 且期望值算术对？AI 维度都打了标？
   供给侧双面写了吗？数字可追溯无造数？无范围外夹带？命中 lens 的必查项是否在正文均有回应（查无证据也写明）？
   → 输出 SPEC-COMPLIANT 或问题清单。
```

用 Edit 替换为：

```
1. **规格符合性**：13 节齐全？frontmatter 合规？三情景概率 Σ=100% 且期望值算术对？AI 维度都打了标？
   供给侧双面写了吗？数字可追溯无造数？无范围外夹带？命中 lens 的必查项是否在正文均有回应（查无证据也写明）？
   **命中成长 lens 时：扩产达产 / 客户增长预期（分层兑证）/ 跑道长度是否在正文均有回应？bull 是否被增长证据包门控（证据全软则概率封顶）？**
   → 输出 SPEC-COMPLIANT 或问题清单。
```

- [ ] **Step 3: 质量审查清单加成长项**

第 84-85 行质量审查项当前为：

```
2. **分析质量**：内在一致性、概率可辩护性、供给侧双面是否走过场、"贵"是否被诚实消化、AI 是否蹭概念拔高、
   slop 检查、buffett 框架贴合度、监控指标是否带阈值可执行。→ APPROVED / APPROVED-WITH-NITS / CHANGES-REQUESTED。
```

用 Edit 替换为：

```
2. **分析质量**：内在一致性、概率可辩护性、供给侧双面是否走过场、"贵"是否被诚实消化、AI 是否蹭概念拔高、
   **增长是否被诚实证据化（非叙事）、bull 赋权是否与增长证据强度匹配、高增长是否稀释了"贵"**、
   slop 检查、buffett 框架贴合度、监控指标是否带阈值可执行。→ APPROVED / APPROVED-WITH-NITS / CHANGES-REQUESTED。
```

- [ ] **Step 4: 质量红线追加第 8 条**

红线列表末条为第 109-110 行（红线 7）：

```
7. **替换=物理删除旧档**：新档落定后该股历史 buffett 档必须 `git rm`，且所有指向旧档的 symmetric 反向链
   改指到新档——目录里同股只留最新一份，refs lint 无悬空引用。
```

用 Edit 在红线 7 之后追加红线 8：

```
7. **替换=物理删除旧档**：新档落定后该股历史 buffett 档必须 `git rm`，且所有指向旧档的 symmetric 反向链
   改指到新档——目录里同股只留最新一份，refs lint 无悬空引用。
8. **看增长但不被增长拔高**：成长/扩产标的必查扩产达产 + 客户增长预期（分层：具名优先、终端兑底）；bull
   情景的概率/倍数由「成长持续性证据包」门控（扩产达产确定性 + 客户 capex 能见度 + TAM 跑道），证据全软则
   概率封顶；同时高增长不许稀释"贵"——这是红线 3（拒绝周期顶定价）的对偶，既防高估也防系统性低估真成长。
```

- [ ] **Step 5: Grep 验证四处插入**

Run:
```bash
rtk grep -n "两个横切 lens（AI、成长）" ".claude/skills/stock-deep-redo/SKILL.md"
rtk grep -n "命中成长 lens 时：扩产达产" ".claude/skills/stock-deep-redo/SKILL.md"
rtk grep -n "增长是否被诚实证据化" ".claude/skills/stock-deep-redo/SKILL.md"
rtk grep -n "看增长但不被增长拔高" ".claude/skills/stock-deep-redo/SKILL.md"
```
Expected: 四条各命中 1 行。

- [ ] **Step 6: 确认红线编号连续到 8**

Run:
```bash
rtk grep -nE "^8\\. \\*\\*看增长" ".claude/skills/stock-deep-redo/SKILL.md"
```
Expected: 命中 1 行（红线 8 编号正确接在 7 之后）。

- [ ] **Step 7: Commit**

```bash
rtk git add .claude/skills/stock-deep-redo/SKILL.md
rtk git commit -m "feat(stock-deep-redo): SKILL 选lens提两横切+红线8(看增长不拔高)+两段式审查加成长项

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: 整体验证 — lint 不误伤 + 交叉引用自洽

**Files:**
- 只读验证，无修改。

- [ ] **Step 1: 跑 docs frontmatter lint 确认零影响**

Run:
```bash
rtk PYTHONIOENCODING=utf-8 python scripts/lint_docs_frontmatter.py
```
Expected: exit 0（本次只改 `.claude/skills/` 下文件，不碰 `docs/stock-analytics/`，应全绿）。
若非 0：检查是否误改了 docs 下文件——本计划不应触及任何 stock-analytics 文档。

- [ ] **Step 2: 交叉引用自洽检查**

Run:
```bash
rtk grep -rn "成长持续性证据包" ".claude/skills/stock-deep-redo/"
```
Expected: 至少在 3 处命中——sector-lenses.md（撰写落点 §9）、playbook.md（§3 门控铁律 + §4 指针）、
确认三个文件对「成长持续性证据包」「扩产达产确定性 / 客户 capex 能见度 / TAM 跑道」三要素措辞一致，
无 sector-lenses 写「跑道长度」而 playbook 写「跑道空间」之类的术语漂移。

- [ ] **Step 3: 确认无删除现有 lens / 红线（git diff 自检）**

Run:
```bash
rtk git diff HEAD~3 --stat
rtk git log --oneline -3
```
Expected: 三个文件均为净增行（insertions 远多于 deletions，deletions 仅来自被替换行的旧版本）；
确认 4 个原有 lens 节（AI/PCB/存储DRAM-NAND/存储NOR）与 7 条原红线全部仍在。

---

## Self-Review

**Spec coverage（逐条对照 spec 验收标准）:**
- ✅ 验收 1（新增成长横切 lens + 头部两横切 + 不写死事实）→ Task 1 Step 1/2/4
- ✅ 验收 2（§3 门控铁律 + §2 节说明 + 不新增节号）→ Task 2 Step 1/2/5
- ✅ 验收 3（SKILL 选 lens 两横切 + 红线 8 + 两段式审查各加一项）→ Task 3 Step 1/2/3/4
- ✅ 验收 4（lint 不误伤 docs/stock-analytics）→ Task 4 Step 1
- ✅ 验收 5（仅追加/微调不删除现有 lens/红线）→ Task 4 Step 3
- ✅ spec 改动 1 的 §4 指针（playbook 加成长 lens 指引）→ Task 2 Step 3

**Placeholder scan:** 无 TBD/TODO；所有插入文本为完整可直接 Edit 的内容；"N 季/Top-N/≤20%"为刻意模板占位（与现有 lens/playbook 风格一致），非计划缺口。

**Type/术语 consistency:** 三文件统一术语「成长持续性证据包」+ 三要素「扩产达产确定性 / 客户 capex 能见度 / TAM 跑道」；Task 4 Step 2 显式做术语漂移检查。门控阈值表述统一为「证据全软则 bull 概率封顶（≤20%）」。

**风险点:** Edit 的 old_string 必须与文件当前内容逐字匹配。执行前若文件已被其他 session 改动，行号会漂移——执行者应以 old_string 文本内容（而非行号）为准定位，行号仅作参考。
