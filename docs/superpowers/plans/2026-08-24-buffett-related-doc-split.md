# buffett 档结构性关联文档独立成 related.md 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 buffett 文件夹档 `index.md` 里的结构性 `related_docs` 整体搬到新文件 `related.md`，并把 `lint_docs_refs.py` 的对称/孤儿判定升到文件夹粒度，使存量档零迁移仍全绿。

**Architecture:** 新增 `doc_type: buffett-related`（第 8 个 doc_type），文件夹档六文件 → 七文件。`lint_docs_refs.py` 引入 node 归并：把 `<股票名>/`（含 `doc_type: buffett` 的 `index.md` 的目录）整体视为一个引用节点，对称性按 node 比对、对端出链按 node 聚合。存量 243 份平铺档与士兰微/扬杰两份文件夹档一行不改。

**Tech Stack:** Python 3.10 / pytest / PyYAML；纯脚本与文档改动，不涉及 Flask 应用层。

**Spec:** `docs/superpowers/specs/2026-08-24-buffett-related-doc-split-design.md`

## Global Constraints

- **所有 git / pytest / python 包管理命令前加 `rtk`**，链式 `&&` 中也要；env 赋值必须在 `rtk` **之前**（`PYTHONIOENCODING=utf-8 rtk python ...`，反之 rtk 会把 env 当程序名报 `Binary not found`）。
- **Windows 编码**：跑任何会打印中文/emoji 的 python 命令一律加 `PYTHONIOENCODING=utf-8`；写含中文的文件必须显式 `encoding='utf-8'`。
- **`git add` 与 `git commit` 必须在同一条命令链内**（并行 session 会在两次工具调用之间清空 index）；中文多行 message 走 `-m` 单行或 `.git/MSG-<任务>.txt` 文件，不用 heredoc。
- **不写 backup 文件**，不留一次性脚本，git 历史即备份。
- **零迁移铁律**：不得修改 `docs/stock-analytics/` 下任何存量档（243 平铺档 + `士兰微/` + `扬杰科技/`）。本计划全程只改 `scripts/`、`tests/`、`.claude/`、`docs/superpowers/`。
- **双 lint 基线（改动前实测）**：`python scripts/lint_docs_frontmatter.py` → exit 0 / `OK: 391 file(s) passed`；`python scripts/lint_docs_refs.py` → exit 0 / `OK: 391 file(s)`。每个任务结束后这两条必须仍是 exit 0 且文件数仍为 391。
- **新 doc_type 字面量**：`buffett-related`（连字符，非下划线）。新文件名固定 `related.md`。
- **禁带字段元组名**：`RELATED_FORBIDDEN`（**不是**复用 `SECTION_FORBIDDEN` —— 后者含 `related_docs`，会禁掉本 doc_type 唯一的实质字段。spec §3/§5 的「复用 SECTION_FORBIDDEN」以本计划为准）。

---

### Task 1: schema 承认 buffett-related

**Files:**
- Modify: `scripts/_docs_schema.py:12-13`（`DOC_TYPES` / 新增 `RELATED_FORBIDDEN`）、`:35-46`（`REQUIRED_FIELDS_BY_TYPE`）、`:88-95`（`validate_frontmatter` 的 doc_type 分支）
- Test: `tests/test_docs_schema.py`

**Interfaces:**
- Consumes: 无（本计划第一个任务）
- Produces: `DOC_TYPES` 含 `'buffett-related'`；`REQUIRED_FIELDS_BY_TYPE['buffett-related'] == {'doc_type', 'stock_code', 'stock_name'}`；模块级 `RELATED_FORBIDDEN: tuple[str, ...] = ('rating', 'valuation', 'themes', 'section')`。Task 2/3 依赖 `buffett-related` 能通过 `validate_frontmatter` 而不报 `doc_type ... not in [...]`。

- [ ] **Step 1: 写失败测试**

在 `tests/test_docs_schema.py` 中，把既有的 `test_enums_are_correct` 改成含新 doc_type（这条现在断言的是精确集合，不改必红）：

```python
def test_enums_are_correct():
    assert DOC_TYPES == {'buffett', 'buffett-section', 'buffett-events', 'buffett-related',
                         'quarterly', 'cross-sector', 'theme', 'comps'}
    assert 'semiconductor' in SECTORS
    assert 'other' in SECTORS
    assert RATINGS == {'core', 'config', 'watch', 'exclude'}
```

