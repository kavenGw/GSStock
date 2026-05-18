# docs/ 股票分析目录重组 + frontmatter 架构优化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 `docs/analysis/` + `docs/financial-analysis/` 重组到 `docs/stock-analytics/`（sectors/cross-sector/themes/quarterly/comps 拍平），统一 5 类 doc_type 的 frontmatter，并以 `related_docs` 字段 + lint 脚本作为跨文档引用的唯一来源。

**Architecture:** 三段式：(1) 写 schema 模块和两个 lint 脚本作为可重入闸门；(2) 物理 `git mv` + 路径改写；(3) frontmatter 全量补齐 + 反向对称化 + markdown 块脚本重生。每个 Stage 用 lint 出错码作为验收。

**Tech Stack:** Python 3 + PyYAML + pathlib + pytest（测试在 `tests/` 平铺）；`rtk git` / `rtk pytest` 前缀；Windows PowerShell + Bash 双环境兼容。

**Spec:** `docs/superpowers/specs/2026-05-18-docs-stock-analytics-reorg-design.md`

---

## Stage 0 — 准备：脚本骨架 + 共享 schema

### Task 0.1: 共享 schema 模块 + 测试

**Files:**
- Create: `scripts/_docs_schema.py`
- Create: `tests/test_docs_schema.py`
- Create: `tests/fixtures/docs_stub/valid_buffett.md`
- Create: `tests/fixtures/docs_stub/missing_required.md`
- Create: `tests/fixtures/docs_stub/bad_enum.md`

- [ ] **Step 1: 写 fixture（valid buffett frontmatter）**

文件 `tests/fixtures/docs_stub/valid_buffett.md`：

```markdown
---
doc_type: buffett
stock_code: '603986'
stock_name: 兆易创新
sector: semiconductor
subsector: storage
themes: [NOR Flash, MCU]
rating: watch
conviction_date: 2026-04-21
thesis: 测试用最小 buffett 样本
watch_reason: 测试用 watch_reason
related_docs: []
---

# 正文
```

- [ ] **Step 2: 写 fixture（缺必填字段）**

文件 `tests/fixtures/docs_stub/missing_required.md`：

```markdown
---
doc_type: buffett
stock_code: '603986'
stock_name: 兆易创新
---

# 正文
```

- [ ] **Step 3: 写 fixture（枚举非法 + stock_code int）**

文件 `tests/fixtures/docs_stub/bad_enum.md`：

```markdown
---
doc_type: buffett
stock_code: 603986
stock_name: 兆易创新
sector: 不存在板块
subsector: storage
themes: [test]
rating: invalid_rating
conviction_date: 2026-04-21
thesis: 测试
---

# 正文
```

- [ ] **Step 4: 写失败的测试**

文件 `tests/test_docs_schema.py`：

```python
import pytest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts._docs_schema import (
    DOC_TYPES, SECTORS, RATINGS,
    REQUIRED_FIELDS_BY_TYPE,
    parse_frontmatter, validate_frontmatter,
)

FIXTURE_DIR = Path(__file__).parent / 'fixtures' / 'docs_stub'

def test_enums_are_correct():
    assert DOC_TYPES == {'buffett', 'quarterly', 'cross-sector', 'theme', 'comps'}
    assert 'semiconductor' in SECTORS
    assert 'other' in SECTORS
    assert RATINGS == {'core', 'config', 'watch', 'exclude'}

def test_required_fields_by_type():
    assert 'stock_code' in REQUIRED_FIELDS_BY_TYPE['buffett']
    assert 'period' in REQUIRED_FIELDS_BY_TYPE['quarterly']
    assert 'stock_codes' in REQUIRED_FIELDS_BY_TYPE['cross-sector']
    assert 'theme_name' in REQUIRED_FIELDS_BY_TYPE['theme']
    assert 'period' in REQUIRED_FIELDS_BY_TYPE['comps']

def test_parse_frontmatter_valid():
    fm, body = parse_frontmatter(FIXTURE_DIR / 'valid_buffett.md')
    assert fm['doc_type'] == 'buffett'
    assert fm['stock_code'] == '603986'
    assert isinstance(fm['stock_code'], str)
    assert fm['rating'] == 'watch'
    assert '# 正文' in body

def test_parse_frontmatter_no_yaml():
    p = FIXTURE_DIR / '_no_yaml.md'
    p.write_text('# 纯正文\n', encoding='utf-8')
    try:
        fm, body = parse_frontmatter(p)
        assert fm == {}
        assert '# 纯正文' in body
    finally:
        p.unlink()

def test_validate_valid():
    fm, _ = parse_frontmatter(FIXTURE_DIR / 'valid_buffett.md')
    violations = validate_frontmatter(fm, FIXTURE_DIR / 'valid_buffett.md')
    assert violations == []

def test_validate_missing_required():
    fm, _ = parse_frontmatter(FIXTURE_DIR / 'missing_required.md')
    violations = validate_frontmatter(fm, FIXTURE_DIR / 'missing_required.md')
    assert any('sector' in v for v in violations)
    assert any('rating' in v for v in violations)

def test_validate_bad_enum_and_int_stock_code():
    fm, _ = parse_frontmatter(FIXTURE_DIR / 'bad_enum.md')
    violations = validate_frontmatter(fm, FIXTURE_DIR / 'bad_enum.md')
    assert any('sector' in v and '不存在板块' in v for v in violations)
    assert any('rating' in v and 'invalid_rating' in v for v in violations)
    assert any('stock_code' in v and 'str' in v for v in violations)

def test_validate_watch_requires_watch_reason():
    fm = {
        'doc_type': 'buffett', 'stock_code': '600000', 'stock_name': 'X',
        'sector': 'financial', 'subsector': 'bank', 'themes': ['银行'],
        'rating': 'watch', 'conviction_date': '2026-01-01', 'thesis': 'x',
    }
    violations = validate_frontmatter(fm, Path('/dummy.md'))
    assert any('watch_reason' in v for v in violations)

def test_validate_exclude_requires_exclude_reason():
    fm = {
        'doc_type': 'buffett', 'stock_code': '600000', 'stock_name': 'X',
        'sector': 'financial', 'subsector': 'bank', 'themes': ['银行'],
        'rating': 'exclude', 'conviction_date': '2026-01-01', 'thesis': 'x',
    }
    violations = validate_frontmatter(fm, Path('/dummy.md'))
    assert any('exclude_reason' in v for v in violations)

def test_validate_quarterly_period_matches_dir():
    fm = {
        'doc_type': 'quarterly', 'stock_code': '600000', 'stock_name': 'X',
        'sector': 'financial', 'subsector': 'bank',
        'period': '26Q2', 'date': '2026-04-29',
    }
    path = Path('docs/stock-analytics/quarterly/26q1/foo.md')
    violations = validate_frontmatter(fm, path)
    assert any('period' in v and '26q1' in v for v in violations)
```

- [ ] **Step 5: 跑测试验证失败**

```bash
rtk PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 python -m pytest tests/test_docs_schema.py -v
```

Expected: 全部 FAIL（`scripts._docs_schema` 不存在）。

- [ ] **Step 6: 实现 `scripts/_docs_schema.py`**

```python
"""共享 schema 定义：docs/stock-analytics/**/*.md 的 frontmatter 约定与解析工具。
被 lint_docs_frontmatter.py / lint_docs_refs.py / 一次性迁移脚本共用。
"""
from __future__ import annotations
import re
from datetime import date
from pathlib import Path
from typing import Any

import yaml

DOC_TYPES: set[str] = {'buffett', 'quarterly', 'cross-sector', 'theme', 'comps'}

SECTORS: set[str] = {
    'semiconductor', 'electronics', 'consumer', 'materials',
    'energy', 'healthcare', 'media', 'financial', 'industrial',
    'ai-application', 'other',
}

RATINGS: set[str] = {'core', 'config', 'watch', 'exclude'}

# 各 doc_type 必填字段集
REQUIRED_FIELDS_BY_TYPE: dict[str, set[str]] = {
    'buffett':      {'doc_type', 'stock_code', 'stock_name', 'sector', 'subsector',
                     'themes', 'rating', 'conviction_date', 'thesis'},
    'quarterly':    {'doc_type', 'stock_code', 'stock_name', 'sector', 'subsector',
                     'period', 'date'},
    'cross-sector': {'doc_type', 'stock_codes', 'stock_names', 'themes', 'date'},
    'theme':        {'doc_type', 'theme_name', 'themes', 'date'},
    'comps':        {'doc_type', 'stock_codes', 'stock_names', 'themes', 'period', 'date'},
}

_FRONTMATTER_RE = re.compile(r'^---\s*\n(.*?)\n---\s*\n(.*)$', re.DOTALL)
_DATE_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')


def parse_frontmatter(path: Path) -> tuple[dict[str, Any], str]:
    """读 md 文件 → (frontmatter dict, body str)。无 YAML 头返回 ({}, 全文)。"""
    text = path.read_text(encoding='utf-8')
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    fm = yaml.safe_load(m.group(1)) or {}
    if not isinstance(fm, dict):
        return {}, text
    return fm, m.group(2)


def _as_str_date(v: Any) -> str:
    """YAML 可能把 YYYY-MM-DD 解析为 datetime.date；统一转 str 比较。"""
    if isinstance(v, date):
        return v.isoformat()
    return str(v) if v is not None else ''


def validate_frontmatter(fm: dict[str, Any], path: Path) -> list[str]:
    """返回违规清单（空 list = 通过）。每条 violation 是 'path: 描述' 格式。"""
    violations: list[str] = []
    p = str(path)

    dt = fm.get('doc_type')
    if dt not in DOC_TYPES:
        violations.append(f"{p}: doc_type '{dt}' not in {sorted(DOC_TYPES)}")
        return violations  # 后续 check 依赖 doc_type 合法

    required = REQUIRED_FIELDS_BY_TYPE[dt]
    for field in sorted(required):
        if field not in fm or fm[field] in (None, '', []):
            violations.append(f"{p}: missing required field '{field}' for doc_type={dt}")

    # sector 枚举（A/B 类必填，已上方 required 校验；这里只校 enum 合法）
    if 'sector' in fm and fm['sector'] not in SECTORS:
        violations.append(f"{p}: sector '{fm['sector']}' not in {sorted(SECTORS)}")

    # rating 枚举
    if dt == 'buffett':
        if fm.get('rating') not in RATINGS:
            violations.append(f"{p}: rating '{fm.get('rating')}' not in {sorted(RATINGS)}")
        if fm.get('rating') == 'watch' and not fm.get('watch_reason'):
            violations.append(f"{p}: rating=watch requires watch_reason")
        if fm.get('rating') == 'exclude' and not fm.get('exclude_reason'):
            violations.append(f"{p}: rating=exclude requires exclude_reason")

    # stock_code 必须 str（防 YAML int 化丢前导 0）
    if 'stock_code' in fm and not isinstance(fm['stock_code'], str):
        violations.append(f"{p}: stock_code must be str (got {type(fm['stock_code']).__name__})")

    # stock_codes 数组里每项也必须 str
    if 'stock_codes' in fm and isinstance(fm['stock_codes'], list):
        for i, c in enumerate(fm['stock_codes']):
            if not isinstance(c, str):
                violations.append(f"{p}: stock_codes[{i}] must be str (got {type(c).__name__})")

    # 日期格式
    for field in ('conviction_date', 'date'):
        if field in fm:
            v = _as_str_date(fm[field])
            if not _DATE_RE.match(v):
                violations.append(f"{p}: {field} '{v}' not YYYY-MM-DD")

    # period 与目录名一致（quarterly / comps quarterly）
    if 'period' in fm and dt in ('quarterly', 'comps'):
        # 取路径中 quarterly/<NNqN>/ 段
        parts = path.parts
        for i, seg in enumerate(parts):
            if seg == 'quarterly' and i + 1 < len(parts):
                dir_period = parts[i + 1]
                if dir_period.lower() != str(fm['period']).lower():
                    violations.append(
                        f"{p}: period '{fm['period']}' != dir '{dir_period}'")
                break

    return violations
```

