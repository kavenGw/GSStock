
# 模式 3 · 新闻事件影响分析（原 news-impact）

拿一条新闻，问一个问题：**它改变了我 docs 池里哪些标的的投资逻辑，怎么改的？**

这个 skill 的价值不在"列一堆相关股票打 sentiment 分"——那是噪音。价值在**纪律**：先核实新闻真伪、把每个标的的影响接到它 doc 里**已有的旧 thesis 和评级**上、利好利空双面看、诚实标"无影响"、最后落一份能复查的 themes/ 档并把引用对称回个股 doc。

## 何时用 / 何时不用

**用**：用户给一条新闻/事件（粘文本或给 URL），想知道对 docs 池内标的的影响、利好利空、哪些该重看评级。

**不用**：单股深度重估 → 模式 1；单股财报点评本体 → 模式 2；单股会议纪要 → 模式 4；板块批量 → `analyze-category`；再平衡 → `portfolio-rebalance`；清仓 → `liquidation-strategy`；只查实时价/单个事实 → 直接查。

## 默认参数（烘进流程，不必每次问）

除非检测到歧义，按这些默认直接做，开工一句话说明用了什么默认：

| 维度 | 默认 |
|------|------|
| 输入 | 用户粘的新闻文本或 URL。给 URL → WebFetch 抓原文 |
| 搜索范围 | **仅 docs/stock-analytics 池**（不外扩 supply_chain.py 图谱），但池内上下游/同业二阶联动要追到 |
| 新闻核实 | **先核实再分析**，按信源分层（官方 1 家 / 媒体传闻 2-3 家）：传闻/标题党/已辟谣的，置信度压低并写明 |
| 产出形态 | 过建档门槛才写 `docs/stock-analytics/themes/YYYY-MM-DD-<主题>.md`（date=今天，≤250 行）+ related_docs 对称收尾（反向条目带 `impact`/`magnitude`）+ lint |
| 估值视角 | 影响落到旧 thesis/评级，不重算 DCF/RIM/目标价（要重估单股请转模式 1） |
| 语言 | 中文 |

## 流程

### 1. 核实新闻 + 抽取事件要素

- 用户给 URL → `WebFetch` 抓原文；给文本 → 直接用但**不照单全收**。
- **分层核实**（省成本）：信源是交易所公告 / 公司 PDF / 官方统计 → 只核 1 家确认原文存在即可；媒体转述 / 券商观点 / 传闻 → `WebSearch` 交叉验证 2-3 家。新闻是确认事实还是传闻？是否已被辟谣？是旧闻还是增量？
- 抽取要素：事件主体（公司/产品/政策）、事件类型（涨价/扩产/财报/并购/政策/缺货…）、涉及的行业/产品关键词、方向暗示。
- **事件类别**二分，后面闸门要用：
  - `单股事件`：一家公司的财报/业绩预告/定增/收购标的/订单/减持——主体只有一只票
  - `行业事件`：涨价/扩产/政策/关税/出口数据/平台方口径——主体是一条链
- 核实结论后续要写进 theme 档的"事件核实"节，置信度据此定。

**相关性快筛（早退闸门）**：核实后先问一句"这事的主体/行业/产品链与本池（A 股为主的半导体/电子/消费/材料/电力等宇宙）有没有交集？"——若明显**没有**交集（如纯美国本土 SaaS 并购、与中国产业链无关的海外消费事件），直接给"对本池无实质影响、不必建档"的简短结论收尾，**不要**构建全池索引、不要逐票分析。这一步省掉无谓的全池扫描成本。只有存在潜在交集（哪怕间接）才进入第 2 步。

### 2. 匹配候选标的（脚本分档召回）

把第 1 步抽出的要素喂给 bundled 脚本，直接拿分档候选清单（`--out` 必须在 `match` 之前）：

```bash
PYTHONIOENCODING=utf-8 python .claude/skills/stock-research/scripts/pool_index.py --out .omc/artifacts/pool_match.json \
  match --keywords "公司名片段,产品,主题词,subsector名" [--codes 603986,688766] [--sector semiconductor --subsector mcu]
```

