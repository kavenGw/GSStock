# stock-deep-redo 瘦身与闸门机制化设计（2026-08-22）

## 背景

`2026-08-08-stock-deep-redo-提速-design.md` 那一轮解决的是**速度**（三路并行 + 深度上限 + 汇报文件协议）。
本轮解决的是它带来的副作用：**SKILL.md 变成了编年体**。

现状体检（2026-08-22，第十二轮光智科技回填后）：

| 文件 | 行数 / 体积 | 问题 |
|---|---|---|
| `SKILL.md` | 378 行 / 43.2KB | L193–352 约 **150 行是十二轮实测教训叙事**，每轮追加一段。控制者每次起 skill 都要读完，其中"做什么"的指令只占一半 |
| `references/playbook.md` | 24.8KB | §9.0 有一大段"自报时间戳不可信"与 SKILL.md 收尾节重复 |
| `memory/` | 24 条 | 其中 5 条是 stock-deep-redo 专属，与 SKILL.md 教训段内容重叠 |

更关键的是：这些教训里反复出现同一批**结构性**问题，但流程本身没改，只靠"控制者记住要小心"兜底——

1. **Phase A 放行闸门不可靠**：report 存在 ≠ 收工（光智轮 A1 在 report 落盘后 14 分钟又追加 325 行附录，
   其中 10 条改写正文的硬事实，Phase B 已在途）；控制者刚发出的校准消息可能还在队列里未被读到（光迅轮）。
2. **subagent 静默死亡无探测**：光迅轮 147min 里 64min 是纯空转——审查 subagent 跑 66min 零落盘零报错，
   后台等价任务 exit 4 同样无声。控制者在"等两个已经死掉的东西"。
3. **跨日价格锚的派生数靠人肉逐句手算**：雷赛轮控制者做了 71 处字面量替换并 grep 自查干净，
   审查仍抓出 4 处 Major、复核又自查出第 5 处——全部是"反推/隐含"型派生数，**句子里不含任何旧锚字面量**，grep 扫不到。

结论：**措辞管不住这三处**。本轮把它们从"控制者要记住"降级成"一条命令 + 一份案例库"。

## 目标与非目标

**目标**
- `SKILL.md` 从编年体重构为**编排手册**，目标 ≤ 260 行（现 378 行；实际落定 247 行）
- 十二轮教训沉淀为 `references/lessons.md`，编号化（`L1`…`Ln`），SKILL.md 用 `[Ln]` 引用
- 三个最常翻车的判据落成可复用脚本：Phase A/B/review 放行闸门、跨日锚点派生数审计
- memory 去重：skill 专属条目并入 lessons.md 后删除，只留跨 skill 通用的

**非目标（明确不做）**
- 不动 13 节模板、估值机制、8 条质量红线、sector-lenses.md —— 产出质量本轮不碰
- 不改流程结构（跨路校准正式化为 Phase A 第二阶段、Phase B 固定拆两棒）——那属于**提速**范畴，
  需实跑验证，留下一轮单独 brainstorm
- 不追求压缩耗时中位数（现 56.6min）；本轮若顺带省时间是副产品，不是验收标准


> **执行期裁定（2026-08-23）**：目标行数由 ≤180 放宽为 **≤260**，最终落定 **247 行**。
> 原因：四段式结构定型后实测——强制保留的五块（frontmatter / 开篇 / 何时用 / 默认参数 / 质量红线）
> 60 行 + 维护规则与参考文件 22 行 + 编排主体 182 行 = 264 行，压到 180 只能砍 Phase C 动作清单、
> 质量红线 8 条或默认参数表等操作性内容。180 是本文档起草时（结构未定）的估计值，把估计值当硬约束
> 去砍真内容是本末倒置。最终 247 行且**零操作内容损失**。下文出现的 ≤260 均为该裁定后的口径。

## 一、文件结构

```
.claude/skills/stock-deep-redo/
├── SKILL.md                    重写：编排手册，≤ 260 行（实际 247）
└── references/
    ├── playbook.md             微调：§9.0 删与 SKILL.md 重复的"自报时间戳不可信"长段，改一句引用 [L3]
    ├── sector-lenses.md        不动
    └── lessons.md              新建：规则编号 + 案例库
scripts/
├── deep_redo_gate.py           新建（纯 stdlib，不 import app）
└── deep_redo_anchor_audit.py   新建（纯 stdlib）
tests/
├── test_deep_redo_gate.py      新建
└── test_deep_redo_anchor_audit.py  新建
```

