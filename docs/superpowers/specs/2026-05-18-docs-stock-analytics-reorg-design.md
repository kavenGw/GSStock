# docs/ 股票分析目录重组 + 文档表头架构优化 — Design

> 日期：2026-05-18
> 范围：`docs/analysis/` + `docs/financial-analysis/` 重组到 `docs/stock-analytics/`；统一 frontmatter schema；跨文档引用机制脚本化
> 不在范围：`docs/plans/`、`docs/superpowers/`、`docs/TECHNICAL_DOCUMENTATION.md` 保持不动

## 0. 痛点与目标

**现状痛点**（经 brainstorming 锁定 3 条）：
1. **目录结构混杂 + 找文档难** — `docs/analysis/` 根目录 50+ 文件平铺，4 类内容（buffett 个股 / 跨股专题 / 主题事件 / 板块分析）混杂；`docs/financial-analysis/` 与 `analysis/` 边界模糊。
2. **表头 / frontmatter 不统一** — buffett 个股有规整 YAML（portfolio skill v2 依赖），但季报点评 / 专题 / comps 几乎只有 markdown `>` 引用块，格式各异，下游消费不稳定。
3. **跨文档引用易断链** — 顶部 `> 关联文档 / 配套专题` 全靠手工维护，目录调整 / 文件改名容易静默断链；无反向链接校验。

**目标**：
- 物理目录按"按主题/板块"重组，归宿明确
- frontmatter 全量补齐 + 脚本校验
- `related_docs` 作为唯一来源，markdown 块由脚本生成，反向对称强校验

---

## 1. 目录结构

```
docs/
  TECHNICAL_DOCUMENTATION.md           不动（独立技术总文档）
  stock-analytics/                     新顶层
    README.md                          目录约定 + frontmatter schema + 脚本用法（权威）
    sectors/
      <sector>/<subsector>/
        YYYY-MM-DD-<股票>-buffett分析.md   个股主业务归属
    cross-sector/
      YYYY-MM-DD-<主题>.md                 多股专题 + 多股 buffett 对比
    themes/
      YYYY-MM-DD-<主题事件>.md             主题事件（世界杯 / CCL 涨价 / etc）
    quarterly/
      <NNqN>/                              时间归档，跨板块横看一季度
        YYYY-MM-DD-<股票>-季报点评.md
        YYYY-MM-DD-<股票>-同期专题.md
    comps/
      YYYY-MM-DD-<横向主题>-comps.md       估值/财务横向对比
      quarterly/<NNqN>/                    季度 comps
  plans/                               保留，不动
  superpowers/                         保留，不动
    plans/                             writing-plans skill 输出
    specs/                             brainstorming skill 输出
```

**一级 sector 枚举**（linter 强校验，11 项）：
`semiconductor` / `electronics` / `consumer` / `materials` / `energy` / `healthcare` / `media` / `financial` / `industrial` / `ai-application` / `other`

**二级 subsector 自由起名**（linter 不强约束，首次出现即合法），避免初期过度设计，让实际归类驱动结构演进。

**美股标的**（AMD / Intel / Marvell / Oracle 等）走主业务对应 sector，不单设 `us/` 目录。

**跨板块标的归属规则**：
- buffett 个股 → 主业务一级 sector 的 subsector（如工业富联归 `electronics/ems/`，frontmatter `themes` 数组可同时含 `ai_server`）
- 跨股专题（如 AMD-Intel 对比 / 工业富联-甲骨文走势相关性）→ `cross-sector/`
- 主题事件（不绑定单一板块，如世界杯炒作时间锚）→ `themes/`
- 季报点评一律按时间归 `quarterly/<NNqN>/`，frontmatter 含 `sector` / `subsector` 供聚合
- 横向 comps（多股财务/估值对比）→ `comps/`；季度 comps → `comps/quarterly/<NNqN>/`

---

## 2. Frontmatter Schema

5 类 `doc_type`，公共字段 + 类型专属字段：

### A. 个股 buffett — `sectors/<sector>/<subsector>/`

```yaml
---
doc_type: buffett
stock_code: '603986'            # 字符串强制引号，禁 int 化丢前导 0
stock_name: 兆易创新
sector: semiconductor           # 一级，受 lint 枚举校验
subsector: storage              # 二级，自由
themes: [NOR Flash, 存储芯片, MCU]
rating: core|config|watch|exclude
conviction_date: 2026-04-21
thesis: 1-2 句核心论点
exclude_reason: ...             # rating=exclude 必填
watch_reason: ...               # rating=watch 必填
data_source: 可选                # PDF/网址等基准数据出处
related_docs:
  - path: ../../quarterly/26q1/2026-04-29-兆易-26Q1季报点评.md
    note: 26Q1 实证点评
---
```

### B. 季报点评 — `quarterly/<NNqN>/`

