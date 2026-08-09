# stock-deep-redo 提速 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 stock-deep-redo 的单次完整跑动墙钟从实测 ~40min 压到 ~29min，且不降分析深度。

**Architecture:** 三根无损杠杆，全部落在 skill 指令文本上——(1) 各 subagent 汇报改为写固定路径文件、控制者直接 Read，消除追要报告的往返；(2) Phase A 由单 agent 顺序跑六块拆成三路并行采证（A1 数据锚 / A2 论点 / A3 lens），A1 定为数字唯一权威源；(3) 控制者强制内联注入命中 lens 与兄弟档口径，不让 Phase B 写手再去读整份 sector-lenses.md 和兄弟档全文。附加一条耗时度量，让提速可证伪。

**Tech Stack:** Markdown（skill 指令）。无代码改动，无依赖变更。验证靠 grep 断言 + 下一只股实跑。

## Global Constraints

以下约束来自 spec，**每个任务都隐含包含**：

- **深度不降**：不给正文加篇幅上限，不删 13 节结构中的任何一节。
- **Phase B 不拆**：撰写始终是单一 opus 写手，不拆多写手、不做提前开工的流水线重叠。
- **不降模型档位**：Phase A/B 保持 opus，审查/Phase C 保持 sonnet。
- **改动面仅限两份文件**：`.claude/skills/stock-deep-redo/SKILL.md` 与 `.claude/skills/stock-deep-redo/references/playbook.md`。不碰 `app/`、不碰其他 skill、不需要 worktree（投研 skill 改动按分支策略在 main 直接提交）。
- **A1 是唯一数字权威源**：所有行情/财务硬数字以 A1 片段为准，A2/A3 冲突时一律让位。
- **阶段标识固定六种**：`phaseA1` / `phaseA2` / `phaseA3` / `phaseB` / `review` / `phaseC`。
- **目标值**：40min → ~29min。
- Windows 环境：跑 python 加 `PYTHONIOENCODING=utf-8`；写中文文件显式 `encoding='utf-8'`；`git add` 与 `git commit` 必须同一条命令链（并行 session 会抢 index）。

---

## File Structure

| 文件 | 职责 | 本次改动 |
|---|---|---|
| `.claude/skills/stock-deep-redo/SKILL.md` | 总编排：默认参数、歧义门、四棒派发的**做什么** | 先做第 4 步、Phase A 段、Phase B 段、审查段、Phase C 段、控制者收尾段 |
| `.claude/skills/stock-deep-redo/references/playbook.md` | 规格细节：13 节模板、frontmatter、估值铁律、**派发提示骨架（§9）** | §9 新增「汇报文件协议」共享块；Phase A 骨架拆三；Phase B/审查/Phase C 骨架挂协议 |

两文件的分工边界不变：SKILL.md 说「派谁、做什么」，playbook §9 说「prompt 骨架长什么样」。本次所有新增约定放 playbook §9 作单一定义点，SKILL.md 只引用，避免两处维护漂移。

---

### Task 1: 在 playbook §9 定义「汇报文件协议」共享块

这是后续所有任务引用的接口，必须先落地。

**Files:**
- Modify: `.claude/skills/stock-deep-redo/references/playbook.md:200-205`（§9 开头，`## 9. subagent 派发提示骨架` 之后、`**Phase A 采证**` 之前插入）

**Interfaces:**
- Consumes: 无（本任务是起点）
- Produces: 后续 Task 2/3/4 引用的两个约定——
  - 汇报文件路径模板 `.omc/artifacts/<股票名>-<日期>-<阶段标识>-report.md`
  - 六个阶段标识字面量：`phaseA1` `phaseA2` `phaseA3` `phaseB` `review` `phaseC`
  - 报告文件头两行的时间戳格式：`start: YYYY-MM-DD HH:MM:SS` / `end: YYYY-MM-DD HH:MM:SS`

- [ ] **Step 1: 确认当前 §9 开头原文未被他人改动**

Run:
```bash
cd /d/Git/stock && sed -n '200,206p' .claude/skills/stock-deep-redo/references/playbook.md
```

Expected: 输出正是——
```
## 9. subagent 派发提示骨架

每个 subagent 都要给**完整自包含上下文**（别让它读本计划/SKILL，直接喂它需要的）。骨架：

**Phase A 采证**：交代标的+代码+市场+今天日期+知识截止须联网；给 evidence.md 结构（见 §5）；
给 qt.gtimg.cn 取数脚本（见 §6）；强调证据分级+不造数；要求汇报证据强度 + 实时行情 + 状态。
```
若不一致，停下 surface 给用户——说明有并行 session 改过同一区域。

- [ ] **Step 2: 插入汇报文件协议块**

