# docs/stock-analytics/

股票投资分析文档集中目录。所有个股 buffett 深度分析、季报点评、跨股专题、主题事件、横向 comps 全部归这里。

## 目录约定

- `sectors/<sector>/<subsector>/YYYY-MM-DD-<股票名>-buffett分析.md` — 个股深度分析（按主业务归属）
- `cross-sector/YYYY-MM-DD-<主题>.md` — 多股专题 / 多股 buffett 对比
- `themes/YYYY-MM-DD-<主题事件>.md` — 事件驱动主题（世界杯 / CCL 涨价 / etc）
- `quarterly/<NNqN>/YYYY-MM-DD-<股票>-季报点评.md` — 季报点评（时间归档，跨板块横看）
- `quarterly/<NNqN>/YYYY-MM-DD-<股票>-<主题>专题.md` — 同期专题
- `comps/YYYY-MM-DD-<横向主题>-comps.md` — 估值/财务横向对比
- `comps/quarterly/<NNqN>/...` — 季度 comps

## 一级 sector 枚举（11 项，强校验）

`semiconductor` / `electronics` / `consumer` / `materials` / `energy` / `healthcare` / `media` / `financial` / `industrial` / `ai-application` / `other`

二级 subsector 自由起名，首次出现即合法。

## Frontmatter Schema

5 类 `doc_type`：`buffett` / `quarterly` / `cross-sector` / `theme` / `comps`。各类必填字段定义见 `scripts/_docs_schema.py:REQUIRED_FIELDS_BY_TYPE`。

通用强制规则：
- `stock_code` / `stock_codes` 必须字符串（防 YAML int 化丢前导 0：用 `'000021'` 而非 `000021`）
- `rating=watch` → 必填 `watch_reason`；`rating=exclude` → 必填 `exclude_reason`
- `conviction_date` / `date` 必须 `YYYY-MM-DD` 格式
- `period` 必须与所在 `quarterly/<NNqN>/` 目录名一致

公共可选字段：
- `tags: []` — 状态/事件/工具标签（与 themes 区分：themes = 行业/主题）
- `archived: true` — 历史归档（linter 跳过断链告警）

详见 `docs/superpowers/specs/2026-05-18-docs-stock-analytics-reorg-design.md` §2。

## 跨文档引用

`frontmatter.related_docs` 是唯一来源。格式：

```yaml
related_docs:
  - path: ../../quarterly/26q1/2026-04-29-兆易-26Q1季报点评.md
    note: 26Q1 实证点评
    symmetric: true  # 默认 true，要求反向对称引用
```

h1 之后的 `<!-- BEGIN related_docs -->` / `<!-- END related_docs -->` 块由脚本生成，不要手编。

## Lint 脚本（手动 run，不接 pre-commit）

```bash
# 校验所有 frontmatter
python scripts/lint_docs_frontmatter.py

# 校验 related_docs 路径 + 反向对称
python scripts/lint_docs_refs.py

# 重生所有文档顶部 markdown 块（按 frontmatter）
python scripts/lint_docs_refs.py --rewrite-blocks

# 列孤儿文档（0 反向引用）
python scripts/lint_docs_refs.py --check-orphans
```

退出码 0 = 全过；非 0 = 列违例清单。
