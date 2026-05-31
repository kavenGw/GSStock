# stock-deep-redo 优化（物理删除旧档 + 可扩展 sector-lens）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 给 `stock-deep-redo` 编排 skill 加三项能力：替换旧档改为物理删除、新增可扩展 sector-lens 注册表（AI/PCB/存储）、把 lens 与删除收尾接进 SKILL.md 与 playbook.md。

**Architecture:** 纯 markdown skill 文件编辑，无代码、无 pytest。本 skill 是"提示词编排文档"，验证手段是 grep 关键锚点 + 人工读校 + 跑现有 docs lint 确保没破坏文档库。新增一个 reference 文件（sector-lenses.md），改两个既有文件（SKILL.md、playbook.md）。三块改动彼此低耦合，按 B（新文件，零依赖）→ A（删除语义）→ C（接入）顺序做，每块独立 commit。

**Tech Stack:** Markdown；`scripts/lint_docs_frontmatter.py` / `scripts/lint_docs_refs.py`（仅用于回归确认未破坏文档库）；`rg`(ripgrep) 做锚点校验；Windows PowerShell + `rtk git`。

**关键约束（贯穿全程）：**
- sector-lens 只写"必查调查清单/问题"，**严禁写死会过时的事实**（Rubin 时间表、存储报价、退出范围等一律标注"实时联网采证"）。
- 所有 git 命令前缀 `rtk`。
- 写含中文的 markdown 用 Write 工具（已 UTF-8），不用 PowerShell heredoc。
- 验证锚点用 Grep 工具（不用 PowerShell `Select-String`，可能吞输出）。

---

## File Structure

| 文件 | 责任 | 动作 |
|------|------|------|
| `.claude/skills/stock-deep-redo/references/sector-lenses.md` | 可扩展板块视角注册表，每 subsector 一节五段式调查清单 | **新建** |
| `.claude/skills/stock-deep-redo/SKILL.md` | 顶层编排：默认参数、先做步骤、Phase A/B/C 派发、质量红线 | 修改 |
| `.claude/skills/stock-deep-redo/references/playbook.md` | 撰写/审查 subagent 必读细则：§4 精简为指针、Phase C 骨架加删除收尾 | 修改 |

参考（只读，不改）：`docs/superpowers/specs/2026-05-31-stock-deep-redo-sector-lens-design.md`（设计源）。

---

## Task 1：新建 sector-lenses.md（块 B）

**Files:**
- Create: `.claude/skills/stock-deep-redo/references/sector-lenses.md`

- [ ] **Step 1：写注册表文件**

用 Write 工具创建 `.claude/skills/stock-deep-redo/references/sector-lenses.md`，完整内容如下：