```yaml
---
doc_type: quarterly
stock_code: '603986'
stock_name: 兆易创新
sector: semiconductor
subsector: storage              # 同 buffett，便于按板块聚合
period: 26Q1                    # 与目录名一致
date: 2026-04-29
related_docs: [...]
---
```

### C. 跨股专题 — `cross-sector/`

```yaml
---
doc_type: cross-sector
stock_codes: ['AMD', 'INTC']    # 主体多股
stock_names: [AMD, Intel]
themes: [CPU竞争, x86服务器]
date: 2026-05-08
related_docs: [...]
---
```

### D. 主题事件 — `themes/`

```yaml
---
doc_type: theme
theme_name: 世界杯2026炒作时间锚
themes: [体育用品, 事件驱动]
related_codes: ['002780', '002046', '002761']
date: 2026-05-08
related_docs: [...]
---
```

### E. 横向 comps — `comps/` 或 `comps/quarterly/<NNqN>/`

```yaml
---
doc_type: comps
stock_codes: ['603986', '300223', '688766']
stock_names: [兆易创新, 北京君正, 普冉股份]
themes: [SLC NAND, 利基存储, 涨价周期]
period: '2026-05'               # 月度或季度
date: 2026-05-15
related_docs: [...]
---
```

### 公共可选字段

- `tags: []` — 自由打标（与 themes 区分：themes = 行业/主题；tags = 状态/事件/工具，如 `不买` / `减持事件` / `产业链图谱`）
- `archived: true` — 标记历史归档（不再维护，linter 跳过断链告警）

### Lint 校验规则

`scripts/lint_docs_frontmatter.py`：
1. `doc_type` ∈ 枚举集
2. `sector` ∈ 一级枚举集（A / B 类必填，C / D / E 可选）
3. `stock_code` / `stock_codes` 全部字符串引号（防 YAML int 化）
4. `rating=exclude` → `exclude_reason` 必填；`rating=watch` → `watch_reason` 必填
5. `period` 与所在 `quarterly/<NNqN>/` 目录名一致
6. `conviction_date` / `date` 为 `YYYY-MM-DD` 合法日期

---

## 3. 跨文档引用机制

**核心原则**：`frontmatter.related_docs` 是唯一来源，markdown 顶部的 `> 关联文档` 块由脚本生成。

### related_docs 字段格式

```yaml
related_docs:
  - path: ../../quarterly/26q1/2026-04-29-兆易-26Q1季报点评.md  # 相对当前文件
    note: 26Q1 实证点评（朱一明减持已硬触发卖出线）
    symmetric: true       # 默认 true，要求对端反向引用；false 表示单向（如归档引活档）
```

### scripts/lint_docs_refs.py

- 扫所有 `frontmatter.related_docs[].path`
- 校验目标文件存在
- 校验反向对称：A 引 B 且 `symmetric: true` → B.related_docs 也必须含 A
- 校验路径相对性（不允许 `/` 开头绝对路径）
- 子命令：
  - `--rewrite-blocks` 根据 frontmatter.related_docs 重生每个文档 h1 后的 `> 关联文档` 块
  - `--check-orphans` 列出 0 反向引用的文档
- 用法：`python scripts/lint_docs_refs.py [--rewrite-blocks]`
- 退出码 0 = 全通过，非 0 = 有违例 + 列清单

### markdown 块生成格式

脚本注入位置：h1 之后、首段正文之前。固定 HTML 注释 marker：

```markdown
# 兆易创新（603986）— 巴菲特视角深度分析

<!-- BEGIN related_docs (auto-generated from frontmatter, do not edit) -->
> **关联文档**
> - [26Q1 实证点评](../../quarterly/26q1/2026-04-29-兆易-26Q1季报点评.md) — 朱一明减持已硬触发卖出线
> - [SLC NAND 涨价 comps](../../comps/2026-05-15-SLC-NAND-comps.md) — 利基存储弹性测算
<!-- END related_docs -->

## 0. 执行摘要
...
```

脚本只重写两个 marker 之间内容，正文不受影响。

### scripts/_docs_schema.py — 共享定义

单文件定义：
- `DOC_TYPES`：5 个枚举
- `SECTORS`：11 个一级枚举
- `RATINGS`：4 个 buffett 评级
- `REQUIRED_FIELDS_BY_TYPE`：dict 映射 doc_type → 必填字段集
- `parse_frontmatter(path)`：解析 YAML 工具函数

两个 lint 脚本 + `docs-and-portfolio.md` rule 均引用此模块，避免 schema 散落。

---

## 4. 迁移计划

每阶段独立可暂停、可验证，配合 lint 脚本作为闸门。

### Stage 0 — 准备（无文件移动）

