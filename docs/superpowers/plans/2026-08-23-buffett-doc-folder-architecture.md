# buffett 档文件夹架构 v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 stock-deep-redo 新建/重做的 buffett 档落成 `sectors/<sector>/<subsector>/<股票名>/` 下的 6 个文件（index/business/thesis/valuation/sources/events），存量平铺档不动，所有消费者双模识别。

**Architecture:** 只有 `index.md` 持有 `doc_type: buffett` 与完整 frontmatter；其余 4 个正文文件 `doc_type: buffett-section`，`events.md` 是 `doc_type: buffett-events` 的 related_docs 日志。schema/lint/sync/app/gate 各加一条识别分支，skill 文档改落点与收尾分支。

**Tech Stack:** Python 3.10, PyYAML, pytest（`PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest`）。

**Spec:** `docs/superpowers/specs/2026-08-23-buffett-doc-folder-architecture-design.md`

## Global Constraints

- 存量 243 份平铺档零改动；全仓双 lint 在每个 task 后仍 exit 0。
- 所有 git 命令前加 `rtk`；`git add` 与 `git commit` 同一条命令链；中文 message 走 `.git/MSG-folder-arch.txt`。
- Windows：写文件显式 `encoding='utf-8'`；跑 pytest 输出重定向到文件再 grep。
- 不写多余注释；不留 backup 文件。
- 新 doc_type 字面量：`buffett-section`、`buffett-events`；section 枚举：`business | thesis | valuation | sources`。

---

### Task 1: schema 新增两个 doc_type

**Files:**
- Modify: `scripts/_docs_schema.py:12,29-37`（DOC_TYPES / REQUIRED_FIELDS_BY_TYPE / validate_frontmatter）
- Test: `tests/test_docs_schema.py`

**Interfaces:**
- Produces: `SECTIONS: set[str] = {'business','thesis','valuation','sources'}`；`DOC_TYPES` 含 `buffett-section` / `buffett-events`；`REQUIRED_FIELDS_BY_TYPE['buffett-section'] = {'doc_type','stock_code','stock_name','section'}`，`['buffett-events'] = {'doc_type','stock_code','stock_name'}`。

- [ ] **Step 1: 写失败测试**（追加到 `tests/test_docs_schema.py` 末尾）

```python
def test_buffett_section_valid():
    fm = {'doc_type': 'buffett-section', 'stock_code': '603986',
          'stock_name': '兆易创新', 'section': 'thesis'}
    assert validate_frontmatter(fm, Path('x/thesis.md')) == []


def test_buffett_section_rejects_bad_section_and_rating():
    fm = {'doc_type': 'buffett-section', 'stock_code': '603986',
          'stock_name': '兆易创新', 'section': 'foo', 'rating': 'watch'}
    v = validate_frontmatter(fm, Path('x/foo.md'))
    assert any("section 'foo'" in s for s in v)
    assert any('must not carry' in s for s in v)


def test_buffett_events_valid_with_impact_refs():
    fm = {'doc_type': 'buffett-events', 'stock_code': '603986', 'stock_name': '兆易创新',
          'related_docs': [{'path': '../../../../themes/a.md', 'impact': '动摇',
                            'magnitude': '中', 'symmetric': True}]}
    assert validate_frontmatter(fm, Path('x/events.md')) == []
```

- [ ] **Step 2: 跑测试确认失败**

`PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_docs_schema.py -q > C:/Users/kaven/AppData/Local/Temp/claude/D--Git-stock/e84adeb9-b494-47c6-8493-3c9001f9c391/scratchpad/t.txt 2>&1; grep -E "passed|failed" <同文件>` → 3 failed（doc_type not in DOC_TYPES）。

- [ ] **Step 3: 实现**

