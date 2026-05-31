# NOR Flash 涨价纳入 stock-deep-redo — 设计文档

> 日期：2026-05-31　|　状态：已批准，待出实施计划
> 范围：① 给 stock-deep-redo 的存储 sector-lens 补一条独立的「NOR Flash 涨价」视角；② 用新 lens 重做 3 只 NOR 暴露标的。

## 1. 背景与问题

`stock-deep-redo` 的存储 sector-lens（`.claude/skills/stock-deep-redo/references/sector-lenses.md` 的「存储」节）当前的【必查清单】几乎全是 **DRAM/NAND 供给侧**：现货/合约价、三大原厂退出 DDR4/利基 DRAM、HBM 挤出标准 DRAM 产能。**NOR Flash 仅出现在【识别信号】里**，必查/撰写/双面/监控四段都没有 NOR 专属条目。

后果：今天（5-31）重做的兆易档虽零散提到 NOR 涨价（中小容量 SKU 单月 >30%、AMOLED NOR 42-45%、AI server boot/BMC NOR），但都是被 DRAM 主线带出来的副线，没有把"NOR 自成一条供给侧逻辑"系统化；君正档里 NOR 更是被当成 #5 边角料一笔带过。

而 NOR 涨价是**独立于 DRAM 的供需引擎**：
- **供给侧** = 大厂主动退出（Cypress/Infineon 车规 NOR、Micron 早退）+ 代工产能分配（中芯/华虹/力积电），**不是** DRAM 的 HBM 挤出。
- **需求侧** = AMOLED 渗透（每屏 1 颗）、AI server BMC/boot NOR、车规（AEC-Q100）、TWS/可穿戴、工业。
- **盘子与格局** = 全球约 30 亿美元、CR3 >70%，价格波动逻辑与 DRAM 不同步。

## 2. 目标

1. lens 层：让未来任何存储个股 redo 都能系统化识别并双面拷问 NOR 涨价，而不再当 DRAM 副线。
2. 个股层：用定稿后的 NOR lens 重做 3 只标的，刷新结论。

非目标（YAGNI）：不新建 NOR 涨价横评 comps（本次产出是个股 buffett 重做，非 comps）；如需另起任务。

## 3. 执行方案

**方案 1（采纳）：lens 先行 + 个股串行。** 先把 NOR lens 节写好并过审 → 依次跑 3 只，每只 redo 吃到定稿的 NOR lens。
- 理由：NOR lens 是三只共同输入，先定稿最干净；串行契合 skill"串行、不并行派实现者"的纪律，避免 docs/lint 的 git 写入打架。
- 备选方案 2（个股并行）因 stock-deep-redo 为单股设计、三条采证流质量难盯、git 冲突风险被否；方案 3（只做普冉）与"跑三只"的决定不符被否。

执行顺序：**改 lens → 普冉(全重做) → 东芯(全重做) → 兆易(NOR 补强) → 统一 lint 收尾。**

## 4. NOR Flash lens 内容设计

**结构**：在 `sector-lenses.md` **新增独立一节「存储 — NOR Flash」**（五段式），不塞进现有 DRAM/NAND 存储节。现有存储节收窄为 DRAM/NAND；两节可叠加（兆易/东芯/君正会同时命中）。依据文件自带规则"加新板块只需追加一节五段式"。

**铁律遵守**：lens 只写"必查问题"，绝不写死会过时的具体数字/日期/退出范围（这些由 Phase A 实时联网采证）。

五段拟定内容：

- **【识别信号】** subsector storage/memory + 主营含 NOR / SPI NOR / 串行闪存 / 代码型闪存 / AMOLED 驱动存储 / EEPROM（邻接）；玩家锚：兆易 / 普冉 / 东芯 / 武汉新芯 / 旺宏 / 华邦 / 恒烁。

- **【必查清单（采证 face）】**
  1. NOR 现货/合约价**分容量段**（小容量 ≤256Mb vs 中大容量 512Mb-2Gb）报价分化；热门 SKU 单月涨幅 vs 整体口径。
  2. 供给侧：Cypress/Infineon 车规 NOR 退出/EOL、Micron 早退、旺宏/华邦产能迁移或减产 + **可逆性**；明确 NOR 驱动 ≠ HBM 挤出，是大厂退出 + 代工产能分配。
  3. 需求侧结构增量逐条要数字 + 第三方机构口径：AMOLED 渗透（每屏 1 颗，手机/折叠/车载）/ AI server BMC·boot NOR（单机价值量、服务器出货）/ 车规（AEC-Q100，ADAS/智能座舱）/ TWS·可穿戴 / 工业。
  4. 标的**容量段卡位**：小容量 vs 中大容量 512Mb-1Gb vs 车规——景气与毛利分化。
  5. 工艺节点（SONOS 55/50/45nm）与代工依赖（自有 vs 中芯/华虹/力积电），降本路径。
  6. EEPROM/SPD 邻接（DDR5 SPD 用 EEPROM）是否纳入同一涨价链。

