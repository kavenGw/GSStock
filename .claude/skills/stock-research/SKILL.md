---
name: stock-research
description: >-
  统一投研入口，按输入形态自动识别四种模式并路由：(1) 个股深度分析/重做/重估 → 文件夹六文件 buffett 档；
  (2) 财报/业绩预告/年报分析 → 差量更新该股六文件；(3) 新闻/政策/行业事件对 docs 池的影响 → themes/ 专题档；
  (4) 业绩说明会/调研/交流纪要 → quarterly/ 点评档。凡用户要"深度分析 XX""重做 XX""XX 还能不能买"
  "看看 XX 这份财报""分析下 XX 季报""这条新闻/政策对我的股票有什么影响""利好哪些标的"
  "帮我看这份业绩说明会纪要/调研纪要/投资者交流记录"，或粘一段财报/新闻/纪要文本、给 PDF/URL，都务必触发本 skill——
  即使用户没说"buffett""重做""影响分析"也要触发。不要用于：板块批量分析（analyze-category）、
  首次持仓配置（portfolio-init）、再平衡（portfolio-rebalance）、清仓策略（liquidation-strategy）、只查实时价。
---

# stock-research — 统一投研入口

本文件只做**路由**：判模式 → 读对应 `references/mode-*.md` 照做。流程本体、闸门、派发内容全在 references 里，
本文件不重复。

## 四种模式

| # | 模式 | 输入形态 | 意图 | 产出 | 读 |
|---|------|----------|------|------|----|
| 1 | 深度分析 | 一只股票，**无附带材料**（或材料只是触发理由：涨价/AI/政策…） | 值不值得买 / 重估 / 重做 / 推翻旧结论 | `sectors/<sector>/<subsector>/<股票名>/` 六文件 | `references/mode-deep.md` |
| 2 | 财报分析 | 一只股票 + **财报/业绩预告/年报**（文本、PDF、URL） | 点评本体、看财报对旧 thesis 的影响 | 差量更新该股六文件（须已有文件夹档，否则升模式 1） | `references/mode-earnings.md` |
| 3 | 新闻影响 | 行业/政策/多主体事件；**或**单股事件但意图是"影响哪些票" | 利好利空谁、哪些票该重看 | `themes/YYYY-MM-DD-<主题>.md` | `references/mode-news.md` |
| 4 | 会议纪要 | 业绩说明会 / 调研 / 交流的 Q&A、纪要、transcript | 管理层口径对旧 thesis 的增量 | 单股 → `quarterly/<NNqN>/...纪要.md`；行业多主体会议 → 降级模式 3 | `references/mode-meeting.md` |

**判定顺序**：
1. 看附带材料类型：纪要/Q&A → 4；财报/预告/年报 → 2；新闻/政策/公告 → 3；无材料 → 1。
2. 再看意图：材料是单股财报或纪要、但用户问的是"对池/持仓/其他票的影响" → 3。
3. 模式 2 前置失败（该股无文件夹档）→ 升 1。模式 4 主体多家 → 降 3。

开工第一句：`识别为模式 N（<一句理由>），默认参数 <...>`，用户可当场纠正。

## 歧义门（只问这些，其余按默认直接做）

1. 单股财报/纪要，"点评本体"还是"看池影响"意图不明 → 问一句。
2. 模式 2/4 途中发现主论点被证伪、评级须翻转 → **不在本模式内翻**，报给用户并建议升级模式 1。
3. 模式 1 原有歧义门（跨两个一级 sector 主业权重接近 / 其实要 comps / 旧档与底稿冲突）见 `mode-deep.md`。

## 共享默认（所有模式）

- 语言中文；在 `main` 直接写档，不开 worktree，不主动 push（`.claude/rules/dev-environment.md` 分支策略）。
- `mkdir -p .omc/artifacts`（闸门脚本与临时产物落点，已 gitignore）。
- 避坑门：`docs/stock-analytics/avoidance-list.yaml` 对模式 1/2 生效，命中按 `.claude/rules/docs-conventions.md` 重验。
- 收尾闸门：`python scripts/lint_docs_frontmatter.py && python scripts/lint_docs_refs.py` 双 exit 0；
  写档规格见 `buffett-doc-spec`，删旧档/反向链/valuations 同步/提交协议见 `references/finalize.md`。
- 一次性脚本与 `.omc/artifacts/` 产物不入库。

## references 索引

| 文件 | 内容 | 谁读 |
|------|------|------|
| `mode-deep.md` | 模式 1 编排：先做 → A 三路并行 → B → 审查 → C，各阶段闸门与预估 | 控制者 |
| `mode-earnings.md` | 模式 2 编排：模式 1 的增量版（单路采证 + 差量覆盖） | 控制者 |
| `mode-news.md` | 模式 3 六步流程：核实 → 脚本召回 → 判传导 → theme 档门槛 → 对称 → 汇报 | 控制者 |
| `mode-meeting.md` | 模式 4 流程：核实 → 判主体 → 读旧档 → quarterly 档 → 反向链 | 控制者 |
| `dispatch.md` | 模式 1/2 每个 subagent 的派发内容 | 控制者，派发前读对应节 |
| `lessons.md` | 模式 1/2 实测教训 L1–L17，按编号翻 | 控制者 |
| `sector-lenses.md` | 板块视角注册表，控制者摘原文内联 | 控制者 |
| `impact-rubric.md` | 模式 3 传导 rubric + theme 档模板 | 控制者 |
| `finalize.md` | Phase C 收尾动作清单：删旧档 → 反向链 → 双 lint → valuations 同步 → 安全提交 → 亲验 | Phase C 执行者 |
| `scripts/pool_index.py` | 模式 2 溢出 / 模式 3 候选召回 | 脚本 |

## 维护规则

- 路由判据、歧义门、共享默认改本文件；各模式流程改对应 `mode-*.md`；教训只追加到 `lessons.md` 并在对应
  mode 文件闸门处加 `[Ln]` 引用。
- 新增模式 = 加一行表 + 一份 `mode-*.md` + `evals/evals.json` 一条识别用例。
- 本文件目标 **≤100 行**。