## 二、SKILL.md 新骨架

**原样保留**（一字不改）：frontmatter、「何时用 / 何时不用」、「默认参数」表 + 歧义门、
「质量红线」8 条（审查/Phase B 要内联原文，必须留在 SKILL.md 内）、「参考文件」。

**重写主体**为每阶段四段式：

```
### Phase X — <名>
做什么：<动作，表格保留>
必内联：<控制者摘原文注入 prompt 的清单> [Ln]
放行闸门：<命令级判据，可执行> [Ln]
预估：<墙钟口径> [Ln]
```

Phase A 示例：

```
放行闸门：
  python scripts/deep_redo_gate.py <股票名> <日期> --phase A --quiet-min 3
  exit 0 且 所有在途校准项已收到「已闭合」回复 → 派 B          [L1][L2]
  exit 非 0 → 输出里会说哪一路缺 / 仍在写；不许提前放行
预估：最慢路 + 1~2 轮校准，非"三路取最大"                      [L4]
```

**「收尾（控制者本人）」节**收缩为三块：
- 耗时账一行格式（口径不变：以控制者侧派发/收回记录为准）
- 基线表**只留合计列**（12 行表保留，用于派发时预估）；**分棒明细 8 行移入 lessons.md 的
  「附录：分棒耗时明细」节**（不占编号，纯数据附录）
- 「读法」压成 ≤ 5 条要点（三路并行需上限、上限管深度不管条数、Phase B 由成稿长度驱动、
  首建档少两块活、按 40–60min 预估）

**150 行教训叙事全部移出**。

**末尾新增「维护规则」一节**（约 5 行），写死后续轮次的沉淀方式：
> 新一轮跑完有教训时：**只在 `references/lessons.md` 追加 `Ln`**，并在 SKILL.md 对应闸门/预估处
> 加一个 `[Ln]` 引用。SKILL.md 不再写长叙事。基线表只加一行（合计列），分棒明细写进 lessons.md。

这一节是防回归的核心——没有它，下一轮又会长回 378 行。

## 三、lessons.md 归档规则

每条固定三段式，**规则编号永久、只追加不重排**（编号一旦分配不复用、不重排，
因为 SKILL.md 与 memory 里都有 `[Ln]` 引用）：

```markdown
## L1 Phase A 放行看 evidence mtime 稳定，不看 report 是否存在
**规则**：<1–2 句，SKILL.md 引用的就是这句>
**机制**：<对应脚本/命令；无机制则写"仅措辞"> 
**案例**：<原文搬入，保留轮次日期与具体数字>
```

初始 15 条（内容全部来自现 SKILL.md L193–352 与待删的 5 条 memory）：

| 编号 | 规则摘要 | 机制 |
|---|---|---|
| L1 | Phase A 放行看 evidence mtime 稳定，不看 report 是否存在 | `deep_redo_gate.py --quiet-min` |
| L2 | 校准消息在途 ≠ 已闭合；要么发完等回复，要么主动接受重叠 | 仅措辞 |
| L3 | 自报时间戳与自报善后动作均不可信，亲验对象永远是文件 | 仅措辞（playbook §9.0 引用此条）|
| L4 | 跨路校准是常态非例外，Phase A 按"最慢路 + 1~2 轮校准"预估 | 仅措辞 |
| L5 | 控制者派发时给出的前提本身可能错，一律写成"待核实假设"且三路都给 | 仅措辞 |
| L6 | 会话中断杀掉全部 subagent；别把"到点再做"交给它；能亲自接棒就别等 | 仅措辞 |
| L7 | 静默失败须配探测点，else 分支也要发信号 | `deep_redo_gate.py` + `until` 包装 |
| L8 | 跨日价格锚刷新的盲区是二次计算而非字面量，派生句必须逐句手算 | `deep_redo_anchor_audit.py` |
| L9 | 「撞财报日」的代价取决于财报落在 Phase A 之前还是之中 | 仅措辞 |
| L10 | 财报盘后披露 + 次日盘前采证：市值分母整段留空、开盘后补锚 | `--phase B` 占位检查 |
| L11 | 「等收盘」是可选自费项，对财报日标的值得 | 仅措辞 |
| L12 | 附件型（.docx/.pdf）二值事实缺口由控制者亲自补证，别让 subagent 反复试 | 仅措辞 |
| L13 | 亲验用精确锚点（tail + 关键词计数 + mtime + `end:`），别用模糊 grep | `deep_redo_gate.py` |
| L14 | Phase B 拆"主体 + 填锚"两段本身就是抗中断设计 | `--phase B` 占位检查 |
| L15 | 非权威路的数字须送 A1 逐条核定量级/科目/期间/主体四项 | 仅措辞 |