```markdown
# sector-lenses（板块专属视角注册表 · 撰写/审查 subagent 按命中节必读）

> 控制者按识别出的 subsector 挑选命中的 lens 节，把对应内容注入 Phase A 采证 / Phase B 撰写提示。
> **可叠加多选**：一只股可同时命中多套（如 PCB + AI）。AI 是横切 lens，默认对每只股都跑识别。
>
> **铁律**：本文件只写「必查调查清单 / 问题」，**绝不写死会过时的事实**（具体时间表、报价、退出范围
> 等一律由 Phase A 实时联网采证）。看到本文件里出现具体数字/日期即是 bug。

每节统一五段式：
1. **【识别信号】** — 命中本 lens 的 subsector / 关键词 / 业务特征
2. **【必查清单（采证 face）】** — Phase A 必须联网核实的问题
3. **【撰写落点（撰写 face）】** — 发现落到正文哪些节
4. **【双面必答】** — 本 lens 最强反驳点，正文必须正面写
5. **【监控指标模板】** — 带阈值、可执行的卖出/复盘触发器候选

---

## AI（横切 · 默认对每只股跑识别）

### 【识别信号】
- 任何标的都先判：AI 是不是**真业绩驱动**，还是仅蹭概念。
- 强信号：sector=ai-application；或主营/在研明确含算力、HBM、AI 服务器、AI 边缘 SoC/MCU、
  CPO/光模块、ASIC/NPU、液冷/电源等 AI 基础设施；或管理层/财报把增长归因到 AI 需求。

### 【必查清单（采证 face）】
- 标的的 AI 敞口是**产品层**（有能力/在研）还是**业绩层**（已贡献可量化营收/订单）？要数字。
- 该 AI 终端市场（如 AI 服务器、推理、边缘）的 TAM 与增速：找第三方机构口径，注明机构间分歧。
- 竞争格局：标的在该 AI 链节卡位（份额/客户/认证），vs 国际龙头差距。
- 兑现节奏：放量时间表、在手订单/产能锁定、客户导入阶段（送样/小批/量产）。
- 间接 AI 受益（如 AI 挤出大厂产能 → 利基缺口）是否有财报/CEO 归因坐实。

### 【撰写落点（撰写 face）】
- §7 AI/概念潜力：若判定为 AI 真驱动，从"打标签"升级为 **AI 未来前景深挖**
  （TAM 增速 / 竞争格局 / 卡位 / 兑现节奏，明确区分产品层 vs 业绩层）。
- 每个 AI 维度仍结尾打 `【真敏感】` 或 `【蹭概念】` + 一句理由。
- 间接供给侧型 AI 受益落 §6 核心新论点。

### 【双面必答】
- 未兑现的概念**不许进 §9 估值的 owner earnings**；产品层 ≠ 业绩层，后文不得偷偷模糊。
- AI 叙事是否已被市场充分定价（贵不贵）——别用"AI 想象空间"稀释"价格太贵"。

### 【监控指标模板】
- AI 相关营收占比 / 同比增速跌破 X%（兑现证伪）。
- 关键客户导入进度 miss 路线图节点。
- 终端（AI 服务器等）出货/资本开支指引下修。

---

## PCB / CCL

### 【识别信号】
- sector=electronics 且 subsector 含 pcb / components / ccl / 覆铜板 / 载板 / HDI；
- 主营为印制电路板、覆铜板、铜箔、IC 载板、AI 服务器/交换机用高多层板。

### 【必查清单（采证 face）】
- AI 平台（如 Rubin/GB 系列）对高多层/HDI/载板的拉动：联网查**当前**平台时间表、单机价值量、
  拉货节奏（实时采证，勿凭记忆）。
- 标的**扩厂 capex 与产能爬坡**：在建产线、投产时间、达产率、对应增量营收。
- 层数 / ASP / 高多层占比 / 高端料号占比的提升趋势（量价拆分）。
- CCL / 铜箔 / 树脂涨价向标的的成本与售价传导（毛利弹性）。
- HDI / 载板（ABF/BT）升级路径与认证进度。
- 客户集中度与大客户份额变化。

### 【撰写落点（撰写 face）】
- §6 核心新论点：AI 服务器/交换机需求拉动 + 扩产逻辑（结构性 vs 周期性二分）。
- §3 盈利能力：ASP/高端占比驱动的毛利弹性精算。
- §8 周期定位：扩产潮位置（爬坡前期 vs 产能集中释放）。

### 【双面必答】
- 扩产是否埋下未来**产能过剩 / 价格战**风险（同业一起扩）。
- 在手订单/能见度的真实性（框架意向 vs 锁定订单），是否已被股价透支。

### 【监控指标模板】
- 高多层/AI 板营收占比、增速跌破阈值。
- 在建产能达产率 miss 进度、稼动率下滑。
- CCL/铜箔价格与公司提价节奏背离（毛利见顶）。

---

## 存储（memory / storage）

### 【识别信号】
- sector=semiconductor 且 subsector 含 storage / memory / dram / nand / 利基存储；
- 主营为 DRAM / NAND / NOR / 存储模组 / 存储主控。

### 【必查清单（采证 face）】
- 当前 DRAM / NAND 现货价与合约价趋势（实时采证报价，注明来源口径与机构分歧）。
- 三大原厂（SK海力士 / 美光 / 三星）**退出或收缩低端（DDR4 / 利基 DRAM 等）的范围 + 时间表 +
  可逆性**（联网核实，区分公司官方 vs 媒体推测）。
- 利基缺口向标的的传导：标的在让出市场的卡位、能拿到多少份额。
- HBM 对标准 DRAM 产能的挤出效应。
- 库存周期位置（原厂/渠道库存、稼动率、减产进度）。

### 【撰写落点（撰写 face）】
- §6 核心新论点：供给侧出清/退出 → 利基缺口 → 标的受益（结构性 vs 周期性二分判定）。
- §3 盈利能力：涨价弹性与正常化毛利。
- §8 周期定位：当前在涨价周期哪个阶段。

### 【双面必答】
- 大厂退出是否**可逆**（产能可重启、技术可回切）——把最强反驳前置。
- 当前是否已在**周期顶**：估值/价格是否已 price-in 涨价（拒绝用周期顶利润定价）。

### 【监控指标模板】
- DRAM/NAND 合约价环比转跌（涨价证伪）。
- 原厂重启低端产能 / 复产公告。
- 标的存货周转、毛利率见顶回落。

---

> 加新板块只需在本文件追加一节五段式，SKILL.md/playbook.md 无需改动。
```