输出（通常 <10KB）每条带 `code/name/rating/date/path/sector/subsector/thesis(前80字)`，同股多档已去重为最新 buffett 档：
- **T1** 直接命中：名称含关键词 / 代码相等
- **T2** 同 subsector：与 T1 同 subsector，或关键词正好等于某 subsector 名（`mcu`/`power`/`storage`…），或显式 `--subsector`
- **T3** themes 关键词命中
- **T4** 仅同 sector：默认**隐藏**只报 `T4_count`（半导体一个 sector 就 ~100 只）；确需铺开加 `--wide`

关键词要**多放**（中英文名、产品、材料、工艺、subsector 名），宁可 T3 多几只再在总览表里标"无影响"，不要在这步漏。**上下游联动**（新闻里的材料 → 池内下游用户）脚本抓不到，由你从 T1–T3 的 `thesis` 里补，不再全池扫；只有 T1–T3 全空且你确信池内有相关标的时，才退回全量索引（去掉 `match` 子命令即输出旧的 60KB 全池 JSON）。

### 3. 逐标的判传导（核心步骤）

读 `impact-rubric.md` 的传导 rubric。这步分两层，**先全后深**——既要覆盖广度（不漏弱相关标的），又不在弱标的上浪费篇幅：

**(a) 全员进总览表**：上一步召回的**每一个**候选标的都在影响总览表占一行，填齐：传导路径 / 方向（含"弱利好""无影响"）/ 量级（高/中/低）/ 时间窗 / **对旧 thesis** / 是否已 priced in / 置信度。弱相关、无影响的也要列出来并明确标注——这是给用户"我扫过、判过、不漏"的证据。

**(b) 只深写"中量级以上"**：量级达到**中或高**的标的，才单独展开逐标的传导分析段（双面看 + 接旧 thesis + 操作含义）。量级为"低/弱/无影响"的，**留在总览表里一行带过**，不展开，必要时合并成一句"扫描后判定无/弱传导：标的清单 + 各一句话理由"。

**读档分层**（省成本）：先只凭 match 输出里的 `thesis` 前 80 字 + `rating` 填总览表初判；**只有初判达中量级以上的标的才 Read 其 buffett 档原文**（核对旧 thesis、watch_reason、valuation），低量级一律不读原档。

铁律（详见 rubric）：
- **必须接旧 thesis**：脱离 doc 里旧评级的 sentiment 打分没有价值。要回答"这让 core 更稳 / 让 watch 该升 config / 让 exclude 该重看"。需要时读那只票的 buffett 档原文确认旧逻辑。
- **双面看**：扩产=下游成本利好+上游价格利空；涨价=厂商利好但问需求承接。拒绝单边叙事。
- **诚实标"无影响"**：硬凑关联比漏标的更伤可信度，但"列出来标无影响"≠"漏"——弱相关标的进总览表标"无/弱传导"，既不漏也不灌水。
- **反向证据优先**：若某票 doc/IR 口径已明确"此类事件无影响"，按"无影响"标注并引用，不翻案凑数。
- **质地（公司好坏）与估值（贵不贵）分开看**：本 skill 改的是 thesis/评级，不重算估值。但若事件**实质改变了公司质地**（护城河变宽/变窄、可持续利润中枢上移/下移——而非仅股价或估值波动），去 `docs/stock-analytics/valuations.yaml` 看该标的有无显式 `quality`（质地星 1-5）覆写：有则按新质地上调/下调，已过时的覆写删掉（回落到 rating 现算）；若你的判断同时让 `rating` 翻转，现算星级会自动跟随、无需手动写。**纯价格/估值变动不动质地。**详见 `finalize.md`「quality 质地星级」。

### 4. 落 theme 档（带门槛）

