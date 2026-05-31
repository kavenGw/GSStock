# NOR Flash 涨价纳入 stock-deep-redo 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 给 stock-deep-redo 的存储 sector-lens 补一条独立的「NOR Flash 涨价」视角,并用新 lens 串行重做普冉(全)/东芯(全)/兆易(NOR 补强)三只 NOR 暴露标的。

**Architecture:** 先在 `.claude/skills/stock-deep-redo/references/sector-lenses.md` 新增独立五段式「存储 — NOR Flash」节(收窄现有存储节为 DRAM/NAND),作为三只个股的共同输入;再按 skill 既有 3 阶段 subagent + 两段审查流程串行重做个股,每只注入 NOR lens(普冉/东芯全重做删旧档,兆易在 5-31 现档原地补强);最后双 lint 收尾验收。

**Tech Stack:** Markdown 文档 + YAML frontmatter;`stock-deep-redo` skill;`scripts/lint_docs_frontmatter.py` + `scripts/lint_docs_refs.py`;实时行情走腾讯 `qt.gtimg.cn`;采证走 WebSearch/WebFetch。

**设计依据:** `docs/superpowers/specs/2026-05-31-nor-flash-涨价-stock-deep-redo-design.md`

**全程约定:** 响应中文;不写多余注释;不写 backup 文件;所有 git 命令前加 `rtk`(链式 `&&` 中也加);Windows 编码坑见 `.claude/rules/dev-conventions.md`。

---

## 文件结构

| 文件 | 责任 | 动作 |
|---|---|---|
| `.claude/skills/stock-deep-redo/references/sector-lenses.md` | NOR lens 五段式 + 收窄存储节 | 修改 |
| `docs/stock-analytics/sectors/semiconductor/storage/2026-05-31-普冉股份-buffett分析.md` | 普冉新档 | 新建 |
| `docs/stock-analytics/sectors/semiconductor/storage/2026-04-25-普冉股份-buffett分析.md` | 普冉旧档 | `git rm` |
| `docs/stock-analytics/sectors/semiconductor/storage/2026-05-31-东芯股份-buffett分析.md` | 东芯新档 | 新建 |
| `docs/stock-analytics/sectors/semiconductor/storage/2026-05-19-东芯股份-buffett分析.md` | 东芯旧档 | `git rm` |
| `docs/stock-analytics/sectors/semiconductor/storage/2026-05-31-兆易创新-buffett分析.md` | 兆易现档(NOR 补强) | 原地修改 |
| `.omc/artifacts/<股票名>-5-31-evidence.md` | 各股采证底稿 | 新建(gitignore,不入库) |

---

## Task 0: 前置校验(代码 + 旧档清单)

**Files:**
- Read only: `docs/stock-analytics/sectors/semiconductor/storage/2026-05-19-东芯股份-buffett分析.md`(取 frontmatter `stock_code`)

- [ ] **Step 1: 校验东芯代码 + 三只旧档存在性**

Run:
```bash
PYTHONIOENCODING=utf-8 python -c "import re,glob; [print(p, re.search(r\"stock_code: '?([0-9]+)'?\", open(p,encoding='utf-8').read()).group(1)) for p in glob.glob('docs/stock-analytics/sectors/semiconductor/storage/*东芯*buffett*.md')+glob.glob('docs/stock-analytics/sectors/semiconductor/storage/*普冉*buffett*.md')+glob.glob('docs/stock-analytics/sectors/semiconductor/storage/*兆易*buffett*.md')]"
```
Expected: 列出东芯(应为 688110)、普冉(688766)、兆易(603986)各档路径与代码。**若东芯代码 ≠ 688110,以此处实测为准更新后续任务。**

- [ ] **Step 2: 记录待删旧 buffett 档清单**

确认待 `git rm` 清单(全重做的两只):
- `docs/stock-analytics/sectors/semiconductor/storage/2026-04-25-普冉股份-buffett分析.md`
- `docs/stock-analytics/sectors/semiconductor/storage/2026-05-19-东芯股份-buffett分析.md`

兆易 5-31 档**不删**(in-place 补强)。无需 commit,此 task 仅采集信息供后续 task 用。

---

## Task 1: sector-lenses.md 新增独立 NOR Flash 节 + 收窄现有存储节

**Files:**
- Modify: `.claude/skills/stock-deep-redo/references/sector-lenses.md`(现有存储节标题行 + 识别信号;文件末尾「加新板块」说明行之前插入新节)

- [ ] **Step 1: 收窄现有存储节为 DRAM/NAND**

