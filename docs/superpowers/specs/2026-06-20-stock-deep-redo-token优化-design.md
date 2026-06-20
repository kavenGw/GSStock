# stock-deep-redo + 估值机制 token/维护优化 — 设计文档

> 日期：2026-06-20
> 范围：`.claude/skills/stock-deep-redo/`（SKILL.md、playbook.md）、`scripts/_docs_schema.py`、
> 新增 `scripts/sync_valuations.py`、`docs/stock-analytics/valuations.yaml` 同步链。
> **不在范围**：Phase B 的 buffett 注入（保持现状全量 `Skill buffett`）、场景加权方法论本身、`/valuations` 页面渲染逻辑、buffett skill。

## 目标

1. **减少 token**：削减 stock-deep-redo 单次运行的 token 开销，重点在审查阶段（当前 4 个 opus subagent）。
2. **优化维护**：消除 doc→yaml 估值数据"从散文用 LLM 提取"的脆性，改为结构化单一真相源。

## 现状（成本来源）

stock-deep-redo 单次运行派 5 个 subagent：

| 阶段 | 模型 | 职责 |
|------|------|------|
| Phase A 采证 | opus | 联网验证多空事实 + 实时行情锚 → evidence.md |
| Phase B 撰写 | opus | `Skill buffett` 取框架 + 写 13 节正文 + frontmatter |
| 规格审查 | opus（只读） | 机械核对：13 节齐全 / Σ概率=100% / frontmatter 合规 / 无造数 |
| 质量审查 | opus（只读） | 判断：概率可辩护 / 双面性 / "贵"诚实 / AI 不拔高 |
| Phase C 收尾 | sonnet | git rm 旧档 / 反向链 / lint / **LLM 从正文提取估值数字 upsert valuations.yaml** |

两个痛点：
- 审查 2 个独立 opus subagent，各自重读 ~300 行正文 + evidence.md，token 翻倍。
- Phase C 用 LLM 从正文散文里正则/阅读提取 `bear/base/bull 每股内在价值 + dividend_yield`，再 upsert `valuations.yaml`——数字藏在散文里，既费 token 又易错。

## 设计：3 个相互独立的改动

### 改动 1 — 估值数据结构化承载（doc→yaml 去 LLM 化）

**问题**：估值数字（bear/base/bull 每股内在价值 + 分红率）当前只存在于正文散文，Phase C 靠 LLM 重新解析提取，脆且费 token。

**方案**：让 Phase B 撰写时把这些数字直接写进 buffett 档 frontmatter 的可选 `valuation` 块（结构化机器读镜像，正文散文保留供人读）。Phase C 同步退化为确定性脚本。

frontmatter 新增可选块：

```yaml
valuation:
  bear: 6.50            # 每股内在价值（原币），无法估算填 null
  base: 7.78
  bull: 8.87
  currency: CNY         # CNY / USD / HKD，与每股估值币种一致
  dividend_yield: 2.8   # 分红率（%），无分红填 null
```

落地点：

1. **`scripts/_docs_schema.py`**：加**可选** `valuation` 块校验——仅当 frontmatter 含 `valuation` 时才校验：
   - `bear` / `base` / `bull` 必须为数字或 `null`
   - `currency` 必须 ∈ `{CNY, USD, HKD}`
   - `dividend_yield` 必须为数字或 `null`
   - 缺失 `valuation` 块不报错（不影响存量 160 档；buffett 档可渐进补齐，非强制必填）。

2. **新增 `scripts/sync_valuations.py`**：
   - 扫 `docs/stock-analytics/**/*buffett*.md` 的 frontmatter `valuation` 块
   - 对每个含 `valuation` 的 buffett 档，组装 valuations.yaml 条目（复用 frontmatter 的 `stock_code` / `stock_name` / `market`/`sector` / `rating` / `conviction_date`，`source_doc`=相对路径）
   - 按 `stock_code` upsert 到 `valuations.yaml`（已存在→更新，不存在→追加；保持其余条目顺序）
   - **不全量重生**：`valuations.yaml` 现有 157 条里含非 buffett 来源 / 无 `valuation` 块的旧条目，脚本只 upsert 扫到的有效条目，不删除未匹配条目
   - 写回用 `yaml.dump(..., allow_unicode=True, sort_keys=False)`
   - Windows：读写显式 `encoding='utf-8'`
   - 支持 `--stock-code <code>` 只同步单只（Phase C 默认只同步本次股票），无参数则全量扫描 upsert

3. **Phase C 流程**：原"派 LLM 提取估值数字"步骤替换为"运行 `python scripts/sync_valuations.py --stock-code <code>`"。Phase C subagent（sonnet）跑该脚本，其余职责（git rm 旧档 / 反向链改指 / lint）不变。

4. **规格审查**：新增核对项——frontmatter `valuation` 块的 bear/base/bull/dividend_yield 与正文 §0/§9/§3 的数字一致（防镜像不同步）。

