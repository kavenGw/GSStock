# 立讯精密 buffett 重做（六维 + Rubin 三情景 + iPhone 新周期 + 双轨）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 5-30 偏空的立讯 buffett 档 `git mv` 到 5-31 并六维深度重写，量化 Rubin/AI/iPhone 上行催化，给出双轨估值结论。

**Architecture:** 单文档原地重做。先联网取证锁数字（5 项）+ 刷新价格，再 git mv 保历史，逐节重写（§1-§6），§2 现金流硬证据不软化，§6 双轨结论并列，最后跑两支 lint 收尾提交。

**Tech Stack:** Markdown + YAML frontmatter；数据 = WebSearch 取证 + akshare 补采 + `get_realtime_prices` 刷价；校验 = `scripts/lint_docs_frontmatter.py` + `scripts/lint_docs_refs.py`。

**约定**：Windows 写文件显式 `encoding='utf-8'`；一次性脚本走 `scripts/_xxx.py`（顶部 `sys.path.insert`），产物存 `.omc/artifacts/`，结束 `rm`；git 命令加 `rtk` 前缀。

---

## Task 1: 联网取证 —— 锁定五项前瞻数字 + 刷新价格

**Files:**
- Artifact: `.omc/artifacts/luxshare-research-2026-05-31.md`（取证笔记，gitignore）

- [ ] **Step 1: 刷新当前价/市值/PE/PB（基准日 2026-05-31）**

A 股实时价优先腾讯 HTTP 直连（最快无副作用）：

```bash
PYTHONIOENCODING=utf-8 python -c "import urllib.request; print(urllib.request.urlopen('http://qt.gtimg.cn/q=sz002475', timeout=10).read().decode('gbk'))"
```

记录字段：`[3]=price [45]=市值(亿) [39]=PE_TTM [46]=PB`。写入 artifact 笔记的"价格基准"段。

- [ ] **Step 2: WebSearch 取证 Rubin/GB300 高速铜连接单柜价值量 + 立讯 NVIDIA 链份额**

检索关键词（交叉 2-3 家）：`Rubin NVL144 copper cable connector content per rack`、`GB300 高速铜连接 单柜价值量 立讯精密 份额`。
锁定：单柜铜连接价值量区间（USD）、出货量级（柜/GPU）、立讯在背板连接器/线缆环节传闻份额。传闻口径标注"传闻/未证实"。写入 artifact"§4 Rubin"段。

- [ ] **Step 3: WebSearch 取证 iPhone 折叠屏上市时点 / BOM 增量 / 立讯铰链卡位**

关键词：`iPhone foldable 2026 release BOM cost hinge supplier`、`苹果 折叠屏 铰链 立讯精密 结构件`。
锁定：上市时点（2026/2027）、单机 BOM/ASP 增量、铰链+精密结构件单机价值量、立讯卡位（是否独供/二供）、首年出货预估。写入 artifact"§5 折叠屏"段。

- [ ] **Step 4: WebSearch 取证 FY26 iPhone 出货预估（多家投行口径交叉）**

关键词：`iPhone shipments 2026 forecast units Apple`、`iPhone 17 出货 预估 投行`。
锁定：FY26 出货量级（亿部）+ 同比，至少 2 家口径。写入 artifact"§5 iPhone 基本盘"段。

- [ ] **Step 5: WebSearch 取证 Amphenol(APH)/TE(TEL) 互联收入体量（全球对标）**

关键词：`Amphenol communications solutions revenue 2025`、`TE Connectivity data devices revenue`。
锁定：两家互联/数通分部年收入（USD bn）+ 立讯连接器收入占比对照。写入 artifact"§1 全球竞争"段。

- [ ] **Step 6: akshare 补采（按需）确认立讯最新分部/财务口径**

仅当现档 FY2025 数据需复核时跑（脚本 `scripts/_luxshare_fin.py`，顶部加 sys.path）：

```python
import akshare as ak
df = ak.stock_financial_abstract_ths(symbol="002475", indicator="按年度")
print(df.tail(6).to_string())
```

跑完 `rm scripts/_luxshare_fin.py`。结果并入 artifact。

- [ ] **Step 7: 取证完整性自检**

确认 artifact 五段（价格/§4 Rubin/§5 折叠屏/§5 iPhone/§1 对标）每段均有 ≥2 来源或显式标注"单一来源/传闻"。缺口回到对应 Step 补检。无 git commit（artifact 已 gitignore）。

---

## Task 2: git mv + frontmatter 重写

**Files:**
- Move: `docs/stock-analytics/sectors/electronics/ems/2026-05-30-立讯精密-buffett分析.md` → `2026-05-31-立讯精密-buffett分析.md`
- Modify: 新路径 frontmatter（行 1-25）

- [ ] **Step 1: git mv 保历史**

```bash
rtk git mv "docs/stock-analytics/sectors/electronics/ems/2026-05-30-立讯精密-buffett分析.md" "docs/stock-analytics/sectors/electronics/ems/2026-05-31-立讯精密-buffett分析.md"
```