- [ ] **Step 2：校验五段式锚点齐全**

用 Grep 工具在 `.claude/skills/stock-deep-redo/references/sector-lenses.md` 搜索：
- pattern `【识别信号】` → 期望 3 处（AI/PCB/存储各一）
- pattern `【双面必答】` → 期望 3 处
- pattern `【监控指标模板】` → 期望 3 处

Expected：每个锚点正好 3 次命中。少于 3 说明某节缺段，补齐。

- [ ] **Step 3：校验无硬编码会过时事实（反 bug 扫描）**

用 Grep 工具搜本文件，确认没有写死的具体年份/季度/报价数字混进调查清单：
- pattern `\d{4}年|Q[1-4]\b|\$\d|美元/|元/GB` （宽松扫描）

Expected：理想 0 命中。若命中，逐条人工判断——除"近5年"这类口径词外，凡具体时间表/报价数字必须改写成"实时采证"措辞。

- [ ] **Step 4：Commit**

```bash
rtk git add ".claude/skills/stock-deep-redo/references/sector-lenses.md"
rtk git commit -m "feat(skill): stock-deep-redo 新增可扩展 sector-lens 注册表(AI/PCB/存储)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 2：SKILL.md 替换语义改物理删除 + 接入 lens（块 A + 块 C 的 SKILL 部分）

**Files:**
- Modify: `.claude/skills/stock-deep-redo/SKILL.md`

> 注：下列 Edit 的 old_string 取自当前文件。执行前先 Read 整个 SKILL.md 确认行文未被并行 session 改动；若 old_string 不匹配，按同义定位重新截取。

- [ ] **Step 1：改默认参数表「产出形态」行**

Edit `.claude/skills/stock-deep-redo/SKILL.md`：

old_string:
```
| 产出形态 | 新建一份 buffett 深度档（`conviction_date` = 今天），supersede 旧档（旧档保留，related_docs 互链） |
```
new_string:
```
| 产出形态 | 新建一份 buffett 深度档（`conviction_date` = 今天）+ `git rm` 该股**所有历史 buffett 档**（只删 buffett 档；comps/theme/quarterly 一律保留），目录只留最新一份 |
```

- [ ] **Step 2：在「先做（控制者本人）」加 lens 识别 + 待删旧档清单**

Edit `.claude/skills/stock-deep-redo/SKILL.md`，定位「先做（控制者本人）」整块：

old_string:
```
### 先做（控制者本人）
1. 用 Glob 找该股已有底稿：`docs/stock-analytics/**/*<股票名>*.md`（buffett / comps / quarterly / theme）。
   挑出最新 buffett 档 + 最相关 comps 作为基线，传给后续 subagent。