并在文件末尾追加两条新测试：

```python
def test_buffett_related_valid():
    fm = {
        'doc_type': 'buffett-related',
        'stock_code': '300373',
        'stock_name': '扬杰科技',
        'related_docs': [{'path': '../x.md', 'note': 'n', 'symmetric': True}],
    }
    assert validate_frontmatter(fm, Path('related.md')) == []


def test_buffett_related_required_and_forbidden():
    fm = {
        'doc_type': 'buffett-related',
        'stock_name': 'X',
        'rating': 'core',
        'themes': ['t'],
        'related_docs': [{'path': '../a.md'}],
    }
    violations = validate_frontmatter(fm, Path('related.md'))
    assert any("missing required field 'stock_code'" in v for v in violations)
    assert any("must not carry 'rating'" in v for v in violations)
    assert any("must not carry 'themes'" in v for v in violations)
    assert not any("must not carry 'related_docs'" in v for v in violations)
```

- [ ] **Step 2: 跑测试确认失败**

```bash
PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_docs_schema.py -v
```

Expected: FAIL —— `test_enums_are_correct` 断言集合不等；两条新测试报 `doc_type 'buffett-related' not in [...]`（`validate_frontmatter` 在 doc_type 非法时提前 return，故 violations 里既没有 missing 也没有 forbidden）。

- [ ] **Step 3: 改 schema**

`scripts/_docs_schema.py`，`DOC_TYPES` 加一项、`SECTION_FORBIDDEN` 下方加新元组：

```python
DOC_TYPES: set[str] = {'buffett', 'buffett-section', 'buffett-events', 'buffett-related',
                       'quarterly', 'cross-sector', 'theme', 'comps'}
SECTIONS: set[str] = {'business', 'thesis', 'valuation', 'sources'}
SECTION_FORBIDDEN: tuple[str, ...] = ('rating', 'valuation', 'related_docs', 'themes')
RELATED_FORBIDDEN: tuple[str, ...] = ('rating', 'valuation', 'themes', 'section')
```

`REQUIRED_FIELDS_BY_TYPE` 里 `'buffett-events'` 那行之后加：

```python
    'buffett-related': {'doc_type', 'stock_code', 'stock_name'},
```

`validate_frontmatter` 中 `if dt == 'buffett-section':` 整块之后，紧接着加：

```python
    if dt == 'buffett-related':
        for field in RELATED_FORBIDDEN:
            if field in fm:
                violations.append(f"{p}: buffett-related must not carry '{field}'")
```

- [ ] **Step 4: 跑测试确认通过**

```bash
PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_docs_schema.py tests/test_lint_docs_frontmatter.py -v
```

Expected: PASS（全部）。

- [ ] **Step 5: 跑全池 frontmatter lint 确认无回归**

```bash
PYTHONIOENCODING=utf-8 rtk python scripts/lint_docs_frontmatter.py
```

Expected: `OK: 391 file(s) passed`，exit 0。

- [ ] **Step 6: 提交**

```bash
rtk git add scripts/_docs_schema.py tests/test_docs_schema.py && rtk git commit -m "feat(docs-schema): 新增 doc_type buffett-related（结构性关联文档独立档）"
```

---

### Task 2: refs lint 对称/孤儿判定升到文件夹粒度

**Files:**
- Modify: `scripts/lint_docs_refs.py:29`（`_NEVER_ORPHAN`）、`:32-33`（`_resolve` 之后新增 3 个辅助函数）、`:45-75`（`_check`）、`:78-85`（`_orphans`）
- Test: `tests/test_lint_docs_refs.py`

**Interfaces:**
- Consumes: Task 1 的 `buffett-related`（新测试 fixture 会写这个 doc_type；refs lint 本身不校验 doc_type 合法性，但同池跑 frontmatter lint 时需要）
- Produces: 模块级 `_folders(docs) -> set[Path]`、`_node(p: Path, folders: set[Path]) -> Path`、`_node_refs(docs, folders) -> dict[Path, set[Path]]`；`_check(docs)` 与 `_orphans(docs)` 签名不变（仍各收一个 `dict[Path, dict]`、分别返回 `list[str]` / `list[Path]`）。Task 3 不依赖这些内部函数。

- [ ] **Step 1: 写失败测试**