## 四、脚本接口

### 4.1 `scripts/deep_redo_gate.py`

```
python scripts/deep_redo_gate.py <股票名> <日期> --phase A [--quiet-min 3] [--artifacts .omc/artifacts]
python scripts/deep_redo_gate.py <股票名> <日期> --phase B --doc <新档路径>
python scripts/deep_redo_gate.py <股票名> <日期> --phase review
```

文件名按既有约定拼装：`<artifacts>/<股票名>-<日期>-<后缀>`。

| phase | 检查项 | 失败输出样例 |
|---|---|---|
| A | A1/A2/A3 三份 `-evidence-A?-*.md` 与 `-phaseA?-report.md` 均存在；report 含 `end:` 行；每份 evidence mtime 距今 ≥ `--quiet-min`；evidence ≥ 20 行 | `A1 NOT-READY: evidence mtime 0.8min ago (<3)`<br>`A3 MISSING: report` |
| B | `-phaseB-report.md` 存在且含 `end:`；`--doc` 指向的新档存在；新档无 `【待锚】` / `TODO` / `TBD` 占位；frontmatter 含 `valuation:` 块 | `B NOT-READY: 4 处【待锚】 at lines 88,91,204,997` |
| review | `-review-report.md` 存在；同时含规格段结论（`SPEC-COMPLIANT` 或问题清单标记）与质量段结论（`APPROVED` / `APPROVED-WITH-NITS` / `CHANGES-REQUESTED` 之一）| `review MISSING: 质量段结论` |

**退出码**：`0` 全绿 / `1` 有项未就绪 / `2` 参数错。

**不做轮询**——脚本保持无状态、可单测。等待由控制者包一层，SKILL.md 给出这一行模板：

```bash
T=1800; E=0
until python scripts/deep_redo_gate.py 光智科技 2026-08-22 --phase A --quiet-min 3 || [ $E -ge $T ]; do sleep 30; E=$((E+30)); done
[ $E -ge $T ] && echo "TIMEOUT ${E}s — 可能静默失败，控制者接管"
```

`until` 的 `||` 短路保证超时分支也发信号（L7 的"else 分支也要发信号"）。

### 4.2 `scripts/deep_redo_anchor_audit.py`

```
python scripts/deep_redo_anchor_audit.py <档路径> [--old <旧价/旧市值>] [--new <新价/新市值>]
```

- 扫描正文，命中句式常量表：`反推` `隐含` `对照当前市值` `按当前市值` `市值 ?/` `/ ?市值` `÷`
  `相当于 \d+(\.\d+)? ?倍` `前瞻 ?PE` `P/E` `× ?\d+(\.\d+)? ?倍`
- 输出 `行号 | 命中词 | 该行原文（截 120 字）`，末尾打印总计
- 给 `--old` 时，额外把仍含旧字面量的行标 `STALE-LITERAL`
- **退出码恒为 0**：这是报告工具不是裁定工具

**定位说明（写进脚本 docstring 与 SKILL.md）**：它**不算数**，只保证逐句过一遍。
雷赛轮那 5 处的共同特征是"不含旧字面量"，所以 `--old` 分支只是顺带兜底，
主价值在**列出待手算清单**。

## 五、memory 处置