```python
DOC_TYPES: set[str] = {'buffett', 'buffett-section', 'buffett-events',
                       'quarterly', 'cross-sector', 'theme', 'comps'}
SECTIONS: set[str] = {'business', 'thesis', 'valuation', 'sources'}
SECTION_FORBIDDEN: tuple[str, ...] = ('rating', 'valuation', 'related_docs', 'themes')
...
REQUIRED_FIELDS_BY_TYPE 加：
    'buffett-section': {'doc_type', 'stock_code', 'stock_name', 'section'},
    'buffett-events':  {'doc_type', 'stock_code', 'stock_name'},
...
validate_frontmatter 在 `if dt == 'buffett':` 块之后加：
    if dt == 'buffett-section':
        if fm.get('section') not in SECTIONS:
            violations.append(f"{p}: section '{fm.get('section')}' not in {sorted(SECTIONS)}")
        for field in SECTION_FORBIDDEN:
            if field in fm:
                violations.append(f"{p}: buffett-section must not carry '{field}'")
```

- [ ] **Step 4: 跑测试通过**；同时 `python scripts/lint_docs_frontmatter.py` 仍 OK。
- [ ] **Step 5: Commit** `feat(docs-schema): 新增 buffett-section / buffett-events doc_type`

---

### Task 2: refs lint 孤儿检查跳过 section/events

**Files:**
- Modify: `scripts/lint_docs_refs.py:76-83`（`_orphans`）
- Test: `tests/test_lint_docs_refs.py`

- [ ] **Step 1: 失败测试**（追加；复用文件内 `_write` / `run_refs`）

```python
def test_orphans_skip_folder_sections(tmp_path):
    d = tmp_path / 'sectors' / 'semiconductor' / 'storage' / '兆易创新'
    _write(d / 'index.md', """\
    ---
    doc_type: buffett
    stock_code: '603986'
    stock_name: 兆易创新
    sector: semiconductor
    subsector: storage
    themes: [memory]
    rating: config
    conviction_date: 2026-08-23
    thesis: t
    related_docs: []
    ---
    # 兆易创新
    """)
    _write(d / 'thesis.md', """\
    ---
    doc_type: buffett-section
    stock_code: '603986'
    stock_name: 兆易创新
    section: thesis
    ---
    # §6
    """)
    _write(d / 'events.md', """\
    ---
    doc_type: buffett-events
    stock_code: '603986'
    stock_name: 兆易创新
    related_docs: []
    ---
    # 事件
    """)
    rc, out = run_refs(tmp_path, '--check-orphans')
    assert rc == 0
    assert 'thesis.md' not in out and 'events.md' not in out
    assert 'index.md' in out
```

- [ ] **Step 2: 确认失败**（thesis.md/events.md 出现在孤儿清单）。
- [ ] **Step 3: 实现**

```python
_NEVER_ORPHAN = {'buffett-section', 'buffett-events'}

def _orphans(docs):
    ...
    return sorted(p for p, fm in docs.items()
                  if p not in referenced and fm.get('doc_type') not in _NEVER_ORPHAN)
```

- [ ] **Step 4: 通过**；`PYTHONIOENCODING=utf-8 python scripts/lint_docs_refs.py` 仍 exit 0。
- [ ] **Step 5: Commit** `feat(lint-refs): 孤儿检查跳过 buffett-section / buffett-events`

---

### Task 3: sync_valuations 识别 index.md

**Files:**
- Modify: `scripts/sync_valuations.py:123`
- Test: `tests/test_sync_valuations.py`

- [ ] **Step 1: 失败测试**（追加；文件内已有 `sync` import 与 tmp_path 写档模式，仿 `test_sync_end_to_end_creates_yaml`）

```python
def test_sync_picks_folder_index(tmp_path):
    docs_root = tmp_path / 'docs'
    d = docs_root / 'sectors' / 'semiconductor' / 'storage' / '兆易创新'
    d.mkdir(parents=True)
    (d / 'index.md').write_text(
        "---\ndoc_type: buffett\nstock_code: '603986'\nstock_name: 兆易创新\n"
        "sector: semiconductor\nsubsector: storage\nthemes: [memory]\nrating: config\n"
        "conviction_date: 2026-08-23\nthesis: t\nvaluation:\n  bear: 1\n  base: 2\n  bull: 3\n---\n# x\n",
        encoding='utf-8')
    (d / 'valuation.md').write_text(
        "---\ndoc_type: buffett-section\nstock_code: '603986'\nstock_name: 兆易创新\nsection: valuation\n---\n# §9\n",
        encoding='utf-8')
    yaml_path = tmp_path / 'valuations.yaml'
    n = sync(docs_root, yaml_path)
    assert n == 1
    entries = yaml.safe_load(yaml_path.read_text(encoding='utf-8'))
    assert entries[0]['source_doc'] == 'sectors/semiconductor/storage/兆易创新/index.md'
```

