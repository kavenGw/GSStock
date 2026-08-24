# buffett 档结构性关联文档独立成 related.md 设计

日期：2026-08-24
关联：`2026-08-23-buffett-doc-folder-architecture-design.md`（六文件架构 v2，本文档在其上做 v2.1 增量）

## 1. 问题

文件夹档 v2 把事件回写分流到 `events.md`，但**结构性引用**（comps / 兄弟 buffett 档 / quarterly / cross-sector）
仍留在 `index.md` 的 frontmatter。实测扬杰科技档（2026-08-24 重做）暴露三个问题：

1. **体积**：4 条结构性引用的 frontmatter 约 1.5KB，h1 后自动生成的「关联文档」块再重复渲染一遍 1.5KB，
   合计 3KB 全部压在结论页顶部，把 §0/§10/§11 挤到很下面；index.md 实际 18.2KB，远超规格的 ≤12KB。
2. **维护扰动**：`symmetric: true` 要求每建一份同板块兄弟档就回头改 `index.md` 的 frontmatter 补反向条目。
   index.md 是评级结论页，却成了全文件夹改动频率最高的文件——并行 session 抢 git index、diff 噪音都源于此。
3. **职责不纯**：结论 / 结构关联 / 事件回写三类内容的**覆盖语义完全不同**（重做覆盖 / 重做重写 / 永不覆盖），
   却有两类挤在同一个文件里。

## 2. 决定

| 决策 | 选择 |
|------|------|
| D1 落点 | 新建 `related.md`（`doc_type: buffett-related`），文件夹六文件 → **七文件** |
| D2 index.md | 删除 `related_docs` 字段与 h1 后的自动生成块；导航行加「关联文档 → related.md」 |
| D3 对称校验 | `lint_docs_refs.py` 的对称/孤儿判定从**文件粒度**升到**文件夹粒度**（node 归并） |
| D4 自指 | 同 node 内部互指（如 related.md 指本文件夹 index.md）判为 violation，防 node 归并放宽过头 |
| D5 外部反向链 | 一律指 `<股票名>/index.md`（阅读入口不变，人点进去是结论页）；事件 theme 维持指 `events.md` |
| D6 存量 | **零迁移**。243 份平铺档 + 士兰微/扬杰两份现存文件夹档全部不动，lint 双模兼容 |
| D7 网页 | `/stock` 页只渲染 index.md，故网页上不再显示「关联文档」块——预期行为，与体积目标一致 |

被否方案：
- **并入 events.md**（全部 related_docs 收一个文件）：events.md 已 11KB 且语义是「重做不覆盖」，
  塞进「重做要重写」的结构性引用后需在同一 frontmatter 内分区，把"职责不纯"换个地方重演。
- **只搬正文渲染块**（frontmatter 留 index.md）：只解决半个体积问题，维护扰动与职责问题原封不动。

## 3. 目标形态

```
sectors/<sector>/<subsector>/<股票名>/
  index.md       doc_type: buffett          §0 + §10 + §11        重做原地覆盖
  related.md     doc_type: buffett-related  结构性引用            重做重写      ← 新增
  events.md      doc_type: buffett-events   事件 theme 回写       永不覆盖
  business.md    doc_type: buffett-section  §1-§5
  thesis.md      doc_type: buffett-section  §6-§8
  valuation.md   doc_type: buffett-section  §9 + 相对旧档变化清单
  sources.md     doc_type: buffett-section  §12
```

`related.md` 形态：

```yaml
---
doc_type: buffett-related
stock_code: '300373'
stock_name: 扬杰科技
related_docs:
- path: ../2026-06-19-华润微-buffett分析.md
  note: ...
  symmetric: true
---
# 扬杰科技（300373）关联文档

<!-- BEGIN related_docs (auto-generated from frontmatter, do not edit) -->
<!-- END related_docs -->
```

必填字段 `doc_type / stock_code / stock_name`（与 `buffett-events` 同集）；禁带 `rating / valuation / themes / section`
（复用 `SECTION_FORBIDDEN`）。相对路径按 `related.md` 自身所在目录算——与 index.md 同目录，故存量写法可直接平移。

**`_docs_schema.py` 仍允许 index.md 携带 `related_docs`**（不加禁令）：这是 D6 零迁移的兜底，士兰微/扬杰两份
现存文件夹档不动也合规。规格层面（`buffett-doc-spec`）写「新档不写」，由写手与审查员保证。

## 4. lint 改造：文件夹粒度对称（本次唯一有难度的改动）