- [ ] **Step 7: 跑测试验证通过**

```bash
rtk PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 python -m pytest tests/test_docs_schema.py -v
```

Expected: 全 PASS。

- [ ] **Step 8: 提交**

```bash
rtk git add scripts/_docs_schema.py tests/test_docs_schema.py tests/fixtures/docs_stub/
rtk git commit -m "feat(docs): _docs_schema 共享模块 + 单测（stock-analytics frontmatter 校验）"
```

---

### Task 0.2: lint_docs_frontmatter.py + 测试

**Files:**
- Create: `scripts/lint_docs_frontmatter.py`
- Create: `tests/test_lint_docs_frontmatter.py`

- [ ] **Step 1: 写失败的测试**

文件 `tests/test_lint_docs_frontmatter.py`：

```python
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIX = ROOT / 'tests' / 'fixtures' / 'docs_stub'

def run_lint(target_dir: Path) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, str(ROOT / 'scripts' / 'lint_docs_frontmatter.py'),
         '--root', str(target_dir)],
        capture_output=True, text=True, encoding='utf-8',
    )
    return proc.returncode, proc.stdout + proc.stderr

def test_lint_passes_on_valid(tmp_path):
    (tmp_path / 'sectors' / 'semiconductor' / 'storage').mkdir(parents=True)
    (tmp_path / 'sectors' / 'semiconductor' / 'storage' / 'sample.md').write_text(
        (FIX / 'valid_buffett.md').read_text(encoding='utf-8'), encoding='utf-8')
    code, out = run_lint(tmp_path)
    assert code == 0, out

def test_lint_fails_on_missing_required(tmp_path):
    (tmp_path / 'sectors' / 'semiconductor' / 'storage').mkdir(parents=True)
    (tmp_path / 'sectors' / 'semiconductor' / 'storage' / 'bad.md').write_text(
        (FIX / 'missing_required.md').read_text(encoding='utf-8'), encoding='utf-8')
    code, out = run_lint(tmp_path)
    assert code != 0
    assert 'sector' in out

def test_lint_fails_on_bad_enum(tmp_path):
    (tmp_path / 'sectors' / 'semiconductor' / 'storage').mkdir(parents=True)
    (tmp_path / 'sectors' / 'semiconductor' / 'storage' / 'bad.md').write_text(
        (FIX / 'bad_enum.md').read_text(encoding='utf-8'), encoding='utf-8')
    code, out = run_lint(tmp_path)
    assert code != 0
    assert 'not in' in out  # enum 错误描述
```

- [ ] **Step 2: 跑测试验证失败**

```bash
rtk PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 python -m pytest tests/test_lint_docs_frontmatter.py -v
```

Expected: FAIL（脚本不存在）。

- [ ] **Step 3: 实现脚本**

文件 `scripts/lint_docs_frontmatter.py`：

```python
"""扫 docs/stock-analytics/**/*.md，校验 frontmatter schema。退出码 0=全过，非 0=有违例。

用法：
    python scripts/lint_docs_frontmatter.py
    python scripts/lint_docs_frontmatter.py --root docs/stock-analytics
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts._docs_schema import parse_frontmatter, validate_frontmatter


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', default='docs/stock-analytics',
                    help='扫描根目录（默认 docs/stock-analytics）')
    args = ap.parse_args()

    root = Path(args.root)
    if not root.exists():
        print(f"ERROR: root not found: {root}")
        return 2

    all_violations: list[str] = []
    file_count = 0
    for md in sorted(root.rglob('*.md')):
        if md.name == 'README.md':
            continue
        file_count += 1
        try:
            fm, _ = parse_frontmatter(md)
        except Exception as e:
            all_violations.append(f"{md}: yaml parse error: {e}")
            continue
        if not fm:
            all_violations.append(f"{md}: no YAML frontmatter")
            continue
        all_violations.extend(validate_frontmatter(fm, md))

    if all_violations:
        for v in all_violations:
            print(v)
        print(f"\nFAIL: {len(all_violations)} violation(s) across {file_count} file(s)")
        return 1

    print(f"OK: {file_count} file(s) passed")
    return 0


if __name__ == '__main__':
    sys.exit(main())
```

- [ ] **Step 4: 跑测试验证通过**

```bash
rtk PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 python -m pytest tests/test_lint_docs_frontmatter.py -v
```

Expected: 全 PASS。

- [ ] **Step 5: 提交**

```bash
rtk git add scripts/lint_docs_frontmatter.py tests/test_lint_docs_frontmatter.py
rtk git commit -m "feat(docs): lint_docs_frontmatter.py + 单测"
```

---

### Task 0.3: lint_docs_refs.py + 测试

**Files:**
- Create: `scripts/lint_docs_refs.py`
- Create: `tests/test_lint_docs_refs.py`

- [ ] **Step 1: 写失败的测试**

文件 `tests/test_lint_docs_refs.py`：

```python
import subprocess
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

def run_refs(target_dir: Path, *extra_args: str) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, str(ROOT / 'scripts' / 'lint_docs_refs.py'),
         '--root', str(target_dir), *extra_args],
        capture_output=True, text=True, encoding='utf-8',
    )
    return proc.returncode, proc.stdout + proc.stderr


def _write(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).lstrip(), encoding='utf-8')


def test_refs_passes_on_symmetric_pair(tmp_path):
    a = tmp_path / 'sectors' / 'semiconductor' / 'storage' / 'a.md'
    b = tmp_path / 'quarterly' / '26q1' / 'b.md'
    _write(a, """\
    ---
    doc_type: buffett
    stock_code: '600000'
    stock_name: X
    sector: semiconductor
    subsector: storage
    themes: [test]
    rating: core
    conviction_date: 2026-01-01
    thesis: t
    related_docs:
      - path: ../../../quarterly/26q1/b.md
        note: q1 点评
    ---
    # X
    """)
    _write(b, """\
    ---
    doc_type: quarterly
    stock_code: '600000'
    stock_name: X
    sector: semiconductor
    subsector: storage
    period: 26q1
    date: 2026-04-29
    related_docs:
      - path: ../../sectors/semiconductor/storage/a.md
        note: 主 buffett
    ---
    # X-Q1
    """)
    code, out = run_refs(tmp_path)
    assert code == 0, out


def test_refs_fails_on_missing_target(tmp_path):
    a = tmp_path / 'sectors' / 'semiconductor' / 'storage' / 'a.md'
    _write(a, """\
    ---
    doc_type: buffett
    stock_code: '600000'
    stock_name: X
    sector: semiconductor
    subsector: storage
    themes: [t]
    rating: core
    conviction_date: 2026-01-01
    thesis: t
    related_docs:
      - path: ../../../quarterly/26q1/ghost.md
        note: 不存在
    ---
    """)
    code, out = run_refs(tmp_path)
    assert code != 0
    assert 'ghost.md' in out or 'not found' in out.lower()


def test_refs_fails_on_asymmetric(tmp_path):
    a = tmp_path / 'sectors' / 'semiconductor' / 'storage' / 'a.md'
    b = tmp_path / 'quarterly' / '26q1' / 'b.md'
    _write(a, """\
    ---
    doc_type: buffett
    stock_code: '600000'
    stock_name: X
    sector: semiconductor
    subsector: storage
    themes: [t]
    rating: core
    conviction_date: 2026-01-01
    thesis: t
    related_docs:
      - path: ../../../quarterly/26q1/b.md
        note: q1
    ---
    """)
    _write(b, """\
    ---
    doc_type: quarterly
    stock_code: '600000'
    stock_name: X
    sector: semiconductor
    subsector: storage
    period: 26q1
    date: 2026-04-29
    related_docs: []
    ---
    """)
    code, out = run_refs(tmp_path)
    assert code != 0
    assert 'symmetric' in out.lower() or 'asymmetric' in out.lower() or 'reverse' in out.lower()


def test_refs_rewrite_blocks(tmp_path):
    a = tmp_path / 'sectors' / 'semiconductor' / 'storage' / 'a.md'
    b = tmp_path / 'quarterly' / '26q1' / 'b.md'
    _write(a, """\
    ---
    doc_type: buffett
    stock_code: '600000'
    stock_name: X
    sector: semiconductor
    subsector: storage
    themes: [t]
    rating: core
    conviction_date: 2026-01-01
    thesis: t
    related_docs:
      - path: ../../../quarterly/26q1/b.md
        note: q1 点评
    ---
    # X

    ## 0. 执行摘要
    """)
    _write(b, """\
    ---
    doc_type: quarterly
    stock_code: '600000'
    stock_name: X
    sector: semiconductor
    subsector: storage
    period: 26q1
    date: 2026-04-29
    related_docs:
      - path: ../../sectors/semiconductor/storage/a.md
        note: 主 buffett
    ---
    # X-Q1
    """)
    code, out = run_refs(tmp_path, '--rewrite-blocks')
    assert code == 0, out
    a_text = a.read_text(encoding='utf-8')
    assert '<!-- BEGIN related_docs' in a_text
    assert '<!-- END related_docs -->' in a_text
    assert 'q1 点评' in a_text
    # 二次跑应幂等（不再变化）
    a_before = a_text
    code2, _ = run_refs(tmp_path, '--rewrite-blocks')
    assert code2 == 0
    assert a.read_text(encoding='utf-8') == a_before
```