- [ ] **Step 2: 确认失败**（n == 0，`*buffett*.md` 不匹配 index.md）。
- [ ] **Step 3: 实现**：`for md in sorted(docs_root.rglob('*.md')):`（下一行已有 `doc_type != 'buffett'` 过滤，README 无 frontmatter 自然跳过）。同步改文件 docstring 第 1 行为「扫 docs/stock-analytics/**/*.md 中 doc_type=buffett 的档」。
- [ ] **Step 4: 通过**；`PYTHONIOENCODING=utf-8 rtk python scripts/sync_valuations.py` 全量跑一遍后 `git diff --stat docs/stock-analytics/valuations.yaml` 应为空（证明存量不受影响）；若非空则 `git checkout` 还原并排查。
- [ ] **Step 5: Commit** `feat(sync-valuations): 识别文件夹架构 index.md`

---

### Task 4: 网页索引识别 `<股票名>/index.md`

**Files:**
- Modify: `app/services/buffett_analysis.py:13-36`
- Test: `tests/test_buffett_analysis.py`

**Interfaces:**
- `build_index` 返回值不变 `dict[str, Path]`；文件夹形态的 value 是 `.../<股票名>/index.md`。

- [ ] **Step 1: 失败测试**（追加）

```python
def test_build_index_folder_form_wins_over_flat(analysis_dir):
    _write(analysis_dir, '2026-04-21-兆易创新-buffett分析.md', body='OLD')
    d = analysis_dir / 'storage' / '兆易创新'
    d.mkdir(parents=True)
    idx = _write(d, 'index.md', body='---\ndoc_type: buffett\nconviction_date: 2026-08-23\n---\n# 兆易创新\n')
    _write(d, 'thesis.md', body='---\ndoc_type: buffett-section\n---\n# §6')

    index = BuffettAnalysisService.build_index(analysis_dir)

    assert index['兆易创新'] == idx
    assert set(index.keys()) == {'兆易创新'}
```

- [ ] **Step 2: 确认失败**。
- [ ] **Step 3: 实现**（替换 `build_index` 的循环体）

```python
from scripts._docs_schema import parse_frontmatter, _as_str_date
...
        for path in directory.rglob('*.md'):
            if not path.is_file():
                continue
            if path.name == 'index.md':
                fm, _ = parse_frontmatter(path)
                if fm.get('doc_type') != 'buffett':
                    continue
                name = path.parent.name
                date_str = _as_str_date(fm.get('conviction_date')) or '9999-99-99'
            else:
                m = FILENAME_RE.match(path.name)
                if not m:
                    continue
                date_str, name = m.group(1), m.group(2)
            prev = latest.get(name)
            if prev is None or date_str > prev[0] or path.name == 'index.md':
                latest[name] = (date_str, path)
```

  `scripts/` 已是可 import 包（`sync_valuations.py` 同样 `from scripts._docs_schema import`，仓根在 sys.path 因 `run.py` 在根）；若 app 内 import 失败则在文件顶部 `sys.path.insert(0, str(Path(__file__).resolve().parents[2]))`。

- [ ] **Step 4: 通过**（全文件 `tests/test_buffett_analysis.py`）。
- [ ] **Step 5: Commit** `feat(buffett-analysis): 网页索引识别 <股票名>/index.md，文件夹优先`

---

### Task 5: gate / anchor_audit 接受目录

**Files:**
- Modify: `scripts/deep_redo_gate.py:90-103,130`；`scripts/deep_redo_anchor_audit.py:49-66`
- Test: `tests/test_deep_redo_gate.py`、`tests/test_deep_redo_anchor_audit.py`

**Interfaces:**
- 新常量 `FOLDER_FILES = ('index.md','business.md','thesis.md','valuation.md','sources.md','events.md')` 在 gate 内。

- [ ] **Step 1: 失败测试**（gate 追加；复用 `_make_phase_b` 的 artifacts 部分与 `DOC_FRONTMATTER`）