在 `tests/test_lint_docs_refs.py` 末尾追加四条（`run_refs` / `_write` 复用文件顶部已有的 helper）：

```python
def test_refs_folder_symmetry_via_related_md(tmp_path):
    d = tmp_path / 'sectors' / 'semiconductor' / 'power' / '扬杰科技'
    c = tmp_path / 'comps' / 'c.md'
    _write(d / 'index.md', """\
    ---
    doc_type: buffett
    stock_code: '300373'
    stock_name: 扬杰科技
    sector: semiconductor
    subsector: power
    themes: [功率半导体]
    rating: watch
    watch_reason: w
    conviction_date: 2026-08-24
    thesis: t
    ---
    # 扬杰科技
    """)
    _write(d / 'related.md', """\
    ---
    doc_type: buffett-related
    stock_code: '300373'
    stock_name: 扬杰科技
    related_docs:
      - path: ../../../../comps/c.md
        note: 七方横评
    ---
    # 扬杰科技 关联文档
    """)
    _write(c, """\
    ---
    doc_type: comps
    stock_codes: ['300373']
    stock_names: [扬杰科技]
    themes: [功率半导体]
    period: 26h1
    date: 2026-07-03
    related_docs:
      - path: ../sectors/semiconductor/power/扬杰科技/index.md
        note: 质地第一档
    ---
    # C
    """)
    code, out = run_refs(tmp_path)
    assert code == 0, out


def test_refs_rejects_same_folder_self_ref(tmp_path):
    d = tmp_path / 'sectors' / 'semiconductor' / 'power' / '扬杰科技'
    _write(d / 'index.md', """\
    ---
    doc_type: buffett
    stock_code: '300373'
    stock_name: 扬杰科技
    sector: semiconductor
    subsector: power
    themes: [功率半导体]
    rating: watch
    watch_reason: w
    conviction_date: 2026-08-24
    thesis: t
    ---
    # 扬杰科技
    """)
    _write(d / 'related.md', """\
    ---
    doc_type: buffett-related
    stock_code: '300373'
    stock_name: 扬杰科技
    related_docs:
      - path: index.md
        note: 自指
    ---
    # 关联
    """)
    code, out = run_refs(tmp_path)
    assert code != 0
    assert '同一股票文件夹' in out


def test_refs_non_folder_dirs_stay_strict(tmp_path):
    a = tmp_path / 'themes' / 'a.md'
    b = tmp_path / 'themes' / 'b.md'
    _write(a, """\
    ---
    doc_type: theme
    theme_name: A
    themes: [t]
    date: 2026-08-01
    related_docs:
      - path: b.md
        note: 同目录兄弟
    ---
    # A
    """)
    _write(b, """\
    ---
    doc_type: theme
    theme_name: B
    themes: [t]
    date: 2026-08-02
    related_docs: []
    ---
    # B
    """)
    code, out = run_refs(tmp_path)
    assert code != 0
    assert 'asymmetric' in out.lower()


def test_orphans_folder_referenced_through_index(tmp_path):
    d = tmp_path / 'sectors' / 'semiconductor' / 'power' / '扬杰科技'
    c = tmp_path / 'comps' / 'c.md'
    _write(d / 'index.md', """\
    ---
    doc_type: buffett
    stock_code: '300373'
    stock_name: 扬杰科技
    sector: semiconductor
    subsector: power
    themes: [功率半导体]
    rating: watch
    watch_reason: w
    conviction_date: 2026-08-24
    thesis: t
    ---
    # 扬杰科技
    """)
    _write(d / 'related.md', """\
    ---
    doc_type: buffett-related
    stock_code: '300373'
    stock_name: 扬杰科技
    related_docs:
      - path: ../../../../comps/c.md
        note: 七方横评
    ---
    # 关联
    """)
    _write(c, """\
    ---
    doc_type: comps
    stock_codes: ['300373']
    stock_names: [扬杰科技]
    themes: [功率半导体]
    period: 26h1
    date: 2026-07-03
    related_docs:
      - path: ../sectors/semiconductor/power/扬杰科技/index.md
        note: 质地第一档
    ---
    # C
    """)
    rc, out = run_refs(tmp_path, '--check-orphans')
    assert rc == 0
    assert 'No orphans' in out
```

- [ ] **Step 2: 跑测试确认失败**

```bash
PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_lint_docs_refs.py -v
```

