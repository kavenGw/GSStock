# buffett 档文件夹架构（v2）设计

日期：2026-08-23

## 1. 问题

- stock-deep-redo 产出单一大档：最新一批 58–98KB（建滔 98KB、天岳 77KB）。portfolio-rebalance / news-impact /
  下一轮 deep-redo 只想要结论却得整档读入，token 成本随篇幅线性增长。
- news-impact 每次事件都往个股档 frontmatter `related_docs` 追加一条回写（最多 14 条 ≈ 6.5KB），档随事件无限膨胀。
- 每次重做 = 新建带日期档 + `git rm` 旧档 + 全仓改反向链，Phase C 最痛的动作全来自路径不稳定。

## 2. 决定

| 决策 | 选择 |
|------|------|
| 路径 | 稳定路径 `sectors/<sector>/<subsector>/<股票名>/`，重做原地覆盖，历史靠 git |
| 粒度 | 6 文件：index / business / thesis / valuation / sources / events |
| 事件回写 | 写到 `events.md`（独立日志），theme 档的 symmetric 链指向 events.md |
| 网页渲染 | `/stock` 页只渲染 `index.md` |
| 存量档 | 243 份平铺档**完全不动**；只有新建/重做的标的用新架构；消费者双模识别 |

## 3. 目录与文件

```
sectors/<sector>/<subsector>/<股票名>/
  index.md      doc_type: buffett —— frontmatter 唯一持有者（stock_code/rating/valuation/related_docs 等全部现有字段）
                + §0 结论摘要 + §10 评级决策 + §11 风险/监控/卖出触发器        目标 ≤12KB
  business.md   §1 能力圈&触发 + §2 市场规模 + §3 盈利能力 + §4 全球竞争力 + §5 护城河
  thesis.md     §6 核心新论点 + §7 AI/概念潜力 + §8 周期定位
  valuation.md  §9 场景加权估值 + 相对旧档变化清单
  sources.md    §12 数据来源 & 局限
  events.md     doc_type: buffett-events —— news-impact 回写日志；重做时不覆盖
```

节编号与内容规格沿用 `buffett-doc-spec` 13 节，仅改落点。§0/§10/§11 里引用其他文件用相对链接
`[§9](valuation.md#9-估值)`，不复制正文。

### 3.1 frontmatter

- `index.md`：与现行 buffett 档完全相同的字段集（`REQUIRED_FIELDS_BY_TYPE['buffett']` 不变）。
  `related_docs` 只放结构性引用（comps / quarterly / cross-sector / 兄弟 buffett 档），**不放事件 theme**。
- `business.md / thesis.md / valuation.md / sources.md`：

  ```yaml
  doc_type: buffett-section
  stock_code: '603986'
  stock_name: 兆易创新
  section: business   # business | thesis | valuation | sources
  ```

  不含 rating / themes / related_docs（防消费者误把它当个股档）。
- `events.md`：

  ```yaml
  doc_type: buffett-events
  stock_code: '603986'
  stock_name: 兆易创新
  related_docs:           # news-impact 追加，每条带 impact/magnitude，symmetric: true
  - path: ../../../../themes/2026-08-21-xxx.md
    note: ...
    impact: 动摇
    magnitude: 中
    symmetric: true
  ```

  正文只有 h1 + 自动生成的 related_docs 块（`--rewrite-blocks` 渲染 `【动摇·中】`），不手写表格。
  首建时 `related_docs: []`。

### 3.2 「已消化」判定

事件是否已被重做吸收不加字段：theme 档 `date` ≤ `index.md.conviction_date` 即视为已消化。deep-redo 先做步骤
读 events.md，把 `date > conviction_date` 的条目作为「未消化的动摇/推翻」输入 Phase A。

## 4. schema / lint / 脚本改动

| 文件 | 改动 |
|------|------|
| `scripts/_docs_schema.py` | `DOC_TYPES` + `buffett-section` / `buffett-events`；`REQUIRED_FIELDS_BY_TYPE` 加两条（section 枚举校验）；`buffett-section` 禁止出现 rating/valuation/related_docs |
| `scripts/lint_docs_frontmatter.py` | 无需改（走 schema） |
| `scripts/lint_docs_refs.py` | `_orphans` 跳过 `buffett-section` / `buffett-events`（它们天然无人反链）；其余不变 |
| `scripts/sync_valuations.py` | `rglob('*buffett*.md')` → `rglob('*.md')` + `doc_type == 'buffett'` 过滤；`source_doc` 形如 `sectors/x/y/<股票名>/index.md`，`valuations_helpers` 取 `parts[2]` 仍为 subsector，不改 |
| `scripts/deep_redo_gate.py` | `--doc` 接受目录：目录时对其下 6 个 md 逐个跑占位检查，`valuation:` 块只查 index.md，并检查 6 文件齐全 |
| `scripts/deep_redo_anchor_audit.py` | `doc` 接受目录，逐文件扫描并带文件名前缀输出 |
| `app/services/buffett_analysis.py` | `build_index` 同时识别 `<股票名>/index.md`（名=父目录名，日期取 frontmatter `conviction_date`）；同名平铺档与文件夹并存时文件夹优先；`get_html` 不变（只渲染该文件） |
| `.claude/skills/news-impact/scripts/pool_index.py` | `parse_doc` 跳过 `buffett-section` / `buffett-events` |
| `.claude/skills/portfolio-rebalance/SKILL.md` 内嵌 `scan_universe` | 条件加 `fm.get('doc_type') == 'buffett'` |

## 5. skill 改动

- **buffett-doc-spec**：§1 改为「文件夹 + 6 文件」命名与 frontmatter 规格（保留旧平铺格式一段标「存量档，不再新建」）；
  §2 13 节表加「落点文件」列；写手职责加「index.md ≤12KB、跨文件用相对链接不复制」。
- **stock-deep-redo**：默认参数表「产出形态」改为「写入/覆盖 `<股票名>/` 文件夹；该股若有平铺历史档则 `git rm`
  （一次性迁移），已是文件夹则原地覆盖、events.md 不动」；先做步骤加「读 events.md 未消化条目」；闸门命令
  `--doc` 传目录。`dispatch.md` §2 写手 prompt 同步。
- **stock-doc-finalize**：步骤 2/3 加分支「目标已是文件夹 → 跳过删旧档与反向链改指」；首次迁移时反向链改指到
  `<股票名>/index.md`。
- **news-impact** §5：受影响个股若为文件夹架构 → 回写到 `events.md`（path 多一层 `../`），平铺档沿用原逻辑；
  theme 档 related_docs 指向 `events.md`。
- `.claude/rules/docs-conventions.md` + `docs/stock-analytics/README.md`：目录约定加文件夹形态一行。

## 6. 不做

- 不迁移存量 243 份档；不写迁移脚本。
- 网页不拼接渲染其他 5 个文件。
- 不给 events 条目加「已消化」字段。

## 7. 验证

- 新增单测 `tests/test_docs_folder_arch.py`：临时目录造一个文件夹档 + 一个平铺档，断言 frontmatter lint 过、
  refs orphan 不报 section、sync_valuations 抓到 index.md 且 source_doc 正确、`BuffettAnalysisService.build_index`
  文件夹优先、gate/anchor_audit 接受目录。
- 全仓双 lint 仍 exit 0（存量档零改动）。
- 下一次 stock-deep-redo 实跑作为端到端验收。