```python
def test_phase_b_folder_doc(tmp_path, capsys):
    art, _ = _make_phase_b(tmp_path)
    d = tmp_path / '光智科技'
    d.mkdir()
    _write(d / 'index.md', DOC_FRONTMATTER)
    for n in ('business', 'thesis', 'valuation', 'sources'):
        _write(d / f'{n}.md', f'---\ndoc_type: buffett-section\nsection: {n}\n---\n# x\n正文')
    _write(d / 'events.md', '---\ndoc_type: buffett-events\nrelated_docs: []\n---\n# 事件\n')
    rc = main([STOCK, DATE, '--phase', 'B', '--doc', str(d), '--artifacts', str(art)])
    assert rc == 0 and 'B READY' in capsys.readouterr().out


def test_phase_b_folder_missing_file_and_placeholder(tmp_path, capsys):
    art, _ = _make_phase_b(tmp_path)
    d = tmp_path / '光智科技'
    d.mkdir()
    _write(d / 'index.md', DOC_FRONTMATTER)
    _write(d / 'thesis.md', '---\ndoc_type: buffett-section\nsection: thesis\n---\n# x\n市值【待锚】')
    rc = main([STOCK, DATE, '--phase', 'B', '--doc', str(d), '--artifacts', str(art)])
    out = capsys.readouterr().out
    assert rc == 1
    assert 'business.md' in out and 'thesis.md' in out and '【待锚】' in out or 'lines' in out
```

  anchor_audit 追加（文件内已有 `main` import 模式，照抄）：

```python
def test_audit_accepts_directory(tmp_path, capsys):
    d = tmp_path / 'x'
    d.mkdir()
    (d / 'index.md').write_text('按当前市值反推 10 倍\n', encoding='utf-8')
    (d / 'valuation.md').write_text('无\n隐含 PE 12x\n', encoding='utf-8')
    rc = main([str(d)])
    out = capsys.readouterr().out
    assert rc == 0
    assert 'index.md:    1' in out.replace('\n', ' ') or 'index.md' in out
    assert 'valuation.md' in out and '合计 2 行' in out
```

- [ ] **Step 2: 确认失败**（目录 `read_text` 抛 IsADirectoryError / PermissionError）。
- [ ] **Step 3: 实现 gate**

```python
FOLDER_FILES = ('index.md', 'business.md', 'thesis.md', 'valuation.md', 'sources.md', 'events.md')

def _placeholder_hits(path: Path) -> list[int]:
    return [i for i, line in enumerate(_read(path).splitlines(), 1) if PLACEHOLDER_RE.search(line)]


def check_phase_b(artifacts, stock, date, doc):
    problems = _check_report(artifacts / f'{stock}-{date}-phaseB-report.md', 'B')
    doc_path = Path(doc)
    if not doc_path.exists():
        return problems + [f'B MISSING: 新档 {doc}']
    if doc_path.is_dir():
        files = [doc_path / n for n in FOLDER_FILES]
        missing = [f.name for f in files if not f.exists()]
        if missing:
            problems.append('B MISSING: 文件夹缺 ' + ','.join(missing))
        files = [f for f in files if f.exists()]
        index = doc_path / 'index.md'
    else:
        files, index = [doc_path], doc_path
    for f in files:
        hits = _placeholder_hits(f)
        if hits:
            problems.append(f'B NOT-READY: {f.name} {len(hits)} 处【待锚】/TODO/TBD at lines '
                            + ','.join(str(i) for i in hits))
    if index.exists() and not VALUATION_BLOCK_RE.search(_read(index)):
        problems.append('B NOT-READY: frontmatter 缺 valuation: 块')
    return problems
```

  `--doc` help 改为「新档路径（平铺 .md 或文件夹）」。现有 `test_phase_b_placeholder_left` 断言 `'3 处'`——单文件形态输出变为 `doc.md 3 处`，仍含 `3 处`，不动。

  实现 anchor_audit：