Expected:
- `test_refs_folder_symmetry_via_related_md` FAIL —— 报 `index.md: asymmetric ref to .../c.md`（对端出链写在 related.md 里，现实现只读 target 文件自身）；
- `test_refs_rejects_same_folder_self_ref` FAIL —— 现实现认为 related.md ↔ index.md 不对称（报 asymmetric）而非报「同一股票文件夹」，`'同一股票文件夹' in out` 断言失败；
- `test_refs_non_folder_dirs_stay_strict` PASS（回归保护，本就该过）；
- `test_orphans_folder_referenced_through_index` FAIL —— 现实现按文件粒度，`index.md` 无人直接... 实际会被 comps 引用故不算孤儿，但 `related.md` 的 doc_type 不在 `_NEVER_ORPHAN` 里且无人指向它 → 被列为孤儿，`'No orphans' in out` 失败。

- [ ] **Step 3: 改实现**

`scripts/lint_docs_refs.py`。先把 `_NEVER_ORPHAN` 加一项：

```python
_NEVER_ORPHAN = {'buffett-section', 'buffett-events', 'buffett-related'}
```

在 `_resolve` 函数之后插入三个辅助函数：

```python
def _folders(docs: dict[Path, dict]) -> set[Path]:
    """股票文件夹档目录集合：含 doc_type: buffett 的 index.md 的那个目录。"""
    return {p.parent for p, fm in docs.items()
            if p.name == 'index.md' and fm.get('doc_type') == 'buffett'}


def _node(p: Path, folders: set[Path]) -> Path:
    """引用节点：文件夹档内任一文件归并到文件夹本身，其余按文件自身。"""
    return p.parent if p.parent in folders else p


def _node_refs(docs: dict[Path, dict], folders: set[Path]) -> dict[Path, set[Path]]:
    """node -> 该 node 全部文件出链指向的 node 集合。"""
    out: dict[Path, set[Path]] = {}
    for path, fm in docs.items():
        bucket = out.setdefault(_node(path, folders), set())
        for r in fm.get('related_docs') or []:
            if isinstance(r, dict) and 'path' in r:
                bucket.add(_node(_resolve(path, r['path']), folders))
    return out
```

把 `_check` 整体替换为：

```python
def _check(docs: dict[Path, dict]) -> list[str]:
    violations: list[str] = []
    folders = _folders(docs)
    node_refs = _node_refs(docs, folders)
    for path, fm in docs.items():
        rels = fm.get('related_docs') or []
        if not isinstance(rels, list):
            violations.append(f"{path}: related_docs must be list")
            continue
        for i, ref in enumerate(rels):
            if not isinstance(ref, dict) or 'path' not in ref:
                violations.append(f"{path}: related_docs[{i}] missing 'path'")
                continue
            rel = ref['path']
            if rel.startswith('/'):
                violations.append(f"{path}: related_docs[{i}].path '{rel}' must be relative")
                continue
            target = _resolve(path, rel)
            if target not in docs:
                violations.append(f"{path}: related_docs[{i}].path -> '{rel}' not found")
                continue
            src, dst = _node(path, folders), _node(target, folders)
            if src == dst:
                violations.append(
                    f"{path}: related_docs[{i}].path '{rel}' 指向同一股票文件夹内部，"
                    f"应改用正文相对链接")
                continue
            if ref.get('symmetric', True) and src not in node_refs.get(dst, set()):
                violations.append(
                    f"{path}: asymmetric ref to {target} "
                    f"(set symmetric: false to allow one-way)")
    return violations
```

把 `_orphans` 整体替换为：

```python
def _orphans(docs: dict[Path, dict]) -> list[Path]:
    folders = _folders(docs)
    referenced: set[Path] = set()
    for path, fm in docs.items():
        for ref in fm.get('related_docs') or []:
            if isinstance(ref, dict) and 'path' in ref:
                referenced.add(_node(_resolve(path, ref['path']), folders))
    return sorted(p for p, fm in docs.items()
                  if _node(p, folders) not in referenced
                  and fm.get('doc_type') not in _NEVER_ORPHAN)
```

`_render_block` / `_rewrite_blocks` / `main` 不动。

- [ ] **Step 4: 跑测试确认通过**

```bash
PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_lint_docs_refs.py -v
```

Expected: PASS（含既有 7 条 + 新增 4 条）。既有 `test_orphans_skip_folder_sections` 必须仍 PASS —— 它断言无人引用的文件夹只报 `index.md`、不报 `thesis.md`/`events.md`，node 归并后仍按文件逐个打印、只是判据换成 node，行为不变。

