# stock-research 统一投研入口 — 设计

日期：2026-08-23

## 目标

把 `stock-deep-redo` 与 `news-impact` 合并为一个 skill `stock-research`，由它按输入形态自动识别四种模式并路由，
同时补上此前只在两份 skill 里被"踢给 quarterly 流程"却从未有 skill 承接的财报分析，以及投资者会议记录两种新模式。
旧两个 skill 目录删除，不留别名。

## 非目标

- 不重写模式 1（深度分析）与模式 3（新闻影响）的流程本体——它们的编排、闸门、脚本、references 原样迁入。
- 不新增 `doc_type`，不改 `_docs_schema.py` / lint。
- 不改历史分析档正文里出现的旧 skill 名（45 份，属历史记录）。
- `scripts/deep_redo_gate.py` / `deep_redo_anchor_audit.py` 文件名不改（它们是模式 1/2 的闸门，名字与 skill 名解耦）。

## 目录

```
.claude/skills/stock-research/
  SKILL.md                      路由层（≤100 行）：触发描述、四模式判据、歧义门、共享默认、分支策略
  references/
    mode-deep.md                ← 原 stock-deep-redo/SKILL.md 正文（去 frontmatter，改内部引用路径）
    mode-earnings.md            新：财报模式 = 模式 1 的增量版
    mode-news.md                ← 原 news-impact/SKILL.md 正文
    mode-meeting.md             新：会议纪要模式
    dispatch.md                 ← 原样迁
    lessons.md                  ← 原样迁（编号 L1–L17 不动，后续继续追加）
    sector-lenses.md            ← 原样迁
    impact-rubric.md            ← 原样迁
  scripts/pool_index.py         ← 原样迁
  evals/evals.json              ← 迁入，skill_name 改名，补四模式识别用例各 1 条
```

`.claude/skills/stock-deep-redo-workspace/`（optim.log / trigger-eval.json）是一次性优化残留，一并删除。

## SKILL.md 路由层

### 模式判据（按输入形态，不靠关键词硬匹配）

| 模式 | 判据 | 产出 |
|------|------|------|
| 1 深度分析 | 主体是一只股票，**无附带材料**（或材料只是触发理由），意图是"值不值得买 / 重估 / 重做" | 文件夹六文件（`mode-deep.md`） |
| 2 财报分析 | 主体是一只股票，**附带财报/业绩预告/年报**（文本、PDF、URL），意图是"看这份财报 / 点评本体" | 差量更新该股文件夹六文件（`mode-earnings.md`） |
| 3 新闻影响 | 行业/政策/多主体事件；**或**单股事件但意图是"影响哪些票 / 利好利空谁" | `themes/` 专题档（`mode-news.md`） |
| 4 会议纪要 | 输入是业绩说明会 / 调研 / 交流的 Q&A、纪要、transcript | 单股会议 → `quarterly/<NNqN>/` 点评档；行业多主体会议 → 降级走模式 3（`mode-meeting.md`） |

判定顺序：先看输入有没有附带材料及材料类型（纪要 → 4；财报 → 2；新闻 → 3；无 → 1），再看意图是"本体"还是"池"
（单股财报/纪要 + 意图为池 → 3）。开工第一句话报"识别为模式 N，理由一句"，用户可纠正。

### 歧义门（只问这些）

1. 单股财报或纪要，"点评本体"还是"看池影响"意图不明 → 问一句。
2. 模式 2/4 途中发现关键假设被证伪、评级须翻转 → 不在本模式内翻，报给用户并建议升级到模式 1。
3. 模式 1 原有歧义门（跨 sector 主业权重接近 / 其实要 comps / 旧档与底稿冲突）保留在 `mode-deep.md`。

### 共享默认

语言中文；在 `main` 分支直接写档、不开 worktree、不主动 push（沿 `.claude/rules/dev-environment.md` 分支策略）；
`mkdir -p .omc/artifacts`；避坑门（`avoidance-list.yaml`）对模式 1/2 生效；lint 双绿是所有模式的收尾闸门。

## 模式 2 财报分析（mode-earnings.md）

定位：一份财报落地 → 对该股已有文件夹档做**差量重承做**，而非另写 quarterly 点评档。

前置：该股必须已有 `sectors/<sector>/<subsector>/<股票名>/` 文件夹档。只有平铺档或无档 → 升级模式 1（首建/迁移需完整承做）。

流程（复用模式 1 的闸门与角色，缩减采证与撰写范围）：

1. **先做**（控制者）：Read 六文件，从 `valuation.md` 抽出旧档关键假设清单（收入/毛利率/资本开支/分红/三情景概率）；
   读 `events.md` 未消化事件；避坑门。