把现有这段:
```markdown
## 存储（半导体 · DRAM/NAND/利基存储）

### 【识别信号】
- sector=semiconductor 且 subsector 含 storage / memory / dram / nand / 利基存储；
- 主营为 DRAM / NAND / NOR / 存储模组 / 存储主控。
```
替换为:
```markdown
## 存储 — DRAM / NAND（半导体 · 标准/利基 DRAM、NAND）

### 【识别信号】
- sector=semiconductor 且 subsector 含 storage / memory / dram / nand / 利基存储；
- 主营为 DRAM / NAND / 存储模组 / 存储主控。
- **NOR 单独见下节「存储 — NOR Flash」**；兼营 DRAM/NAND + NOR 的标的（如兆易/东芯/君正）两节可叠加，分别按各自供需引擎拷问。
```

- [ ] **Step 2: 在文件末尾「加新板块」说明行之前插入独立 NOR 节**

在这一行之前:
```markdown
> 加新板块只需在本文件追加一节五段式，SKILL.md/playbook.md 无需改动。
```
插入(保留其上方的 `---` 分隔结构,新节前后各留一空行):
```markdown
## 存储 — NOR Flash（半导体 · 代码型/串行闪存，独立于 DRAM/NAND 供需引擎）

### 【识别信号】
- sector=semiconductor 且 subsector 含 storage / memory；主营含 NOR / SPI NOR / 串行闪存 / 代码型闪存 / AMOLED 驱动存储 / EEPROM（邻接）。
- 玩家锚：兆易创新 / 普冉股份 / 东芯股份 / 武汉新芯 / 旺宏 / 华邦 / 恒烁。
- **与「存储 — DRAM / NAND」节可叠加**：兼营标的两节同时命中，分别按各自引擎拷问。

### 【必查清单（采证 face）】
- NOR 现货/合约价**分容量段**走势：小容量（≤256Mb）vs 中大容量（512Mb-2Gb）报价分化，热门 SKU 单月涨幅 vs 整体口径（实时采证，注明来源与机构分歧）。
- 供给侧：Cypress/Infineon 车规 NOR、Micron 等大厂退出/EOL 的**范围 + 时间表 + 可逆性**；旺宏/华邦产能迁移或减产。**强调 NOR 供给驱动 ≠ DRAM 的 HBM 挤出**——是大厂主动退出 + 晶圆代工（中芯/华虹/力积电）产能分配，机制不同。
- 需求侧结构增量（逐条要数字 + 第三方机构口径）：AMOLED 渗透率（每屏约 1 颗 NOR，手机/折叠/车载）/ AI server BMC·boot NOR（单机价值量、服务器出货）/ 车规（AEC-Q100，ADAS/智能座舱）/ TWS·可穿戴 / 工业。
- 标的**容量段卡位**：小容量 vs 中大容量 512Mb-1Gb vs 车规——景气与毛利分化，定位决定弹性大小。
- 工艺节点（SONOS 55/50/45nm）与代工依赖（自有 vs 中芯/华虹/力积电），制程降本路径。
- EEPROM / DDR5 SPD 邻接：是否与 NOR 同处一条涨价链（共用代工/客户/景气）。

### 【撰写落点（撰写 face）】
- §6 核心新论点：NOR 供给侧（大厂退出 + 代工分配，**独立于 DRAM HBM 挤出**）+ 需求结构增量（AMOLED/AI server/车规），做结构性 vs 周期性二分判定。
- §2 市场规模：按容量段、按应用拆 NOR 的 SAM/SOM。
- §3 盈利能力：NOR 涨价弹性**按容量段**精算（小容量纯弹性 vs 中大容量温和）。
- §8 周期定位：NOR 周期与 DRAM 周期**不同步**（盘子小、CR3 >70%、价格逻辑不同），勿用 DRAM 周期位置直接套 NOR。

### 【双面必答】
- NOR 涨价是"大厂退出的结构性缺口"，还是"DRAM 涨价外溢带动的周期性补涨"？把最强反驳前置。
- 旺宏/华邦的 NOR 产能是否可回流（涨价后复产/扩产）？
- 涨价能兑现到标的净利，还是被代工（中芯/华虹/力积电）NOR 报价上调吃掉？
- AMOLED / AI server NOR 增量是否已被股价 price-in；NOR 占标的营收比重决定是"纯弹性"还是"温和受益"——勿把温和受益当纯弹性叙事。

### 【监控指标模板】
- NOR 现货价（分容量段）环比转跌；旺宏/华邦复产或扩产公告（涨价证伪 / 供给回流）。
- AMOLED 面板出货 / 渗透率增速下修；AI server 出货 / 资本开支指引下修。
- 标的 NOR 毛利率较峰值回落 > X ppt；代工（中芯/华虹/力积电）NOR 报价上调侵蚀毛利。
- 标的 NOR 营收占比与价格弹性匹配度（验证纯弹性 vs 温和受益的判断是否成立）。

---
```