- [ ] **Step 5: 跑全池双 lint 确认零回归**

```bash
PYTHONIOENCODING=utf-8 rtk python scripts/lint_docs_refs.py
PYTHONIOENCODING=utf-8 rtk python scripts/lint_docs_frontmatter.py
PYTHONIOENCODING=utf-8 rtk python scripts/lint_docs_refs.py --check-orphans
```

Expected: 前两条 exit 0、各 `391 file(s)`；第三条的孤儿清单与改动前一致（node 归并只可能让孤儿变少，若出现**新增**孤儿即为 bug，须停下排查）。

- [ ] **Step 6: 确认存量档一行未改**

```bash
rtk git status --short docs/stock-analytics/
```

Expected: 空输出（`--rewrite-blocks` 全程未跑，存量档不该有任何改动）。

- [ ] **Step 7: 提交**

```bash
rtk git add scripts/lint_docs_refs.py tests/test_lint_docs_refs.py && rtk git commit -m "feat(lint-refs): 对称/孤儿判定升到文件夹粒度（node 归并）+ 同文件夹自指守卫"
```

---

### Task 3: Phase B 闸门查七文件、池索引跳过 buffett-related

**Files:**
- Modify: `scripts/deep_redo_gate.py:35`（`FOLDER_FILES`）
- Modify: `.claude/skills/stock-research/scripts/pool_index.py:60`（`parse_doc` 的跳过集合）
- Test: `tests/test_deep_redo_gate.py:205-211`（`_make_folder` helper）+ 新增 1 条；`tests/test_pool_index_match.py` 新增 1 条；`tests/test_buffett_analysis.py` 新增 1 条守卫测试

**Interfaces:**
- Consumes: Task 1 的 `buffett-related` 字面量
- Produces: `FOLDER_FILES` 含 `'related.md'`（七项）；`pool_index.parse_doc(path, root)` 对 `doc_type: buffett-related` 返回 `None`。无下游任务依赖。

- [ ] **Step 1: 写失败测试**

`tests/test_deep_redo_gate.py`：先给 `_make_folder` 补上新文件（否则既有的 `test_phase_b_folder_doc` 会因缺 related.md 而红，这是预期的红→绿路径的一部分）：

```python
def _make_folder(tmp_path: Path, names=('business', 'thesis', 'valuation', 'sources')) -> Path:
    d = tmp_path / STOCK
    d.mkdir()
    _write(d / 'index.md', DOC_FRONTMATTER)
    for n in names:
        _write(d / f'{n}.md', f'---\ndoc_type: buffett-section\nsection: {n}\n---\n# x\n正文')
    _write(d / 'events.md', '---\ndoc_type: buffett-events\nrelated_docs: []\n---\n# 事件\n')
    _write(d / 'related.md', '---\ndoc_type: buffett-related\nrelated_docs: []\n---\n# 关联文档\n')
    return d
```

再在该文件末尾追加：

```python
def test_phase_b_folder_missing_related(tmp_path, capsys):
    art, _ = _make_phase_b(tmp_path)
    d = _make_folder(tmp_path)
    (d / 'related.md').unlink()
    rc = main([STOCK, DATE, '--phase', 'B', '--doc', str(d), '--artifacts', str(art)])
    out = capsys.readouterr().out
    assert rc == 1
    assert 'related.md' in out
```

`tests/test_pool_index_match.py`：把顶部 import 改成同时引入 `parse_doc`，并在末尾追加一条：

```python
from pool_index import match_pool, parse_doc  # noqa: E402
```

```python
def test_parse_doc_skips_buffett_related(tmp_path):
    p = tmp_path / 'related.md'
    p.write_text(
        "---\n"
        "doc_type: buffett-related\n"
        "stock_code: '300373'\n"
        "stock_name: 扬杰科技\n"
        "related_docs: []\n"
        "---\n"
        "# 扬杰科技 关联文档\n",
        encoding='utf-8',
    )
    assert parse_doc(p, tmp_path) is None
```

- [ ] **Step 2: 跑测试确认失败**

```bash
PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_deep_redo_gate.py tests/test_pool_index_match.py -v
```