2. 确认股票代码、市场（A/US/HK）、sector/subsector 归属。
```
new_string:
```
### 先做（控制者本人）
1. 用 Glob 找该股已有底稿：`docs/stock-analytics/**/*<股票名>*.md`（buffett / comps / quarterly / theme）。
   挑出最新 buffett 档 + 最相关 comps 作为基线，传给后续 subagent。
2. 确认股票代码、市场（A/US/HK）、sector/subsector 归属。
3. **列待删旧档清单**：从上面 Glob 结果筛出该股所有历史 buffett 档（`*buffett*.md`）。删前**先 Read 一眼
   确认确属同股旧 buffett 档**（CLAUDE.md 铁律：删除前看目标；若内容与预期严重不符或并非同股，停下 surface
   给用户，不照删）。把确认后的待删清单传给 Phase C。
4. **选 sector-lens**：按 subsector 从 `references/sector-lenses.md` 挑命中的 lens 节（**可叠加**：主 lens
   如 PCB/存储 + 横切 AI lens 默认跑识别）。把命中节的【必查清单】【撰写落点】摘出，分别注入 Phase A / Phase B 提示。
```

- [ ] **Step 3：Phase A 派发提示加 lens 必查清单注入**

Edit `.claude/skills/stock-deep-redo/SKILL.md`，定位 Phase A 块的「详细采证清单与字段见 references/playbook.md。」一行：

old_string:
```
- 详细采证清单与字段见 `references/playbook.md`。
```
new_string:
```
- **注入命中 lens 的【必查清单】**（来自 `references/sector-lenses.md` 命中节）：要求逐条联网核实，
  查不到就明写"未找到公开证据"，不许跳过。
- 详细采证清单与字段见 `references/playbook.md`。
```

- [ ] **Step 4：Phase B 派发提示加 lens 撰写落点注入**

Edit `.claude/skills/stock-deep-redo/SKILL.md`，定位 Phase B 块结尾「13 节模板...撰写 subagent 必须先读它。」：

old_string:
```
**只跑 `lint_docs_frontmatter.py`，不跑 refs**（对称留给 Phase C）。13 节模板、frontmatter 字段、场景加权
估值机制、AI 四维度标签法、质量红线全部在 `references/playbook.md`，撰写 subagent 必须先读它。
```
new_string:
```
**只跑 `lint_docs_frontmatter.py`，不跑 refs**（对称留给 Phase C）。13 节模板、frontmatter 字段、场景加权
估值机制、AI 维度标签法、质量红线全部在 `references/playbook.md`，撰写 subagent 必须先读它。
**注入命中 lens 的【撰写落点】**（来自 `references/sector-lenses.md` 命中节）：要求对应节按落点深化，
命中 lens 的每个必查项都要在正文有回应（查无证据也要写明）。
```

- [ ] **Step 5：Phase C 收尾加删除旧档 + 反向链改指**

Edit `.claude/skills/stock-deep-redo/SKILL.md`，定位 Phase C 整块：

old_string:
```
### Phase C — 收尾（派 1 个 subagent，sonnet 足够）
- 给被链的旧档/comps 补反向 related_docs 条目（symmetric: true 的那些）。
- `python scripts/lint_docs_refs.py --rewrite-blocks` 重生顶部块（别手编 `<!-- BEGIN/END related_docs -->`）。
- `lint_docs_frontmatter.py` + `lint_docs_refs.py` **都要 exit 0**。
- 确认一次性采证脚本已删、evidence.md 未被 add。
- 提交终稿。
```
new_string:
```
### Phase C — 收尾（派 1 个 subagent，sonnet 足够）
- **删除旧档**：对"先做"传来的待删清单逐个 `git rm`（该股历史 buffett 档）。
- **反向链改指**：扫所有 `symmetric: true` 指向被删档的反向条目（别的 comps/theme/quarterly 的
  related_docs）→ 改指到新档，或删除该条目（防 refs lint 悬空报错）。