用 Edit 工具，`old_string`：
```
每个 subagent 都要给**完整自包含上下文**（别让它读本计划/SKILL，直接喂它需要的）。骨架：

**Phase A 采证**
```

`new_string`：
```
每个 subagent 都要给**完整自包含上下文**（别让它读本计划/SKILL，直接喂它需要的）。骨架：

### 9.0 汇报文件协议（所有 subagent 通用，硬约定）

**问题**：实测多数 subagent 完成后只发 idle 通知、不回传汇报正文，控制者须逐个 `SendMessage` 追要，
每次一个完整往返（实测一轮吃掉约 5 分钟）。在 prompt 里写"最终回复必须包含完整正文"**已被证明无效**
（审查 subagent 收到该指令后仍先回 idle）——靠措辞加压治不了，必须改机制。

**约定**：每个 subagent 的派发 prompt 末尾**必须**包含以下要求，一字不可省：

> 汇报**必须**用 Write 写到 `.omc/artifacts/<股票名>-<日期>-<阶段标识>-report.md`，写完才结束。
> 文件头两行固定为耗时戳（开工时与收工时各跑一次 `date "+%Y-%m-%d %H:%M:%S"` 取值）：
> ```
> start: YYYY-MM-DD HH:MM:SS
> end: YYYY-MM-DD HH:MM:SS
> ```
> 其后是汇报正文。消息回传是可选冗余通道，不是交付方式。

**阶段标识固定六种**：`phaseA1` / `phaseA2` / `phaseA3` / `phaseB` / `review` / `phaseC`。

**控制者侧**：不等消息、不追要报告，subagent 结束后直接 `Read` 对应文件。收尾时把六个 start/end
汇总成一行耗时账报给用户（这是"提速是否真的发生"的唯一可证伪依据）。

**为什么顺带加固了可信度**：subagent 的口头汇报本就不可信（已有教训：Phase A 曾自报"一次性脚本已删"
而实际未删）。落成文件后，控制者的亲验对象从"它说了什么"变成"它写了什么 + 我自己查到什么"。

**Phase A 采证**
```

- [ ] **Step 3: 验证协议块已落地且六个标识齐全**

Run:
```bash
cd /d/Git/stock && for s in phaseA1 phaseA2 phaseA3 phaseB review phaseC; do echo -n "$s: "; grep -c "$s" .claude/skills/stock-deep-redo/references/playbook.md; done && grep -c "9.0 汇报文件协议" .claude/skills/stock-deep-redo/references/playbook.md
```

Expected: 六个标识每个计数 ≥1，最后一行输出 `1`。任一为 0 即失败。

- [ ] **Step 4: 验证 frontmatter lint 未被波及**

Run:
```bash
cd /d/Git/stock && PYTHONIOENCODING=utf-8 python scripts/lint_docs_frontmatter.py; echo "EXIT=$?"
```

Expected: `EXIT=0`（本任务不碰 docs，此步是防误伤的兜底）。

- [ ] **Step 5: Commit**

```bash
cd /d/Git/stock && git add .claude/skills/stock-deep-redo/references/playbook.md && git commit -m "feat(skill): stock-deep-redo 新增汇报文件协议——subagent 汇报写文件，消除 idle 追要往返

实测 3/4 subagent 完成后只回 idle 通知，prompt 明写必须回正文仍无效。
改机制：汇报写 .omc/artifacts/<股票名>-<日期>-<阶段标识>-report.md，
头两行记 start/end 耗时戳，控制者直接 Read 不等消息。

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Phase A 拆三路并行采证

**Files:**
- Modify: `.claude/skills/stock-deep-redo/SKILL.md:64-72`（`### Phase A — 联网采证` 整段）
- Modify: `.claude/skills/stock-deep-redo/references/playbook.md`（§9 的 `**Phase A 采证**` 骨架段，即 Task 1 插入块之后那段）

**Interfaces:**
- Consumes: Task 1 的汇报文件协议与阶段标识 `phaseA1` / `phaseA2` / `phaseA3`
- Produces: 三个 evidence 片段文件名，Task 3 的 Phase B 段要引用——
  - `.omc/artifacts/<股票名>-<日期>-evidence-A1-数据锚.md`
  - `.omc/artifacts/<股票名>-<日期>-evidence-A2-论点.md`
  - `.omc/artifacts/<股票名>-<日期>-evidence-A3-lens.md`

- [ ] **Step 1: 确认 SKILL.md Phase A 段原文未被改动**

Run:
```bash
cd /d/Git/stock && sed -n '64,72p' .claude/skills/stock-deep-redo/SKILL.md
```

Expected: 首行为 `### Phase A — 联网采证（派 1 个 subagent，opus）`，末行为 `- 详细采证清单与字段见 \`references/playbook.md\`。`。不一致则停下 surface。

- [ ] **Step 2: 整段替换 SKILL.md 的 Phase A**

