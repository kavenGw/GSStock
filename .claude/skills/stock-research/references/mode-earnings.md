# 模式 2 · 财报分析（模式 1 的增量版）

一份财报/业绩预告/年报落地 → 对该股**已有文件夹档**做差量重承做：只核财报改变了什么、只改受影响段落、
其余原文保留。角色、闸门、审查、收尾全部复用模式 1（`mode-deep.md` / `dispatch.md` / `lessons.md`），
差别只在采证缩成单路、撰写改成差量覆盖。

## 前置（不满足则升模式 1）

- 该股已有 `sectors/<sector>/<subsector>/<股票名>/` 七文件。只有平铺档或无档 → 首建/迁移需要完整承做，升模式 1，
  财报作为 A1 的必查项内联进去。文件夹已存在但缺 `related.md`（2026-08-24 前建的遗留六文件档，如士兰微/扬杰科技）
  → 同样升模式 1（Phase B 闸门硬性要求 `related.md`，遗留档借这次财报全量重做顺势补出第七个文件，见 `mode-deep.md`
  「存量文件夹档 index.md 的 related_docs 本轮迁进 related.md」条款）。
- 财报是**本体**的（主体一家）。用户意图若是"这份财报对池内其他票有什么影响" → 模式 3。

## 默认参数

| 维度 | 默认 |
|------|------|
| 产出 | 原地差量覆盖 `index/business/thesis/valuation/sources.md`；`events.md` / `related.md` 不动（结构性引用有增删才改 `related.md`）；`conviction_date`=今天 |
| 评级 | 可更新三情景数字与期望内在价值；**评级翻转不在本模式内做**——主论点被证伪即走 `SKILL.md` 歧义门 2，报用户并建议升模式 1 |
| 采证 | 单路 A1：财报原文（交易所/公司 PDF 一家核实即可）+ 指引/管理层口径 + 实时行情锚 |
| 溢出 | 财报暴露的行业信号对池内其他标的 ≥ 中量级时，用 `scripts/pool_index.py match` 召回并在汇报里列"建议看池的标的"，**不写 theme 档** |

## 编排：先做 → A'（单路）→ B'（差量）→ 审查 → C

### 先做（控制者本人）

1. Read 七文件。从 `valuation.md` 抽**旧档关键假设清单**（收入增速 / 毛利率 / 资本开支 / 分红 / 三情景概率与每股价值），
   从 `index.md` §11 抽**监控指标与卖出触发器**——这两张清单是 A1 对账的靶子，必内联。
2. 读 `events.md` 的 related_docs，theme `date` > 旧 `conviction_date` 的条目即「未消化事件」，摘 note/impact/magnitude 备内联。
3. 避坑门（`avoidance-list.yaml`）。
4. 财报材料：用户给 PDF/URL → 先抓原文；给文本 → 标明"用户粘贴，A1 须核原文存在"。
5. `mkdir -p .omc/artifacts`。

### Phase A' — 单路采证（1 个 opus）→ `dispatch.md §1` A1 节 + 以下增量

A1 交办在模式 1 的 A1 清单之上加三项：
- **逐条对账旧假设清单与 §11 触发器**：每条标 `证实 / 证伪 / 无信息`，证伪的给财报原文数字 + 页码/URL。
  **比率型阈值先跑上年同期回测，确认该指标对本公司有判别力再据以裁决** [L25]。
  触发器命中后只能执行、或在档内显式写出「触发器要求 X / 本档裁定 Y」的分歧，**不得重新解释其适用前提** [L37]；
  措辞含「再次/新增」的条款，须先 grep 旧档确认该事件是否已计入基线，并核证据级别达条款字面要求 [L38]。
- **指引与口径**：管理层对下季/全年的指引、订单/库存/产能利用率口径，原话摘要 + 来源。
- **一次性项剥离**：非经常损益、减值、汇兑、政府补助——写出扣除后的可比口径。