Expected: FAIL —— `test_phase_b_folder_missing_related` 报 rc == 0（闸门还不认识 related.md，删掉也照样放行）；`test_parse_doc_skips_buffett_related` 报返回的是 dict 而非 None。

- [ ] **Step 3: 改实现**

`scripts/deep_redo_gate.py:35`：

```python
FOLDER_FILES = ('index.md', 'related.md', 'business.md', 'thesis.md',
                'valuation.md', 'sources.md', 'events.md')
```

`.claude/skills/stock-research/scripts/pool_index.py:60`：

```python
    if fm.get('doc_type') in ('buffett-section', 'buffett-events', 'buffett-related'):
        return None
```

同文件顶部 docstring 第 15 行的 doc_type 说明行保持不变（它列的是**会进池**的类型，`buffett-related` 不进池，故不必加）。

- [ ] **Step 4: 跑测试确认通过**

```bash
PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_deep_redo_gate.py tests/test_pool_index_match.py -v
```

Expected: PASS（全部，含既有的 `test_phase_b_folder_doc` 与 `test_phase_b_folder_missing_file_and_placeholder`）。

- [ ] **Step 5: 加网页渲染层守卫测试（spec D7）**

`app/services/buffett_analysis.py` 按设计**无需改动**（`build_index` 只认 `index.md` 且 `doc_type == 'buffett'`，`related.md` 既不是 index.md 也不匹配平铺档文件名正则）。这条是钉住该结论的守卫测试，写完应**直接绿**（非红→绿）。在 `tests/test_buffett_analysis.py` 末尾追加：

```python
def test_build_index_ignores_related_md(analysis_dir):
    d = analysis_dir / '扬杰科技'
    d.mkdir()
    _write(d, 'index.md',
           body="---\ndoc_type: buffett\nconviction_date: 2026-08-24\n---\n# 扬杰科技\n")
    _write(d, 'related.md',
           body="---\ndoc_type: buffett-related\nrelated_docs: []\n---\n# 关联文档\n")

    index = BuffettAnalysisService.build_index(analysis_dir)

    assert set(index.keys()) == {'扬杰科技'}
    assert index['扬杰科技'].name == 'index.md'
```

```bash
PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_buffett_analysis.py -v
```

Expected: PASS，且 `git diff app/` 为空（一行应用层代码都没改）。

- [ ] **Step 6: 提交**

```bash
rtk git add scripts/deep_redo_gate.py .claude/skills/stock-research/scripts/pool_index.py tests/test_deep_redo_gate.py tests/test_pool_index_match.py tests/test_buffett_analysis.py && rtk git commit -m "feat(gate,pool): Phase B 闸门查七文件、池索引跳过 buffett-related"
```

---

### Task 4: 规格与流程文档同步到七文件

**Files:**
- Modify: `.claude/skills/buffett-doc-spec/SKILL.md`（§1 frontmatter 示例 + 文件表 + 落点说明段）
- Modify: `.claude/skills/stock-research/references/mode-deep.md`（默认参数表「产出形态」行）
- Modify: `.claude/skills/stock-research/references/mode-earnings.md`（差量更新文件清单）
- Modify: `.claude/skills/stock-research/references/dispatch.md`（Phase B 写手产出清单）
- Modify: `.claude/skills/stock-research/references/finalize.md`（步骤 4 补反向链落点）
- Modify: `.claude/rules/docs-conventions.md`（§跨文档引用）
- Modify: `docs/superpowers/specs/2026-08-24-buffett-related-doc-split-design.md`（把 §3/§5 的「复用 `SECTION_FORBIDDEN`」订正为 `RELATED_FORBIDDEN`）
- Modify: `C:\Users\kaven\.claude\projects\D--Git-stock\memory\buffett-doc-folder-architecture.md`（六文件 → 七文件）
- Test: 无单测（纯文档）；验收靠全池双 lint + 全量 pytest

**Interfaces:**
- Consumes: Task 1-3 的全部产出（`buffett-related` doc_type、七文件闸门）
- Produces: 无代码接口。写手/审查员/Phase C 三方读到的规格与实现一致。

- [ ] **Step 1: 改 `buffett-doc-spec/SKILL.md` 的 frontmatter 示例**

把示例 YAML 里 `related_docs:` 整段（`related_docs:` 到 `symmetric: true` 那几行）从 index.md 的示例中**删除**，并在 `commodity_impact` 行之后直接接 `---`。删掉的内容改写成 `related.md` 的独立示例，插在文件表**之后**：