- [ ] **Step 2: 跑测试验证失败**

```bash
rtk PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 python -m pytest tests/test_lint_docs_refs.py -v
```

Expected: FAIL（脚本不存在）。

- [ ] **Step 3: 实现脚本**

文件 `scripts/lint_docs_refs.py`：

```python
"""校验 docs/stock-analytics/**/*.md 的 related_docs：
1. path 指向的文件存在
2. symmetric: true 时对端反向引用
3. --rewrite-blocks 子命令根据 frontmatter 重生 markdown 块
4. --check-orphans 列零反向引用文档

用法：
    python scripts/lint_docs_refs.py
    python scripts/lint_docs_refs.py --rewrite-blocks
    python scripts/lint_docs_refs.py --check-orphans
"""
from __future__ import annotations
import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts._docs_schema import parse_frontmatter

BLOCK_BEGIN = '<!-- BEGIN related_docs (auto-generated from frontmatter, do not edit) -->'
BLOCK_END = '<!-- END related_docs -->'

_BLOCK_RE = re.compile(
    r'<!-- BEGIN related_docs.*?-->.*?<!-- END related_docs -->\n?',
    re.DOTALL,
)
_H1_RE = re.compile(r'^(# [^\n]+\n)', re.MULTILINE)


def _resolve(base: Path, rel: str) -> Path:
    return (base.parent / rel).resolve()


def _gather(root: Path) -> dict[Path, dict]:
    """{abs_path: frontmatter dict}"""
    out: dict[Path, dict] = {}
    for md in root.rglob('*.md'):
        if md.name == 'README.md':
            continue
        fm, _ = parse_frontmatter(md)
        if fm:
            out[md.resolve()] = fm
    return out


def _check(docs: dict[Path, dict]) -> list[str]:
    violations: list[str] = []
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
            if ref.get('symmetric', True):
                # 对端 frontmatter.related_docs 必须含返回链接
                back = docs[target].get('related_docs') or []
                back_paths = {_resolve(target, r['path']) for r in back
                              if isinstance(r, dict) and 'path' in r}
                if path not in back_paths:
                    violations.append(
                        f"{path}: asymmetric ref to {target} "
                        f"(set symmetric: false to allow one-way)")
    return violations


def _orphans(docs: dict[Path, dict]) -> list[Path]:
    """0 反向引用文档"""
    referenced: set[Path] = set()
    for path, fm in docs.items():
        for ref in fm.get('related_docs') or []:
            if isinstance(ref, dict) and 'path' in ref:
                referenced.add(_resolve(path, ref['path']))
    return sorted(p for p in docs if p not in referenced)


def _render_block(fm: dict, md_path: Path) -> str:
    rels = fm.get('related_docs') or []
    if not rels:
        return ''
    lines = [BLOCK_BEGIN, '> **关联文档**']
    for ref in rels:
        if not isinstance(ref, dict) or 'path' not in ref:
            continue
        rel = ref['path']
        note = ref.get('note', '')
        title = Path(rel).stem
        suffix = f' — {note}' if note else ''
        lines.append(f'> - [{title}]({rel}){suffix}')
    lines.append(BLOCK_END)
    return '\n'.join(lines) + '\n'


def _rewrite_blocks(docs: dict[Path, dict]) -> int:
    changed = 0
    for path, fm in docs.items():
        text = path.read_text(encoding='utf-8')
        new_block = _render_block(fm, path)
        if _BLOCK_RE.search(text):
            new_text = _BLOCK_RE.sub(new_block, text, count=1) if new_block \
                else _BLOCK_RE.sub('', text, count=1)
        elif new_block:
            # 插入到 h1 之后
            m = _H1_RE.search(text)
            if not m:
                continue
            idx = m.end()
            new_text = text[:idx] + '\n' + new_block + text[idx:]
        else:
            new_text = text
        if new_text != text:
            path.write_text(new_text, encoding='utf-8')
            changed += 1
    return changed


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', default='docs/stock-analytics')
    ap.add_argument('--rewrite-blocks', action='store_true',
                    help='根据 frontmatter 重生 h1 后的 related_docs markdown 块')
    ap.add_argument('--check-orphans', action='store_true',
                    help='列出 0 反向引用文档')
    args = ap.parse_args()

    root = Path(args.root)
    if not root.exists():
        print(f"ERROR: root not found: {root}")
        return 2

    docs = _gather(root)

    if args.check_orphans:
        orphans = _orphans(docs)
        if orphans:
            print(f"Orphan docs (no incoming refs): {len(orphans)}")
            for p in orphans:
                print(f"  {p}")
        else:
            print("No orphans")
        return 0

    violations = _check(docs)
    if violations:
        for v in violations:
            print(v)
        print(f"\nFAIL: {len(violations)} violation(s)")
        return 1

    if args.rewrite_blocks:
        changed = _rewrite_blocks(docs)
        print(f"Rewrote {changed} file(s)")

    print(f"OK: {len(docs)} file(s)")
    return 0


if __name__ == '__main__':
    sys.exit(main())
```

- [ ] **Step 4: 跑测试验证通过**

```bash
rtk PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 python -m pytest tests/test_lint_docs_refs.py -v
```

Expected: 全 PASS。

- [ ] **Step 5: 提交**

```bash
rtk git add scripts/lint_docs_refs.py tests/test_lint_docs_refs.py
rtk git commit -m "feat(docs): lint_docs_refs.py + 单测（路径/对称/--rewrite-blocks 幂等）"
```

---

### Task 0.4: 对现状跑两个 lint（验收脚本可用）

**Files:** 无新增；仅运行。

- [ ] **Step 1: 跑 frontmatter lint 对现状**

```bash
PYTHONIOENCODING=utf-8 python scripts/lint_docs_frontmatter.py --root docs/analysis
PYTHONIOENCODING=utf-8 python scripts/lint_docs_frontmatter.py --root docs/financial-analysis
```

Expected: 非 0 退出码，输出 50+ 违例（季报 / 专题 / comps 无 YAML；buffett 部分缺 sector/subsector）。证明脚本能识别真实数据违例。

- [ ] **Step 2: 跑 refs lint 对现状**

```bash
PYTHONIOENCODING=utf-8 python scripts/lint_docs_refs.py --root docs/analysis
```

Expected: 大量 violation（frontmatter 没有 related_docs，且 markdown `>` 链接不被脚本读）。证明脚本运行不崩溃 + 报告格式可读。

- [ ] **Step 3: 记录基线**

将两次 lint 输出（违例数 + 文件计数）记入提交信息，作为迁移前基线。

```bash
PYTHONIOENCODING=utf-8 python scripts/lint_docs_frontmatter.py --root docs/analysis 2>&1 | tail -2 > .omc/artifacts/lint-baseline.txt
PYTHONIOENCODING=utf-8 python scripts/lint_docs_frontmatter.py --root docs/financial-analysis 2>&1 | tail -2 >> .omc/artifacts/lint-baseline.txt
```

（`.omc/artifacts/` 已 gitignore，仅本地留底。）

无 commit 需要。

---

### Task 0.5: 写 stock-analytics/README.md

**Files:**
- Create: `docs/stock-analytics/README.md`

- [ ] **Step 1: 写 README**

```markdown
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
```

- [ ] **Step 2: 提交**

```bash
rtk git add docs/stock-analytics/README.md
rtk git commit -m "docs(stock-analytics): README 目录约定 + frontmatter schema + lint 用法"
```

---

### Task 0.6: 路径硬编码影响面预扫描

**Files:** 无；记录到提交信息。

- [ ] **Step 1: 扫描全仓**