- 写 `scripts/_docs_schema.py`（共享枚举 + parse 工具）
- 写 `scripts/lint_docs_frontmatter.py` + `scripts/lint_docs_refs.py`
- 写 `docs/stock-analytics/README.md`（目录约定 + frontmatter schema + 脚本用法）
- 预扫描硬编码路径影响面（见 §5）

**验收**：脚本对**现状**（`docs/analysis/` + `docs/financial-analysis/`）能跑通，列出大量违例（预期 ~50+ 缺字段警告），证明 schema 落地正确。

### Stage 1 — 物理迁移（`git mv` 保 history）

按文件名 / 现有 frontmatter 分流：
- buffett 个股 → `stock-analytics/sectors/<sector>/<subsector>/`
- 跨股专题 → `stock-analytics/cross-sector/`
- 主题事件 → `stock-analytics/themes/`
- `docs/analysis/26q1/*` → `stock-analytics/quarterly/26q1/`
- `docs/financial-analysis/*` → `stock-analytics/comps/`（含 `26q1/` 子目录）

**关键风险点**：跨文件 markdown 链接（`../analysis/...` / `../financial-analysis/...`）会全部失效。处理方式：
- 迁移脚本一次性 `git mv` + 同步 `Grep` 出所有引用 sed 改写
- 跑 `lint_docs_refs.py` 验证 0 断链

**验收**：`rtk git status` 显示文件 rename + 改写一致；`rtk grep -r "docs/analysis" --include="*.md"` 0 命中（除 archive 例外）。

### Stage 2 — Frontmatter 补齐（最大工作量）

- buffett 个股（~50 个）：YAML 已基本规整，只补缺漏字段（sector / subsector / related_docs）
- 季报点评（~30 个）：从 0 补 YAML
- 专题 / 主题 / comps（~15 个）：从 0 补 YAML

**执行策略**：一次性脚本 `scripts/_xxx_batch_frontmatter.py` 用 GLM Flash / Gemini 读全文 + schema → 输出 YAML 草稿；人工逐文件 review + 分批 commit（~10 个/批）。

**验收**：`lint_docs_frontmatter.py` 退出码 0。

### Stage 3 — related_docs 抽取 + 双向对称化

- 扫每个文档现有顶部 markdown `> 关联文档 / 配套专题 / 关联档案` 块 → 抽 link → `frontmatter.related_docs`
- `lint_docs_refs.py --check-orphans` 列孤儿
- 反向不对称的对子人工判断是否补反向（"buffett 引季报"反向天然合理，"主题专题引被涉及个股"反向可选）

**验收**：`lint_docs_refs.py` 退出码 0。

### Stage 4 — 生成统一 markdown 块 + 配套更新

- `lint_docs_refs.py --rewrite-blocks` 一次性注入 / 重写 `<!-- BEGIN related_docs -->` 块
- 重写 `.claude/rules/docs-and-portfolio.md`（目录约定 / frontmatter schema / 脚本用法）
- 微调 `CLAUDE.md` rule 触发条件描述（新增 stock-analytics 关键词）
- 更新下游 skill / 模块的 Glob 模式（见 §5）

**验收**：`portfolio-init --dry-run` 跑通 + 文档计数与迁移前一致。

### Stage 5 — 一次性脚本清理

- 删除 `scripts/_xxx_batch_frontmatter.py` 等一次性辅助脚本（按 `dev-conventions.md` "一次性脚本不入库"约定）
- 保留 `scripts/_docs_schema.py` + 两个 lint 脚本（可复用）

**验收**：`rtk git status` 干净；新增可复用文件清单 = `_docs_schema.py` + `lint_docs_frontmatter.py` + `lint_docs_refs.py` + `stock-analytics/README.md`。

### 预估工作量

| Stage | 时长 |
|-------|------|
| 0 准备 | 30 min |
| 1 物理迁移 | 60 min |
| 2 frontmatter 补齐 | 90-150 min |
| 3 related_docs 抽取 | 60 min |
| 4 生成块 + 下游 | 45 min |
| 5 清理 | 15 min |
| **合计** | **~5-7 小时**，可分多 session |

---

## 5. 下游配套与影响面

### 路径硬编码影响面

| 位置 | 内容 | 改写方式 |
|------|------|---------|
| `.claude/rules/docs-and-portfolio.md` | 现有 `docs/analysis/` / `docs/financial-analysis/` 描述、Glob 例子、约定段落 | 整段重写指向新结构 |
| `.claude/rules/data-architecture.md` | 暂无明显涉及，需扫一遍确认 | Grep 后判断 |
| `CLAUDE.md`（项目级） | docs-and-portfolio rule 「何时读」描述 | 微调新增关键词 |
| `.claude/skills/portfolio-init/SKILL.md` + `config.yaml` | Glob `docs/analysis/**/*.md` | 改 `docs/stock-analytics/sectors/**/*.md` 等多 Glob |
| `.claude/skills/portfolio-init/local-config.yaml.example` | 路径示例 | 同上 |
| `.claude/skills/portfolio-rebalance/` | 同 init skill | 同上 |
| `app/services/portfolio_shortlist/doc_cache.py` | 文档源 Glob | 同上 |
| `app/services/portfolio_shortlist/scoring.py` 等 | 读 frontmatter.sector / subsector 等字段 | 检查现有读法，可能需要更新 |
| 已有文档间 `../analysis/...` / `../financial-analysis/...` markdown 链接 | Stage 1 sed 批量改写 | 配合 lint_docs_refs.py 校验 |
| `graphify-out/` | graphify 缓存 | 重跑 graphify 重建即可 |

