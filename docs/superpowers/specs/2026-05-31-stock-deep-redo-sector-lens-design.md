# stock-deep-redo 优化设计：物理删除旧档 + 可扩展 sector-lens

- **日期**：2026-05-31
- **作者**：kaven（brainstorming with Claude）
- **范围**：优化 `.claude/skills/stock-deep-redo/` 编排 skill
- **状态**：设计已批准，待写实施计划

## 背景与动机

现有 `stock-deep-redo` 是个股 buffett 深度重做的 3 阶段编排（采证 → 撰写 → 收尾）+ 两段式审查。
本次优化要解决四个诉求：

1. **替换旧 buffett 文档**：当前默认是新建带日期新档 + 旧档保留互链（supersede 不删），
   用户要改成**物理删除旧档**，目录里同一标的只留最新一份 buffett 档。
2. **AI 板块前景**：判断标的是否 AI 驱动，若是则深挖 AI 未来前景（不止打标签）。
3. **PCB → Rubin/扩产**：PCB/CCL 标的要查 Rubin 平台拉动、扩厂 capex、产能爬坡。
4. **存储 → 短缺 + 大厂退出低端**：存储标的要查当前供需短缺、SK/美光/三星退出收缩低端市场。

诉求 2–4 本质是同一件事：**按 subsector 注入一套板块专属分析视角（sector lens）**。

## 核心设计决策（已确认）

| 维度 | 决策 |
|------|------|
| 替换语义 | **物理删除旧档**：新档写好后 `git rm` 该股所有历史 buffett 档，目录只留最新 |
| lens 承载形式 | **可扩展注册表** `references/sector-lenses.md`，每 subsector 一节 |
| lens 选择模型 | **可叠加多选 + AI 作为横切默认**：一只股可同时命中 PCB+AI 等多套 lens |
| lens 内容约束 | 只写「必查调查清单」驱动实时联网采证，**不写死会过时的结论/数字/时间表** |
| 原 §4 AI 维度法 | 并入 sector-lenses 的 AI 节，playbook 只留指针（避免两处重复维护） |

## 块 A — 替换语义改为「物理删除旧档」

**默认参数表**：产出形态 从「supersede 旧档保留 + related_docs 互链」
改为「新建新档（`conviction_date` = 今天）+ `git rm` 该股所有历史 buffett 档」（只删 buffett 档，
comps / theme / quarterly 一律保留）。

流程改动：

- **先做（控制者）**：Glob 列出该股全部历史 buffett 档（`sectors/**/*<股票名>*buffett*.md`）；
  删前**先 Read 一眼确认确属同股旧 buffett 档**（CLAUDE.md 铁律：删除/覆盖前先看目标，
  若与描述矛盾则 surface 而非照删），形成待删清单传给 Phase C。
- **Phase C 收尾**新增三步：
  1. `git rm` 待删旧 buffett 档。
  2. 扫所有 `symmetric: true` 指向被删档的反向链（别的 comps/theme/quarterly 的 related_docs）
     → **改指到新档**或删除该条目。
  3. `lint_docs_refs.py` 必须 exit 0（悬空 ref 会被抓出），`--check-orphans` 确认新档非孤儿。
- **规格审查**新增核对项：旧档已删 / 反向链已改指到新档 / 无悬空 ref。

边界：若 Glob 命中的"旧档"经 Read 发现并非同股、或内容与预期严重不符，**停下来 surface 给用户**，不照删。

## 块 B — 新增 `references/sector-lenses.md`（可扩展注册表）

每个 subsector 一节，统一五段式结构：

1. **【识别信号】**：什么 subsector / 关键词 / 业务特征命中本 lens。
2. **【必查清单（采证 face）】**：Phase A 必须联网核实的问题列表。
3. **【撰写落点（撰写 face）】**：这些发现落到正文哪些节（§6/§7/§8 等）。
4. **【双面必答】**：本 lens 最强的反驳点，必须正面写出。
5. **【监控指标模板】**：带阈值、可执行的卖出/复盘触发器候选。