- [ ] **Step 2: 改写 frontmatter**

用 Edit 改新文件 frontmatter：
- `conviction_date: 2026-05-31`
- `stock_code: '002475'`（保持字符串引号）
- `rating: watch`（维持）
- `watch_reason` 改写为双轨口径：纪律轨偏空（毛利率十年腰斩/FCF 仅净利 43%/估值已计入 AI 完美兑现）+ 成长轨上行已量化（Rubin 三情景/iPhone 新周期），二者并列，等报表 PE 回落或 AI·汽车毛利财报实证再入合格买点。
- `themes` 保留：消费电子 / ai_compute / 汽车线束
- `related_docs` 三篇路径不变（歌尔对比 / 汽车线束专题 / 工业富联）

- [ ] **Step 3: 提交 git mv + frontmatter**

```bash
rtk git add -A && rtk git commit -m "docs(立讯精密): git mv 5-30→5-31 + frontmatter 双轨口径准备六维重写

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: §1 市场规模与全球竞争格局

**Files:**
- Modify: `2026-05-31-立讯精密-buffett分析.md`（正文 §1）

- [ ] **Step 1: 写 §1**

替换原"Circle of Competence / Business Quality"中关于竞争格局的零散句，新增独立 §1 节，含：
- 三块 TAM 拆分表：消费电子代工 / AI 高速铜连接（224G/448G、背板+线缆）/ 汽车线束，各列市场规模量级 + 立讯收入与份额
- 全球对标：Amphenol(APH)/TE(TEL) 互联收入体量 vs 立讯连接器收入（用 Task 1 取证数字，标来源年度）
- 定位结论：立讯是高速互联**追赶者非定义者**，消费电子代工龙头但 commodity

数字一律标注来源与年度；传闻标"传闻"。

- [ ] **Step 2: 自检 §1**

确认每个量化数字有来源标注，无"待核实/TBD"占位。

- [ ] **Step 3: 提交**

```bash
rtk git add -A && rtk git commit -m "docs(立讯精密): §1 市场规模与全球竞争格局（TAM 三拆+APH/TEL 对标）

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: §2 盈利能力与现金流真相（不软化）

**Files:**
- Modify: `2026-05-31-立讯精密-buffett分析.md`（正文 §2）

- [ ] **Step 1: 写 §2**

整合原"Financial Snapshot + 近 5 年自由现金流"为独立 §2，**保留全部硬证据不软化**：
- 毛利率 23.3%(2014)→11.9%(2025) 十年腰斩；净利率 5.47%
- ROE ~21% 但由杠杆制造（负债率 66%、权益乘数 ~2.9x、ROIC 仅 10-12%）
- 近 5 年 FCF 表（2021-2025，累计净利 571.5 / FCF +245.1 ≈ 43%）原样保留
- 2025 capex 179 亿致当年 FCF −5.8 亿
- 真实股东盈余 ≈ 净利 45-55% ≈ 75-90 亿

- [ ] **Step 2: 自检 §2 未软化**

逐条比对原档：毛利率腰斩、FCF/净利 43%、capex 黑洞三项措辞强度不得弱于原档。

- [ ] **Step 3: 提交**

```bash
rtk git add -A && rtk git commit -m "docs(立讯精密): §2 盈利能力与现金流真相（硬证据保留不软化）

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: §3 核心优势/护城河

**Files:**
- Modify: `2026-05-31-立讯精密-buffett分析.md`（正文 §3）

- [ ] **Step 1: 写 §3**

独立 §3，含：
- 核心优势：垂直整合 + 精密制造工艺 + 王来春执行力（营收 3.5 亿→3323 亿）+ 连接器切换成本雏形
- 张力论证：上述优势 vs commodity 本质（定价权弱、客户集中、年降压力）—— 优势是"经营体优秀"非"生意护城河宽"
- 管理层：诚信 ✅ / 资本配置中等偏紧（莱尼跨境整合周期长、capex 高企）/ 主人翁心态 ✅ / 机构强迫令警示 ⚠️（四战场同时扩张）

- [ ] **Step 2: 提交**

```bash
rtk git add -A && rtk git commit -m "docs(立讯精密): §3 核心优势与护城河（优秀经营体 vs commodity 本质张力）

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: §4 Rubin/AI 三情景量化

**Files:**
- Modify: `2026-05-31-立讯精密-buffett分析.md`（正文 §4）

- [ ] **Step 1: 写 §4 含三情景表**

独立 §4，用 Task 1 取证数字建熊/基/牛三情景表，列：

| 情景 | Rubin/GB 出货(柜或 GPU) | 单柜铜连接价值量 | 立讯份额 | AI 连接收入(亿) | 增量毛利(亿) |
|---|---|---|---|---|---|