```python
    doc = Path(args.doc)
    if not doc.exists():
        ap.error(f'档不存在: {doc}')
    files = sorted(doc.glob('*.md')) if doc.is_dir() else [doc]
    if args.old or args.new:
        print(f'锚点刷新：{args.old or "?"} → {args.new or "?"}')
    total = 0
    for f in files:
        rows = scan(f.read_text(encoding='utf-8'), args.old)
        prefix = f'{f.name}:' if doc.is_dir() else ''
        for lineno, tags, snippet in rows:
            print(f'{prefix}{lineno:>5} | {",".join(tags):<24} | {snippet}')
        total += len(rows)
    print(f'合计 {total} 行待手算（本工具不算数，逐句核对派生关系）')
```

- [ ] **Step 4: 两个测试文件全过**。
- [ ] **Step 5: Commit** `feat(deep-redo-gate): gate/anchor_audit 接受文件夹档`

---

### Task 6: pool_index 与 portfolio-rebalance 扫描过滤

**Files:**
- Modify: `.claude/skills/news-impact/scripts/pool_index.py:47-60`（`parse_doc`）
- Modify: `.claude/skills/portfolio-rebalance/SKILL.md:88`

- [ ] **Step 1: 实现 pool_index**：`parse_doc` 解析出 `fm` 后加

```python
    if fm.get('doc_type') in ('buffett-section', 'buffett-events'):
        return None
```

- [ ] **Step 2: 冒烟**：`PYTHONIOENCODING=utf-8 python .claude/skills/news-impact/scripts/pool_index.py --help` 退出 0；按 SKILL.md 第 57 行命令跑一次无异常。
- [ ] **Step 3: SKILL.md 第 88 行** `if fm and 'stock_code' in fm:` → `if fm and fm.get('doc_type') == 'buffett':`，并在该函数 docstring 补一句「文件夹架构只认 index.md（doc_type=buffett），section/events 跳过」。
- [ ] **Step 4: Commit** `fix(news-impact/portfolio-rebalance): 扫描跳过 buffett-section / buffett-events`

---

### Task 7: buffett-doc-spec 改规格

**Files:**
- Modify: `.claude/skills/buffett-doc-spec/SKILL.md` §1（frontmatter/命名）、§2（13 节加落点列）

- [ ] **Step 1: §1 末尾「文件命名」段改为**

```
文件落点：`sectors/<sector>/<subsector>/<股票名>/`（稳定路径，重做原地覆盖）：

| 文件 | doc_type | 内容 | 体量 |
|------|----------|------|------|
| index.md | buffett（上述完整 frontmatter） | §0 + §10 + §11 | ≤12KB |
| business.md | buffett-section / section: business | §1-§5 | — |
| thesis.md | buffett-section / section: thesis | §6-§8 | — |
| valuation.md | buffett-section / section: valuation | §9 + 相对旧档变化清单 | — |
| sources.md | buffett-section / section: sources | §12 | — |
| events.md | buffett-events | 只含 frontmatter related_docs（news-impact 回写）+ h1；**重做时不覆盖**，不存在才新建 `related_docs: []` | — |

section 档 frontmatter 仅 `doc_type / stock_code / stock_name / section` 四字段，禁止 rating/valuation/related_docs/themes。
index.md 的 `related_docs` 只放结构性引用（comps/quarterly/cross-sector/兄弟 buffett 档），事件 theme 一律在 events.md。
跨文件引用用相对链接 `[§9](valuation.md)`，不复制正文。存量平铺档 `YYYY-MM-DD-<股票名>-buffett分析.md` 不再新建。
```

- [ ] **Step 2: §2 每节标题后加落点**：§0/§10/§11 → `index.md`；§1-§5 → `business.md`；§6-§8 → `thesis.md`；§9 + 变化清单 → `valuation.md`；§12 → `sources.md`。
- [ ] **Step 3: 写手职责边界加一句**：「写完只跑 `python scripts/lint_docs_frontmatter.py`」不变，补「6 文件齐全由 gate `--doc <文件夹>` 校验」。
- [ ] **Step 4: Commit** `docs(buffett-doc-spec): 文件夹 6 文件落点规格`

---

### Task 8: stock-deep-redo 编排 + dispatch 同步

**Files:**
- Modify: `.claude/skills/stock-deep-redo/SKILL.md`（默认参数表、先做、Phase B 闸门、跨日恢复）
- Modify: `.claude/skills/stock-deep-redo/references/dispatch.md` §2（写手 prompt）