现状 `_check()` 判对称是**精确路径**匹配：A 指 B 时，要求 B 的 `related_docs` 里存在解析后等于 A 的条目。
一旦 index.md 不再有 related_docs，所有存量「comps → `<股>/index.md`」的条目立刻报 asymmetric，与 D6 冲突。

改造：引入 node 归并。

```python
def _folders(docs: dict[Path, dict]) -> set[Path]:
    return {p.parent for p, fm in docs.items()
            if p.name == 'index.md' and fm.get('doc_type') == 'buffett'}

def _node(p: Path, folders: set[Path]) -> Path:
    return p.parent if p.parent in folders else p
```

- **对称判定**：`_node(source)` 是否出现在 `{_node(_resolve(target, r['path'])) for r in target 的 related_docs}`。
- **孤儿判定**：`referenced` 集合与候选集合都按 `_node` 归并；`_NEVER_ORPHAN` 增加 `buffett-related`（双保险）。
- **自指守卫（D4）**：`_node(path) == _node(target)` 时报 violation
  （`related_docs 指向同一股票文件夹内部，应使用正文相对链接`）。文件夹内部本来就用 `[§9](valuation.md)`
  行内链接而非 related_docs，故不影响任何现存档。
- **不改**：`--rewrite-blocks`（按文件渲染）、`_resolve`（按文件所在目录解析）、路径存在性校验。

三个效果：新形态（外部指 index.md、反向条目写在 related.md）合法；现存「themes → events.md」双落点顺带
合法化（今天靠 events.md 自己回指才过）；存量「comps → index.md」在 index.md 已无 related_docs 时仍绿。

## 5. 连带改动清单

| 文件 | 改动 |
|------|------|
| `scripts/_docs_schema.py` | `DOC_TYPES` + `REQUIRED_FIELDS_BY_TYPE` 加 `buffett-related`；对其复用 `SECTION_FORBIDDEN` 校验 |
| `scripts/lint_docs_refs.py` | §4 的 node 归并 + 自指守卫 |
| `scripts/deep_redo_gate.py:35` | `FOLDER_FILES` 加 `'related.md'`（Phase B 闸门查七文件齐全 + 占位） |
| `.claude/skills/stock-research/scripts/pool_index.py:60` | 跳过集合加 `'buffett-related'`，否则混进一条无 sector 的池索引记录 |
| `.claude/skills/buffett-doc-spec/SKILL.md` | 文件表六→七行；index.md 行去掉 related_docs；frontmatter 示例中 `related_docs` 段挪到 related.md；写手职责边界 |
| `.claude/skills/stock-research/references/mode-deep.md` | 默认参数「六文件」→「七文件」 |
| `.claude/skills/stock-research/references/mode-earnings.md` | 差量更新的文件清单 |
| `.claude/skills/stock-research/references/dispatch.md` | Phase B 写手 prompt 内联的产出文件清单 |
| `.claude/skills/stock-research/references/finalize.md` | Phase C 补反向链落到 related.md；改指目标仍是 index.md（D5） |
| `.claude/rules/docs-conventions.md` | §跨文档引用：结构性 vs 事件的落点说明 + 文件夹粒度对称说明 |
| memory `buffett-doc-folder-architecture.md` | 六文件 → 七文件 |

`app/services/buffett_analysis.py` **无需改动**：`build_index` 只认 `index.md` + `doc_type == 'buffett'`，
`related.md` 既不匹配平铺档文件名正则也不是 index.md，自动被忽略（D7）。

## 6. 测试

TDD，先写测试再改实现。

`tests/test_lint_docs_refs.py` 新增：
1. comps 指 `<股>/index.md`、`<股>/related.md` 回指 comps（index.md 无 related_docs）→ 通过。
2. 文件夹**外**的普通档之间仍按文件粒度严格判对称 → 不误放行。
3. `related_docs.path` 指向不存在文件 → 仍报错。
4. 同文件夹内自指（related.md → index.md）→ 报 violation（D4）。
5. 孤儿检查：文件夹整体有入链时，`related.md` / `index.md` 均不被列为孤儿。

`tests/test_docs_schema.py` 新增：`buffett-related` 缺 `stock_code` 报错；带 `rating` 报错。

收尾验证（真实全池）：`python scripts/lint_docs_frontmatter.py` 与 `python scripts/lint_docs_refs.py`
双 exit 0，且违规集合与改动前一致（不引入新违规、不吞掉旧违规）。

## 7. 不做

- 不写迁移脚本，不批量改存量档（D6）。存量档在下次走 stock-research 模式 1 重做时自然产出 `related.md`。
- 不改 `--rewrite-blocks` 的渲染逻辑，不改块的 markdown 形态。
- 不改网页渲染层（D7）。
- 不动 events.md 的既有语义与落点。