- 假设全部标注来源/口径；传闻份额标"传闻"
- 文字论证：为何这是 31x 估值的核心支撑、Amphenol/TE 卡位风险（份额能否持续抢）
- 结论：AI 连接是结构改善亮点，但牛市情景兑现需完美执行

- [ ] **Step 2: 自检 §4**

三情景假设链可追溯（出货×价值量×份额），无凭空数字。

- [ ] **Step 3: 提交**

```bash
rtk git add -A && rtk git commit -m "docs(立讯精密): §4 Rubin/AI 三情景量化（单柜价值量×份额×熊基牛）

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: §5 iPhone 新周期（出货弹性 + 折叠屏 BOM）

**Files:**
- Modify: `2026-05-31-立讯精密-buffett分析.md`（正文 §5）

- [ ] **Step 1: 写 §5 两条线**

独立 §5：
- **①FY26 iPhone 出货弹性**：用 Task 1 出货预估，算立讯组装份额 + AirPods/Watch 份额 × ASP → 消费电子基本盘收入弹性区间
- **②折叠屏 iPhone**：BOM 增量表 —— 铰链 + 精密结构件 + 连接器单机价值量增量 × 立讯卡位（独/二供）× 渗透节奏（首年/三年出货）→ 增量收入区间
- 结论：iPhone 新周期是基本盘修复 + 折叠屏期权，量化其对 FY27/FY28 的贡献

- [ ] **Step 2: 自检 §5**

折叠屏卡位为传闻则显式标注；BOM 增量给区间不给单点。

- [ ] **Step 3: 提交**

```bash
rtk git add -A && rtk git commit -m "docs(立讯精密): §5 iPhone 新周期（FY26 出货弹性+折叠屏 BOM 量化）

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 8: §6 双轨估值与结论 + Sell Criteria + Monitoring

**Files:**
- Modify: `2026-05-31-立讯精密-buffett分析.md`（正文 §6 + Conclusion）

- [ ] **Step 1: 写 §6 双轨**

- **纪律轨**：真实股东盈余多倍数法 → 内在价值区间（沿用 2000-2500 亿框架按新数据微调）→ 安全边际（现价 vs 内在价值）→ 合格买点（报表 PE ≤15x ≈ 35 元 观察线）
- **成长轨**：§4+§5 三情景加权 FY27/FY28 盈利 → 期望市值区间；显式前提"为成长付溢价 = 博弈非投资，需 Rubin 份额+折叠屏+汽车毛利同时兑现"
- 双轨并列结论：空仓者/持有者各自读法；主评级维持 watch

- [ ] **Step 2: 更新 Conclusion + Sell Criteria 逐项 + Monitoring Indicators**

- 顶部 Conclusion 改为双轨口径
- Sell Criteria 四项复核（严重高估✓ / 护城河窄化⚠️ / 管理层诚信否 / 机会成本✓）
- Monitoring：AI 连接收入毛利、综合毛利率趋势、capex/FCF 转正、苹果占比、折叠屏量产进度

- [ ] **Step 3: 提交**

```bash
rtk git add -A && rtk git commit -m "docs(立讯精密): §6 双轨估值与结论（纪律轨+成长轨并列）+ Sell/Monitoring 复核

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 9: lint 收尾 + 清理

**Files:**
- Run: `scripts/lint_docs_frontmatter.py`、`scripts/lint_docs_refs.py`

- [ ] **Step 1: frontmatter lint**

```bash
PYTHONIOENCODING=utf-8 python scripts/lint_docs_frontmatter.py
```

Expected: 退出码 0。非 0 则按违例清单修 frontmatter 字段。

- [ ] **Step 2: related_docs 反向对称 + 重生块**

```bash
PYTHONIOENCODING=utf-8 python scripts/lint_docs_refs.py --rewrite-blocks
```

Expected: 退出码 0，三篇 related_docs 块按新路径重生。三篇关联档若有指回 5-30 旧路径的反向引用，同步改成 5-31。

- [ ] **Step 3: 确认一次性脚本已清理**

```bash
ls scripts/_luxshare*.py 2>/dev/null && echo "STILL EXISTS - rm it" || echo "clean"
```

Expected: `clean`。

- [ ] **Step 4: 最终提交（含 lint 重生块 + 关联档反向引用修正）**

```bash
rtk git add -A && rtk git commit -m "docs(立讯精密): lint 收尾(frontmatter 过/refs 对称/块重生)+关联档反向引用对齐 5-31

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Self-Review（plan 对 spec 覆盖核对）

- spec §1-§6 六节 → Task 3-8 一一对应 ✓
- spec 研究计划 5 项 WebSearch → Task 1 Step 2-6 ✓
- spec git mv 5-30→5-31 → Task 2 Step 1 ✓
- spec §2 不软化 → Task 4 Step 2 自检 ✓
- spec 双轨结论不互相覆盖 → Task 8 Step 1 ✓
- spec lint 收尾 + 一次性脚本 rm → Task 9 ✓
- spec related_docs 反向对称 → Task 9 Step 2（含三篇旧路径反向引用修正）✓