- 给被链的旧档/comps 补反向 related_docs 条目（symmetric: true 的那些）。
- `python scripts/lint_docs_refs.py --rewrite-blocks` 重生顶部块（别手编 `<!-- BEGIN/END related_docs -->`）。
- `lint_docs_frontmatter.py` + `lint_docs_refs.py` **都要 exit 0**；`--check-orphans` 确认新档非孤儿。
- 确认一次性采证脚本已删、evidence.md 未被 add。
- 提交终稿。
```

- [ ] **Step 6：质量红线加「替换=物理删除」条**

Edit `.claude/skills/stock-deep-redo/SKILL.md`，定位质量红线第 6 条之后（`6. **数字可追溯**...无造数。`）追加第 7 条：

old_string:
```
6. **数字可追溯**：正文每个关键数字能回指 evidence.md 或基线底稿；无裸断言、无造数。
```
new_string:
```
6. **数字可追溯**：正文每个关键数字能回指 evidence.md 或基线底稿；无裸断言、无造数。
7. **替换=物理删除旧档**：新档落定后该股历史 buffett 档必须 `git rm`，且所有指向旧档的 symmetric 反向链
   改指到新档——目录里同股只留最新一份，refs lint 无悬空引用。
```

- [ ] **Step 7：「参考文件」加 sector-lenses.md 指针**

Edit `.claude/skills/stock-deep-redo/SKILL.md`，定位参考文件首条（`- references/playbook.md ...`）：

old_string:
```
- `references/playbook.md` — 13 节模板、frontmatter 字段集 + rating 枚举、场景加权估值机制、AI 四维度标签法、采证清单、qt.gtimg.cn 字段、lint 命令、各 subagent 派发提示骨架。**撰写/审查 subagent 必读。**
```
new_string:
```
- `references/playbook.md` — 13 节模板、frontmatter 字段集 + rating 枚举、场景加权估值机制、采证清单、qt.gtimg.cn 字段、lint 命令、各 subagent 派发提示骨架。**撰写/审查 subagent 必读。**
- `references/sector-lenses.md` — 可扩展板块视角注册表（AI/PCB/存储…），每 subsector 一节五段式调查清单。**命中 lens 的撰写/审查 subagent 必读对应节。**
```

- [ ] **Step 8：校验改动锚点**

用 Grep 工具在 `.claude/skills/stock-deep-redo/SKILL.md` 验证：
- pattern `git rm` → 期望 ≥2 处（默认表 + Phase C + 红线 7，实际 ≥2 即可）
- pattern `sector-lenses` → 期望 ≥3 处（先做选 lens + Phase A + Phase B + 参考文件）
- pattern `待删清单` → 期望 ≥2 处（先做 + Phase C 呼应）

Expected：均命中。缺失说明某步 Edit 未生效，回查。

- [ ] **Step 9：Commit**

```bash
rtk git add ".claude/skills/stock-deep-redo/SKILL.md"
rtk git commit -m "feat(skill): stock-deep-redo 替换语义改物理删除旧档 + 接入 sector-lens

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3：playbook.md §4 精简为指针 + Phase C 骨架同步（块 C 的 playbook 部分）

**Files:**
- Modify: `.claude/skills/stock-deep-redo/references/playbook.md`

> 执行前先 Read 整个 playbook.md 确认行文未被并行改动。

- [ ] **Step 1：§4 AI 维度标签法 → 精简为指向 sector-lenses 的指针**

Edit `.claude/skills/stock-deep-redo/references/playbook.md`，定位 §4 整节：