| memory 文件 | 处置 |
|---|---|
| `cross-lane-debate-converge-before-relay.md` | 并入 L2 → 删除 |
| `phasea-numbers-need-authority-lane-adjudication.md` | 并入 L15 → 删除 |
| `review-before-phasec-false-critical.md` | 并入 SKILL.md 审查段派发提示 → 删除 |
| `review-scope-follows-checklist-wording.md` | 并入 SKILL.md 审查段派发提示 → 删除 |
| `subagent-report-needs-explicit-request.md` | 已被 playbook §9.0 汇报文件协议机制取代 → 删除 |
| `session-boundary-kills-subagents.md` | **保留**（跨 skill 通用），末尾加"详见 lessons.md L6" |
| `silent-failure-needs-probe.md` | **保留**，末尾加"详见 lessons.md L7" |
| `subagent-message-contradicts-its-own-file.md` | **保留**，末尾加"详见 lessons.md L3" |
| `MEMORY.md` | 同步删除对应 5 行索引 |

## 六、测试与验证

**单测**（`PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_deep_redo_*.py -v`）：

- `test_deep_redo_gate.py`：`tmp_path` 造 artifacts 目录，覆盖
  ① 三路全绿 exit 0；② 缺 A3 report → exit 1 且输出含 `A3 MISSING`；
  ③ evidence mtime 太新（`os.utime` 回拨制造）→ exit 1 含 `NOT-READY`；
  ④ `--phase B` 新档含 3 处 `【待锚】` → exit 1 且报出行号；
  ⑤ `--phase review` 只有规格段结论 → exit 1 含 `质量段结论`
- `test_deep_redo_anchor_audit.py`：造含 3 个派生句 + 1 处旧字面量的 md，
  断言命中 4 行、`STALE-LITERAL` 标记正确、exit 0

**文档侧验证**：
- `python -c "print(sum(1 for _ in open('.claude/skills/stock-deep-redo/SKILL.md',encoding='utf-8')))"` ≤ 260
  （Windows `wc -l` 对含中文 md 不可靠，见 `.claude/rules/dev-environment.md`）
- `[Ln]` 引用双向可解析：SKILL.md 里出现的每个 `[Ln]` 在 lessons.md 有对应 `## Ln` 标题；
  用一次性脚本检查，**跑完 `rm`、不入库**（一次性脚本不入库约定）
- 两脚本读写文件一律显式 `encoding='utf-8'`（`.bat`/`.ps1` 的纯 ASCII 铁律不适用于 `.py`，
  但 Windows 下默认 cp950 会炸中文，见 `.claude/rules/dev-environment.md`）

**回归确认**：本轮不动 docs/stock-analytics，无需跑 `lint_docs_frontmatter.py` / `lint_docs_refs.py`。

## 七、提交计划

按 `.claude/rules/dev-environment.md` 分支策略拆两笔：

1. **文档侧在 `main` 直接提交**（skill 文档属投研写档范畴，且不改 `app/`）：
   `SKILL.md` + `references/lessons.md` + `references/playbook.md` + memory 的 5 删 3 改 + `MEMORY.md`
   → `docs(skill): stock-deep-redo 瘦身——教训编号化沉淀 lessons.md，SKILL.md 378→247 行`
2. **脚本侧开独立 worktree**（改 `scripts/` 属功能改动）：
   两脚本 + 两测试 → `feat(scripts): stock-deep-redo 放行闸门与锚点审计脚本` → 合回 main

两笔均遵守 `git add <精确路径...> && git commit -F .git/MSG-<任务后缀>.txt` 同链铁律，
message 文件名带任务专属后缀（防并行 session 覆盖）。

## 八、验收标准

- [x] `SKILL.md` ≤ 260 行（实际 247），且每个阶段有可执行的放行闸门命令
- [ ] `lessons.md` 含 L1–L15，每条三段式齐全，案例保留原始轮次与数字
- [ ] SKILL.md 中所有 `[Ln]` 在 lessons.md 有对应条目（双向可解析）
- [ ] 两脚本单测全绿
- [ ] memory 删 5 保 3，`MEMORY.md` 索引同步
- [ ] 下一轮实跑时：Phase A 放行由 `deep_redo_gate.py` 判定而非肉眼；
      跨日重启时由 `deep_redo_anchor_audit.py` 列清单再手算