- [ ] **Step 3: 结构自检**

Run:
```bash
PYTHONIOENCODING=utf-8 python -c "t=open('.claude/skills/stock-deep-redo/references/sector-lenses.md',encoding='utf-8').read(); assert '存储 — NOR Flash' in t, 'NOR 节缺失'; assert '存储 — DRAM / NAND' in t, '存储节未收窄'; assert t.count('### 【识别信号】')>=4, '五段式节数不足(AI/PCB/DRAM-NAND/NOR=4)'; assert '> 加新板块' in t.split('存储 — NOR Flash')[1], 'NOR 节未插在末尾说明之前'; print('OK 结构自检通过')"
```
Expected: `OK 结构自检通过`

- [ ] **Step 4: Commit**

```bash
rtk git add .claude/skills/stock-deep-redo/references/sector-lenses.md
rtk git commit -m "feat(stock-deep-redo): sector-lenses 新增独立 NOR Flash 节

收窄现有存储节为 DRAM/NAND;新增「存储 — NOR Flash」五段式(供给侧=大厂退出+代工分配,
区别于 HBM 挤出;需求侧=AMOLED/AI server BMC/车规),两节可叠加。

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: 普冉股份 688766 全重做(stock-deep-redo 全流程)

**Files:**
- Create: `docs/stock-analytics/sectors/semiconductor/storage/2026-05-31-普冉股份-buffett分析.md`
- `git rm`: `docs/stock-analytics/sectors/semiconductor/storage/2026-04-25-普冉股份-buffett分析.md`
- Evidence(不入库): `.omc/artifacts/普冉-5-31-evidence.md`

- [ ] **Step 1: 起 stock-deep-redo,注入 NOR(主)+ AI(横切) lens**

调用 `stock-deep-redo` skill,目标股票"普冉股份 688766",显式告知:
- 命中 lens:`存储 — NOR Flash`(主)+ `AI`(横切)。把这两节的【必查清单】【撰写落点】注入 Phase A/B。
- 基线底稿:`docs/stock-analytics/sectors/semiconductor/storage/2026-04-25-普冉股份-buffett分析.md` + `docs/stock-analytics/quarterly/26q1/2026-04-29-普冉股份-26Q1季报点评.md`。
- 待删旧档:`2026-04-25-普冉股份-buffett分析.md`(Phase C `git rm`)。
- NOR 采证必须覆盖:小容量段(≤256Mb)报价、普冉该段份额/卡位、EEPROM(含 DDR5 SPD)邻接涨价、fabless 代工依赖(中芯/华虹/力积电)、车规 NOR 进展。

- [ ] **Step 2: 等 skill 完成 Phase A/B + 两段式审查**

由 skill 内部串行执行(Phase A 采证 → Phase B 撰写 + frontmatter lint → 规格审查 → 质量审查)。门槛:质量审查须达 APPROVED 或 APPROVED-WITH-NITS。Critical/Important 问题须回修复审至过。

- [ ] **Step 3: 验证新档 frontmatter lint**

Run:
```bash
PYTHONIOENCODING=utf-8 python scripts/lint_docs_frontmatter.py
```
Expected: exit 0(全过)。`subsector=storage`、`stock_code:'688766'` 带引号、`conviction_date:2026-05-31`。

- [ ] **Step 4: 验证 NOR 必查项落正文**

Run:
```bash
PYTHONIOENCODING=utf-8 python -c "t=open('docs/stock-analytics/sectors/semiconductor/storage/2026-05-31-普冉股份-buffett分析.md',encoding='utf-8').read(); import sys; [sys.exit('缺 NOR 必查回应: '+k) for k in ['容量','AMOLED','代工'] if k not in t]; print('OK NOR 必查项已回应')"
```
Expected: `OK NOR 必查项已回应`(查无证据也须在正文写明,故关键词应出现)。

- [ ] **Step 5: Commit(由 skill Phase C 完成,含 git rm 旧档 + 反向链)**

skill Phase C 会 `git rm` 4-25 旧档、改指 symmetric 反向链、补新档 related_docs、`lint_docs_refs.py --rewrite-blocks`、提交终稿。控制者核验 commit 已落:
```bash
rtk git log --oneline -3
rtk git status
```
Expected: 有普冉重做 commit;`git status` 干净;无 evidence.md 被 add。

---

## Task 3: 东芯股份 688110 全重做(NOR + DRAM/NAND 叠加 + AI)

**Files:**
- Create: `docs/stock-analytics/sectors/semiconductor/storage/2026-05-31-东芯股份-buffett分析.md`
- `git rm`: `docs/stock-analytics/sectors/semiconductor/storage/2026-05-19-东芯股份-buffett分析.md`
- Evidence(不入库): `.omc/artifacts/东芯-5-31-evidence.md`

- [ ] **Step 1: 起 stock-deep-redo,注入 NOR + DRAM/NAND(叠加)+ AI lens**

调用 `stock-deep-redo` skill,目标"东芯股份"(代码以 Task 0 实测为准,预期 688110),显式告知:
- 命中 lens:`存储 — NOR Flash` + `存储 — DRAM / NAND`(叠加)+ `AI`(横切)——三节【必查】【落点】全注入。这是验证两节可叠加的典型。
- 基线底稿:`docs/stock-analytics/sectors/semiconductor/storage/2026-05-19-东芯股份-buffett分析.md`。
- 待删旧档:`2026-05-19-东芯股份-buffett分析.md`。
- 采证须分线拷问:NOR 与 SLC NAND 双线景气**分化**、各自营收占比与弹性、利基 DRAM 小敞口;勿用单一存储周期一概而论。

- [ ] **Step 2: 等 skill 完成 Phase A/B + 两段式审查**

同 Task 2 Step 2 门槛(质量审查 APPROVED / APPROVED-WITH-NITS)。

- [ ] **Step 3: 验证新档 frontmatter lint**

Run:
```bash
PYTHONIOENCODING=utf-8 python scripts/lint_docs_frontmatter.py
```
Expected: exit 0。`stock_code` 与 Task 0 实测一致并带引号、`conviction_date:2026-05-31`。

- [ ] **Step 4: 验证 NOR + NAND 双线落正文**

Run:
```bash
PYTHONIOENCODING=utf-8 python -c "t=open('docs/stock-analytics/sectors/semiconductor/storage/2026-05-31-东芯股份-buffett分析.md',encoding='utf-8').read(); import sys; [sys.exit('缺双线必查回应: '+k) for k in ['NOR','NAND','容量'] if k not in t]; print('OK NOR+NAND 双线已回应')"
```
Expected: `OK NOR+NAND 双线已回应`

- [ ] **Step 5: Commit(skill Phase C 完成 git rm + 反向链)**

```bash
rtk git log --oneline -3
rtk git status
```
Expected: 有东芯重做 commit;status 干净;evidence.md 未 add。

---

## Task 4: 兆易创新 603986 NOR 主线补强(非全重做,原地 Edit)

**Files:**
- Modify: `docs/stock-analytics/sectors/semiconductor/storage/2026-05-31-兆易创新-buffett分析.md`(§2 / §3 / §6 / §8 四节)
- Evidence(不入库): `.omc/artifacts/兆易-NOR补强-5-31-evidence.md`

- [ ] **Step 1: 起 stock-deep-redo 的裁剪流程(NOR 专项)**

调用 `stock-deep-redo` skill,**显式声明这是"NOR 主线补强 in-place",非全重做**,偏离默认(不 git rm、不新建档):
- 命中 lens:`存储 — NOR Flash`。
- Phase A 只采 NOR 专项证据(`.omc/artifacts/兆易-NOR补强-5-31-evidence.md`):NOR 分容量段报价、AMOLED NOR 细分、AI server boot/BMC NOR 单机价值量与份额、Cypress/Infineon 退出对兆易中大容量段的传导。
- Phase B 改为**原地 Edit 5-31 现档**四节,不动其余结构、不动 `<!-- BEGIN/END related_docs -->` 块:
  - §2:补 NOR 分容量段/应用 TAM。
  - §3:NOR 涨价弹性分容量段精算(深化既有"温和受益 vs 君正纯弹性"对比)。
  - §6:把 NOR 供给侧写成**与 DRAM HBM 挤出并列的独立子论点**(大厂退出 + 代工分配),含双面(旺宏/华邦可回流?)。
  - §8:NOR 周期 vs DRAM 周期不同步。
- `conviction_date` 维持 2026-05-31;`rating` 除非证据翻转否则维持 `watch`。

- [ ] **Step 2: 单段质量审查(不重跑规格全审)**

派 1 个 read-only subagent 只审 NOR 补强四节:内在一致性、NOR 供给侧双面是否走过场、NOR 涨价是否被偷渡进 owner earnings(应排除未兑现概念)、数字可追溯。Critical/Important 回修复审至过。

- [ ] **Step 3: 验证 frontmatter 未破 + NOR 补强落正文**

Run:
```bash
PYTHONIOENCODING=utf-8 python scripts/lint_docs_frontmatter.py
PYTHONIOENCODING=utf-8 python -c "t=open('docs/stock-analytics/sectors/semiconductor/storage/2026-05-31-兆易创新-buffett分析.md',encoding='utf-8').read(); import sys; [sys.exit('缺 NOR 补强: '+k) for k in ['容量段','AMOLED','boot'] if k not in t]; assert \"conviction_date: 2026-05-31\" in t; assert 'rating: watch' in t; assert '<!-- END related_docs -->' in t, 'related_docs 块被破坏'; print('OK 兆易 NOR 补强已落且结构完好')"
```
Expected: frontmatter lint exit 0;`OK 兆易 NOR 补强已落且结构完好`。

- [ ] **Step 4: Commit**

```bash
rtk git add docs/stock-analytics/sectors/semiconductor/storage/2026-05-31-兆易创新-buffett分析.md
rtk git commit -m "docs(buffett): 兆易创新 NOR 主线补强(§2/§3/§6/§8)