```bash
PYTHONIOENCODING=utf-8 python -c "
from pathlib import Path
import re
patterns = [r'docs/analysis', r'docs/financial-analysis', r'\.\./analysis/', r'\.\./financial-analysis/']
exts = {'.md', '.py', '.yaml', '.yml', '.json', '.html', '.j2'}
hits = []
for p in Path('.').rglob('*'):
    if p.is_file() and p.suffix in exts and 'node_modules' not in p.parts and '__pycache__' not in p.parts and '.git' not in p.parts and 'graphify-out' not in p.parts:
        try:
            text = p.read_text(encoding='utf-8')
        except Exception:
            continue
        for pat in patterns:
            for m in re.finditer(pat, text):
                line = text[:m.start()].count('\n') + 1
                hits.append(f'{p}:{line}:{pat}')
                break
print('\n'.join(hits))
print(f'\nTotal: {len(hits)} hits')
" > .omc/artifacts/path-prescan.txt 2>&1
```

- [ ] **Step 2: 检查扫描结果**

```bash
PYTHONIOENCODING=utf-8 python -c "print(open('.omc/artifacts/path-prescan.txt', encoding='utf-8').read())"
```

Expected: 看到 `.claude/rules/docs-and-portfolio.md`、`.claude/skills/portfolio-init/SKILL.md`、`.claude/skills/portfolio-rebalance/SKILL.md`、`.claude/skills/portfolio-init/config.yaml` 等。还有大量 markdown 内的 `../analysis/` / `../financial-analysis/` 引用。

预扫描清单后续 Stage 1 / Stage 4 直接消费。无 commit 需要。

---

## Stage 1 — 物理迁移

### Task 1.1: 生成 sector 映射表（一次性脚本）

**Files:**
- Create: `scripts/_migration_mapping.py`（一次性，Stage 5 删除）

- [ ] **Step 1: 写映射表**

`scripts/_migration_mapping.py`：

```python
"""一次性迁移映射：buffett 文件名 -> (sector, subsector)。
Stage 1 用，Stage 5 删除。
若文件名未在映射中，迁移脚本会 abort 等人工补全。
"""
SECTOR_MAPPING: dict[str, tuple[str, str]] = {
    # ===== semiconductor =====
    # foundry
    '中芯国际': ('semiconductor', 'foundry'),
    '华虹半导体': ('semiconductor', 'foundry'),
    # storage / NOR / NAND / DRAM
    '兆易创新': ('semiconductor', 'storage'),
    '北京君正': ('semiconductor', 'storage'),
    '普冉股份': ('semiconductor', 'storage'),
    '江波龙': ('semiconductor', 'storage'),
    '聚辰股份': ('semiconductor', 'storage'),
    '复旦微电': ('semiconductor', 'storage'),
    '中颖电子': ('semiconductor', 'mcu'),
    '大普微': ('semiconductor', 'storage'),
    '长鑫科技': ('semiconductor', 'storage'),
    '太极实业': ('semiconductor', 'storage'),
    # packaging / 封测
    '长电科技': ('semiconductor', 'packaging'),
    '通富微电': ('semiconductor', 'packaging'),
    '华天科技': ('semiconductor', 'packaging'),
    '深科技': ('semiconductor', 'packaging'),
    '盛合晶微': ('semiconductor', 'packaging'),
    # design / IP / SoC
    '国芯科技': ('semiconductor', 'design'),
    '希荻微': ('semiconductor', 'design'),
    '全志科技': ('semiconductor', 'design'),
    '芯原股份': ('semiconductor', 'design'),
    # equipment / 设备
    '中微公司': ('semiconductor', 'equipment'),
    '赛腾股份': ('semiconductor', 'equipment'),
    # materials / 材料
    '彤程新材': ('semiconductor', 'materials'),
    '南大光电': ('semiconductor', 'materials'),
    '巨化股份': ('semiconductor', 'materials'),
    '昊华化学': ('semiconductor', 'materials'),
    '石英股份': ('semiconductor', 'materials'),
    '西部材料': ('semiconductor', 'materials'),
    '雅克科技': ('semiconductor', 'materials'),
    '中巨芯': ('semiconductor', 'materials'),
    # PCB / CCL
    '沪电股份': ('semiconductor', 'pcb'),
    '南亚新材': ('semiconductor', 'pcb'),
    '金安国纪': ('semiconductor', 'pcb'),
    '生益科技': ('semiconductor', 'pcb'),
    '兴森科技': ('semiconductor', 'pcb'),
    '胜宏科技': ('semiconductor', 'pcb'),
    # optical / 光通信
    '光迅科技': ('semiconductor', 'optical'),
    '光库科技': ('semiconductor', 'optical'),
    '源杰科技': ('semiconductor', 'optical'),
    '烽火通信': ('semiconductor', 'optical'),
    # 美股半导体
    '迈威尔科技': ('semiconductor', 'design'),
    'AMD': ('semiconductor', 'design'),
    'Intel': ('semiconductor', 'design'),
    # 其他半导体
    '宏和科技': ('semiconductor', 'materials'),  # 电子级玻纤
    '圣泉集团': ('semiconductor', 'materials'),  # 电子树脂
    '江丰电子': ('semiconductor', 'materials'),  # 靶材
    '万华化学': ('materials', 'chemicals'),

    # ===== electronics =====
    '工业富联': ('electronics', 'ems'),
    '立讯精密': ('electronics', 'ems'),
    '鸿博股份': ('electronics', 'consumer'),
    '三花智控': ('electronics', 'components'),  # 制冷+热管理

    # ===== consumer =====
    '青岛啤酒': ('consumer', 'beer'),
    '重庆啤酒': ('consumer', 'beer'),
    '燕京啤酒': ('consumer', 'beer'),
    '安踏体育': ('consumer', 'sportswear'),
    '舒华体育': ('consumer', 'sportswear'),
    '金陵体育': ('consumer', 'sportswear'),
    '中体产业': ('consumer', 'sportswear'),
    '共创草坪': ('consumer', 'sportswear'),

    # ===== materials =====
    '中国铝业': ('materials', 'nonferrous'),
    '云铝股份': ('materials', 'nonferrous'),
    '南山铝业': ('materials', 'nonferrous'),
    '天山铝业': ('materials', 'nonferrous'),
    '紫金矿业': ('materials', 'nonferrous'),
    '洛阳钼业': ('materials', 'nonferrous'),
    '盛屯矿业': ('materials', 'nonferrous'),
    '中金黄金': ('materials', 'nonferrous'),
    '盛达资源': ('materials', 'nonferrous'),
    '西部矿业': ('materials', 'nonferrous'),

    # ===== energy =====
    '阳光电源': ('energy', 'solar'),

    # ===== healthcare =====
    '药明康德': ('healthcare', 'cro'),

    # ===== media =====
    '粤传媒': ('media', 'advertising'),

    # ===== financial =====
    '东吴证券': ('financial', 'securities'),

    # ===== ai-application =====
    '甲骨文': ('ai-application', 'database'),
}

# 跨股专题、主题、板块综合分析的归类
SPECIAL_DESTINATIONS: dict[str, str] = {
    # 跨股专题 -> cross-sector/
    'AMD-Intel': 'cross-sector',
    '立昂微-沪硅产业': 'cross-sector',
    '立讯精密-歌尔股份': 'cross-sector',
    '光迅科技-光库科技': 'cross-sector',
    '工业富联-甲骨文': 'cross-sector',
    # 主题事件 -> themes/
    '世界杯2026': 'themes',
    # 板块分析 -> themes/（板块定性分析作为主题处理）
    '磷化铟': 'themes',
    # 横向 comps -> comps/
    'SLC-NAND': 'comps',
    '利基型存储涨价': 'comps',
}
```

- [ ] **Step 2: 提交（一次性脚本不入库；但因 Stage 5 之前要执行，先 commit 后删）**

```bash
rtk git add scripts/_migration_mapping.py
rtk git commit -m "chore(migration): sector mapping 一次性表（Stage 5 删除）"
```

---

### Task 1.2: 写迁移驱动脚本

**Files:**
- Create: `scripts/_run_migration.py`（一次性）

- [ ] **Step 1: 写脚本**

`scripts/_run_migration.py`：