### 预扫描命令（Stage 0 跑一次留底）

```bash
rtk grep -r "docs/analysis" --include="*.md" --include="*.py" --include="*.yaml" --include="*.json"
rtk grep -r "docs/financial-analysis" --include="*.md" --include="*.py" --include="*.yaml" --include="*.json"
rtk grep -r "../analysis/" docs/
rtk grep -r "../financial-analysis/" docs/
```

### 明确不在范围

- `docs/plans/` 旧 29 个 design/plan — 不动
- `docs/superpowers/specs/` + `docs/superpowers/plans/` — 不动（brainstorming / writing-plans skill 默认输出位置保留）
- `docs/TECHNICAL_DOCUMENTATION.md` — 不动
- `app/seeds/`、`app/services/` 业务代码 — 不动（仅 `portfolio_shortlist` doc_cache 链 Glob 更新）
- 数据库 schema、`Stock` 表 themes 字段 — 不动

### 失败回滚

每 Stage = 单 commit 或一小批 commit，回滚靠 `rtk git revert`。Stage 1 物理迁移如果链路改写不完全，立即 revert 而非补丁修复。两个 lint 脚本作可重入验收闸门，每 Stage 通过才推进。

### 后续演进（不在本次 spec 范围）

- `pre-commit` hook 跑 lint（默认手动 run，本次不接）
- `lint_docs_refs.py --fix` 自动补反向引用
- 生成 `docs/stock-analytics/INDEX.md`（按 sector / theme / quarter 多维聚合）
- 板块二级 subsector 收敛 / 强枚举校验（等 6-12 个月数据积累后）

---

## 6. 决策记录（来自 brainstorming）

| 决策点 | 选定方案 | 备选与拒绝原因 |
|--------|---------|-------------|
| 顶层目录 | 新建 `docs/stock-analytics/` 包装股票分析；`docs/plans/` + `docs/superpowers/` 保留 | 用户明示保留 plans / superpowers，将股票分析挪出 |
| 内部结构 | 拍平 `sectors/cross-sector/themes/quarterly/comps`，去掉 `analysis/financial-analysis` 中间层 | 中间层方案被拒：语义不清 + 路径更深 |
| 板块归属 | 顶层 `cross-sector/` + `themes/` 并列，个股按主业务归 sector | 仅主业务归属 + symlink 方案被拒：路径头不直观 |
| 季报归属 | `quarterly/<NNqN>/` 时间归档，frontmatter 标 sector | 季报下沉板块子目录被拒：跨板块横看一季度麻烦 |
| financial-analysis 处理 | 改名 `comps/` 拍入 `stock-analytics/`，buffett-风格深度对比挪 `cross-sector/` | 完全合并到 `analysis/` 拒：跨文档引用修复量大 |
| frontmatter 严格度 | 全量补齐 + 脚本校验（手动 run，不接 hook） | 仅 buffett 加 / 轻量公共 4 字段拒：表头不统一痛点不解 |
| 跨文档引用 | frontmatter `related_docs` 唯一源 + 脚本生成 markdown 块 + 反向对称校验 | 仅验证 markdown 链接 / 只填 frontmatter 不生成块 均被拒 |

---

## 7. 验收标准（spec 级总闸门）

- [ ] `docs/stock-analytics/` 顶层目录 + 6 个子目录（sectors/cross-sector/themes/quarterly/comps + README）就位
- [ ] `docs/analysis/` 和 `docs/financial-analysis/` 已清空并删除
- [ ] `docs/plans/` 和 `docs/superpowers/` 完全不变
- [ ] 所有 stock-analytics 下文档 frontmatter 通过 `lint_docs_frontmatter.py`
- [ ] 所有 `related_docs` 通过 `lint_docs_refs.py`（路径存在 + 反向对称）
- [ ] 所有文档 h1 后含统一 `<!-- BEGIN related_docs -->` 块
- [ ] `portfolio-init --dry-run` 跑通，标的清单与迁移前一致
- [ ] `.claude/rules/docs-and-portfolio.md` 重写完成并描述新约定
- [ ] 一次性脚本已删除，仓库新增长期文件 = 3 脚本 + 1 README