把 NOR 供给侧写成独立于 DRAM HBM 挤出的子论点(大厂退出+代工分配),
分容量段精算 NOR 涨价弹性,NOR 周期 vs DRAM 不同步;评级维持 watch。

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: 统一 lint 收尾 + 验收汇报

**Files:** 无(只跑 lint + 汇报)

- [ ] **Step 1: 双 lint 全绿 + 孤儿检查**

Run:
```bash
PYTHONIOENCODING=utf-8 python scripts/lint_docs_frontmatter.py && PYTHONIOENCODING=utf-8 python scripts/lint_docs_refs.py && PYTHONIOENCODING=utf-8 python scripts/lint_docs_refs.py --check-orphans
```
Expected: 三条全 exit 0;普冉/东芯新档非孤儿(已被既有 comps/quarterly 反向链或新档 related_docs 互链)。若 refs 报悬空(指向已删旧档),回到对应 Phase C 改指。

- [ ] **Step 2: 确认采证脚本/evidence 未入库**

Run:
```bash
rtk git status
PYTHONIOENCODING=utf-8 python -c "import glob; print('遗留一次性脚本:', glob.glob('scripts/_*.py')+glob.glob('scripts/verify_*.py'))"
```
Expected: `git status` 干净;无遗留一次性采证脚本(有则 `rm`);`.omc/artifacts/*evidence*.md` 未被 add(gitignore)。