核心约束：只写"必查问题"，**不写死数字/时间表/结论**——所有事实由 Phase A 实时联网取，
符合 SKILL.md「联网而非凭记忆」红线。

首发三节：

### AI（横切 · 默认跑）
- 先判定标的是否 **AI 真驱动**（业绩归因 vs 纯概念）。
- 若是 AI 驱动：§7 从"打标签"升级为 **AI 未来前景深挖**——TAM 增速 / 竞争格局 / 算力链卡位 /
  兑现节奏（产品层 vs 业绩层）。
- 每股仍保留 AI 维度 `【真敏感】`/`【蹭概念】` 打标（原 playbook §4 法并入此节）。
- 双面必答：未兑现的概念不许进 §9 估值的 owner earnings。

### PCB / CCL（electronics/components 或 pcb subsector）
- 必查：Rubin/GB 平台时间表与拉货节奏、**扩厂 capex 与产能爬坡进度**、
  层数/ASP/高多层占比提升、CCL/铜箔涨价传导、HDI/载板升级路径、客户集中度。
- 撰写落点：§6 核心新论点（AI 服务器拉动）、§3 盈利能力（ASP/毛利弹性）、§8 周期定位。
- 双面必答：扩产是否埋下未来过剩、在手订单能见度的真实性。

### 存储（semiconductor/storage）
- 必查：DRAM/NAND 现货与合约价趋势、**SK/美光/三星退出或收缩低端（DDR4/利基）的范围+时间表+可逆性**、
  利基缺口向标的的传导、HBM 挤出效应、库存周期位置。
- 撰写落点：§6 核心新论点（供给侧出清）、§3（涨价弹性）、§8 周期定位。
- 双面必答：大厂退出是否可逆、当前是否已在周期顶。

注册表可扩展：以后加板块只追加一节，零改流程。

## 块 C — 控制者编排接入 lens

- **先做**步骤加：识别 subsector → 选命中 lens 集合（主 lens + AI 横切，可叠加）→
  把对应 lens 节内容传给后续 subagent。
- **Phase A 采证提示**附命中 lens 的【必查清单】。
- **Phase B 撰写提示**附命中 lens 的【撰写落点】，并要求对应节深化。
- **审查**核对：命中 lens 的必查项是否都在正文有回应（没查到要明写"未找到公开证据"，不许跳过）。

## 块 D — 文件落地清单

- **SKILL.md**：
  - 改默认参数表（产出形态 → 物理删除）。
  - 先做步骤加 lens 识别 + 待删旧档清单。
  - Phase A/B/C 派发提示加 lens 注入 + 删除收尾。
  - 质量红线加「替换 = 物理删除旧档 + 反向链改指到新档」。
- **playbook.md**：§4「AI 维度标签法」精简为一句话 + 指向 sector-lenses.md 的 AI 节；
  Phase C 收尾骨架加删除旧档 + 改指反向链；其余不动。
- **新增 `references/sector-lenses.md`**：上述五段式 × 三节。

## 不做（YAGNI）

- 不做 lens 自动识别引擎/代码；识别由控制者按 subsector 人工判断（注册表给【识别信号】辅助）。
- 不在 lens 里硬编码任何当下事实（Rubin 时间表、存储报价等一律实时采证）。
- 不动 13 节文档主结构、不动 frontmatter 字段集、不动两段式审查的基本框架。

## 验收标准

- SKILL.md 默认参数表产出形态为物理删除，Phase C 含删除 + 反向链改指 + 双 lint exit 0。
- `references/sector-lenses.md` 存在，含 AI/PCB/存储三节五段式，无硬编码会过时事实。
- playbook §4 精简为指针，无与 sector-lenses 重复维护。
- 跑一遍真实标的（如沪电=PCB+AI 叠加、兆易=存储+AI）验证 lens 叠加生效、旧档被删、lint 全绿。
