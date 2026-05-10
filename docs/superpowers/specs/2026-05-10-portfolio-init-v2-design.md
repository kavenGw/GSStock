# Portfolio Init v2 设计 spec

> 日期：2026-05-10
> 范围：`portfolio-init` + `portfolio-rebalance` 两个 skill 的一次性架构升级
> 关联文件：
> - `.claude/skills/portfolio-init/SKILL.md`
> - `.claude/skills/portfolio-init/config.yaml`
> - `.claude/skills/portfolio-init/report-template.html`
> - `.claude/skills/portfolio-rebalance/SKILL.md`
> - `docs/analysis/**/*.md`（增量加 frontmatter）

## 0. 背景与痛点

当前 `/portfolio-init` 已能产出完整的 HTML 配置报告（参考 `D:\Git\GSStockHold\portfolio-init-2026-05-10.html`），但跑过几次后暴露 4 类问题：

1. **数据一致性**：主题列表、股票→主题映射硬编码在 `SKILL.md` §4 表格里，与 `config.yaml` 的 themes 重复；`portfolio-rebalance` 输出的 `000021 000021` 是名称回填的 bug
2. **可重复性**：每只股的「核心/配置/观察/排除」评级、选取理由都是 LLM 现场读 docs 推理，同样输入下次跑结果未必一致
3. **HTML 信息密度**：理由列表与表格分离重复展示；缺持仓成本/盈亏列；无锚点导航；观察池/排除池缺评级日期、保留原因、文档链接
4. **执行可靠性**：stock_code 反查链散落 3 处（stock 表 / docs / supply_chain.py），新增标的要改 SKILL.md 表，流程脆弱

## 1. 总体方案

把所有「业务知识」（评级 + 主题归属 + 选股理由）从 SKILL.md 硬编码迁出，**单一来源**改为 `docs/analysis/*.md` 的 YAML frontmatter。`SKILL.md` 仅描述算法，不再保存业务数据。

```
docs/analysis/**/*.md (frontmatter)
        │
        ▼
  [universe scanner]  ◄── config.yaml (themes / rules / metadata_schema)
        │
        ▼ 按 stock_code 去重，取 conviction_date 最新条作为权威评级
        │
  [theme aggregator]  ──► 按 themes[0] 分组
        │
        ▼
  [code resolver]  ──► frontmatter > stock 表 > supply_chain.py
        │
        ▼
  [capacity allocator] ◄── realtime prices
        │
        ▼
  写 StockWeight / RebalanceConfig / PositionPlan
        │
        ▼
  HTML v2 渲染（持仓盈亏 + 内联理由 + 锚点导航 + 文档链接 + 迁移待办）
```

## 2. Frontmatter Schema

### 2.1 字段定义

```yaml
---
stock_code: 601138              # 必填，stock 表主键
stock_name: 工业富联             # 必填，HTML 显示用
themes: [ai_compute]            # 必填，数组；themes[0] 为计仓主题
rating: core                    # 必填，枚举：core | config | watch | exclude
conviction_date: 2026-05-09     # 必填，YYYY-MM-DD；同股多 doc 时取最新
thesis: AI 服务器代工龙头，2026Q1 营收+45%   # 必填，1-2 句，HTML 表格"理由"列
watch_reason: valuation_too_high   # 仅 rating=watch 必填
exclude_reason: out_of_theme       # 仅 rating=exclude 必填
supersedes: 2026-04-21-工业富联-buffett分析.md   # 可选，记录被覆盖的旧 doc
---
```

### 2.2 枚举定义（集中在 config.yaml）

```yaml
metadata_schema:
  rating: [core, config, watch, exclude]
  watch_reason:
    valuation_too_high: 估值偏高，等回调
    await_quarterly: 等季报兑现
    quality_marginal: 质地一般，主题驱动
    size_too_large: 单股 100 股已超主题上限
    thesis_unproven: 投资逻辑待验证
  exclude_reason:
    out_of_theme: 主题外
    quality_concern: 质地差/盈利弱
    overvalued: 估值已透支
    cross_market: 跨市场（港股/美股）执行复杂
    redundant: 主题内已有更优替代
```

### 2.3 取数语义

- **同股多 doc**（buffett + 季报 + 专题）：按 `conviction_date` desc 取首条作为权威评级；其余 doc 在「文档链接」列以折叠形式列出
- **跨主题股**（themes 数组多元素）：以 `themes[0]` 计入主题市值；其他 themes 仅在表格"附属主题"列展示
- **conviction_date 相同**（罕见冲突）：取文件名字典序后者
- **frontmatter YAML 解析失败**：跳过该 doc，记 warning 进迁移待办，**不阻塞流程**
- **没填 frontmatter**：用 `config.yaml.migration_fallback` 表填默认值 + 报告末尾列入「待迁移」清单
- **`themes[0]` 在 config.yaml 找不到**：报错并停（防 typo）