```python
"""一次性物理迁移：
1. mkdir docs/stock-analytics/{sectors,cross-sector,themes,quarterly,comps}
2. 按 SECTOR_MAPPING / SPECIAL_DESTINATIONS 用 git mv 迁移文件
3. 季报点评 / 季度 comps 走 quarterly/<NNqN>/ 或 comps/quarterly/<NNqN>/
4. 失败即 abort
"""
from __future__ import annotations
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts._migration_mapping import SECTOR_MAPPING, SPECIAL_DESTINATIONS

ROOT = Path(__file__).resolve().parent.parent
SRC_ANALYSIS = ROOT / 'docs' / 'analysis'
SRC_FINANCIAL = ROOT / 'docs' / 'financial-analysis'
DST = ROOT / 'docs' / 'stock-analytics'

# 季度子目录名（如 26q1）正则
_QUARTER_RE = re.compile(r'^\d{2}q\d$', re.IGNORECASE)
# 文件名 YYYY-MM-DD-<名>-<类型>.md
_NAME_RE = re.compile(r'^\d{4}-\d{2}-\d{2}-(.+?)-([^-]+)\.md$')


def git_mv(src: Path, dst: Path):
    dst.parent.mkdir(parents=True, exist_ok=True)
    print(f"git mv {src.relative_to(ROOT)} -> {dst.relative_to(ROOT)}")
    res = subprocess.run(['git', 'mv', str(src), str(dst)],
                         cwd=ROOT, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"FAIL: {res.stderr}")
        sys.exit(1)


def _decide_buffett(src: Path) -> Path:
    """buffett 个股 -> sectors/<sector>/<subsector>/"""
    m = _NAME_RE.match(src.name)
    if not m:
        print(f"abort: filename pattern miss: {src.name}")
        sys.exit(1)
    stem_main = m.group(1)
    # 多股专题（含 '-' 连接如 '光迅科技-光库科技'）走 SPECIAL
    for key, dest in SPECIAL_DESTINATIONS.items():
        if key in stem_main:
            return DST / dest / src.name
    # 单股 buffett
    sector_info = SECTOR_MAPPING.get(stem_main)
    if not sector_info:
        print(f"abort: stock '{stem_main}' not in SECTOR_MAPPING (file: {src.name})")
        sys.exit(1)
    sector, subsector = sector_info
    return DST / 'sectors' / sector / subsector / src.name


def _decide_special(src: Path) -> Path | None:
    """命中 SPECIAL_DESTINATIONS 的 -> 对应目录"""
    for key, dest in SPECIAL_DESTINATIONS.items():
        if key in src.name:
            return DST / dest / src.name
    return None


def migrate_analysis_root():
    for src in sorted(SRC_ANALYSIS.glob('*.md')):
        # 先看是否专题/主题
        dst = _decide_special(src)
        if dst is None:
            dst = _decide_buffett(src)
        git_mv(src, dst)


def migrate_analysis_quarterly():
    """docs/analysis/<NNqN>/*.md -> docs/stock-analytics/quarterly/<NNqN>/*.md"""
    for sub in sorted(SRC_ANALYSIS.iterdir()):
        if not sub.is_dir() or not _QUARTER_RE.match(sub.name):
            continue
        for src in sorted(sub.glob('*.md')):
            dst = DST / 'quarterly' / sub.name.lower() / src.name
            git_mv(src, dst)


def migrate_financial_root():
    for src in sorted(SRC_FINANCIAL.glob('*.md')):
        # 全部归 comps/
        dst = DST / 'comps' / src.name
        git_mv(src, dst)


def migrate_financial_quarterly():
    for sub in sorted(SRC_FINANCIAL.iterdir()):
        if not sub.is_dir() or not _QUARTER_RE.match(sub.name):
            continue
        for src in sorted(sub.glob('*.md')):
            dst = DST / 'comps' / 'quarterly' / sub.name.lower() / src.name
            git_mv(src, dst)


def main():
    if not SRC_ANALYSIS.exists():
        print("docs/analysis/ already migrated, abort")
        return
    migrate_analysis_root()
    migrate_analysis_quarterly()
    migrate_financial_root()
    migrate_financial_quarterly()
    print("\nDone. Remove empty source dirs manually if needed.")


if __name__ == '__main__':
    main()
```

- [ ] **Step 2: dry-run（先注释掉 subprocess.run 改成 print）确认目标路径正确**

手动 review 一遍 `SECTOR_MAPPING` 和 `_decide_special` 输出。如果发现未在映射的股票（比如新加入的），abort 后补到 mapping。

```bash
# 临时把 git_mv 改成 print 跑一遍
PYTHONIOENCODING=utf-8 python scripts/_run_migration.py
```

Expected: 看到所有 `git mv old -> new` 候选。检查无 "abort" 行。

- [ ] **Step 3: 真跑迁移**

恢复 `git_mv` 原状（如果第 2 步改过），执行：

```bash
PYTHONIOENCODING=utf-8 python scripts/_run_migration.py
```

Expected: 全部 git mv 成功，无 abort。

- [ ] **Step 4: 清理空源目录**

```bash
PYTHONIOENCODING=utf-8 python -c "
import shutil
from pathlib import Path
for d in ['docs/analysis', 'docs/financial-analysis']:
    p = Path(d)
    if p.exists():
        # 应该全空了
        remaining = list(p.rglob('*.md'))
        if remaining:
            print(f'ABORT: {d} still has {len(remaining)} files: {remaining[:3]}')
        else:
            shutil.rmtree(p)
            print(f'removed empty {d}')
"
```

Expected: `removed empty docs/analysis` + `removed empty docs/financial-analysis`。

- [ ] **Step 5: 提交物理迁移**

```bash
rtk git add docs/
rtk git commit -m "refactor(docs): 物理迁移 analysis + financial-analysis -> stock-analytics（git mv 保 history）"
```

---

### Task 1.3: 改写跨文档 markdown 相对链接

**Files:** 多个 .md 文件批量编辑。

- [ ] **Step 1: 写改写脚本**

`scripts/_rewrite_links.py`（一次性）：

```python
"""扫 docs/stock-analytics/**/*.md，重写形如 (../analysis/...) (../financial-analysis/...) 
   的 markdown 相对链接到新路径。

策略：解析每个 link，根据被指向的文件名查找新位置（git ls-files 已迁移的目标），重写。
不匹配的链接打 WARN 不 abort，留人工修。
"""
from __future__ import annotations
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STOCK = ROOT / 'docs' / 'stock-analytics'

# Markdown link: [text](path)
_LINK_RE = re.compile(r'\[([^\]]+)\]\(([^)]+)\)')


def _all_md() -> dict[str, Path]:
    """{filename: abs_path}（仅 stock-analytics 内）"""
    out: dict[str, Path] = {}
    for p in STOCK.rglob('*.md'):
        if p.name == 'README.md':
            continue
        # 同名冲突时保留首个，并打 WARN
        if p.name in out:
            print(f"WARN: duplicate filename {p.name}")
        else:
            out[p.name] = p
    return out


def _rewrite_file(path: Path, by_name: dict[str, Path]) -> int:
    text = path.read_text(encoding='utf-8')
    changed = [0]

    def repl(m: re.Match) -> str:
        label, url = m.group(1), m.group(2)
        # 只重写指向 ../analysis/ 或 ../financial-analysis/ 的相对链接
        if '../analysis/' not in url and '../financial-analysis/' not in url:
            return m.group(0)
        # 跳过外链 / 锚点 / 当前文件锚
        if url.startswith(('http', '#', 'mailto:')):
            return m.group(0)
        # 取文件名
        target_name = Path(url).name
        if not target_name.endswith('.md'):
            return m.group(0)
        new_abs = by_name.get(target_name)
        if not new_abs:
            print(f"WARN: {path}: cannot resolve link '{url}'")
            return m.group(0)
        try:
            new_rel = new_abs.relative_to(path.parent.resolve(), walk_up=True)
        except (ValueError, TypeError):
            # Python <3.12 没 walk_up；fallback 用 os.path.relpath
            import os
            new_rel = Path(os.path.relpath(new_abs, path.parent))
        changed[0] += 1
        return f'[{label}]({new_rel.as_posix()})'

    new = _LINK_RE.sub(repl, text)
    if new != text:
        path.write_text(new, encoding='utf-8')
    return changed[0]


def main():
    by_name = _all_md()
    print(f"index: {len(by_name)} files")
    total = 0
    for p in STOCK.rglob('*.md'):
        if p.name == 'README.md':
            continue
        n = _rewrite_file(p, by_name)
        if n:
            print(f"  {p.relative_to(ROOT)}: {n} link(s) rewritten")
            total += n
    print(f"\nDone: {total} link(s) rewritten")


if __name__ == '__main__':
    main()
```

- [ ] **Step 2: 跑脚本**

```bash
PYTHONIOENCODING=utf-8 python scripts/_rewrite_links.py 2>&1 | tee .omc/artifacts/link-rewrite.log
```

Expected: 看到若干文件被重写。所有 `WARN: cannot resolve` 行需人工 review。

- [ ] **Step 3: 人工修剩余 WARN**

打开 `.omc/artifacts/link-rewrite.log`，对每条 WARN：
- 用 Grep 找原 markdown 中的链接
- 如果目标文件被改名，用 Edit 工具手动修

- [ ] **Step 4: 验证无残留旧路径**

```bash
PYTHONIOENCODING=utf-8 python -c "
from pathlib import Path
import re
hits = []
for p in Path('docs/stock-analytics').rglob('*.md'):
    text = p.read_text(encoding='utf-8')
    for m in re.finditer(r'\.\./(analysis|financial-analysis)/', text):
        line = text[:m.start()].count('\n') + 1
        hits.append(f'{p}:{line}')
print('\n'.join(hits) if hits else 'OK: no stale paths')
print(f'\nTotal: {len(hits)}')
"
```

Expected: `OK: no stale paths` 或仅极少需要人工修的剩余。

- [ ] **Step 5: 提交改链**

```bash
rtk git add docs/stock-analytics/
rtk git commit -m "refactor(docs): 改写跨文档相对链接到 stock-analytics 新路径"
```

---

## Stage 2 — Frontmatter 全量补齐

### Task 2.1: buffett 个股补 sector/subsector/related_docs

**Files:** `docs/stock-analytics/sectors/**/*.md`（~50 个）

- [ ] **Step 1: 写 LLM 辅助批补脚本**

`scripts/_batch_frontmatter.py`（一次性）：