````markdown
`related.md` 形态（结构性引用唯一落点）：

```yaml
---
doc_type: buffett-related
stock_code: '300373'
stock_name: 扬杰科技
related_docs:
- path: <相对路径>            # 按 related.md 所在目录算（与 index.md 同目录，写法同旧档）
  note: ...
  symmetric: true            # true 要求被链档补反向条目（Phase C 做）；不想补就 false
---
# <股票名>（<code>）关联文档

<!-- BEGIN related_docs (auto-generated from frontmatter, do not edit) -->
<!-- END related_docs -->
```
````

- [ ] **Step 2: 改 `buffett-doc-spec/SKILL.md` 的文件表与落点说明**

文件表在 `index.md` 行之后插入一行、并把 index.md 行的「内容」列改掉：

```markdown
| index.md | buffett（上述完整 frontmatter，**不含 related_docs**） | §0 + §10 + §11 | ≤12KB |
| related.md | buffett-related | 只含 frontmatter related_docs（结构性引用）+ h1；重做时**重写** | — |
```

表下方那段说明里，把

> section 档 frontmatter 仅 `doc_type / stock_code / stock_name / section` 四字段，禁止 rating/valuation/related_docs/themes（lint 强校验）。index.md 的 `related_docs` 只放结构性引用（comps/quarterly/cross-sector/兄弟 buffett 档），事件 theme 一律在 events.md。

改为

> section 档 frontmatter 仅 `doc_type / stock_code / stock_name / section` 四字段，禁止 rating/valuation/related_docs/themes（lint 强校验）。`related.md` 仅 `doc_type / stock_code / stock_name / related_docs` 四字段，禁止 rating/valuation/themes/section。**index.md 不写 `related_docs`**：结构性引用（comps/quarterly/cross-sector/兄弟 buffett 档）一律在 `related.md`，事件 theme 一律在 `events.md`。三者覆盖语义不同：index 重做覆盖、related 重做重写、events 永不覆盖。外部档指过来时**一律指 `<股票名>/index.md`**（阅读入口），对称性由 refs lint 按文件夹粒度判定，不必指 related.md。存量文件夹档（2026-08-24 前建的）index.md 里仍带 related_docs 属**合规存量**，不迁移。

- [ ] **Step 3: 改 stock-research 的三份 reference**

`mode-deep.md` 默认参数表「产出形态」行：把「写 `sectors/<sector>/<subsector>/<股票名>/` 六文件」改成「七文件」；把行尾「已是文件夹 → 原地覆盖 5 文件、`events.md` 不动」改成「已是文件夹 → 原地覆盖 6 文件（含 `related.md`）、`events.md` 不动；存量文件夹档 index.md 里的 `related_docs` 本轮迁进 `related.md` 并从 index.md 删除」。

`mode-earnings.md` 四处（逐处改，别只改第一处）：
- 第 9 行「该股已有 `sectors/<sector>/<subsector>/<股票名>/` 六文件」→「七文件」；
- 第 17 行产出行「原地差量覆盖 `index/business/thesis/valuation/sources.md`；`events.md` 不动」→「原地差量覆盖 `index/business/thesis/valuation/sources.md`；`events.md` / `related.md` 不动（结构性引用有增删才改 `related.md`）」；
- 第 26 行「Read 六文件」→「Read 七文件」；
- 第 47 行「旧档六文件路径（写手 Read）」→「旧档七文件路径（写手 Read）」。

`dispatch.md` §2（Phase B 写手派发）两处：
- 第 84-85 行「产出 6 文件（index/business/thesis/valuation/sources/events，节落点见规格）；**events.md 已存在则不碰**，不存在才新建 `related_docs: []`；index.md ≤12KB」→「产出 7 文件（index/related/business/thesis/valuation/sources/events，节落点见规格）；**`index.md` 的 frontmatter 不写 `related_docs`，结构性引用（comps/兄弟档/quarterly/cross-sector）全部写进 `related.md`**；**events.md 已存在则不碰**，不存在才新建 `related_docs: []`；index.md ≤12KB」；
- 第 99-100 行「六文件天然分段，落盘顺序建议 index → valuation → thesis → business → sources → events」→「七文件天然分段，落盘顺序建议 index → valuation → thesis → business → sources → related → events」。

- [ ] **Step 4: 改 `finalize.md` 步骤 4**