## 3. SKILL.md 工作流改造

### 3.1 portfolio-init/SKILL.md 步骤变化

| 旧步骤 | 新步骤 | 变化 |
|------|------|------|
| §0 读 config | §0 读 config + 校验 metadata_schema | 加 schema 完整性检查（themes 引用一致） |
| §1 总资产 | §1 总资产 | 不变 |
| §2 持仓快照 | §2 持仓快照（含成本/盈亏） | 查 positions.total_amount 算 avg_cost；查实时价算浮盈亏 |
| §3 候选池（手工 Glob+反查） | §3 universe scan（统一函数） | 新增 `_scan_universe()`：解析 frontmatter，无则 fallback |
| §4 主题分组（硬编码表） | §4 主题分组（按 themes[0]） | 删 SKILL.md 主题表，移到 config.yaml `migration_fallback` 段 |
| §5 评级（LLM 推理标准） | §5 评级（读 frontmatter） | 删评级标准说明，rating 直接来自 frontmatter |
| §6 算目标仓位 | §6 算目标仓位 | 不变 |
| §7 写库 | §7 写库 | 不变 |
| §8 markdown | §8 markdown（增列） | 加成本/盈亏；移除独立"理由"列表（改进 HTML 表格） |
| §9 HTML | §9 HTML v2 | 用新 template，加迁移待办段 |

### 3.2 universe scan 算法（伪代码）

```python
def scan_universe(docs_root: Path, config: dict) -> list[dict]:
    """扫描 docs/analysis/**/*.md，返回 universe 列表。"""
    raw_entries = []
    migration_pending = []

    for md in docs_root.glob('**/*.md'):
        fm = parse_frontmatter(md)  # YAML 头解析；失败返回 None

        if fm and 'stock_code' in fm:
            entry = {
                'stock_code': fm['stock_code'],
                'stock_name': fm['stock_name'],
                'themes': fm['themes'],
                'rating': fm['rating'],
                'conviction_date': fm['conviction_date'],
                'thesis': fm.get('thesis', ''),
                'watch_reason': fm.get('watch_reason'),
                'exclude_reason': fm.get('exclude_reason'),
                'doc_path': md,
            }
            raw_entries.append(entry)
        else:
            # fallback：从文件名取股票名 + supply_chain.py 反查 code
            #         + config.yaml.migration_fallback 查主题/评级
            fb = fallback_from_filename(md, config['migration_fallback'])
            if fb:
                fb['doc_path'] = md
                fb['_fallback'] = True
                raw_entries.append(fb)
                migration_pending.append(md)
            else:
                # 完全无法识别（主题外的边缘标的）—— 跳过
                pass

    # 按 stock_code 去重，取 conviction_date desc 首条
    by_code = {}
    for entry in sorted(raw_entries, key=lambda e: (e['conviction_date'], str(e['doc_path'])), reverse=True):
        code = entry['stock_code']
        if code not in by_code:
            entry['related_docs'] = []
            by_code[code] = entry
        else:
            by_code[code]['related_docs'].append(entry['doc_path'])

    # 校验：themes[0] 必须在 config.themes 内
    valid_themes = set(config['themes'].keys())
    for entry in by_code.values():
        if entry['themes'][0] not in valid_themes:
            raise ValueError(f"未知主题 {entry['themes'][0]} in {entry['doc_path']}")

    return list(by_code.values()), migration_pending
```

### 3.3 stock_code 反查统一函数

```python
def resolve_stock_code(name: str, frontmatter_entry: dict | None = None) -> str | None:
    """
    反查顺序：
    1. frontmatter.stock_code（首选）
    2. data/stock.db 的 stock 表 WHERE stock_name = name
    3. app/config/supply_chain.py 的 SUPPLY_CHAIN_GRAPHS 字典 grep
    找不到返回 None，由调用方决定标"代码缺失"还是 raise。
    """
```

### 3.4 portfolio-rebalance/SKILL.md 同步改造

- universe scan 用同一份算法（**inline 复制**到 rebalance SKILL.md，保持每个 skill markdown 独立可读）
- 修 `000021 000021` bug：生成表格行时统一用 `stock_meta_lookup(code)` 函数，缺名时 raise warning 而非静默用 code 占位
- HTML 升级到 v2 同款 template
- SELL 表加「平均成本」「预期盈亏」列
- 主题偏离表行加锚点跳到对应主题 section
- 操作清单的「理由」列表删除，理由直接进 BUY/SELL 表的「理由」列

## 4. config.yaml 改造

### 4.1 新增段