用 Edit 工具，`old_string` 为上一步 sed 输出的完整九行，`new_string`：

```
### Phase A — 联网采证（派 **3 个并行** subagent，均 opus）

**并行，不串行**——六大采证块之间无依赖，单 agent 顺序跑完实测 ~7min，拆三路 ~4min。
三个 agent 各写各的 evidence 片段，**不派合并 agent**（合并会把省下的时间又串回去），Phase B 同时读三份。

| Agent | 负责 | evidence 片段 | 汇报文件（见 playbook §9.0）|
|---|---|---|---|
| **A1 数据锚** | 实时行情双源交叉 + 市值自洽校验、最新财报、逐月交付/出货、可比公司估值表 | `-evidence-A1-数据锚.md` | `-phaseA1-report.md` |
| **A2 论点验证** | 核心多空论点逐条联网核实（最重的一块，决定整轮墙钟）| `-evidence-A2-论点.md` | `-phaseA2-report.md` |
| **A3 lens 专项** | 命中 lens 的【必查清单】逐条核实（AI / 成长 / 板块 lens）| `-evidence-A3-lens.md` | `-phaseA3-report.md` |

（片段与汇报均落 `.omc/artifacts/`，已 gitignore、不入库。）

**A1 是所有行情/财务硬数字的唯一权威源**（铁律）：A2/A3 涉及数字时以定性表述为主，
与 A1 冲突一律以 A1 为准；要求 Phase B 发现冲突时在正文显式标注，不得静默取一个。

**三路共同纪律**：
- WebSearch/WebFetch 英文+中文交叉验证；区分公司官方 vs 媒体 vs 分析师。
- **证据分级**：【硬】=公司公告/财报/官方 EOL；【软】=媒体/分析师推测；【缺】=未找到。找不到就写"未找到公开证据"，**绝不编造数字或来源**，每个关键数字挂一个真实 URL + 日期。

**A1 专属**：实时行情直连腾讯 HTTP（比走 service 快且无副作用）。**A 股与港股字段索引不同，不可照搬**：
- A 股 `qt.gtimg.cn/q=sh<code>`（6 开头 sh、0/3 开头 sz），GBK 解码、`~` 分隔，`[1]=name [3]=price [39]=PE_TTM [45]=市值(亿) [46]=PB`
- **港股 `q=hk<code>` 索引异于 A 股**，勿套用上面的 39/45/46——先把整串字段 dump 出来自行辨认，
  并用 **市值 = 现价 × 总股本** 自洽校验兜底（详见 `.claude/rules/data-fetch-conventions.md` 腾讯HTTP节）
- 港股/美股市值、PE、PB、52 周区间**必须交叉验证 2 源**（stockanalysis.com / Yahoo / 富途），市值口径常分歧
- 脚本跑完即删，控制者会亲验

**"相对旧档变化清单"不由 A1/A2/A3 写**——它需要全局视野，任何单路都写不了，**移交 Phase B**
（Phase B 本就要读全部三份 evidence + 旧档，天然有全局视野，不增加串行时间）。

- 详细采证清单与字段见 `references/playbook.md`。
```

- [ ] **Step 3: 替换 playbook §9 的 Phase A 骨架**

用 Edit 工具，`old_string`：
```
**Phase A 采证**：交代标的+代码+市场+今天日期+知识截止须联网；给 evidence.md 结构（见 §5）；
给 qt.gtimg.cn 取数脚本（见 §6）；强调证据分级+不造数；要求汇报证据强度 + 实时行情 + 状态。
```

`new_string`：
```
**Phase A 采证（3 个并行，均 opus）**：三份 prompt 都要交代标的+代码+市场+今天日期+知识截止须联网、
证据分级+不造数、§9.0 汇报文件协议（标识分别 `phaseA1`/`phaseA2`/`phaseA3`）。各自差异：

- **A1 数据锚**：给 qt.gtimg.cn 取数脚本（见 §6）**并强调港股字段索引异于 A 股、须 dump 全串自辨 +
  市值=现价×总股本自洽校验 + 双源交叉**；要它产出 `-evidence-A1-数据锚.md`（行情锚 / 最新财报 /
  逐月交付 / 可比公司估值表）；明告它**是本轮所有硬数字的唯一权威源**，另两路会让位于它。
- **A2 论点验证**：给旧档核心论点清单 + 本次重审触发的新变量；要它逐条联网核实、每条给
  证据（硬/软/缺）+ URL + 日期 + **反驳点**，产出 `-evidence-A2-论点.md`；
  **明告它数字以 A1 为准、自己以定性表述为主**。
- **A3 lens 专项**：**把命中 lens 的【必查清单】原文内联进 prompt**（不是给文件路径让它自己去读，
  见 §9.1），要求逐条核实、查不到明写"未找到公开证据"不许跳过，产出 `-evidence-A3-lens.md`。

**不派合并 agent**（合并把省下的时间串回去）；**"相对旧档变化清单"移交 Phase B**（需全局视野）。
```