old_string:
```
## 4. AI 维度标签法

逐维度写，**每维度结尾打 `【真敏感】` 或 `【蹭概念】` + 一句理由**。常见四维度（按标的取舍）：
1. 间接供给侧（AI/HBM 挤出大厂产能 → 利基缺口 → 标的受益）——通常最硬，若有财报/CEO 归因则【真敏感】
2. 边缘 AI 产品（MCU/SoC 的 AI 能力）——区分**产品层 vs 业绩层**：有产品能力≠有营收贡献
3. 算力卡/服务器周边（boot NOR、配套存储等）——查是否真切入 + 有无份额拆分
4. 自身高端 AI 产品（HBM/高端 DRAM/NPU/ASIC）——没有就诚实写【蹭概念/缺位】，作空头论据

红线：未兑现的概念不许进 §9 估值的 owner earnings；产品/业绩区分不能在后文被偷偷模糊。
```
new_string:
```
## 4. AI 维度标签法 → 见 sector-lenses.md「AI」节

AI 视角已统一到 `references/sector-lenses.md` 的 **AI（横切）** 节，避免两处维护。要点：逐维度写，
**每维度结尾打 `【真敏感】` 或 `【蹭概念】` + 一句理由**；区分**产品层 vs 业绩层**；
未兑现的概念不许进 §9 估值的 owner earnings。命中 AI lens 时撰写 subagent 读该节的【撰写落点】。
```

- [ ] **Step 2：Phase C 派发骨架同步删除旧档 + 反向链改指**

Edit `.claude/skills/stock-deep-redo/references/playbook.md`，定位 §8 末尾「Phase C 收尾」骨架行：

old_string:
```
**Phase C 收尾**：先 `git status` 查遗留改动；给要补反向条目的被链档路径 + 反向 YAML；跑 `--rewrite-blocks` + 双 lint
exit 0；确认采证脚本已删、evidence.md 未 add；提交终稿；汇报双 lint 退出码 + SHA + 状态。
```
new_string:
```
**Phase C 收尾**：先 `git status` 查遗留改动；**`git rm` 控制者传来的待删旧 buffett 档清单**；
**把所有 symmetric 指向被删档的反向链改指到新档或删条目**；给要补反向条目的被链档路径 + 反向 YAML；
跑 `--rewrite-blocks` + 双 lint exit 0 + `--check-orphans` 确认新档非孤儿；确认采证脚本已删、evidence.md 未 add；
提交终稿；汇报双 lint 退出码 + SHA + 状态。
```

- [ ] **Step 3：Phase B 派发骨架去掉「AI 四维度」措辞，引 sector-lens**

Edit `.claude/skills/stock-deep-redo/references/playbook.md`，定位 §8 的「Phase B 撰写」骨架行：

old_string:
```
13 节结构（§2）+ 场景加权机制（§3）+ AI 标签法（§4）+ 6 条质量红线（SKILL.md）；给关键事实锚（实时市值/PE/PB
```
new_string:
```
13 节结构（§2）+ 场景加权机制（§3）+ 命中 lens 的【撰写落点】（sector-lenses.md）+ 7 条质量红线（SKILL.md）；给关键事实锚（实时市值/PE/PB
```

- [ ] **Step 4：目录索引同步（§4 标题变了）**

Edit `.claude/skills/stock-deep-redo/references/playbook.md`，定位顶部目录第 4 行：

old_string:
```
4. [AI 维度标签法](#4-ai-维度标签法)
```
new_string:
```
4. [AI 维度标签法 → sector-lenses](#4-ai-维度标签法--见-sector-lensesmd-ai-节)
```

- [ ] **Step 5：校验锚点**

用 Grep 工具在 `.claude/skills/stock-deep-redo/references/playbook.md` 验证：
- pattern `sector-lenses` → 期望 ≥3 处（§4 指针 + Phase B 骨架 + §4 标题）
- pattern `git rm` → 期望 ≥1 处（Phase C 骨架）
- pattern `7 条质量红线` → 期望 1 处（与 SKILL.md 红线条数一致）

