# 文档写作与 lint 规范

> **何时读**：写 docs/stock-analytics/ 新文档、改 frontmatter、跑 lint_docs_*、维护 related_docs、判 sector 归属
> **不必读**：portfolio/valuations skill 行为（见 portfolio-valuations.md）/ 纯代码 / 通知 / 数据获取

## 文档目录约定（docs/stock-analytics/）

- `sectors/<sector>/<subsector>/YYYY-MM-DD-<股票名>-buffett分析.md` — 个股 buffett 风格深度分析（按主业务归属）
- `cross-sector/YYYY-MM-DD-<主题>.md` — 多股专题 / 多股 buffett 对比（如 AMD-Intel、立讯-歌尔、工业富联-甲骨文）
- `themes/YYYY-MM-DD-<主题>.md` — 事件驱动主题（世界杯炒作 / CCL 涨价 / 磷化铟板块）
- `quarterly/<NNqN>/YYYY-MM-DD-<股票>-<类型>.md` — 季报点评 + 同期专题（时间归档，跨板块横看）
- `comps/YYYY-MM-DD-<横向主题>-comps.md` — 估值/财务横向对比
- `comps/quarterly/<NNqN>/...` — 季度 comps

**一级 sector 枚举**（11 项，linter 强校验）：
`semiconductor` / `electronics` / `consumer` / `materials` / `energy` / `healthcare` / `media` / `financial` / `industrial` / `ai-application` / `other`

二级 subsector 自由起名。详细 schema + lint 用法见 `docs/stock-analytics/README.md` 与 `scripts/_docs_schema.py`。

**跨板块标的 sector 归属准则**：标的横跨两个一级板块时（如罗博特科 51% 半导体 + 48% 光伏、工业富联 PCB+服务器），按**收入第一权重**归类，次要业务在 thesis / themes 中说明。仅在两业务旗鼓相当且核心叙事来自次要业务时，例外放 `cross-sector/`。判断主业权重用 `ak.stock_zygc_em(symbol='SZ<code>')` 取最新报告期的"按产品分类"切片。

**锂电/储能成品制造归 `energy`/`battery`，不归 `materials`**：电芯/电池系统/动力/储能/消费电池制造（如亿纬锂能）属 energy；`materials` 仅放上游锂盐/正负极/隔膜/电解液（如赣锋锂业=materials/lithium）。中游电池厂 vs 上游锂资源成本传导方向相反（电池厂是锂买方，锂价涨=成本压力）。采证 subagent 易误判电池厂为 materials/industrial，控制者需纠。

## Frontmatter 约定（5 类 doc_type）

所有文档必须有 YAML frontmatter，按 `scripts/_docs_schema.py:REQUIRED_FIELDS_BY_TYPE` 字段集补齐。

**强制规则**：
- `stock_code` / `stock_codes` 必须字符串引号（防 YAML int 化丢前导 0）—— `'000021'` 而非 `000021`
- `rating=watch` → 必填 `watch_reason`；`rating=exclude` → 必填 `exclude_reason`
- `conviction_date` / `date` 必须 `YYYY-MM-DD` 格式
- `period` 必须与所在 `quarterly/<NNqN>/` 目录名一致

**`conviction_date` YAML 解析为 `datetime.date` 不是 str** — `yaml.safe_load` 把 `conviction_date: 2026-05-09` 转 `datetime.date` 对象。与字符串做 `>` 比较会抛 `TypeError`。聚合多 doc 取最新时必须 `str(fm.get('conviction_date') or '')` 先转字符串。

## 跨文档引用：frontmatter.related_docs 唯一源

```yaml
related_docs:
  - path: ../../quarterly/26q1/2026-04-29-兆易-26Q1季报点评.md
    note: 26Q1 实证点评
    symmetric: true  # 默认 true，要求反向对称
```

h1 之后的 `<!-- BEGIN related_docs -->` / `<!-- END related_docs -->` 块由脚本生成，**不要手编**。

## Lint 脚本（手动 run）

```bash
python scripts/lint_docs_frontmatter.py          # 校验所有 frontmatter
python scripts/lint_docs_refs.py                 # 校验 related_docs 路径 + 反向对称
python scripts/lint_docs_refs.py --rewrite-blocks  # 重生所有文档顶部 markdown 块
python scripts/lint_docs_refs.py --check-orphans   # 列孤儿文档
```

退出码 0 = 全过；非 0 = 列违例清单。新写或迁移文档后跑 lint 自检。

**Lint 坑（Windows + 并发）**：
> 编码坑见 dev-environment.md
- `--check-orphans` 会因 print 含中文（如「铜」）的孤儿路径撞 cp950 抛 `UnicodeEncodeError` 返回 exit 1，**而 orphan 判定逻辑其实已跑完**——加 `PYTHONIOENCODING=utf-8` 才得真实 exit 0，别误判为 lint 失败。
- `--rewrite-blocks` 会重生**所有** block 与 frontmatter 失步的文档（含并行 session 未提交的在写档），易产生跨任务连带 diff。跑完**只精确 `git add` 本任务的档**，**勿 `git add -A`**，避免裹挟他人半成品。
- 但"精确 add"仍有盲区：refs `symmetric: true` **强制**你 touch 兄弟档补反向条目才过 lint，若该兄弟档正被并行 session 改（带未提交分析改动），`git add <兄弟档>` 会连其未提交改动一并裹挟进你的 commit。add 前先 `git diff <兄弟档>`：若有 `related_docs` 块以外的改动即对方在写，归其自行提交（其后续 commit 会干净收尾、非破坏性，但勿误判为本任务产物）。**对偶情形**：并行 session 同跑 stock-deep-redo 于同板块兄弟股、共享同一 comps 时，指向你新档的反向条目可能已被对方抢先写入并 committed——补反向链前先 `grep <新档名> <兄弟档>`，已在则跳过（勿重复追加），以 `refs lint exit 0` 为真闸而非"必须由我添加"。
