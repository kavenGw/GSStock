---
paths:
  - "docs/stock-analytics/**"
  - "scripts/**"
---
# 文档写作与 lint 规范

> **何时读**：写 docs/stock-analytics/ 文档、改 frontmatter、跑 lint_docs_*、维护 related_docs、判 sector 归属、建档前 gating

## 目录约定（docs/stock-analytics/）

- `sectors/<sector>/<subsector>/<股票名>/{index,business,thesis,valuation,sources,events,related}.md` — 个股 buffett 文件夹档（新建/重做一律用此；只有 `index.md` 是 `doc_type: buffett`，规格见 `buffett-doc-spec`）
- `sectors/<sector>/<subsector>/YYYY-MM-DD-<股票名>-buffett分析.md` — 平铺存量档，不再新建
- `cross-sector/YYYY-MM-DD-<主题>.md` — 多股专题/对比
- `themes/YYYY-MM-DD-<主题>.md` — 事件驱动主题
- `quarterly/<NNqN>/YYYY-MM-DD-<股票>-<类型>.md` — 季报点评
- `comps/YYYY-MM-DD-<主题>-comps.md`、`comps/quarterly/<NNqN>/...` — 横向对比

**一级 sector 枚举**（linter 强校验）：`semiconductor` / `electronics` / `consumer` / `materials` / `energy` / `healthcare` / `media` / `financial` / `industrial` / `ai-application` / `other`。subsector 自由起名。schema 见 `scripts/_docs_schema.py`。

**sector 归属**：跨板块标的按**收入第一权重**归类（用 `ak.stock_zygc_em` 最新报告期「按产品分类」判），次要业务在 thesis/themes 说明；仅两业务旗鼓相当且核心叙事来自次要业务时放 `cross-sector/`。锂电/储能成品制造归 `energy`，`materials` 仅放上游锂盐/正负极/隔膜/电解液（两者锂价传导方向相反，采证 subagent 易误判）。

## 建档 gating

**低质地非科技不建档**：质地差（ROE 长期低/曾巨亏/无护城河多元化）且非科技类的标的，采证粗筛命中即口头说明「不建档」停手，不写档、不写 valuations。判别核心是**题材敞口≈0**（主业与所蹭题材无关）；若题材就是主业（锂矿商锂价 watch、周期股顶部 watch），属合理归类正常建档。科技类即便 exclude 仍可建档；非科技高质地不受限。删档时同步删 valuations 条目、清兄弟档反向链、跑 `lint_docs_refs.py`。

**避坑列表硬门**：采证第一步 load `docs/stock-analytics/avoidance-list.yaml` 按 `stock_code` 查。命中 → 用最新单季 + akshare 重取指标，对照 `avoid_reason` **逐条列出当前实测值**判仍成立/被推翻；仍成立 → 中断建档；被推翻 → 放行，建档完成后移除该条并 commit。新判掉一只标的或删档时补一条（`stock_code` 带引号）。该文件不受 docs linter 约束。

## Frontmatter

按 `scripts/_docs_schema.py:REQUIRED_FIELDS_BY_TYPE` 补齐。强制：
- `stock_code`/`stock_codes` 字符串引号（防丢前导 0）
- `rating=watch` 必填 `watch_reason`；`rating=exclude` 必填 `exclude_reason`
- `conviction_date`/`date` 为 `YYYY-MM-DD`；`period` 与 `quarterly/<NNqN>/` 目录一致
- `yaml.safe_load` 把 `conviction_date` 解析为 `datetime.date`，与 str 比较抛 TypeError，聚合时先 `str(...)`

## related_docs（跨文档引用唯一源）

```yaml
related_docs:
  - path: ../../quarterly/26q1/2026-04-29-兆易-26Q1季报点评.md
    note: 26Q1 实证点评
    symmetric: true   # 默认 true，要求反向对称
    impact: 动摇      # 可选（模式 3 回写）：强化/动摇/推翻/无关
    magnitude: 中     # 可选：高/中/低
```

- h1 后的 `<!-- BEGIN/END related_docs -->` 块由脚本生成，不手编。首建档 `related_docs: []` 时 `--rewrite-blocks` 移除空占位块、`--check-orphans` 列为孤儿，均属预期，frontmatter lint exit 0 即合规。
- **文件夹档落点**：`related.md` 放结构性引用，`events.md` 放事件回写，`index.md` 不写 related_docs。lint 按**文件夹粒度**判对称：外部档指 `index.md`、回链写在 `related.md` 即对称；文件夹内互指报错（内部用正文相对链接）。

## Lint

```bash
python scripts/lint_docs_frontmatter.py            # frontmatter
python scripts/lint_docs_refs.py                   # related_docs 路径 + 反向对称
python scripts/lint_docs_refs.py --rewrite-blocks  # 重生文档顶部块
python scripts/lint_docs_refs.py --check-orphans   # 列孤儿
```

exit 0 为真闸。坑：
- `--check-orphans` 打印含中文路径会撞 cp950 返回 exit 1，加 `PYTHONIOENCODING=utf-8`。
- `--rewrite-blocks` 会重生**所有**失步文档（含并行 session 在写档），跑完只精确 `git add` 本任务档，勿 `-A`。
- `symmetric: true` 强制 touch 兄弟档：add 前 `git diff <兄弟档>`，若有 related_docs 以外改动即对方在写，归其提交。补反向链前先 `grep <新档名> <兄弟档>`，已被对方写入则跳过。
- `--rewrite-blocks` 全局 fail-closed：任何违例（含他人无关的不对称）都会让一个块都不渲染。绕过：import 该模块后对只含本任务文件的 dict 调 `_rewrite_blocks(sub)`，无关违例留对方收尾。