```python
"""遍历 docs/stock-analytics/sectors/**/*.md，对每个 buffett 文件：
1. 读现有 frontmatter
2. 如缺 sector/subsector，从文件路径 sectors/<sector>/<subsector>/ 反推填入
3. 如缺 related_docs，从正文顶部 markdown `>` 引用块抽取（heuristic）
4. 重写文件
"""
from __future__ import annotations
import re
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts._docs_schema import parse_frontmatter

ROOT = Path(__file__).resolve().parent.parent
STOCK = ROOT / 'docs' / 'stock-analytics'

# 从正文中 markdown link 抽取（用于 related_docs 抽取）
_LINK_RE = re.compile(r'\[([^\]]+)\]\(([^)]+)\)')


def _extract_related(body: str, base: Path) -> list[dict]:
    """扫前 50 行的 markdown link，收集 *.md 链接作为 related_docs 候选"""
    head = '\n'.join(body.splitlines()[:60])
    rels = []
    seen = set()
    for m in _LINK_RE.finditer(head):
        label, url = m.group(1).strip(), m.group(2).strip()
        if url.startswith(('http', '#', 'mailto:')) or not url.endswith('.md'):
            continue
        if url in seen:
            continue
        seen.add(url)
        rels.append({'path': url, 'note': label})
    return rels


def _process_buffett(path: Path):
    fm, body = parse_frontmatter(path)
    if not fm:
        # 没 YAML，跳过（应该在 Task 2.2-2.5 处理其他类型）
        return False
    if fm.get('doc_type') != 'buffett' and 'rating' not in fm:
        return False

    # 路径反推 sector/subsector
    parts = path.relative_to(STOCK).parts
    if len(parts) >= 4 and parts[0] == 'sectors':
        sector, subsector = parts[1], parts[2]
        fm.setdefault('doc_type', 'buffett')
        if fm.get('sector') != sector:
            fm['sector'] = sector
        if fm.get('subsector') != subsector:
            fm['subsector'] = subsector

    # stock_code 强转 str
    if 'stock_code' in fm and not isinstance(fm['stock_code'], str):
        fm['stock_code'] = str(fm['stock_code']).zfill(6)

    # related_docs 抽取（仅当字段缺）
    if 'related_docs' not in fm or not fm['related_docs']:
        fm['related_docs'] = _extract_related(body, path)

    # 写回
    new_yaml = yaml.safe_dump(fm, allow_unicode=True, sort_keys=False, default_flow_style=False)
    new_text = f"---\n{new_yaml}---\n{body}"
    path.write_text(new_text, encoding='utf-8')
    return True


def main():
    n = 0
    for p in sorted((STOCK / 'sectors').rglob('*.md')):
        if _process_buffett(p):
            n += 1
            print(f"updated {p.relative_to(ROOT)}")
    print(f"\nDone: {n} file(s)")


if __name__ == '__main__':
    main()
```

- [ ] **Step 2: 跑脚本**

```bash
PYTHONIOENCODING=utf-8 python scripts/_batch_frontmatter.py 2>&1 | tee .omc/artifacts/batch-buffett.log
```

Expected: ~50 files updated。

- [ ] **Step 3: lint 校验**

```bash
PYTHONIOENCODING=utf-8 python scripts/lint_docs_frontmatter.py --root docs/stock-analytics/sectors
```

Expected: 全过（如果有遗留违例，多半是 rating=watch/exclude 但缺 reason，人工补；或缺 thesis 等字段）。

- [ ] **Step 4: 人工补漏（每发现 1 项就 fix 1 项）**

针对 lint 输出每行违例，用 Edit 工具改对应文件。

- [ ] **Step 5: 提交**

```bash
rtk git add docs/stock-analytics/sectors/
rtk git commit -m "docs(stock-analytics): buffett 全量补 sector/subsector/related_docs frontmatter"
```

---

### Task 2.2: 季报点评从 0 补 frontmatter

**Files:** `docs/stock-analytics/quarterly/26q1/*.md`（~30 个）

- [ ] **Step 1: 扩展 _batch_frontmatter.py 处理 quarterly**

在 `scripts/_batch_frontmatter.py` 加 `_process_quarterly(path)` 函数：

```python
# 文件名 YYYY-MM-DD-<股票名>-<类型>.md
_FNAME_RE = re.compile(r'^(\d{4}-\d{2}-\d{2})-(.+?)-(.+?)\.md$')


def _process_quarterly(path: Path):
    fm, body = parse_frontmatter(path)
    if fm and fm.get('doc_type'):
        return False  # 已有

    m = _FNAME_RE.match(path.name)
    if not m:
        print(f"WARN: bad filename: {path}")
        return False
    date_str, stock_name, doc_kind = m.group(1), m.group(2), m.group(3)

    # 反推 sector/subsector：从 _migration_mapping 拿
    from scripts._migration_mapping import SECTOR_MAPPING
    sector_info = SECTOR_MAPPING.get(stock_name)
    if not sector_info:
        print(f"WARN: stock '{stock_name}' not in mapping ({path})")
        return False
    sector, subsector = sector_info

    # period 从路径
    period = path.parent.name  # e.g. '26q1'

    # 季报点评 vs 同期专题
    if '季报点评' in doc_kind:
        doc_type = 'quarterly'
    else:
        # 同期专题归为 quarterly 但 doc_kind 不一样 -> 还是按 quarterly schema 处理
        # 或者升级到 cross-sector？保持 quarterly，加 tags 标记
        doc_type = 'quarterly'

    new_fm = {
        'doc_type': doc_type,
        'stock_code': '',  # 人工补
        'stock_name': stock_name,
        'sector': sector,
        'subsector': subsector,
        'period': period,
        'date': date_str,
        'related_docs': _extract_related(body, path),
    }
    if '专题' in doc_kind:
        new_fm['tags'] = [doc_kind.replace('专题', '').strip() or 'special-topic']

    new_yaml = yaml.safe_dump(new_fm, allow_unicode=True, sort_keys=False, default_flow_style=False)
    new_text = f"---\n{new_yaml}---\n{body}"
    path.write_text(new_text, encoding='utf-8')
    return True


# 在 main() 里追加：
#   for p in sorted((STOCK / 'quarterly').rglob('*.md')):
#       if _process_quarterly(p):
#           n += 1
#           print(f"updated {p.relative_to(ROOT)}")
```

- [ ] **Step 2: 跑脚本**

```bash
PYTHONIOENCODING=utf-8 python scripts/_batch_frontmatter.py 2>&1 | tee -a .omc/artifacts/batch-quarterly.log
```

- [ ] **Step 3: 人工补 stock_code 字段**

脚本留空了 `stock_code: ''`。Grep + Edit 逐个补：

```bash
PYTHONIOENCODING=utf-8 python -c "
from pathlib import Path
import re
for p in sorted(Path('docs/stock-analytics/quarterly').rglob('*.md')):
    text = p.read_text(encoding='utf-8')
    if \"stock_code: ''\" in text:
        print(p)
"
```

对每个文件，从同名 buffett 主文档读 `stock_code`，写回。可写一次性辅助脚本扫 mapping 自动补：

```python
# scripts/_fill_stock_code.py（一次性）
from pathlib import Path
from scripts._migration_mapping import SECTOR_MAPPING
import re

# 从 sectors/ 主 buffett 文档读 stock_code -> {stock_name: stock_code}
name_to_code = {}
for p in Path('docs/stock-analytics/sectors').rglob('*.md'):
    text = p.read_text(encoding='utf-8')
    m_name = re.search(r"^stock_name:\s*(.+)$", text, re.M)
    m_code = re.search(r"^stock_code:\s*['\"]?([^'\"\n]+)['\"]?$", text, re.M)
    if m_name and m_code:
        name_to_code[m_name.group(1).strip()] = m_code.group(1).strip()

for p in Path('docs/stock-analytics/quarterly').rglob('*.md'):
    text = p.read_text(encoding='utf-8')
    if "stock_code: ''" not in text:
        continue
    m = re.search(r"^stock_name:\s*(.+)$", text, re.M)
    if not m:
        continue
    name = m.group(1).strip()
    code = name_to_code.get(name)
    if not code:
        print(f"miss: {p} ({name})")
        continue
    new = text.replace("stock_code: ''", f"stock_code: '{code}'", 1)
    p.write_text(new, encoding='utf-8')
    print(f"filled {p}")
```

跑 `python scripts/_fill_stock_code.py`，对剩余 miss 手动 Edit。

- [ ] **Step 4: lint 校验**

```bash
PYTHONIOENCODING=utf-8 python scripts/lint_docs_frontmatter.py --root docs/stock-analytics/quarterly
```

Expected: 全过。

- [ ] **Step 5: 提交**

```bash
rtk git add docs/stock-analytics/quarterly/
rtk git commit -m "docs(stock-analytics): quarterly 从 0 补 frontmatter（stock_code/sector/period/date）"
```

---

### Task 2.3: cross-sector 补 frontmatter

**Files:** `docs/stock-analytics/cross-sector/*.md`（~5 个）

- [ ] **Step 1: 人工补**

数量小，对每个文件人工写 YAML 头：

```yaml
---
doc_type: cross-sector
stock_codes: ['AMD', 'INTC']
stock_names: [AMD, Intel]
themes: [CPU竞争, x86服务器]
date: 2026-05-08
related_docs:
  - path: ../sectors/semiconductor/design/2026-05-09-甲骨文-buffett分析.md
    note: 甲骨文 buffett 主分析
    symmetric: false
---
```

逐个文件用 Read 看正文 + Edit 加 YAML。

- [ ] **Step 2: lint 校验**

```bash
PYTHONIOENCODING=utf-8 python scripts/lint_docs_frontmatter.py --root docs/stock-analytics/cross-sector
```

Expected: 全过。

- [ ] **Step 3: 提交**

```bash
rtk git add docs/stock-analytics/cross-sector/
rtk git commit -m "docs(stock-analytics): cross-sector 补 frontmatter"
```

---

### Task 2.4: themes 补 frontmatter

**Files:** `docs/stock-analytics/themes/*.md`（~3 个：世界杯、磷化铟、可能后续）

- [ ] **Step 1: 人工补**

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

- [ ] **Step 2: lint 校验**

```bash
PYTHONIOENCODING=utf-8 python scripts/lint_docs_frontmatter.py --root docs/stock-analytics/themes
```

- [ ] **Step 3: 提交**

```bash
rtk git add docs/stock-analytics/themes/
rtk git commit -m "docs(stock-analytics): themes 补 frontmatter"
```

---

### Task 2.5: comps 补 frontmatter

**Files:** `docs/stock-analytics/comps/**/*.md`（~7 个含 26q1 子目录）

- [ ] **Step 1: 人工补**

```yaml
---
doc_type: comps
stock_codes: ['603986', '300223', '688766']
stock_names: [兆易创新, 北京君正, 普冉股份]
themes: [SLC NAND, 利基存储, 涨价周期]
period: '2026-05'
date: 2026-05-15
related_docs: [...]
---
```

季度 comps 用 period: '26q1'。

- [ ] **Step 2: lint 校验**

