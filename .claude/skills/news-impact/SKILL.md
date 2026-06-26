---
name: news-impact
description: >-
  把一条新闻/事件映射到 docs/stock-analytics 已建档的标的池，逐个判断传导路径、方向、量级，
  并落到每只票 doc 里的旧 thesis（强化/动摇/推翻），最后产出一份 themes/ 专题档并做 related_docs 对称收尾。
  当用户给出一条新闻、政策、财报、涨价/扩产、并购、行业事件，并想知道"这对我关注的股票/持仓有什么影响""利好/利空哪些标的"
  "哪些票该重看"时，务必触发本 skill——即使用户没说"影响分析"也要触发。典型触发语：
  "这条新闻对我的股票有什么影响""某事件利好哪些标的""帮我看看这个政策影响哪些票""粘一段新闻分析下影响"。
  不要用于：单只个股深度重做（用 stock-deep-redo）、板块批量分析（用 analyze-category）、
  纯季报点评（quarterly 流程）、持仓再平衡（portfolio-rebalance）、清仓（liquidation-strategy）。
---

# 新闻事件影响分析（news-impact）

拿一条新闻，问一个问题：**它改变了我 docs 池里哪些标的的投资逻辑，怎么改的？**

这个 skill 的价值不在"列一堆相关股票打 sentiment 分"——那是噪音。价值在**纪律**：先核实新闻真伪、把每个标的的影响接到它 doc 里**已有的旧 thesis 和评级**上、利好利空双面看、诚实标"无影响"、最后落一份能复查的 themes/ 档并把引用对称回个股 doc。

## 何时用 / 何时不用

**用**：用户给一条新闻/事件（粘文本或给 URL），想知道对 docs 池内标的的影响、利好利空、哪些该重看评级。

**不用**：单股深度重估 → `stock-deep-redo`；板块批量 → `analyze-category`；季报点评 → quarterly 流程；再平衡 → `portfolio-rebalance`；清仓 → `liquidation-strategy`；只查实时价/单个事实 → 直接查不起 skill。

## 默认参数（烘进流程，不必每次问）

除非检测到歧义，按这些默认直接做，开工一句话说明用了什么默认：

| 维度 | 默认 |
|------|------|
| 输入 | 用户粘的新闻文本或 URL。给 URL → WebFetch 抓原文 |
| 搜索范围 | **仅 docs/stock-analytics 池**（不外扩 supply_chain.py 图谱），但池内上下游/同业二阶联动要追到 |
| 新闻核实 | **先联网核实再分析**：传闻/标题党/已辟谣的，置信度压低并写明 |
| 产出形态 | 直接写一份 `docs/stock-analytics/themes/YYYY-MM-DD-<主题>.md`（date=今天）+ related_docs 对称收尾 + lint |
| 估值视角 | 影响落到旧 thesis/评级，不重算 DCF（要重估单股请转 stock-deep-redo） |
| 语言 | 中文 |

## 流程

### 1. 核实新闻 + 抽取事件要素

- 用户给 URL → `WebFetch` 抓原文；给文本 → 直接用但**不照单全收**。
- **联网核实**：关键数字/主体/真伪交叉验证 2-3 家信源（`WebSearch`）。新闻是确认事实还是传闻？是否已被辟谣？是旧闻还是增量？
- 抽取要素：事件主体（公司/产品/政策）、事件类型（涨价/扩产/财报/并购/政策/缺货…）、涉及的行业/产品关键词、方向暗示。
- 核实结论后续要写进 theme 档的"事件核实"节，置信度据此定。

**相关性快筛（早退闸门）**：核实后先问一句"这事的主体/行业/产品链与本池（A 股为主的半导体/电子/消费/材料/电力等宇宙）有没有交集？"——若明显**没有**交集（如纯美国本土 SaaS 并购、与中国产业链无关的海外消费事件），直接给"对本池无实质影响、不必建档"的简短结论收尾，**不要**构建全池索引、不要逐票分析。这一步省掉无谓的全池扫描成本。只有存在潜在交集（哪怕间接）才进入第 2 步。

### 2. 构建池索引并匹配候选标的

跑 bundled 脚本拿到全池紧凑索引（一次扫描代替逐篇读 161 篇 doc）：

```bash
PYTHONIOENCODING=utf-8 python .claude/skills/news-impact/scripts/pool_index.py --out .omc/artifacts/pool_idx.json
```

读这份 JSON（约 60KB），按四条线**尽量多召回**候选标的（宁可多列再分级，不要在这步就剪枝）：
1. 直接命中：新闻点名的公司名/代码 = 某 doc 的 `names`/`codes`
2. 同业：命中标的的 `sector`+`subsector` 下的其它标的
3. 上下游：新闻里的产品/材料在池内的下游用户、或上游供应商（看 thesis/subsector 语义）
4. 主题：新闻关键词 ⊂ 某 doc 的 `themes`