Expected：均命中。

- [ ] **Step 6：Commit**

```bash
rtk git add ".claude/skills/stock-deep-redo/references/playbook.md"
rtk git commit -m "feat(skill): stock-deep-redo playbook §4 收敛到 sector-lens + Phase C 删档骨架

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 4：回归验证 + 一致性收尾

**Files:**（只读验证，无修改）

- [ ] **Step 1：文档库 lint 未被破坏**

本次只改 skill 文件，未动 `docs/stock-analytics/`，但跑一遍确认环境与既有文档库仍干净：

```bash
rtk PYTHONIOENCODING=utf-8 python scripts/lint_docs_frontmatter.py
rtk PYTHONIOENCODING=utf-8 python scripts/lint_docs_refs.py
```

Expected：两条均 exit 0（若既有库本就有历史 lint 债，记录但不在本任务修——确认非本次改动引入即可）。

- [ ] **Step 2：质量红线条数一致性**

用 Grep 工具确认 SKILL.md 红线编号到 7、playbook.md 引用也写「7 条」：
- SKILL.md pattern `^7\. \*\*替换` → 1 处
- playbook.md pattern `7 条质量红线` → 1 处

Expected：均命中，编号一致（避免 Task2 写 7 条、Task3 漏改成 6 条的偏差）。

- [ ] **Step 3：三文件交叉引用闭环**

用 Grep 工具确认引用闭环无断点：
- SKILL.md 提到 `sector-lenses.md`（Task2 已加）
- playbook.md 提到 `sector-lenses`（Task3 已加）
- sector-lenses.md 文件存在（Task1）

Expected：三者互指，无指向不存在文件的死链。

- [ ] **Step 4：lens 叠加可用性人工抽查（read-through）**

人工读 `sector-lenses.md`，按两个真实标的走查命中逻辑：
- 沪电股份（PCB + AI 服务器驱动）→ 应命中 **PCB 节 + AI 节** 两套，必查清单不冲突、撰写落点都落 §6/§7。
- 兆易创新（存储 + AI 边缘概念）→ 应命中 **存储节 + AI 节**，存储【双面必答】含"退出可逆/周期顶"。

Expected：两标的都能从注册表挑出 ≥2 节且内容自洽。若某节缺识别信号导致挑不中，回 Task1 补【识别信号】。

- [ ] **Step 5：终态 git 确认**

```bash
rtk git log --oneline -4
rtk git status
```

Expected：3 个 feat commit（Task1/2/3）按序在链上；工作区无遗留本任务的未提交改动（立讯精密那条并行 session 的 staged rename 不属本任务，保持原样勿动）。

---

## Self-Review（计划自检结果）

- **Spec 覆盖**：块 A（删除语义）→ Task2 Step1/2/5/6 + Task3 Step2；块 B（注册表）→ Task1；
  块 C（接入）→ Task2 Step2-4/7 + Task3 Step1/3/4。三块全覆盖，含「不做」边界（注册表只写清单不写死事实，
  由 Task1 Step3 反 bug 扫描守住）。
- **占位符扫描**：无 TBD/TODO；每个 Edit 步给出完整 old/new 文本；每个校验步给出具体 Grep pattern 与期望命中数。
- **类型/命名一致**：质量红线条数 6→7 的连锁改动在 Task2 Step6（加第7条）、Task3 Step3（引"7 条"）、
  Task4 Step2（一致性校验）三处对齐；`sector-lenses.md` 文件名全程拼写一致；五段式锚点
  （【识别信号】/【必查清单】/【撰写落点】/【双面必答】/【监控指标模板】）Task1 定义、Task4 Step4 复用一致。
- **风险点**：Edit 的 old_string 依赖当前文件原文，已在 Task2/Task3 开头要求"先 Read 确认、不匹配则重新截取"，
  应对并行 session 改动。