```yaml
metadata_schema:
  rating: [core, config, watch, exclude]
  watch_reason: { ... }
  exclude_reason: { ... }

# 兼容期使用，frontmatter 全部就位后可删除
migration_fallback:
  ai_compute:
    keywords: [工业富联, 光迅, 光库, 源杰, 阳光电源]
    default_rating: config
  cpu_pcb:
    keywords: [通富微电, 长电科技, 华天科技, 盛合晶微, 胜宏科技, 沪电股份, 生益科技, 南亚新材, 金安国纪, 宏和科技, 彤程新材]
    default_rating: config
  memory:
    keywords: [北京君正, 江波龙, 兆易创新, 聚辰股份, 普冉股份, 深科技, 太极实业, 雅克科技, 南大光电, 复旦微电, 希荻微, 国芯科技]
    default_rating: config
  world_cup:
    keywords: [安踏, 舒华, 金陵体育, 中体产业, 粤传媒, 共创草坪, 青岛啤酒, 燕京啤酒, 重庆啤酒, 鸿博股份]
    default_rating: config
  gold_defense:
    keywords: [紫金矿业, 洛阳钼业, 中金黄金]
    default_rating: config

# 完全无法归类的标的，标 exclude
# fallback 解析优先级：先查 migration_exclude，命中即标 exclude；再查 migration_fallback.themes 反向匹配
migration_exclude:
  - { keyword: 万华化学,  reason: out_of_theme }
  - { keyword: 巨化股份,  reason: out_of_theme }
  - { keyword: 昊华化学,  reason: out_of_theme }
  - { keyword: 药明康德,  reason: out_of_theme }
  - { keyword: 东吴证券,  reason: out_of_theme }
  - { keyword: 赛腾股份,  reason: out_of_theme }
  - { keyword: 西部材料,  reason: out_of_theme }
  - { keyword: 石英股份,  reason: out_of_theme }
  - { keyword: 立讯精密,  reason: out_of_theme }
  - { keyword: 安踏,      reason: cross_market }
  - { keyword: 甲骨文,    reason: cross_market }
```

### 4.2 themes / rules 段保持不变

```yaml
themes:
  ai_compute: { name: AI算力,           weight: 0.30, description: ... }
  cpu_pcb:    { name: CPU+封测+PCB,     weight: 0.30, description: ... }
  memory:     { name: 存储涨价,         weight: 0.15, description: ... }
  world_cup:  { name: 世界杯,           weight: 0.15, description: ... }
  gold_defense: { name: 黄金防御,       weight: 0.10, description: ... }

rules:
  single_stock_max_pct_of_theme: 0.50
  rebalance_threshold_value: 2000
  theme_drift_threshold: 0.05
  share_unit: 100
  buy_round: floor
  sell_round: ceil
```

## 5. HTML v2 模板改造

### 5.1 结构

```
┌─ 顶部主题导航条（sticky） ───────────────────────────────────┐
│ [总览] [AI算力] [CPU+封测+PCB] [存储涨价] [世界杯]         │
│ [黄金防御] [观察池] [排除池] [待迁移]                        │
└───────────────────────────────────────────────────────────┘

┌─ 当前持仓快照 ───────────────────────────────────────────┐
│ 代码 | 名称 | 股数 | 成本价 | 现价 | 浮盈亏 | 浮盈亏% | 市值 │
└───────────────────────────────────────────────────────────┘

┌─ AI算力 ─── #ai_compute ─────────────────────────────────┐
│ 代码 | 名称↗ | 评级 | 主题占比 | 目标股数 | 现价 | 目标市值 | 选股理由
│ ↗：file:// 链接到 conviction_date 对应的 doc
│ thesis 超 80 字截断 + title 全文 tooltip
└───────────────────────────────────────────────────────────┘

[其他主题同样格式]

┌─ 观察池 ─── #watch ──────────────────────────────────────┐
│ 按主题分组，每条：
│ • 002636 金安国纪 (CPU+封测+PCB) | watch:估值偏高 | 评级 04-30 | thesis
└───────────────────────────────────────────────────────────┘

┌─ 排除池 ─── #exclude ────────────────────────────────────┐
│ 按 reason 分组：
│ ▸ 主题外（5）：万华化学、巨化股份、…
│ ▸ 跨市场（2）：安踏、ORCL
└───────────────────────────────────────────────────────────┘

┌─ 元数据迁移待办 ─── #migration ──────────────────────────┐
│ N 个 docs 缺 frontmatter，已用 fallback 填默认值，建议补全：
│ - docs/analysis/2026-04-21-工业富联-buffett分析.md
│   建议：rating=core, themes=[ai_compute], thesis="…"
└───────────────────────────────────────────────────────────┘
```

### 5.2 CSS 新增类