- [ ] **Step 4: 验证两份文件都已改到位、旧的单 agent 措辞已消失**

Run:
```bash
cd /d/Git/stock/.claude/skills/stock-deep-redo && echo "--- 应为 0（旧措辞已消失）:" && grep -c "联网采证（派 1 个 subagent" SKILL.md; echo "--- 应为 1（新措辞已落地）:" && grep -c "3 个并行" SKILL.md; echo "--- 三个片段名各应 ≥1:" && for f in "evidence-A1-数据锚" "evidence-A2-论点" "evidence-A3-lens"; do echo -n "$f: "; cat SKILL.md references/playbook.md | grep -c "$f"; done; echo "--- A1 权威源铁律应 ≥1:" && grep -c "唯一权威源" SKILL.md
```

Expected: 第一个 `0`；第二个 `1`；三个片段名各 ≥1；权威源 ≥1。

- [ ] **Step 5: 验证港股字段坑已写进 A1 职责（本轮实跑踩过）**

Run:
```bash
cd /d/Git/stock && grep -c "索引异于 A 股" .claude/skills/stock-deep-redo/SKILL.md; grep -c "市值 = 现价 × 总股本" .claude/skills/stock-deep-redo/SKILL.md
```

Expected: 两条均 ≥ `1`。任一为 0 说明 Step 2 的替换漏了港股字段坑那段——补上再继续。

- [ ] **Step 6: Commit**

```bash
cd /d/Git/stock && git add .claude/skills/stock-deep-redo/SKILL.md .claude/skills/stock-deep-redo/references/playbook.md && git commit -m "feat(skill): stock-deep-redo Phase A 拆三路并行采证（7min → ~4min）

A1 数据锚 / A2 论点验证 / A3 lens 专项并行，各写 evidence 片段，不派合并 agent。
A1 定为所有行情/财务硬数字的唯一权威源，A2/A3 冲突让位，Phase B 须显式标注冲突。
相对旧档变化清单移交 Phase B（需全局视野，单路写不了）。
顺带把港股腾讯字段索引异于 A 股的坑写进 A1 职责（本轮零跑实跑踩过）。

代价：3 个 opus 并行，token 成本上升——墙钟优先取舍下接受。

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: 强制内联注入 + Phase B 段

**Files:**
- Modify: `.claude/skills/stock-deep-redo/SKILL.md:59-60`（先做第 4 步「选 sector-lens」）
- Modify: `.claude/skills/stock-deep-redo/SKILL.md:74-79`（`### Phase B — 撰写` 整段）
- Modify: `.claude/skills/stock-deep-redo/references/playbook.md`（§9 的 `**Phase B 撰写**` 骨架段；并新增 §9.1 内联铁律）

**Interfaces:**
- Consumes: Task 1 的汇报协议与标识 `phaseB`；Task 2 的三个 evidence 片段文件名
- Produces: §9.1「内联铁律」小节，Task 2 的 A3 骨架已引用它（`见 §9.1`）——本任务必须真的建出这一节，否则 Task 2 留下悬空引用

- [ ] **Step 1: 确认两处 SKILL.md 原文未被改动**

Run:
```bash
cd /d/Git/stock && echo "--- 先做第4步:" && sed -n '59,60p' .claude/skills/stock-deep-redo/SKILL.md && echo "--- Phase B 段:" && sed -n '74,79p' .claude/skills/stock-deep-redo/SKILL.md
```

Expected: 第一段以 `4. **选 sector-lens**` 开头；第二段以 `### Phase B — 撰写（派 1 个 subagent，opus）` 开头。不一致则停下 surface。

- [ ] **Step 2: 改写「先做第 4 步」为强制内联**

用 Edit 工具，`old_string`：
```
4. **选 sector-lens**：按 subsector 从 `references/sector-lenses.md` 挑命中的 lens 节（**可叠加**：主 lens
   如 PCB/存储 + **两个横切 lens（AI、成长）默认对每只股跑识别**）。把命中节的【必查清单】【撰写落点】摘出，分别注入 Phase A / Phase B 提示。
```