2. **Phase A'（单路 opus）**：财报原文核实（交易所/公司 PDF 一家确认即可）+ 指引与管理层口径 + 逐条对账旧假设
   （证实 / 证伪 / 无信息）+ 实时行情锚。evidence 写 `.omc/artifacts/<股票名>-<日期>-evidence-A1-*.md`，
   闸门 `deep_redo_gate.py --phase A` 只查 A1。
3. **Phase B'（1 个 opus）**：**差量覆盖**——只改受财报影响的段落：`business.md` 的经营数据、`valuation.md` 的假设
   与三情景数字（含"相对旧档变化清单"）、`thesis.md` 中被证实/证伪的论点、`index.md` 的 §0/§10/§11 与 frontmatter
   `valuation` 块 + `conviction_date`=今天；`sources.md` 追加财报来源；`events.md` 不动。未受影响段落原文保留。
   闸门 `deep_redo_gate.py --phase B --doc <文件夹>`。
4. **合并审查 + Phase C**：与模式 1 相同（`dispatch.md §3/§4`、`stock-doc-finalize`），含 `valuations.yaml` 同步。
5. **溢出 read-across**（可选）：财报暴露的行业信号（涨价 / 缺货 / 资本开支）若对池内 ≥1 只其他标的达中量级，
   调用模式 3 的 `pool_index.py match` 召回并在汇报里列出"建议看池的标的"，**不在本模式内写 theme 档**；
   用户要则另起模式 3。

评级铁律：模式 2 可以更新三情景数字与期望内在价值，但**评级翻转须走歧义门 2**——财报证伪了主论点就升级模式 1，
不在增量版里翻评级。

预估：A' 10-15min + B' 10-15min + 审查 + C ≈ 30-40min。

## 模式 4 会议纪要（mode-meeting.md）

定位：一份业绩说明会 / 调研纪要 → 提炼管理层口径对旧 thesis 的增量信息，落 `quarterly/` 点评档。

流程：

1. **核实**：纪要来源（交易所互动平台 / 公司 IR / 券商整理）；券商整理稿按媒体层级交叉 1 家。
2. **判主体**：单股（主体一家）→ 继续；行业会议 / 多家路演 → 降级模式 3。
3. **读旧档**：该股 buffett 档（文件夹 `index.md` + `thesis.md`，或平铺档）抽旧 thesis、watch_reason、§11 监控指标。
4. **写档**：`quarterly/<NNqN>/YYYY-MM-DD-<股票名>-<会议名>纪要.md`，`doc_type: quarterly`，`period` 取会议对应
   季度（业绩说明会 = 该期财报季度；非财报会议 = 召开日所在季度），`date`=今天。结构：会议要素（时间/出席/来源）
   → 管理层关键口径（逐条：原话摘要 / 对应旧 thesis 变量 / 证实·动摇·无信息）→ §11 监控指标对账 → 操作含义。
   ≤200 行；**不重算估值**。
5. **反向链**：`related_docs` 指向该股档（文件夹 → `index.md`，结构性引用；平铺 → 该档），`symmetric: true`；
   反向条目写回对应档 frontmatter。跑双 lint。
6. **汇报**：口径对旧 thesis 的净效果一句话 + 是否建议升级模式 1/2。

无该股档 → 仍可写 quarterly 档（`related_docs: []`），汇报时提示"该股未建档，要深度分析另起模式 1"。

## 引用改名清单

| 位置 | 动作 |
|------|------|
| `CLAUDE.md` 投研 skill 路由行 | 列表改为 `stock-research` / `analyze-category` / ... |
| `.claude/rules/dev-environment.md` 分支策略段 | skill 名替换 |
| `.claude/rules/docs-conventions.md` / `supply-chain.md` | skill 名替换 |
| `.claude/skills/buffett-doc-spec/SKILL.md` | "stock-deep-redo 的 Phase B" → "stock-research 模式 1/2 的 Phase B" |
| `.claude/skills/stock-doc-finalize/SKILL.md` | 同上 |
| `scripts/_docs_schema.py` 注释 | "news-impact 回写" → "stock-research 模式 3 回写" |
| `scripts/deep_redo_gate.py` / `deep_redo_anchor_audit.py` docstring | skill 名替换 |
| `tests/test_pool_index_match.py` | sys.path 改 `stock-research/scripts` |
| memory `MEMORY.md` | 索引行中的 skill 名替换 |

`docs/superpowers/plans|specs/` 历史文件与 `.omc/artifacts/` 不改。

## 验证

- `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_pool_index_match.py` 通过。
- `grep -rn "stock-deep-redo\|news-impact" CLAUDE.md .claude scripts tests` 只剩 `lessons.md` 历史叙事与 evals 提示词。
- `python scripts/lint_docs_frontmatter.py && python scripts/lint_docs_refs.py` 双 exit 0（本次不动 docs 池，应保持绿）。
- 对 evals 四条模式识别用例人工走一遍路由判据，确认各落到预期模式。