```css
nav.theme-anchor { position: sticky; top: 0; background: #fff;
                   padding: 8px 0; border-bottom: 1px solid #e5e7eb; z-index: 10; }
nav.theme-anchor a { margin-right: 12px; color: #2563eb; text-decoration: none; font-size: 13px; }
.gain-positive { color: #dc2626; font-weight: 600; }
.gain-negative { color: #16a34a; font-weight: 600; }
.doc-link::after { content: ' ↗'; color: #6b7280; font-size: 11px; }
.thesis-cell { max-width: 280px; }
.migration-pending { background: #fef3c7; border-left: 3px solid #f59e0b; }
```

### 5.3 rebalance HTML 同样改造

- 修 `000021 000021` bug
- SELL 表加平均成本 + 预期盈亏列
- 主题偏离表行加锚点跳转
- 删独立理由列表，理由进 BUY/SELL 表

## 6. 文件清单

```
.claude/skills/portfolio-init/
├── SKILL.md                       [改] 工作流缩短，删主题硬编码表
├── config.yaml                    [改] 加 metadata_schema + migration_fallback
├── local-config.yaml.example      [不变]
└── report-template.html           [改] v2: 锚点导航 + 新 CSS 类

.claude/skills/portfolio-rebalance/
└── SKILL.md                       [改] universe scan 同步 + 修 bug + HTML v2

docs/analysis/                     [迁移可逐步做，spec 不强制]
└── *.md                           [可选] 顶部加 frontmatter

docs/superpowers/specs/
└── 2026-05-10-portfolio-init-v2-design.md   [本 spec]
```

## 7. 实施顺序

一次性 PR，按提交分块：

1. 改 `report-template.html` v2 + CSS
2. 改 `config.yaml` 加 `metadata_schema` + `migration_fallback`
3. 改 `portfolio-init/SKILL.md` 工作流（含 `_scan_universe()` 伪代码）
4. 改 `portfolio-rebalance/SKILL.md` 同步 + 修 `000021` bug
5. 试跑 `/portfolio-init`，验证 fallback 正常 + 报告渲染正确（与现有 `D:\Git\GSStockHold\portfolio-init-2026-05-10.html` 对比）
6. 试跑 `/portfolio-rebalance`，验证 000021 名称回填、SELL 表盈亏列正确
7. 抽 3-5 个高频 docs（工业富联/胜宏科技/兆易创新/青岛啤酒/紫金矿业）加 frontmatter，回归对比 fallback vs 真实 frontmatter 走两遍结果一致

## 8. 风险与边界

| 风险 | 处理 |
|------|------|
| 所有 frontmatter 字段缺失 | fallback 路径 + 报告"待迁移"段，不阻塞 |
| 同股 conviction_date 相同 | 取文件名字典序后者 |
| frontmatter YAML 解析失败 | 跳过该 doc，记 warning 进迁移待办 |
| `themes[0]` 在 config.yaml 找不到 | 报错并停（防 typo） |
| docs 头部已有非 frontmatter 的 `>` 引用块 | parser 仅在文件开头第一行 `---` 时启用，与 `>` 引用兼容 |
| stock 表查不到 + supply_chain.py 也查不到 | 在「待迁移」段标"代码缺失"，不入 StockWeight |
| 迁移期 fallback 主题与 frontmatter 冲突 | frontmatter 优先；fallback 仅在缺 frontmatter 时生效 |

## 9. 验收

- 不写 frontmatter 时，输出与 `D:\Git\GSStockHold\portfolio-init-2026-05-10.html` 内容等价（评级/主题归属/股数）
- 给 5 只样本股加 frontmatter，输出 thesis、conviction_date、文档链接全部从 frontmatter 读出
- HTML 顶部 sticky 导航点击跳转到对应主题 section
- 持仓快照表显示成本价/浮盈亏列
- rebalance 报告 000021 名称为「深科技」，SELL 表显示青岛啤酒平均成本与预期盈亏
- 所有 frontmatter 字段缺失时，报告底部「待迁移」段列出全部 docs

## 10. 不做的事（YAGNI）

- 不引入 universe scan 的公共库（`.claude/skills/_lib/universe.py`）：保持每个 skill markdown 独立可读，inline 复制 50 行 Python 是可接受的代价
- 不做 frontmatter 校验 CLI 工具（如 `pre-commit` hook）：人工管理 50-100 个 docs 的 frontmatter，靠 skill 报告的「待迁移」段提示即可
- 不做 web UI 编辑 frontmatter：直接编辑 markdown 文件最快
- 不做迁移脚本批量注入 frontmatter：增量手工迁移，避免错评级污染
- 不做 db 字段 sync（不在 stock 表加 rating/theme 列）：保持 frontmatter 是单一来源