- [ ] **Step 1: 默认参数表「产出形态」行改为**：`写入 sectors/<sector>/<subsector>/<股票名>/ 六文件（规格见 buffett-doc-spec）；该股若只有平铺历史档 → 新建文件夹 + Phase C git rm 平铺档（一次性迁移）；已是文件夹 → 原地覆盖 5 文件、events.md 不动`。
- [ ] **Step 2: 「先做」第 1 条后加**：`1b. 若 <股票名>/events.md 存在：读其 related_docs，date > index.md.conviction_date 的条目即「未消化事件」，摘 note/impact/magnitude 内联给 A2（dispatch.md §1）。`
- [ ] **Step 3: 「先做」第 4 条改为**：`列待删旧档清单：仅平铺 *buffett*.md（文件夹档不删），逐个 Read 确认...`。
- [ ] **Step 4: Phase B 闸门命令改** `--doc <新档文件夹>`；跨日恢复里 anchor_audit 命令改 `<新档文件夹>`。
- [ ] **Step 5: dispatch.md §2** 写手 prompt 骨架：产出从单文件改为 6 文件清单（逐文件列节号），加「index.md ≤12KB；events.md 已存在则不碰」；§1 A2 prompt 加「未消化事件」内联槽位。
- [ ] **Step 6: 行数闸**：`python -c "print(sum(1 for _ in open('.claude/skills/stock-deep-redo/SKILL.md', encoding='utf-8')))"` ≤130。
- [ ] **Step 7: Commit** `docs(stock-deep-redo): 产出改文件夹六文件，先做读 events.md 未消化事件`

---

### Task 9: stock-doc-finalize 与 news-impact 收尾分支

**Files:**
- Modify: `.claude/skills/stock-doc-finalize/SKILL.md` 步骤 2/3/10
- Modify: `.claude/skills/news-impact/SKILL.md` §5

- [ ] **Step 1: finalize 步骤 2 开头加**：`目标已是文件夹（上一轮已迁移）→ 步骤 2/3 整体跳过。首次迁移：` 然后原文。步骤 3 「改指到新档」改为「改指到 `<股票名>/index.md`」。步骤 10 的 `git add <新档>` 改为 `git add <新档文件夹>/`。
- [ ] **Step 2: news-impact §5 改**：反向条目写入位置分支——

```
- 个股是文件夹档（存在 `<股票名>/events.md`）→ 追加到 `events.md` 的 related_docs（path 形如 `../../../../themes/YYYY-MM-DD-<主题>.md`，比平铺档多一层 `../`），theme 档的 related_docs 也指向 `.../<股票名>/events.md`；index.md 不动。
- 平铺档 → 沿用原逻辑写该档 frontmatter。
```

- [ ] **Step 3: docs-conventions.md 目录约定**加一行：`sectors/<sector>/<subsector>/<股票名>/{index,business,thesis,valuation,sources,events}.md — 2026-08-23 起新建/重做档的文件夹形态（spec: docs/superpowers/specs/2026-08-23-buffett-doc-folder-architecture-design.md）；平铺档为存量`。`docs/stock-analytics/README.md` 目录约定同步一行。
- [ ] **Step 4: Commit** `docs(finalize/news-impact/conventions): 文件夹档收尾与事件回写分支`

---

### Task 10: 端到端验证

- [ ] **Step 1**: 全量 `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_docs_schema.py tests/test_lint_docs_refs.py tests/test_lint_docs_frontmatter.py tests/test_sync_valuations.py tests/test_buffett_analysis.py tests/test_deep_redo_gate.py tests/test_deep_redo_anchor_audit.py -q > <scratch>/t.txt 2>&1; grep -E "passed|failed" <scratch>/t.txt` → 0 failed。
- [ ] **Step 2**: `PYTHONIOENCODING=utf-8 python scripts/lint_docs_frontmatter.py` / `python scripts/lint_docs_refs.py` / `--check-orphans` 三者 exit 0。
- [ ] **Step 3**: `rtk git status` 干净；`rtk git log --oneline -10` 看到 Task 1-9 的 commit。