- [ ] **Step 3: commit 链核验 + 汇报**

Run:
```bash
rtk git log --oneline -8
```
Expected: 见到 lens 节(Task1)+ 普冉 + 东芯 + 兆易补强 commit 链干净。

向用户汇报每只:评级是否相对旧档翻转、场景加权期望内在价值、安全边际、NOR 涨价对结论的具体影响。默认 main 直接提交、**不主动 push**(等用户要)。

---

## Self-Review(规格覆盖核对)

- **设计 §3 执行方案(lens 先行 + 串行)** → Task 1→2→3→4→5 串行顺序 ✓
- **设计 §4 NOR lens 五段 + 独立节 + 收窄存储节** → Task 1 Step 1(收窄)+ Step 2(完整五段 markdown)✓
- **设计 §5.1 普冉全重做 + git rm 4-25** → Task 2 ✓
- **设计 §5.2 东芯全重做 + 代码校验 + 双 lens 叠加 + git rm 5-19** → Task 0 Step 1(代码校验)+ Task 3 ✓
- **设计 §5.3 兆易 in-place 补强四节 + 流程裁剪 + 维持 watch** → Task 4 ✓
- **设计 §6 收尾(双 lint exit 0 + check-orphans + 反向链对称 + evidence 不入库)** → 各 Task Step 3/5 + Task 5 ✓
- **设计 §7 风险(东芯代码校验、NOR/DRAM 口径分开、兆易 related_docs 块不破)** → Task 0 Step1 / Task 4 Step3(块完好断言)✓
- **占位符扫描**:监控模板 `> X ppt` 为 lens 铁律阈值占位,非缺口;无 TBD/TODO。
- **类型/路径一致性**:三只档路径、git rm 目标、代码(688766/688110/603986)在各 task 一致。东芯 688110 在 Task 0 标注"实测为准"。