**market 字段来源**：buffett 档 frontmatter 当前无 `market` 必填字段。sync 脚本从 `stock_code` 形态推断（6 位纯数字→A；字母开头→US；含 `.HK` 或港股形态→HK），与 `app/utils/market_identifier.py` 规则对齐；A+H 选定口径由 frontmatter `stock_code` 本身体现（已是选定那一侧的代码）。

### 改动 2 — 两段审查合并 + 降级 sonnet

**问题**：规格审查 + 质量审查 = 2 个独立 opus subagent，各自重读正文 + evidence，token 翻倍。

**方案**：合并为 **1 个 sonnet 只读 subagent**，单 prompt 内分两段顺序输出（先规格、后质量，顺序不可反）：

- **第一段 规格符合性** → `SPEC-COMPLIANT` 或问题清单。核对：13 节齐全 / 三情景概率 Σ=100% 且期望值算术对 / frontmatter 合规 / **`valuation` 块与正文数字一致** / AI 维度均打标 / 供给侧双面 / 数字可追溯无造数 / 无范围外夹带 / 命中 lens 必查项均有回应。
- **第二段 分析质量** → `APPROVED` / `APPROVED-WITH-NITS` / `CHANGES-REQUESTED`。判断：内在一致性 / 概率可辩护 / 双面非走过场 / "贵"诚实消化 / AI 不蹭概念拔高 / 增长证据化 / buffett 框架贴合 / 监控指标带阈值可执行。

**安全阀（保住纪律）**：
- 撰写≠审查上下文铁律保持：审查员是独立 subagent，非撰写者自审。
- **升级机制**：sonnet 审查给出 `CHANGES-REQUESTED`，或第一段发现 Critical 规格问题时，控制者**自动追派 1 个 opus 只读审查员复核该结论**，再据复核结果让撰写 subagent 修。即 sonnet 把关日常、opus 仅异常时介入。
- 修复后由**同一审查上下文**复审（沿用 SendMessage 续跑），直到过。

**token 账**：正常路径 4 opus → 2 opus（Phase A 采证 + Phase B 撰写）+ 1 sonnet（合并审查）。异常路径才 +1 opus。审查阶段 token 约降 80%+。

### 改动 3 — SKILL.md / playbook.md 文档同步

回写 skill 文档以反映改动 1、2，并顺手去重瘦身。**Phase B 的 buffett 注入流程不动（仍全量 `Skill buffett`）。**

- **SKILL.md**：
  - 总编排"两段式审查"节改为"一段 sonnet 合并审查 + opus 异常升级"，更新派发顺序描述。
  - Phase C 收尾节："同步 valuations.yaml"由"LLM 提取"改为"运行 `sync_valuations.py --stock-code <code>`"。
  - 质量红线、Phase A、Phase B 描述不变。
- **playbook.md**：
  - §1 frontmatter 模板加 `valuation` 可选块说明。
  - §8「valuations.yaml 同步」整节重写：删除散文提取规则（"A 股 X.XX 元/股 格式""市值反推每股"等约 50 行），改为"frontmatter `valuation` 块字段定义 + 跑 `sync_valuations.py`"。保留特殊情况里仍有效的部分（港股代码形态、A+H 口径覆盖语义）。
  - §9 派发提示骨架：合并审查的派发提示改为单 sonnet 双段 prompt + 升级条件；Phase C 骨架的 valuations 同步改脚本。

## 风险与权衡

- **sonnet 审查质量回退风险**：sonnet 判断力弱于 opus，可能漏判软性质量问题。缓解：升级机制（CHANGES-REQUESTED/Critical → opus 复核）+ 规格段大多是机械核对（sonnet 足够）。
- **frontmatter 与正文双写不同步风险**：缓解：规格审查新增一致性核对项；正文仍是人读权威，frontmatter 是镜像。
- **sync 脚本对存量 157 条 yaml 的兼容**：脚本只 upsert 不删除未匹配条目，存量非 buffett 来源条目（comps 等）不受影响。
- **buffett 注入未优化**：Phase B 仍注入约 150KB，本次刻意不动（用户决定），是后续可选优化空间。

## 验收标准

1. `scripts/_docs_schema.py` 对含/不含 `valuation` 块的 frontmatter 均正确校验，存量 160 档 `lint_docs_frontmatter.py` 仍 exit 0。
2. `scripts/sync_valuations.py` 能从一份带 `valuation` 块的 buffett 档正确 upsert valuations.yaml 单条目（单测：新增 / 更新已有 / 港股代码形态）。
3. SKILL.md / playbook.md 改动后内部无矛盾：审查描述、Phase C 描述、frontmatter 模板三处一致。
4. 不破坏现有 lint 链：`lint_docs_frontmatter.py` + `lint_docs_refs.py` 均 exit 0。

## 不做（YAGNI）

- 不把 valuations.yaml 全量从 frontmatter 重生（存量含非 buffett 条目）。
- 不做 git hook / pre-commit 自动同步（Phase C subagent 跑脚本即可）。
- 不优化 Phase B buffett 注入。
- 不改 `/valuations` 页面渲染、场景加权方法论。