**建档门槛**（两道，都要过）——档案进了池子会成为后续选股/复查的信噪源，给"全是弱/情绪级利好"或"只关本体一家"的事件建档是污染：
1. **量级门槛**：至少一只标的传导量级达到"中"或以上。
2. **read-across 门槛（仅单股事件）**：第 1 步判为 `单股事件` 的，**除本体外**还须 ≥1 只池内标的达中量级。只影响本体的财报/预告/定增/收购承做，**不建 theme 档**——在对话里给总览表 + 结论，并明确一句"本体重估请转模式 1/2"。本体的 thesis 变化归模式 1/2 承做，不在 theme 档里替它重估。

不达标 → 默认**不建档**，只在对话里给影响总览表 + 结论，并问用户一句"要不要仍归档为主题背书？"——用户要才建。

**篇幅上限**（硬约束，写完自查）：
- 总览表不限行；逐标的深写段 **≤ 8 只、每只 ≤ 15 行**；全文（含 frontmatter）**≤ 250 行**。
- 正文出现"重算估值 / DCF / RIM / 目标价 / 期望内在价值"等重估动作即越界——theme 档只改 thesis/评级方向，不产估值数字。
- 超限说明事件本身是模式 1 量级：theme 档只留 read-across 部分，本体部分截断并在"操作含义"里写"转模式 1"。

落档模板见 `impact-rubric.md`，写到 `docs/stock-analytics/themes/YYYY-MM-DD-<主题>.md`：
- frontmatter 必填 `doc_type: theme` / `theme_name` / `themes` / `date`；`related_codes` 用字符串引号防丢前导 0；`related_docs` 只收**中量级以上**标的（低量级只进总览表、不建链，避免 related_docs 膨胀），加 `symmetric: true`。
- 正文：事件核实 → 影响总览表（全员）→ 逐标的传导分析（仅中量级以上展开）→ 操作含义。
- `<!-- BEGIN/END related_docs -->` 块留空，由 lint 生成。

### 5. related_docs 对称 + lint 收尾（必做）

theme 档引用了个股 doc，个股 doc 要反向引用回来，否则 refs lint 报不对称。回写位置按个股档形态分支：

- **文件夹档**（存在 `sectors/<sector>/<subsector>/<股票名>/events.md`）→ theme 档的 related_docs 指向 `.../<股票名>/events.md`，反向条目追加到 `events.md` 的 frontmatter `related_docs`（path 比平铺档多一层 `../`，形如 `../../../../themes/YYYY-MM-DD-<主题>.md`）；**index.md 不动**。
- **平铺档** → 沿用原逻辑，写该档 frontmatter。

给每个受影响个股 doc 的对应位置加一条指回 theme 档，**反向条目必带结论回写字段**（这是把 theme 结论结构化落回个股档的唯一通道，后续模式 1/2 据此看"有无未消化的动摇/推翻"）：

```yaml
- path: ../../../themes/YYYY-MM-DD-<主题>.md
  note: <一句话：新闻改变了旧 thesis 的哪个变量>
  impact: 强化 | 动摇 | 推翻 | 无关
  magnitude: 高 | 中 | 低
  symmetric: true
```

schema 只认这四个 `impact` 值、三个 `magnitude` 值，写错 frontmatter lint 会报。lint `--rewrite-blocks` 会把它渲染成 `【动摇·中】` 标签进顶部关联块。然后跑（repo 根的 scripts/）：

```bash
python scripts/lint_docs_refs.py --rewrite-blocks   # 重生所有顶部 markdown 块
python scripts/lint_docs_frontmatter.py             # 新 theme 档 frontmatter 合法性
python scripts/lint_docs_refs.py                    # 路径 + 反向对称，退出码 0 = 过
```

非 0 按违例清单补齐再复跑。

### 6. 收尾汇报

向用户一句话总结：核实结论 + 命中 N 只标的（按方向/量级排序的前几只）+ 哪些该调评级（以及哪只本体该转模式 1/2）+ theme 档路径与行数 + lint 是否通过。一次性数据脚本（如临时 pool_match.json 在 .omc/artifacts/ 已 gitignore）不入库。