```bash
PYTHONIOENCODING=utf-8 python scripts/lint_docs_frontmatter.py --root docs/stock-analytics/comps
```

- [ ] **Step 3: 提交**

```bash
rtk git add docs/stock-analytics/comps/
rtk git commit -m "docs(stock-analytics): comps 补 frontmatter"
```

---

### Task 2.6: 全量 lint 闸门

- [ ] **Step 1: 全局 lint**

```bash
PYTHONIOENCODING=utf-8 python scripts/lint_docs_frontmatter.py
```

Expected: `OK: <N> file(s) passed`，退出码 0。

- [ ] **Step 2: 如有违例，回到 Task 2.1-2.5 fix**

无 commit 需要。

---

## Stage 3 — related_docs 抽取与反向对称化

### Task 3.1: refs lint 报告

- [ ] **Step 1: 跑 refs lint**

```bash
PYTHONIOENCODING=utf-8 python scripts/lint_docs_refs.py 2>&1 | tee .omc/artifacts/refs-violations.txt
```

Expected: 看到一批 `not found` 和 `asymmetric` 报告。

- [ ] **Step 2: 跑孤儿检查**

```bash
PYTHONIOENCODING=utf-8 python scripts/lint_docs_refs.py --check-orphans 2>&1 | tee .omc/artifacts/refs-orphans.txt
```

Expected: 看到没被任何文档反向引用的文件清单。

无 commit 需要。

---

### Task 3.2: 修 not-found 路径

- [ ] **Step 1: 逐条 fix not-found**

对 `.omc/artifacts/refs-violations.txt` 每行 `not found`：
- 用 Glob 找文件实际位置
- 用 Edit 改 frontmatter.related_docs 的 path

- [ ] **Step 2: 重跑 refs lint**

```bash
PYTHONIOENCODING=utf-8 python scripts/lint_docs_refs.py
```

继续 fix 直到不再有 `not found`。

- [ ] **Step 3: 提交**

```bash
rtk git add docs/stock-analytics/
rtk git commit -m "docs(stock-analytics): 修 frontmatter related_docs not-found 路径"
```

---

### Task 3.3: 反向对称化（补反向引用 / 标 symmetric:false）

- [ ] **Step 1: 逐条处理 asymmetric**

对每条 `asymmetric ref to X` 报告：
- 判断反向引用是否合理（buffett 引季报，反向天然合理 → 在对端补反向引用）
- 不合理（如 buffett 引外部档案，反向不必要 → 在 path 行加 `symmetric: false`）

用 Edit 改对应文件。

- [ ] **Step 2: 重跑 refs lint**

```bash
PYTHONIOENCODING=utf-8 python scripts/lint_docs_refs.py
```

Expected: 退出码 0。

- [ ] **Step 3: 提交**

```bash
rtk git add docs/stock-analytics/
rtk git commit -m "docs(stock-analytics): related_docs 反向对称化"
```

---

## Stage 4 — Markdown 块生成 + 下游配套

### Task 4.1: 一键重生所有 markdown `> 关联文档` 块

- [ ] **Step 1: 跑 --rewrite-blocks**

```bash
PYTHONIOENCODING=utf-8 python scripts/lint_docs_refs.py --rewrite-blocks
```

Expected: `Rewrote <N> file(s)` + `OK: <total> file(s)`。

- [ ] **Step 2: 抽检 3-5 个文件确认块格式**

```bash
PYTHONIOENCODING=utf-8 python -c "
from pathlib import Path
import re
for p in sorted(Path('docs/stock-analytics').rglob('*.md'))[:5]:
    text = p.read_text(encoding='utf-8')
    m = re.search(r'<!-- BEGIN related_docs.*?<!-- END related_docs -->', text, re.DOTALL)
    if m:
        print('===', p)
        print(m.group(0))
        print()
"
```

Expected: 块结构正确，h1 后正确插入。

- [ ] **Step 3: 二次跑验证幂等**

```bash
PYTHONIOENCODING=utf-8 python scripts/lint_docs_refs.py --rewrite-blocks
```

Expected: `Rewrote 0 file(s)`。

- [ ] **Step 4: 提交**

```bash
rtk git add docs/stock-analytics/
rtk git commit -m "docs(stock-analytics): 自动生成所有文档 h1 后 related_docs markdown 块"
```

---

### Task 4.2: 重写 docs-and-portfolio rule

**Files:**
- Modify: `.claude/rules/docs-and-portfolio.md`

- [ ] **Step 1: 重写整个文件**

完全替换为：

```markdown
# 文档目录与 portfolio skill

> **何时读**：写 docs/stock-analytics/ 新文档、修改文档 frontmatter、调用 /portfolio-init 或 /portfolio-rebalance、调整 RebalanceConfig / StockWeight / PositionPlan、跑 lint_docs_frontmatter / lint_docs_refs
> **不必读**：纯代码改动 / 通知 / 数据获取

## 文档目录约定（docs/stock-analytics/）

- `sectors/<sector>/<subsector>/YYYY-MM-DD-<股票名>-buffett分析.md` — 个股 buffett 风格深度分析（按主业务归属）
- `cross-sector/YYYY-MM-DD-<主题>.md` — 多股专题 / 多股 buffett 对比（如 AMD-Intel、立讯-歌尔）
- `themes/YYYY-MM-DD-<主题>.md` — 事件驱动主题（世界杯炒作 / CCL 涨价 / 磷化铟板块定性）
- `quarterly/<NNqN>/YYYY-MM-DD-<股票>-<类型>.md` — 季报点评 + 同期专题（时间归档，跨板块横看）
- `comps/YYYY-MM-DD-<横向主题>-comps.md` — 估值/财务横向对比
- `comps/quarterly/<NNqN>/...` — 季度 comps

**一级 sector 枚举**（11 项，linter 强校验）：
`semiconductor` / `electronics` / `consumer` / `materials` / `energy` / `healthcare` / `media` / `financial` / `industrial` / `ai-application` / `other`

二级 subsector 自由起名。详细 schema + lint 用法见 `docs/stock-analytics/README.md` 与 `scripts/_docs_schema.py`。

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

## 持仓再平衡报告输出（不变）

- 入口：`/portfolio-init`（首次配置 / 主题大调）+ `/portfolio-rebalance`（日常算 diff，支持 `--dry-run`）
- HTML 报告输出目录走本地配置 `.claude/skills/portfolio-init/local-config.yaml` 的 `portfolio.output_dir`（已 gitignore；模板 `local-config.yaml.example`）。skill 启动时缺该文件会立即报错。
- 报告文件名：`{output_dir}/portfolio-init-{YYYY-MM-DD}.html`（按日覆盖）/ `{output_dir}/portfolio-rebalance-{YYYY-MM-DD-HHMM}.html`（按时分留历史）。
- 共享 HTML 模板（git 跟踪）：`.claude/skills/portfolio-init/report-template.html`。
- 写库表：`RebalanceConfig.target_value` / `StockWeight` / `PositionPlan`（PositionPlan 无 unique，写前先 `DELETE FROM position_plans`）。
- `StockWeight.weight` 存原始 float，不要 `round(_, 4-6)`。rebalance 的 shares 计算同时加 `floor(diff/price/100 + 1e-6)*100` / `ceil(.../100 - 1e-6)*100` 吸收 FP roundtrip 噪声。

## docs/stock-analytics/ 是 portfolio skill 的隐式选股池

- 用 Glob `docs/stock-analytics/sectors/**/*.md` + `docs/stock-analytics/cross-sector/**/*.md` 提取候选标的
- 评级 / 主题 / 选股理由从 frontmatter 读
- 同股多 doc 时按 `conviction_date` desc 取首条作为权威评级，其余进 `related_docs`
- 季报点评（`quarterly/`）不进选股池，只作为同期事件清单源（见 portfolio-rebalance SKILL）
```

- [ ] **Step 2: 提交**

```bash
rtk git add .claude/rules/docs-and-portfolio.md
rtk git commit -m "docs(rule): docs-and-portfolio 重写指向 stock-analytics 新结构 + lint 脚本用法"
```

---

### Task 4.3: 微调 CLAUDE.md rule 触发条件

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Read 当前 CLAUDE.md 的 docs-and-portfolio 行**

```bash
PYTHONIOENCODING=utf-8 python -c "print('\n'.join(l for l in open('CLAUDE.md', encoding='utf-8').readlines() if 'docs-and-portfolio' in l))"
```

- [ ] **Step 2: Edit 该行**

把：
```
- `.claude/rules/docs-and-portfolio.md` — docs 命名 + frontmatter + portfolio skill — 写分析或调 portfolio 前
```

改为：
```
- `.claude/rules/docs-and-portfolio.md` — docs/stock-analytics 目录 + frontmatter + lint + portfolio skill — 写分析、改 frontmatter、跑 lint、调 portfolio 前
```

- [ ] **Step 3: 提交**

```bash
rtk git add CLAUDE.md
rtk git commit -m "docs(claude-md): 微调 docs-and-portfolio 触发条件（新增 stock-analytics / lint 关键词）"
```

---

### Task 4.4: portfolio-init skill 路径更新

**Files:**
- Modify: `.claude/skills/portfolio-init/SKILL.md`
- Modify: `.claude/skills/portfolio-init/config.yaml`

- [ ] **Step 1: Edit SKILL.md description + universe scan**

把所有 `docs/analysis/` 替换为 `docs/stock-analytics/sectors/`（个股池）+ `docs/stock-analytics/cross-sector/`（跨股专题）。