> 池索引字段：`path/doc_type/codes/names/sector/subsector/themes/rating/thesis/date`。同股多 doc 时以最新 `date` 的 `buffett` 档为权威评级锚。

### 3. 逐标的判传导（核心步骤）

读 `references/impact-rubric.md` 的传导 rubric。这步分两层，**先全后深**——既要覆盖广度（不漏弱相关标的），又不在弱标的上浪费篇幅：

**(a) 全员进总览表**：上一步召回的**每一个**候选标的都在影响总览表占一行，填齐：传导路径 / 方向（含"弱利好""无影响"）/ 量级（高/中/低）/ 时间窗 / **对旧 thesis** / 是否已 priced in / 置信度。弱相关、无影响的也要列出来并明确标注——这是给用户"我扫过、判过、不漏"的证据。

**(b) 只深写"中量级以上"**：量级达到**中或高**的标的，才单独展开逐标的传导分析段（双面看 + 接旧 thesis + 操作含义）。量级为"低/弱/无影响"的，**留在总览表里一行带过**，不展开，必要时合并成一句"扫描后判定无/弱传导：标的清单 + 各一句话理由"。

铁律（详见 rubric）：
- **必须接旧 thesis**：脱离 doc 里旧评级的 sentiment 打分没有价值。要回答"这让 core 更稳 / 让 watch 该升 config / 让 exclude 该重看"。需要时读那只票的 buffett 档原文确认旧逻辑。
- **双面看**：扩产=下游成本利好+上游价格利空；涨价=厂商利好但问需求承接。拒绝单边叙事。
- **诚实标"无影响"**：硬凑关联比漏标的更伤可信度，但"列出来标无影响"≠"漏"——弱相关标的进总览表标"无/弱传导"，既不漏也不灌水。
- **反向证据优先**：若某票 doc/IR 口径已明确"此类事件无影响"，按"无影响"标注并引用，不翻案凑数。
- **质地（公司好坏）与估值（贵不贵）分开看**：本 skill 改的是 thesis/评级，不重算估值。但若事件**实质改变了公司质地**（护城河变宽/变窄、可持续利润中枢上移/下移——而非仅股价或估值波动），去 `docs/stock-analytics/valuations.yaml` 看该标的有无显式 `quality`（质地星 1-5）覆写：有则按新质地上调/下调，已过时的覆写删掉（回落到 rating 现算）；若你的判断同时让 `rating` 翻转，现算星级会自动跟随、无需手动写。**纯价格/估值变动不动质地。**详见 stock-deep-redo `references/playbook.md` §8「quality 质地星级」。

### 4. 落 theme 档（带门槛）

**建档门槛**：只有当**至少一只标的传导量级达到"中"或以上**时才落 themes/ 档——因为档案进了池子会成为后续选股/复查的信噪源，给"全是弱/情绪级利好"的事件建档是污染。判定分两种：
- **达标（≥1 只中量级）**：按下方模板落档。
- **不达标（全是低/弱/情绪级）**：默认**不建档**，只在对话里给出影响总览表 + 结论，并问用户一句"要不要仍归档为主题背书？"——用户要才建。这避免了为弱传导事件强行造档。

落档模板见 `references/impact-rubric.md`，写到 `docs/stock-analytics/themes/YYYY-MM-DD-<主题>.md`：
- frontmatter 必填 `doc_type: theme` / `theme_name` / `themes` / `date`；`related_codes` 用字符串引号防丢前导 0；`related_docs` 对受影响个股档加 `symmetric: true`。
- 正文：事件核实 → 影响总览表（全员）→ 逐标的传导分析（仅中量级以上展开）→ 操作含义。
- `<!-- BEGIN/END related_docs -->` 块留空，由 lint 生成。

### 5. related_docs 对称 + lint 收尾（必做）

theme 档引用了个股 doc，个股 doc 要反向引用回来，否则 refs lint 报不对称。给每个受影响个股 doc 的 frontmatter `related_docs` 加一条指回 theme 档，然后跑（repo 根的 scripts/）：

```bash
python scripts/lint_docs_refs.py --rewrite-blocks   # 重生所有顶部 markdown 块
python scripts/lint_docs_frontmatter.py             # 新 theme 档 frontmatter 合法性
python scripts/lint_docs_refs.py                    # 路径 + 反向对称，退出码 0 = 过
```

非 0 按违例清单补齐再复跑。

### 6. 收尾汇报

向用户一句话总结：核实结论 + 命中 N 只标的（按方向/量级排序的前几只）+ 哪些该调评级 + theme 档路径 + lint 是否通过。一次性数据脚本（如临时 pool_idx.json 在 .omc/artifacts/ 已 gitignore）不入库。