`new_string`：
```
4. **选 sector-lens 并把命中节原文摘出**：按 subsector 从 `references/sector-lenses.md` 挑命中的 lens 节
   （**可叠加**：主 lens 如 PCB/存储 + **两个横切 lens（AI、成长）默认对每只股跑识别**）。
   **控制者必须把命中节的【必查清单】原文内联进 A3 提示、【撰写落点】【双面必答】【监控指标模板】原文内联进
   Phase B 提示——不许只报 lens 名字让 subagent 自己去读整份 sector-lenses.md**（261 行里命中的通常只有
   约 70 行，让它自读是纯浪费，且它可能挑错节）。铁律与理由见 `references/playbook.md` §9.1。
5. **备兄弟档口径摘要**：若同板块有近期兄弟档可参照，控制者**读一遍并提炼成 3-5 行口径要点**
   （如"兄弟档用 TTM 营收作分母 / bull 封顶 20% / 买点取 30% 折价"）备用于 Phase B 提示。
   **不把兄弟档全文塞给写手、也不让它自己去读全文**（实测兄弟档 791 行，真正有用的就那几条）。
```

- [ ] **Step 3: 在 playbook §9 新增 §9.1 内联铁律**

用 Edit 工具，在 §9.0 协议块之后、`**Phase A 采证（3 个并行，均 opus）**` 之前插入。`old_string`：
```
**Phase A 采证（3 个并行，均 opus）**
```

`new_string`：
```
### 9.1 内联铁律：控制者摘原文，不给路径让 subagent 自读

**问题**：让 subagent 自己去读整份参考文件，既费它的墙钟（读+导航往返），又有挑错节的风险。
实测一轮里写手自读了 6 份材料，其中两份是纯浪费：兄弟档 791 行（真正有用的仅 3-5 条口径）、
sector-lenses.md 261 行（命中的仅约 70 行）。

**铁律**：以下内容**由控制者摘成原文内联进 prompt**，**不许给文件路径让 subagent 自读**——

| 内容 | 内联到 | 不许的做法 |
|---|---|---|
| 命中 lens 的【必查清单】 | A3 采证提示 | ❌ "命中 AI + 成长 lens，去读 sector-lenses.md" |
| 命中 lens 的【撰写落点】【双面必答】【监控指标模板】 | Phase B 提示 | ❌ 同上 |
| 兄弟档口径要点（3-5 行） | Phase B 提示 | ❌ "参考兄弟档 xxx.md 的质量水位" |

**仍由 subagent 自读的**（必要，压不掉）：evidence 片段（事实源）、旧档（翻转对照）、
本 playbook（规格）、`Skill buffett`（框架）。

**这条不是新约定，是把既有约定的漏洞堵上**：SKILL.md「先做」本就写着"把命中节摘出注入"，
但措辞允许控制者只报 lens 名字了事——实测控制者确实这么偷懒过。现措辞不留"指路"这个选项。

**Phase A 采证（3 个并行，均 opus）**
```

- [ ] **Step 4: 改写 SKILL.md 的 Phase B 段**

用 Edit 工具，`old_string` 为 Step 1 中 sed 输出的 Phase B 完整六行，`new_string`：

```
### Phase B — 撰写（派 1 个 subagent，opus）

**不拆**——13 节长文的价值很大程度在「§6 论点 → §9 估值 → §10 评级」的链式推导，拆多写手最容易断链。

先 `Skill buffett` 取框架，读 **Phase A 的三份 evidence 片段（A1 数据锚 / A2 论点 / A3 lens）** + 旧档，
按 13 节结构写正文 + frontmatter，跑 frontmatter lint。
**只跑 `lint_docs_frontmatter.py`，不跑 refs**（对称留给 Phase C）；**不 git add/commit**（提交由 Phase C 统一做）。
13 节模板、frontmatter 字段、场景加权估值机制、AI 维度标签法、质量红线全部在 `references/playbook.md`，撰写 subagent 必须先读它。

**控制者必须内联进提示的**（见 `references/playbook.md` §9.1，不许给路径让它自读）：
- 命中 lens 的【撰写落点】【双面必答】【监控指标模板】原文 —— 要求对应节按落点深化，
  命中 lens 的每个必查项都要在正文有回应（查无证据也要写明）
- 兄弟档口径要点 3-5 行 —— 不给兄弟档全文
- A1 片段里的关键事实锚（实时市值/PB/PS/股本/汇率）+ 任何需纠正的旧档错误假设

**Phase B 独有的两项交办**：
- **写"相对旧档变化清单"**（Phase A 三路都写不了，需全局视野）：逐条列旧档口径 vs 最新事实 + 变化方向。
- **标注三路 evidence 的数字冲突**：A1 是唯一权威源，若 A2/A3 与之打架，取 A1 并在正文显式标注，不得静默取一个。

汇报按 `references/playbook.md` §9.0 写文件，标识 `phaseB`。
```

- [ ] **Step 5: 改写 playbook §9 的 Phase B 骨架**