具体修改点（Grep 行号）：
- Line 3 (description): `从 docs/analysis/` → `从 docs/stock-analytics/sectors/ + cross-sector/`
- Line 18: `docs/analysis/*.md` → `docs/stock-analytics/{sectors,cross-sector}/**/*.md`
- Line 75: docstring 同上
- Line 79: `glob('docs/analysis/**/*.md')` → 用 `chain(glob('docs/stock-analytics/sectors/**/*.md'), glob('docs/stock-analytics/cross-sector/**/*.md'))`
- Line 279: 路径示例 `docs/analysis/2026-04-21-工业富联-buffett分析.md` → `docs/stock-analytics/sectors/electronics/ems/2026-04-21-工业富联-buffett分析.md`
- Line 333: `docs/analysis/ 全空` → `docs/stock-analytics/sectors/ 全空`

用 Edit 工具逐处改（每处单独 Edit 避免 string ambiguity）。

- [ ] **Step 2: Edit config.yaml**

行 36（约）: `docs/analysis/*.md 顶部 YAML frontmatter` → `docs/stock-analytics/sectors/*.md`
行 54（约）: 同上

- [ ] **Step 3: 提交**

```bash
rtk git add .claude/skills/portfolio-init/
rtk git commit -m "feat(portfolio-init): Glob 路径迁到 docs/stock-analytics/{sectors,cross-sector}"
```

---

### Task 4.5: portfolio-rebalance skill 路径更新

**Files:**
- Modify: `.claude/skills/portfolio-rebalance/SKILL.md`

- [ ] **Step 1: Edit 路径**

按 Task 0.6 预扫描里 portfolio-rebalance SKILL.md 的所有命中行（6 行）：
- Line 18: `docs/analysis/*.md` → `docs/stock-analytics/sectors/*.md`
- Line 82: docstring `扫 docs/analysis/**/*.md` → `扫 docs/stock-analytics/sectors/**/*.md`
- Line 86: glob 同上
- Line 187: `scan_universe('docs/analysis', config)` → `scan_universe('docs/stock-analytics/sectors', config)`
- Line 254: `docs/analysis/ 近 7 天文档` → `docs/stock-analytics/ 近 7 天文档`
- Line 256: glob 同上
- Line 364: edge case `docs/analysis 近 7 天无新增` → `docs/stock-analytics 近 7 天无新增`

逐处 Edit。

- [ ] **Step 2: 提交**

```bash
rtk git add .claude/skills/portfolio-rebalance/
rtk git commit -m "feat(portfolio-rebalance): Glob 路径迁到 docs/stock-analytics/"
```

---

### Task 4.6: app/services/portfolio_shortlist 检查与可能更新

**Files:**
- Modify (if needed): `app/services/portfolio_shortlist/doc_cache.py` / `scoring.py` / `theme_allocator.py`

- [ ] **Step 1: 扫硬编码路径**

```bash
PYTHONIOENCODING=utf-8 python -c "
from pathlib import Path
import re
for p in Path('app/services/portfolio_shortlist').rglob('*.py'):
    text = p.read_text(encoding='utf-8')
    for m in re.finditer(r'docs/(analysis|financial-analysis|stock-analytics)', text):
        line = text[:m.start()].count('\n') + 1
        print(f'{p}:{line}: {m.group(0)}')
"
```

- [ ] **Step 2: 如有硬编码，Edit 替换**

`docs/analysis` → `docs/stock-analytics/sectors`（个股池）  
`docs/financial-analysis` → `docs/stock-analytics/comps`

如果是配置驱动（Path 从 config 传入），改 config 而非 .py。

- [ ] **Step 3: 跑 portfolio_shortlist 单测**

```bash
rtk PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 python -m pytest tests/test_portfolio_shortlist_doc_cache.py tests/test_portfolio_shortlist_scoring.py tests/test_portfolio_shortlist_allocator.py tests/test_portfolio_shortlist_technical.py tests/test_portfolio_shortlist_renderer.py -v
```

Expected: 全 PASS（若 fixture 中有旧路径，同步 fixture 改）。

- [ ] **Step 4: 提交（如有改）**

```bash
rtk git add app/services/portfolio_shortlist/ tests/
rtk git commit -m "feat(portfolio_shortlist): docs 路径迁到 stock-analytics"
```

如果 Step 1 0 命中（说明全配置驱动），跳过 commit。

---

### Task 4.7: portfolio-init dry-run 端到端验证

- [ ] **Step 1: 跑 dry-run**

通过 Skill 工具调用 `/portfolio-init --dry-run`，或如果不便走 skill，直接调底层函数：

```bash
rtk PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 python -c "
import sys
sys.path.insert(0, '.')
from app import create_app
app = create_app()
with app.app_context():
    from app.services.portfolio_shortlist.doc_cache import scan_universe
    universe = scan_universe('docs/stock-analytics/sectors')
    print(f'universe size: {len(universe)}')
    for u in list(universe)[:5]:
        print(u)
"
```

Expected: universe size > 0（应该 ~50），输出几条示例。

- [ ] **Step 2: 对比迁移前基线**

如果之前在 Task 0.4 记录过 universe size，对比一致。如果数量明显少（如缺 cross-sector 池），回 Task 4.4 检查 Glob。

无 commit 需要（只是验证）。

---

## Stage 5 — 清理

### Task 5.1: 删除一次性脚本

- [ ] **Step 1: 删 scripts/_*.py 一次性脚本**

```bash
rm scripts/_migration_mapping.py
rm scripts/_run_migration.py
rm scripts/_rewrite_links.py
rm scripts/_batch_frontmatter.py
rm scripts/_fill_stock_code.py 2>$null
```

（Windows PowerShell 用 `Remove-Item`；bash 用 `rm`。）

- [ ] **Step 2: 验证仅保留可复用脚本**

```bash
PYTHONIOENCODING=utf-8 python -c "
from pathlib import Path
for p in sorted(Path('scripts').glob('*.py')):
    print(p.name)
"
```

Expected:
- `_docs_schema.py`
- `lint_docs_frontmatter.py`
- `lint_docs_refs.py`

（任何其他历史 `scripts/*.py` 保留不动。）

- [ ] **Step 3: 提交**

```bash
rtk git add -A scripts/
rtk git commit -m "chore(scripts): 清理一次性迁移脚本（按 dev-conventions 约定）"
```

---

### Task 5.2: 最终全闸门验收

- [ ] **Step 1: lint frontmatter**

```bash
PYTHONIOENCODING=utf-8 python scripts/lint_docs_frontmatter.py
```

Expected: 退出码 0。

- [ ] **Step 2: lint refs**

```bash
PYTHONIOENCODING=utf-8 python scripts/lint_docs_refs.py
```

Expected: 退出码 0。

- [ ] **Step 3: 单测套全跑**

```bash
rtk PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 python -m pytest tests/test_docs_schema.py tests/test_lint_docs_frontmatter.py tests/test_lint_docs_refs.py tests/test_portfolio_shortlist_doc_cache.py -v
```

Expected: 全 PASS。

- [ ] **Step 4: 旧路径残留扫描**

```bash
PYTHONIOENCODING=utf-8 python -c "
from pathlib import Path
import re
patterns = ['docs/analysis(/|\b)', 'docs/financial-analysis(/|\b)']
hits = []
for p in Path('.').rglob('*'):
    if p.is_file() and p.suffix in {'.md', '.py', '.yaml', '.yml', '.json'} and '.git' not in p.parts and 'graphify-out' not in p.parts and '__pycache__' not in p.parts:
        try:
            text = p.read_text(encoding='utf-8')
        except Exception:
            continue
        for pat in patterns:
            for m in re.finditer(pat, text):
                hits.append(f'{p}:{text[:m.start()].count(chr(10))+1}: {m.group(0)}')
print('\n'.join(hits) or 'OK: 0 residual')
print(f'\nTotal: {len(hits)}')
"
```

Expected: `OK: 0 residual`（除了 spec 历史描述、CLAUDE.md/rule 中的「不变路径」例外可接受，应都已改完）。

- [ ] **Step 5: 验证最终目录树**

```bash
PYTHONIOENCODING=utf-8 python -c "
from pathlib import Path
for p in sorted(Path('docs').iterdir()):
    print(p.name)
print('---')
for p in sorted(Path('docs/stock-analytics').iterdir()):
    print(p.name)
"
```

Expected 输出包含 `stock-analytics/`、`plans/`、`superpowers/`、`TECHNICAL_DOCUMENTATION.md`，且 `docs/analysis` / `docs/financial-analysis` 不存在。`stock-analytics/` 下含 `README.md` + 5 个子目录（sectors/cross-sector/themes/quarterly/comps）。

- [ ] **Step 6: 跑 graphify 重建（可选）**

```bash
rtk PYTHONIOENCODING=utf-8 python -c "
from graphify.watch import _rebuild_code
from pathlib import Path
_rebuild_code(Path('.'))
"
```

让 graphify 反映新目录结构。

- [ ] **Step 7: 总结性 commit 或 PR**

如果以 PR 形式合并，在 PR description 引用 spec 路径和验收清单。

```bash
rtk git log --oneline -20
```

确认 commit 历史清晰。无新增 commit。

---

## 自检清单（spec §7 对照）

- [ ] `docs/stock-analytics/` 顶层 + 6 子目录（sectors / cross-sector / themes / quarterly / comps + README）就位
- [ ] `docs/analysis/` 和 `docs/financial-analysis/` 已清空并删除
- [ ] `docs/plans/` 和 `docs/superpowers/` 完全不变
- [ ] 所有 stock-analytics 下文档 frontmatter 通过 `lint_docs_frontmatter.py`
- [ ] 所有 `related_docs` 通过 `lint_docs_refs.py`（路径存在 + 反向对称）
- [ ] 所有文档 h1 后含统一 `<!-- BEGIN related_docs -->` 块
- [ ] `portfolio-init --dry-run` 或等效底层调用跑通，universe size 与迁移前一致
- [ ] `.claude/rules/docs-and-portfolio.md` 重写完成
- [ ] 一次性脚本已删除，仓库新增长期文件 = 3 脚本 + 1 README