产出落 `.omc/artifacts/<股票名>-<日期>-A1.md`（明细层 + 结论层，见 `dispatch.md §0.1`）。

闸门：`python scripts/deep_redo_gate.py <股票名> <日期> --phase A --lanes A1`，exit 0 才派 B'。
等待按 [L7] 探测模板包一层。A1 报「前提变化」（主论点被证伪）→ 停，走歧义门 2。

### Phase B' — 差量撰写（1 个 opus）→ `dispatch.md §2` + 以下差量交办

内联：**A1 产出文件路径**（写手自 Read 明细层，勿把全文抄进 prompt）、旧档七文件路径、对账结果；兄弟档口径摘要可省。交办铁律：
- **只改受财报影响的段落**，逐文件：`business.md` 经营数据与分部；`thesis.md` 被证实/证伪的论点（证伪的改写并标"26QN 财报证伪"）；
  `valuation.md` 假设与三情景数字 + 末尾"相对旧档变化清单"（必须列出每个改动的数字：旧 → 新 → 依据）；
  `index.md` §0/§10/§11 与 frontmatter `valuation` 块、`thesis`、`conviction_date`；`sources.md` 追加财报来源。
- 未受影响段落**原文保留**，不润色、不重排。`events.md` 不动。
- 评级字段 `rating` 不改；若写手判断该翻，在**产出文件的结论层**写「建议升模式 1：<理由>」并在消息里点名，
  **不写进新档正文**（这是给控制者的信号，绝不该进 docs）。
- 数字镜像：frontmatter 所有含数字字段与正文一致（`buffett-doc-spec` 撰写纪律）。

闸门：`python scripts/deep_redo_gate.py <股票名> <日期> --phase B --doc <文件夹>`。

### 合并审查（1 个 read-only sonnet）→ `dispatch.md §3`

在模式 1 审查项之上加一项：**diff 审查**——`git diff <文件夹>` 里每处改动都能在 A1 evidence 找到依据；
没依据的改动列为 Major。闸门 `--phase review`。

### Phase C — 收尾（1 个 sonnet）→ `dispatch.md §4`（动作清单已在 `sr-finalize` 定义里）

无平铺旧档可删、无反向链新增（结构性引用不变），主要是 `valuations.yaml` 同步 + 双 lint + 按并行 session 协议提交。

**但本模式是旧档清理的主触发场景**（写中报时清同股一季报、清本期业绩预告 theme）：控制者按 `mode-deep.md`
步骤 **4b/4c** 判据扫本股被本次覆盖期取代的 `quarterly/**/*季报点评.md` 与**单主体**业绩预告 theme，
**surface 给用户确认后**并入待删清单传给 Phase C。无命中或用户不确认 → 清单为空，按原流程走。
4c 的 ④ 号前置（对账链已由 `events.md` note 承接）在本模式下须**先确认差量撰写已写进 note** 再列入清单。

## 溢出 read-across（控制者本人，可选）

A1 evidence 若出现行业级信号（涨价 / 缺货 / 资本开支转向 / 客户集中度变化），跑：

```bash
PYTHONIOENCODING=utf-8 python .claude/skills/stock-research/scripts/pool_index.py --out .omc/artifacts/pool_match.json \
  match --keywords "<信号关键词,产品,subsector>" --codes <本股代码>
```

T1–T3 里初判达中量级的标的列进汇报"建议看池"一节，附一句传导路径。要落 theme 档 → 用户另起模式 3。

## 收尾汇报

一行耗时账（A' + B' + 审查 + C），预估 **30-40min**。报：财报对旧假设的对账结果（证实 n / 证伪 m / 无信息 k）、
期望内在价值旧 → 新、评级是否建议翻转（若是 → 升模式 1）、建议看池的标的、lint 是否双绿、commit SHA。
默认在 `main` 直接提交，不主动 push。

## 维护规则

教训只追加到 `lessons.md`（与模式 1 共用编号），本文件对应闸门处加 `[Ln]`。派发内容变化改 `dispatch.md`。