用 Edit 工具，`old_string`：
```
**Phase B 撰写**：要求先 `Skill buffett`；给 evidence.md 路径 + 基线底稿路径；给 frontmatter 模板（§1）+
13 节结构（§2）+ 场景加权机制（§3）+ 命中 lens 的【撰写落点】（sector-lenses.md）+ 7 条质量红线（SKILL.md）；
给关键事实锚（实时市值/PE/PB + 证据硬软分级 + 任何需纠正的错误假设）；要求只跑 frontmatter lint 后提交；汇报评级+期望内在价值+安全边际+SHA+状态。
```

`new_string`：
```
**Phase B 撰写（1 个 opus，不拆）**：要求先 `Skill buffett`；给**三份 evidence 片段路径**（A1/A2/A3）+ 旧档路径；
给 frontmatter 模板（§1）+ 13 节结构（§2）+ 场景加权机制（§3）+ 7 条质量红线（SKILL.md）；
**按 §9.1 内联铁律直接贴入**命中 lens 的【撰写落点】【双面必答】【监控指标模板】原文 + 兄弟档口径要点 3-5 行
（**不给 sector-lenses.md / 兄弟档的路径让它自读**）；给关键事实锚（A1 的市值/PB/PS/股本/汇率 + 硬软分级 +
需纠正的旧档错误假设）；交办两项独有活——**写"相对旧档变化清单"**、**标注 A2/A3 与 A1 的数字冲突**；
要求只跑 frontmatter lint、**不 git add/commit**；汇报按 §9.0 写文件（标识 `phaseB`），内容含评级 +
期望内在价值 + 安全边际 + 最脆弱论点自评。
```

- [ ] **Step 6: 验证内联铁律落地、悬空引用已闭合**

Run:
```bash
cd /d/Git/stock/.claude/skills/stock-deep-redo && echo "--- §9.1 应存在（Task 2 已引用它）:" && grep -c "9.1 内联铁律" references/playbook.md; echo "--- 旧的可偷懒措辞应为 0:" && grep -c "把命中节的【必查清单】【撰写落点】摘出，分别注入" SKILL.md; echo "--- 新的强制措辞应 ≥1:" && grep -c "不许只报 lens 名字让 subagent 自己去读" SKILL.md; echo "--- Phase B 不拆声明应为 1:" && grep -c "拆多写手最容易断链" SKILL.md; echo "--- 三份片段在 Phase B 段被引用，应 ≥2:" && cat SKILL.md references/playbook.md | grep -c "三份 evidence 片段"
```

Expected: §9.1 为 `1`；旧措辞为 `0`；新强制措辞 ≥1；不拆声明为 `1`；三份片段引用 ≥2。

- [ ] **Step 7: 验证 Task 2 留下的 `见 §9.1` 引用不再悬空**

Run:
```bash
cd /d/Git/stock/.claude/skills/stock-deep-redo && grep -n "见 §9.1" references/playbook.md && grep -n "^### 9.1" references/playbook.md
```

Expected: 两条 grep 都有输出——前者是引用点，后者是定义点。定义点缺失即 Task 2 的引用悬空，必须补。

- [ ] **Step 8: Commit**

```bash
cd /d/Git/stock && git add .claude/skills/stock-deep-redo/SKILL.md .claude/skills/stock-deep-redo/references/playbook.md && git commit -m "feat(skill): stock-deep-redo 强制内联注入，收紧 Phase B 输入包（~2-3min）

新增 playbook §9.1 内联铁律：命中 lens 的清单/落点、兄弟档口径要点一律由控制者
摘原文内联进 prompt，不许给路径让 subagent 自读（实测写手自读 6 份材料，
兄弟档 791 行与 sector-lenses 261 行两份是纯浪费）。

这不是新约定，是把既有约定的漏洞堵上——SKILL.md 本就写着'摘出注入'，
但措辞允许只报 lens 名字了事，实测控制者确实这么偷懒过。

同时明确 Phase B 不拆（链式推导怕断链）、不 git add（提交归 Phase C）、
交办'相对旧档变化清单'与'A1 数字冲突标注'两项独有活。

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: 审查段 / Phase C 段 / 控制者收尾段挂协议

**Files:**
- Modify: `.claude/skills/stock-deep-redo/SKILL.md:81-93`（合并审查段，仅追加汇报要求）
- Modify: `.claude/skills/stock-deep-redo/SKILL.md:111`（Phase C 的"确认一次性采证脚本已删"一行）
- Modify: `.claude/skills/stock-deep-redo/SKILL.md:114-116`（`### 收尾（控制者本人）`，加耗时账）
- Modify: `.claude/skills/stock-deep-redo/references/playbook.md`（§9 的合并审查、Phase C 两段骨架结尾）

**Interfaces:**
- Consumes: Task 1 的汇报协议与标识 `review` / `phaseC`；Task 2 的三个 evidence 片段文件名（Phase C 的遗留检查要覆盖三份而非一份）
- Produces: 无（终点任务，无下游消费者）

- [ ] **Step 1: 在审查段末尾追加汇报要求**