- **【撰写落点（撰写 face）】**
  - §6 核心新论点：NOR 供给侧（独立于 DRAM HBM 挤出）+ 需求结构增量，结构性 vs 周期性二分判定。
  - §2 TAM：分容量段、分应用拆 NOR SAM/SOM。
  - §3 盈利能力：NOR 涨价弹性**按容量段**精算（小容量纯弹性 vs 中大容量）。
  - §8 周期定位：NOR 周期与 DRAM **不同步**（盘子小、CR3 >70%、价格逻辑不同）。

- **【双面必答】**
  - NOR 涨价是"大厂退出的结构性缺口"还是"DRAM 涨价外溢带动的周期性补涨"？
  - 旺宏/华邦产能可回流吗？
  - 涨价能兑现到标的净利，还是被代工（中芯/华虹）涨价吃掉？
  - AMOLED/AI server NOR 增量是否已被股价 price-in；NOR 占标的营收比重（纯弹性 vs 温和受益）。

- **【监控指标模板】**
  - NOR 现货（分容量段）环比转跌 / 旺宏·华邦复产·扩产公告。
  - AMOLED 面板出货·渗透率增速下修、AI server 出货指引下修。
  - 标的 NOR 毛利较峰值回落 > X ppt / 代工（中芯/华虹/力积电）NOR 报价上调侵蚀毛利。
  - 标的 NOR 营收占比与价格弹性匹配度（验证纯弹性 vs 温和受益）。

## 5. 个股重做计划

### 5.1 普冉股份 688766 — 全重做（stock-deep-redo 全流程）
- 定位：最纯的小容量 NOR+EEPROM 弹性标的；4-25 旧档完全无本轮供给侧。命中 lens：**NOR（主）+ AI（横切）**。
- 采证重点：小容量段（≤256Mb）报价、普冉在该段份额/卡位、EEPROM（含 DDR5 SPD）邻接涨价、fabless 代工依赖、车规 NOR 进展。
- 落档：新建 `conviction_date: 2026-05-31` + `git rm` 4-25 旧 buffett 档，反向链改指新档。

### 5.2 东芯股份 688110 — 全重做
- 注意：此股**不在 watch 股票池 DB**，但有 5-19 buffett 档；代码以档内 frontmatter 为准（设计文档暂记 688110，执行时校验）。
- 定位：多线利基 = SLC NAND + NOR + 利基 DRAM。命中 lens：**NOR + DRAM/NAND（叠加）+ AI**——验证"两节可叠加"的典型。
- 采证重点：NOR 与 NAND 双线景气分化、各自营收占比与弹性、利基 DRAM 小敞口。
- 落档：新建 5-31 + `git rm` 5-19 旧档，反向链改指。

### 5.3 兆易创新 603986 — NOR 主线补强（非全重做）
- **偏离 skill 默认**（默认 git rm + 新建）：兆易今天刚做过，只在 5-31 现档**原地 Edit** 深化四节：
  - §2：NOR 分容量段/应用 TAM。
  - §3：NOR 涨价弹性分容量段精算。
  - §6：把 NOR 供给侧**与 DRAM HBM 挤出并列**写成独立子论点（Cypress/Infineon 退出 + AMOLED + AI server boot NOR）。
  - §8：NOR 周期 vs DRAM 周期不同步。
- 流程裁剪：Phase A 只采 NOR 专项证据 → 原地 Edit 四节 → 单段质量审查（不重跑规格全审，结构未动）。
- `conviction_date` 维持 5-31；rating 除非证据翻转否则维持 watch。

## 6. 收尾与验收

- 普冉/东芯：`git rm` 旧档 + 扫所有 `symmetric: true` 指向被删档的反向条目 → 改指新档 + `python scripts/lint_docs_refs.py --rewrite-blocks` 重生顶部块。
- 新档 related_docs 互链到既有底稿并保证对称：`2026-05-25 兆易-君正 comps`、`2026-05-15 利基型存储涨价-SLC-NAND-comps`、`2026-05-20 存储扩厂双雄受益链-comps`、兆易/君正 5-31 buffett 档。
- 兆易：原地 Edit 无删档；若 NOR 补强新增 related_docs，更新对称链。
- **验收门**：`lint_docs_frontmatter.py` 与 `lint_docs_refs.py` 双双 exit 0；`--check-orphans` 确认新档非孤儿；一次性采证脚本已删、evidence.md 未入库。
- 控制者 `git log --oneline` + `git status` 确认 commit 链干净，向用户汇报每只评级是否翻转、期望内在价值、安全边际。默认 main 直接提交、不主动 push。

## 7. 风险与注意

- 东芯不在 DB 股票池，执行时先 Read 其 5-19 档 frontmatter 确认 `stock_code`，删档前按 skill 铁律核对"档名含股票名 + frontmatter code 一致"。
- NOR 与 DRAM 涨价证据易混淆口径（兆易档已有此教训：TrendForce/The Elec 多口径）。采证须把 NOR 报价口径与 DRAM 报价口径分开标注来源。
- 兆易补强是 in-place edit，注意不要破坏既有 §6 DRAM 论点结构与 related_docs 块（`<!-- BEGIN/END related_docs -->` 不手编）。