把

> 4. 给新档 `symmetric: true` 指向的每份外部文档补反向 related_docs 条目（path 按被链档所在目录算相对路径）。

改为

> 4. 给新档 `related.md` 里 `symmetric: true` 指向的每份外部文档补反向 related_docs 条目（path 按被链档所在目录算相对路径，**指向 `<股票名>/index.md`** —— 阅读入口；refs lint 按文件夹粒度判对称，指 index.md 即可与 related.md 里的正向条目配对）。

- [ ] **Step 5: 改 `.claude/rules/docs-conventions.md`**

在「## 跨文档引用：frontmatter.related_docs 唯一源」一节的 YAML 示例之后，补一段：

```markdown
**文件夹档的 related_docs 落点（2026-08-24 起）**：`<股票名>/related.md` 放结构性引用（comps/quarterly/cross-sector/兄弟 buffett 档），`<股票名>/events.md` 放事件 theme 回写，`index.md` 不写 related_docs。`lint_docs_refs.py` 的对称与孤儿判定按**文件夹粒度**：`<股票名>/` 下任一文件视为同一引用节点，故外部档指 `index.md`、回链写在 `related.md` 里也算对称；同一文件夹内部互指则报错（文件夹内用正文相对链接 `[§9](valuation.md)`）。2026-08-24 前建的文件夹档 index.md 里仍带 related_docs，属合规存量，不迁移。
```

- [ ] **Step 6: 订正 spec 并同步 memory**

`docs/superpowers/specs/2026-08-24-buffett-related-doc-split-design.md` §3 末尾与 §5 表格里的「复用 `SECTION_FORBIDDEN`」改为「新增 `RELATED_FORBIDDEN = ('rating', 'valuation', 'themes', 'section')`（不能复用 `SECTION_FORBIDDEN`，后者含 `related_docs`）」。

`C:\Users\kaven\.claude\projects\D--Git-stock\memory\buffett-doc-folder-architecture.md`：正文里的「六文件」改「七文件」，并列出 related.md 的职责与「外部反向链指 index.md」这条。同步更新 `MEMORY.md` 里该条的 hook 文字（若提到六文件）。

- [ ] **Step 7: 全量验收**

```bash
PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_docs_schema.py tests/test_lint_docs_refs.py tests/test_lint_docs_frontmatter.py tests/test_deep_redo_gate.py tests/test_pool_index_match.py -v
PYTHONIOENCODING=utf-8 rtk python scripts/lint_docs_frontmatter.py
PYTHONIOENCODING=utf-8 rtk python scripts/lint_docs_refs.py
rtk git status --short docs/stock-analytics/
```

Expected: pytest 全 PASS；两条 lint 各 exit 0 且仍 `391 file(s)`；`git status` 对 `docs/stock-analytics/` 输出为空（零迁移铁律）。

- [ ] **Step 8: 提交**

```bash
rtk git add .claude/skills/buffett-doc-spec/SKILL.md .claude/skills/stock-research/references/mode-deep.md .claude/skills/stock-research/references/mode-earnings.md .claude/skills/stock-research/references/dispatch.md .claude/skills/stock-research/references/finalize.md .claude/rules/docs-conventions.md docs/superpowers/specs/2026-08-24-buffett-related-doc-split-design.md && rtk git commit -m "docs(skills,rules): buffett 文件夹档六文件->七文件，结构性关联文档落 related.md"
```

（memory 目录在仓库外，不进这条 commit。）

---

## 验收标准（全部任务完成后）

1. `rtk python -m pytest tests/test_docs_schema.py tests/test_lint_docs_refs.py tests/test_lint_docs_frontmatter.py tests/test_deep_redo_gate.py tests/test_pool_index_match.py` 全绿。
2. 全池 `lint_docs_frontmatter.py` 与 `lint_docs_refs.py` 均 exit 0、均 `391 file(s)`；`--check-orphans` 清单不新增条目。
3. `git status --short docs/stock-analytics/` 为空 —— 存量档零改动。
4. 手工确认：`.claude/skills/buffett-doc-spec/SKILL.md` 的 index.md frontmatter 示例里**不再有** `related_docs`，且新增了 `related.md` 示例。
5. 下一轮 stock-research 模式 1 跑任一标的时，Phase B 闸门会因缺 `related.md` 而拦截 —— 这是本次改造真正生效的信号。