用 Edit 工具，`old_string`：
```
**纪律保持**：审查员是独立 subagent（非撰写者自审），撰写≠审查上下文铁律不变。
```

`new_string`：
```
**汇报**：按 `references/playbook.md` §9.0 写文件，标识 `review`——**两段正文都要写进文件**。
审查 subagent 是"只回 idle 不给正文"的重灾区（实测 prompt 明写"最终回复必须包含完整两段"仍先回 idle），
控制者一律读文件，不追要。

**纪律保持**：审查员是独立 subagent（非撰写者自审），撰写≠审查上下文铁律不变。
```

- [ ] **Step 2: Phase C 的遗留检查扩到三份 evidence 片段**

用 Edit 工具，`old_string`：
```
- 确认一次性采证脚本已删、evidence.md 未被 add。
- 提交终稿。
```

`new_string`：
```
- 确认一次性采证脚本已删；**三份 evidence 片段（A1/A2/A3）与六份 report 文件均未被 git add**
  （都在 `.omc/artifacts/`，已 gitignore，但仍要确认）。
- 提交终稿。
- 汇报按 `references/playbook.md` §9.0 写文件，标识 `phaseC`。
```

- [ ] **Step 3: 控制者收尾段加耗时账**

用 Edit 工具，`old_string`：
```
### 收尾（控制者本人）
```

`new_string`：
```
### 收尾（控制者本人）

**先算耗时账**：读六份 report 文件的 `start`/`end` 头（`phaseA1`/`phaseA2`/`phaseA3`/`phaseB`/`review`/`phaseC`），
汇总成一行报给用户，例：`A1 3.2min / A2 4.1min / A3 3.5min（并行取 4.1）+ B 15.5 + 审查 5.5 + C 4.0 ≈ 29min`。
**这是"提速是否真的发生"的唯一可证伪依据**，不许省。基线：2026-08-08 零跑实跑 ~40min。
```

- [ ] **Step 4: playbook §9 的审查与 Phase C 骨架各挂一句汇报协议**

用 Edit 工具，`old_string`：
```
APPROVED-WITH-NITS 的 Minor 可修后控制者直接核验。
```

`new_string`：
```
APPROVED-WITH-NITS 的 Minor 可修后控制者直接核验。
**汇报按 §9.0 写文件（标识 `review`），两段正文全文写进文件**——审查是"只回 idle"的重灾区。
```

再用 Edit 工具，`old_string`：
```
提交终稿；汇报双 lint 退出码 + valuations 同步状态 + SHA + 状态。
```

`new_string`：
```
提交终稿；汇报按 §9.0 写文件（标识 `phaseC`），内容含双 lint 退出码 + valuations 同步状态 + SHA +
`git show --stat HEAD` 文件清单 + 遗留检查结论（三份 evidence 片段与六份 report 均未被 add）。
```

- [ ] **Step 5: 验证六个阶段在 SKILL.md 里都挂上了汇报协议**

Run:
```bash
cd /d/Git/stock/.claude/skills/stock-deep-redo && echo "--- SKILL.md 引用 §9.0 的次数（应 ≥3：Phase B/审查/Phase C）:" && grep -c "§9.0" SKILL.md; echo "--- 耗时账应存在:" && grep -c "先算耗时账" SKILL.md; echo "--- 基线 40min 应被记下:" && grep -c "零跑实跑 ~40min" SKILL.md; echo "--- 三份片段的遗留检查:" && grep -c "三份 evidence 片段（A1/A2/A3）" SKILL.md
```

Expected: §9.0 引用 ≥3；耗时账 `1`；基线 `1`；遗留检查 `1`。

- [ ] **Step 6: 全文一致性终检——不该再有"单个 Phase A subagent"的残留**

Run:
```bash
cd /d/Git/stock/.claude/skills/stock-deep-redo && echo "--- 应为 0（旧的单 agent 派发措辞）:" && grep -c "派 1 个 subagent，opus" SKILL.md; echo "--- 应为 0（旧的单份 evidence.md 产出声明）:" && grep -c "日期>-evidence.md" SKILL.md; echo "--- 总编排标题是否已含并行说明:" && grep -n "^## 总编排" SKILL.md
```

Expected: 前两条为 `0`。第三条（`## 总编排：3 阶段 subagent + 合并审查` 标题）若为 `1`，把标题改成 `## 总编排：3 阶段 subagent（A 三路并行）+ 合并审查` 后重跑，直到为 0 或标题已含并行说明。

- [ ] **Step 7: Commit**

```bash
cd /d/Git/stock && git add .claude/skills/stock-deep-redo/SKILL.md .claude/skills/stock-deep-redo/references/playbook.md && git commit -m "feat(skill): stock-deep-redo 审查/Phase C 挂汇报协议 + 控制者收尾出耗时账

审查段标注为'只回 idle'重灾区，两段正文必须写进文件；
Phase C 遗留检查从单份 evidence 扩到三份片段 + 六份 report；
控制者收尾必须汇总六份 report 的 start/end 成一行耗时账——
这是提速是否真的发生的唯一可证伪依据，基线记为 2026-08-08 零跑 ~40min。

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: 实跑验收

前四个任务改的都是指令文本，**唯一能证伪"提速了"的测试是真跑一只股**。本任务不改文件，只跑并记录。

**Files:**
- 无改动（若实跑暴露问题，问题修复另开任务）

**Interfaces:**
- Consumes: Task 1-4 的全部改动
- Produces: 实测耗时账 + 五条验收结论

- [ ] **Step 1: 挑一只标的实跑**

选一只**已有旧 buffett 档**的标的（这样删旧档/反向链/valuations 同步全链路都会被走到）。
执行 `/stock-deep-redo <股票名>`，全程按新指令跑。

- [ ] **Step 2: 逐条核对五条验收标准**

对照 spec 的验收标准，逐条判定：

| # | 标准 | 判定方式 |
|---|---|---|
| 1 | 指令改动落地、措辞不再允许"让 subagent 自己去读 lens 文件" | Task 3 Step 6 的 grep 已验，此处复核 |
| 2 | 六份 report 均在 `.omc/artifacts/` 落盘，控制者**零次** `SendMessage` 追要报告 | `ls .omc/artifacts/*-report.md \| wc -l` 应为 6；回看本轮有无 SendMessage 追要 |
| 3 | Phase A 三路产出三份片段，Phase B 正文硬数字与 A1 一致 | 抽查 5 个数字（市值/PB/PS/股本/汇率）比对 A1 片段与正文 |
| 4 | 收尾汇报含一行耗时账，总墙钟 < 35min | 读控制者收尾汇报 |
| 5 | 深度不低于当前水位：节数齐全、审查给 SPEC-COMPLIANT + APPROVED | 读 `review` report 文件 |

- [ ] **Step 3: 把实测耗时账追记到 spec**

用 Edit 把实测数字追加到 `docs/superpowers/specs/2026-08-08-stock-deep-redo-提速-design.md` 的
「预期效果」表之后，格式：

```markdown
## 实测结果（<标的名> <日期>）

| 阶段 | 预期 | 实测 |
|---|---|---|
| Phase A（三路并行）| ~4 min | X min |
| Phase B | 15.5 min | X min |
| 审查 | 5.5 min | X min |
| Phase C | 4 min | X min |
| 控制者开销 | ~0（零追要）| X min |
| **合计** | **~29 min** | **X min** |

五条验收标准：<逐条 PASS/FAIL + 说明>
```

- [ ] **Step 4: Commit**

```bash
cd /d/Git/stock && git add "docs/superpowers/specs/2026-08-08-stock-deep-redo-提速-design.md" && git commit -m "docs(spec): stock-deep-redo 提速实测结果回填

<标的名> 实跑验收：合计 X min（基线 40min，目标 29min）。
五条验收标准逐条判定见 spec。

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

- [ ] **Step 5: 若任一验收标准 FAIL，surface 给用户决定**

不要自行加码改造。把 FAIL 项、实测数字、可能原因列清楚交给用户判断是回退、微调还是接受。
**特别注意**：若实测显示三路并行的 token 成本涨幅远超预期，而墙钟只省了 1-2min，
这是"杠杆二不划算"的信号——如实报告，别粉饰。

---

## 不做的事（YAGNI，来自 spec）

- 不给正文加篇幅上限
- 不拆 Phase B 为多写手
- 不做"写手提前开工"的流水线重叠（旧档过时事实会被写进去洗不掉——2026-08-08 零跑旧档就有汇率 0.92、PB 5.13、现金 378 亿三处错值）
- 不让审查与 Phase C 重叠（C 要提交，风险高于 ~3min 收益）
- 不降 Phase B 的模型档位
- **不把汇报协议沉淀成 `.claude/rules/`**：spec 里标为"可选"，但目前**只有 stock-deep-redo 一个消费者**（`analyze-category` 不存在、`news-impact` 零 subagent），为单一消费者建仓库级 rule 是过早抽象。将来出现第二个 subagent 编排 skill 时再抽，成本约 5 行。

## 范围外的已知问题（本计划不处理，留给用户决定）

1. **CLAUDE.md 悬空引用 `analyze-category`**：投研 skill 路由列了它，`.claude/skills/` 下无此目录。
2. **`.claude/skills/stock-deep-redo-workspace/` 是残留物**：skill-creator 跑崩产物（`optim.log` 内容为 `ModuleNotFoundError: No module named 'anthropic'`），含 `trigger-eval.json`。
