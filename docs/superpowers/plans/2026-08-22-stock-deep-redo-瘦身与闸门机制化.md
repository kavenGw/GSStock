# stock-deep-redo 瘦身与闸门机制化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `stock-deep-redo` 的 SKILL.md 从 378 行编年体重构为 ≤260 行编排手册（实际落定 247 行），教训编号化沉淀到 `references/lessons.md`，并把三处最常翻车的判据（Phase A/B/review 放行、跨日锚点派生数）落成两个可复用脚本。

**Architecture:** 两个纯 stdlib 脚本先在 worktree 里 TDD 落地并合回 main（Task 1-4），再在 main 上做文档重构（Task 5-9）。脚本无状态、不轮询、不 import `app`——放行判据是"检查文件事实"，等待循环由控制者用 `until` 包一层。文档侧用 `[Ln]` 编号把 SKILL.md 的闸门句与 lessons.md 的案例解耦，SKILL.md 末尾的「维护规则」节负责防止它再长回编年体。

**Tech Stack:** Python 3 标准库（argparse / pathlib / re / time）、pytest、rtk（git/pytest 前缀）、Markdown。

**Spec:** `docs/superpowers/specs/2026-08-22-stock-deep-redo-瘦身与闸门机制化-design.md`

## Global Constraints

- **语言**：所有文档、commit message、脚本 docstring 用中文；代码标识符用英文。
- **不写多余注释**：脚本只保留关键流程注释，说明沉淀在 docstring 与 SKILL.md。
- **不留 backup 文件**：改文件就地改，历史靠 git。
- **Windows 编码铁律**（`.claude/rules/dev-environment.md`）：脚本内所有 `open()` / `read_text()` / `write_text()` **必须显式 `encoding='utf-8'`**（默认 cp950 会炸中文）；跑测试与脚本一律前缀 `PYTHONIOENCODING=utf-8`；**`wc -l` 对含中文 md 不可靠**，算行数用 `python -c "print(sum(1 for _ in open(p,encoding='utf-8')))"`。
- **rtk 前缀**：所有 `git` / `pytest` 命令前加 `rtk`，链式 `&&` 中每条都要；**env 赋值必须在 `rtk` 之前**（`PYTHONIOENCODING=utf-8 rtk python -m pytest ...`，写成 `rtk PYTHONIOENCODING=... python` 会报 Binary not found）。
- **git 提交铁律**（`.claude/rules/dev-environment.md`）：`git add <精确路径...> && git commit -F .git/MSG-<任务后缀>.txt` **必须在同一条命令链**（并行 session 会抢 index）；**绝不用 `git commit -- <pathspec>`**（它提交工作区而非暂存区，会裹挟他人在写改动）；message 文件名带任务专属后缀，**切勿用固定的 `.git/MSG.txt`**。
- **分支策略**（`.claude/rules/dev-environment.md`）：改 `scripts/` 与 `tests/` 属功能改动 → 开独立 worktree（Task 1-3）；改 `.claude/skills/` 与 memory 属投研写档配套 → 直接在 `main`（Task 5-9）。
- **测试布局**：单测平铺在 `tests/test_*.py`，不建子目录；测试文件用 `sys.path.insert(0, repo_root)` 后 `from scripts.X import ...`（`scripts/` 无 `__init__.py`，走命名空间包，与 `tests/test_sync_valuations.py` 同款）。
- **不跑 create_app**：两个脚本与其测试均不 import `app`，不需要 `SCHEDULER_ENABLED=0`。
- **编号永久**：`lessons.md` 的 `Ln` 一旦分配**不复用、不重排**（SKILL.md 与 memory 里都有 `[Ln]` 引用）。

---

## File Structure

| 文件 | 责任 | 任务 |
|---|---|---|
| `scripts/deep_redo_gate.py` | 新建。检查某阶段 subagent 产物是否真就绪，输出未就绪项，退出码 0/1/2。无状态、不轮询。 | 1, 2 |
| `tests/test_deep_redo_gate.py` | 新建。用 `tmp_path` 造 artifacts 目录，覆盖三个 phase 的绿/红路径。 | 1, 2 |
| `scripts/deep_redo_anchor_audit.py` | 新建。扫档列出"派生数"句子供逐句手算，退出码恒 0。 | 3 |
| `tests/test_deep_redo_anchor_audit.py` | 新建。造含派生句与旧字面量的 md，断言命中行与标签。 | 3 |
| `.claude/skills/stock-deep-redo/references/lessons.md` | 新建。L1–L15 三段式案例库 + 分棒耗时明细附录。SKILL.md 的引用目标。 | 5 |
| `.claude/skills/stock-deep-redo/SKILL.md` | 重写。编排手册：每阶段「做什么/必内联/放行闸门/预估」四段式 + 维护规则节。≤260 行（实际 247）。 | 6 |
| `.claude/skills/stock-deep-redo/references/playbook.md` | 微调。§9.0 删与 SKILL.md 重复的"自报时间戳不可信"长段，改一句引用 `[L3]`。 | 7 |
| `C:\Users\kaven\.claude\projects\D--Git-stock\memory\` | 删 5 条 skill 专属、3 条通用加 lessons 引用、`MEMORY.md` 同步索引。 | 8 |

**任务顺序理由**：脚本先落地（Task 1-4），Task 6 的 SKILL.md 才能写进真实可跑的闸门命令并当场验证；memory 处置（Task 8）必须在 lessons.md 建好（Task 5）之后，否则内容会丢。

---

### Task 1: `deep_redo_gate.py` 骨架 + Phase A 闸门

**前置**：本任务与 Task 2、3 改 `scripts/`，按分支策略先建 worktree。若尚未建，先执行：

```bash
cd /d/Git/stock && rtk git worktree add ../stock-deepredo-gate -b feat/deep-redo-gate main
```

之后 Task 1-3 的所有命令都在 `../stock-deepredo-gate` 里跑（**用绝对路径，别裸 `cd`**——Bash 工具 cwd 跨调用持久，会泄漏到后续调用）。

**Files:**
- Create: `scripts/deep_redo_gate.py`
- Test: `tests/test_deep_redo_gate.py`

**Interfaces:**
- Consumes: 无（本计划第一个任务）
- Produces:
  - `main(argv: list[str] | None = None) -> int` —— 退出码 0 全绿 / 1 有项未就绪；参数错由 argparse 抛 `SystemExit(2)`
  - `check_phase_a(artifacts: Path, stock: str, date: str, quiet_min: float, now: float) -> list[str]` —— 返回未就绪项描述列表，空列表=全绿
  - 模块常量 `LANES = ('A1', 'A2', 'A3')`、`MIN_EVIDENCE_LINES = 20`
  - 文件名约定：evidence 用 glob `<stock>-<date>-evidence-<lane>-*.md`（后缀「数据锚/论点/lens」不固定，故用 glob）；report 用精确名 `<stock>-<date>-phase<lane>-report.md`

- [ ] **Step 1: 写失败测试**

创建 `tests/test_deep_redo_gate.py`：

```python
"""deep_redo_gate.py：Phase A/B/review 放行闸门的判据。

核心是「evidence mtime 稳定」而非「report 是否存在」——光智轮 A1 在 report
落盘后 14 分钟又追加 325 行附录，report 存在对「是否收工」没有判别力。
"""
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.deep_redo_gate import main

STOCK = '光智科技'
DATE = '2026-08-22'


def _write(path: Path, text: str, age_min: float = 0.0):
    path.write_text(text, encoding='utf-8')
    if age_min:
        old = time.time() - age_min * 60
        os.utime(path, (old, old))


def _evidence_body(lines: int = 30) -> str:
    return '\n'.join(f'- 证据行 {i}：https://example.com/{i} （2026-08-22）' for i in range(lines))


def _report_body() -> str:
    return 'start: 2026-08-22 08:30:00\nend: 2026-08-22 08:52:00\n\n汇报正文。\n'


def _make_phase_a(tmp_path: Path, *, lanes=('A1', 'A2', 'A3'), age_min=5.0,
                  evidence_lines=30, with_report=True, report_body=None):
    """在 tmp_path 造一套 Phase A 产物，返回 artifacts 目录。"""
    art = tmp_path / 'artifacts'
    art.mkdir(exist_ok=True)
    suffix = {'A1': '数据锚', 'A2': '论点', 'A3': 'lens'}
    for lane in lanes:
        _write(art / f'{STOCK}-{DATE}-evidence-{lane}-{suffix[lane]}.md',
               _evidence_body(evidence_lines), age_min)
        if with_report:
            _write(art / f'{STOCK}-{DATE}-phase{lane}-report.md',
                   report_body if report_body is not None else _report_body(), age_min)
    return art


def test_phase_a_all_green(tmp_path, capsys):
    art = _make_phase_a(tmp_path)
    rc = main([STOCK, DATE, '--phase', 'A', '--quiet-min', '3', '--artifacts', str(art)])
    assert rc == 0
    assert 'A READY' in capsys.readouterr().out


def test_phase_a_missing_report(tmp_path, capsys):
    art = _make_phase_a(tmp_path, lanes=('A1', 'A2'))
    _write(art / f'{STOCK}-{DATE}-evidence-A3-lens.md', _evidence_body(), 5.0)
    rc = main([STOCK, DATE, '--phase', 'A', '--artifacts', str(art)])
    out = capsys.readouterr().out
    assert rc == 1
    assert 'A3 MISSING: report' in out


def test_phase_a_evidence_too_fresh(tmp_path, capsys):
    """evidence 刚落盘 = 这一路可能还在追加，不许放行。"""
    art = _make_phase_a(tmp_path, age_min=0.5)
    rc = main([STOCK, DATE, '--phase', 'A', '--quiet-min', '3', '--artifacts', str(art)])
    out = capsys.readouterr().out
    assert rc == 1
    assert 'NOT-READY' in out and 'mtime' in out


def test_phase_a_report_without_end_stamp(tmp_path, capsys):
    art = _make_phase_a(tmp_path, report_body='start: 2026-08-22 08:30:00\n\n还在写。\n')
    rc = main([STOCK, DATE, '--phase', 'A', '--artifacts', str(art)])
    out = capsys.readouterr().out
    assert rc == 1
    assert 'end:' in out


def test_phase_a_evidence_too_short(tmp_path, capsys):
    art = _make_phase_a(tmp_path, evidence_lines=5)
    rc = main([STOCK, DATE, '--phase', 'A', '--artifacts', str(art)])
    out = capsys.readouterr().out
    assert rc == 1
    assert 'lines' in out
```

- [ ] **Step 2: 跑测试确认失败**

```bash
PYTHONIOENCODING=utf-8 rtk python -m pytest tests/test_deep_redo_gate.py -v
```

Expected: 全部 FAIL，`ModuleNotFoundError: No module named 'scripts.deep_redo_gate'`

- [ ] **Step 3: 写实现**

创建 `scripts/deep_redo_gate.py`：

```python
"""stock-deep-redo 阶段放行闸门：检查 subagent 产物是否真的就绪。

用法：
    python scripts/deep_redo_gate.py <股票名> <日期> --phase A [--quiet-min 3]
    python scripts/deep_redo_gate.py <股票名> <日期> --phase B --doc <新档路径>
    python scripts/deep_redo_gate.py <股票名> <日期> --phase review

退出码：0=全绿可放行 / 1=有项未就绪 / 2=参数错。

本脚本**不轮询**（保持无状态可单测），等待由控制者包一层：

    T=1800; E=0
    until python scripts/deep_redo_gate.py 光智科技 2026-08-22 --phase A || [ $E -ge $T ]; do
      sleep 30; E=$((E+30)); done
    [ $E -ge $T ] && echo "TIMEOUT ${E}s — 可能静默失败，控制者接管"

`||` 短路保证超时分支也发信号（lessons.md L7：只报成功的探测器无法区分
crashloop 与"还没好"）。
"""
from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path

LANES = ('A1', 'A2', 'A3')
MIN_EVIDENCE_LINES = 20
END_STAMP_RE = re.compile(r'^end:\s*\S', re.M)


def _read(path: Path) -> str:
    return path.read_text(encoding='utf-8')


def _count_lines(path: Path) -> int:
    with path.open(encoding='utf-8') as fh:
        return sum(1 for _ in fh)


def _age_min(path: Path, now: float) -> float:
    return (now - path.stat().st_mtime) / 60.0


def _find_one(artifacts: Path, pattern: str) -> Path | None:
    hits = sorted(artifacts.glob(pattern))
    return hits[0] if hits else None


def _check_report(path: Path, tag: str) -> list[str]:
    if not path.exists():
        return [f'{tag} MISSING: report']
    if not END_STAMP_RE.search(_read(path)):
        return [f'{tag} NOT-READY: report 缺 end: 时间戳']
    return []


def check_phase_a(artifacts: Path, stock: str, date: str,
                  quiet_min: float, now: float) -> list[str]:
    problems: list[str] = []
    prefix = f'{stock}-{date}'
    for lane in LANES:
        evidence = _find_one(artifacts, f'{prefix}-evidence-{lane}-*.md')
        if evidence is None:
            problems.append(f'{lane} MISSING: evidence')
        else:
            lines = _count_lines(evidence)
            if lines < MIN_EVIDENCE_LINES:
                problems.append(
                    f'{lane} NOT-READY: evidence only {lines} lines (<{MIN_EVIDENCE_LINES})')
            age = _age_min(evidence, now)
            if age < quiet_min:
                problems.append(
                    f'{lane} NOT-READY: evidence mtime {age:.1f}min ago (<{quiet_min})')
        problems += _check_report(artifacts / f'{prefix}-phase{lane}-report.md', lane)
    return problems


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description='stock-deep-redo 阶段放行闸门',
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('stock', help='股票名（与 .omc/artifacts 文件名前缀一致）')
    ap.add_argument('date', help='日期，形如 2026-08-22')
    ap.add_argument('--phase', required=True, choices=['A', 'B', 'review'])
    ap.add_argument('--quiet-min', type=float, default=3.0,
                    help='evidence mtime 至少多少分钟不变才算收工（默认 3）')
    ap.add_argument('--doc', help='--phase B 必给：新档路径')
    ap.add_argument('--artifacts', default='.omc/artifacts')
    return ap


def main(argv: list[str] | None = None) -> int:
    ap = build_parser()
    args = ap.parse_args(argv)
    artifacts = Path(args.artifacts)
    if not artifacts.is_dir():
        ap.error(f'artifacts 目录不存在: {artifacts}')
    now = time.time()
    problems = check_phase_a(artifacts, args.stock, args.date, args.quiet_min, now)
    if problems:
        for p in problems:
            print(p)
        return 1
    print(f'{args.phase} READY')
    return 0


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    sys.exit(main())
```

- [ ] **Step 4: 跑测试确认通过**

```bash
PYTHONIOENCODING=utf-8 rtk python -m pytest tests/test_deep_redo_gate.py -v
```

Expected: 5 passed

- [ ] **Step 5: 提交**

```bash
printf '%s\n' 'feat(scripts): deep_redo_gate.py Phase A 放行闸门' '' 'Phase A 放行判据从「report 是否存在」改为「evidence mtime 连续 N 分钟不变」——' '光智轮 A1 在 report 落盘后 14 分钟又追加 325 行附录，report 存在对收工无判别力。' '脚本无状态不轮询，等待由控制者用 until 包一层（超时分支也发信号）。' > .git/MSG-gate-a-20260822.txt
rtk git add scripts/deep_redo_gate.py tests/test_deep_redo_gate.py && rtk git commit -F .git/MSG-gate-a-20260822.txt
```

---

### Task 2: `deep_redo_gate.py` Phase B 与 review 闸门

**Files:**
- Modify: `scripts/deep_redo_gate.py`（新增两个 check 函数 + `main()` 分支）
- Test: `tests/test_deep_redo_gate.py`（追加）

**Interfaces:**
- Consumes: Task 1 的 `main()`、`_read()`、`_check_report()`、`END_STAMP_RE`
- Produces:
  - `check_phase_b(artifacts: Path, stock: str, date: str, doc: str) -> list[str]`
  - `check_review(artifacts: Path, stock: str, date: str) -> list[str]`
  - 模块常量 `PLACEHOLDER_RE`（匹配 `【待锚】` / `TODO` / `TBD`）、`SPEC_MARKERS`、`QUALITY_MARKERS`

- [ ] **Step 1: 写失败测试**

在 `tests/test_deep_redo_gate.py` 末尾追加：

```python
DOC_FRONTMATTER = """---
stock_code: '300489'
rating: watch
valuation:
  bull: 120.0
  base: 88.0
  bear: 55.0
---

# 光智科技深度重做

## §9 估值
基准情景每股内在价值 88.0 元。
"""


def _make_phase_b(tmp_path: Path, *, doc_text=DOC_FRONTMATTER, with_report=True):
    art = tmp_path / 'artifacts'
    art.mkdir(exist_ok=True)
    if with_report:
        _write(art / f'{STOCK}-{DATE}-phaseB-report.md', _report_body(), 5.0)
    doc = tmp_path / 'doc.md'
    _write(doc, doc_text)
    return art, doc


def test_phase_b_all_green(tmp_path, capsys):
    art, doc = _make_phase_b(tmp_path)
    rc = main([STOCK, DATE, '--phase', 'B', '--doc', str(doc), '--artifacts', str(art)])
    assert rc == 0
    assert 'B READY' in capsys.readouterr().out


def test_phase_b_placeholder_left(tmp_path, capsys):
    """【待锚】残留 = 主体已落盘但填锚未做，不许进审查。"""
    text = DOC_FRONTMATTER + '\n市值【待锚】亿元。\n前瞻 PE【待锚】倍。\nTODO: 补 §9.10\n'
    art, doc = _make_phase_b(tmp_path, doc_text=text)
    rc = main([STOCK, DATE, '--phase', 'B', '--doc', str(doc), '--artifacts', str(art)])
    out = capsys.readouterr().out
    assert rc == 1
    assert '3 处' in out and 'lines' in out


def test_phase_b_missing_valuation_block(tmp_path, capsys):
    text = DOC_FRONTMATTER.replace('valuation:', 'valuations_todo:')
    art, doc = _make_phase_b(tmp_path, doc_text=text)
    rc = main([STOCK, DATE, '--phase', 'B', '--doc', str(doc), '--artifacts', str(art)])
    out = capsys.readouterr().out
    assert rc == 1
    assert 'valuation' in out


def test_phase_b_without_doc_arg_is_arg_error(tmp_path):
    art, _ = _make_phase_b(tmp_path)
    try:
        main([STOCK, DATE, '--phase', 'B', '--artifacts', str(art)])
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError('缺 --doc 应以退出码 2 结束')


def _review_body(spec='SPEC-COMPLIANT', quality='APPROVED-WITH-NITS'):
    return f'start: 2026-08-22 10:00:00\nend: 2026-08-22 10:04:30\n\n## 规格段\n{spec}\n\n## 质量段\n{quality}\n'


def test_review_all_green(tmp_path, capsys):
    art = tmp_path / 'artifacts'
    art.mkdir()
    _write(art / f'{STOCK}-{DATE}-review-report.md', _review_body(), 1.0)
    rc = main([STOCK, DATE, '--phase', 'review', '--artifacts', str(art)])
    assert rc == 0
    assert 'review READY' in capsys.readouterr().out


def test_review_missing_quality_verdict(tmp_path, capsys):
    """审查是「只回 idle / 只写一段」的重灾区，两段结论都要在文件里。"""
    art = tmp_path / 'artifacts'
    art.mkdir()
    body = 'start: 2026-08-22 10:00:00\nend: 2026-08-22 10:04:30\n\n## 规格段\nSPEC-COMPLIANT\n'
    _write(art / f'{STOCK}-{DATE}-review-report.md', body, 1.0)
    rc = main([STOCK, DATE, '--phase', 'review', '--artifacts', str(art)])
    out = capsys.readouterr().out
    assert rc == 1
    assert '质量段结论' in out


def test_review_report_missing(tmp_path, capsys):
    art = tmp_path / 'artifacts'
    art.mkdir()
    rc = main([STOCK, DATE, '--phase', 'review', '--artifacts', str(art)])
    out = capsys.readouterr().out
    assert rc == 1
    assert 'review MISSING: report' in out
```

- [ ] **Step 2: 跑测试确认失败**

```bash
PYTHONIOENCODING=utf-8 rtk python -m pytest tests/test_deep_redo_gate.py -v
```

Expected: 新增 7 个 FAIL（`main()` 目前无视 `--phase`，一律跑 Phase A 检查），Task 1 的 5 个仍 PASS

- [ ] **Step 3: 写实现**

在 `scripts/deep_redo_gate.py` 的 `LANES` / `MIN_EVIDENCE_LINES` / `END_STAMP_RE` 常量下方追加：

```python
PLACEHOLDER_RE = re.compile(r'【待锚】|\bTODO\b|\bTBD\b')
VALUATION_BLOCK_RE = re.compile(r'^valuation:', re.M)
SPEC_MARKERS = ('SPEC-COMPLIANT', '规格问题', 'Critical', 'Major', 'Minor')
QUALITY_MARKERS = ('APPROVED-WITH-NITS', 'CHANGES-REQUESTED', 'APPROVED')
```

在 `check_phase_a()` 下方追加两个函数：

```python
def check_phase_b(artifacts: Path, stock: str, date: str, doc: str) -> list[str]:
    problems = _check_report(artifacts / f'{stock}-{date}-phaseB-report.md', 'B')
    doc_path = Path(doc)
    if not doc_path.exists():
        return problems + [f'B MISSING: 新档 {doc}']
    text = _read(doc_path)
    hits = [i for i, line in enumerate(text.splitlines(), 1) if PLACEHOLDER_RE.search(line)]
    if hits:
        problems.append(
            f'B NOT-READY: {len(hits)} 处【待锚】/TODO/TBD at lines '
            + ','.join(str(i) for i in hits))
    if not VALUATION_BLOCK_RE.search(text):
        problems.append('B NOT-READY: frontmatter 缺 valuation: 块')
    return problems


def check_review(artifacts: Path, stock: str, date: str) -> list[str]:
    report = artifacts / f'{stock}-{date}-review-report.md'
    problems = _check_report(report, 'review')
    if not report.exists():
        return problems
    text = _read(report)
    if not any(marker in text for marker in SPEC_MARKERS):
        problems.append('review MISSING: 规格段结论')
    if not any(marker in text for marker in QUALITY_MARKERS):
        problems.append('review MISSING: 质量段结论')
    return problems
```

把 `main()` 里那一行无条件的 `problems = check_phase_a(...)` 换成分支：

```python
    if args.phase == 'A':
        problems = check_phase_a(artifacts, args.stock, args.date, args.quiet_min, now)
    elif args.phase == 'B':
        if not args.doc:
            ap.error('--phase B 必须给 --doc <新档路径>')
        problems = check_phase_b(artifacts, args.stock, args.date, args.doc)
    else:
        problems = check_review(artifacts, args.stock, args.date)
```

`now` 只有 Phase A 用到，保留原处的 `now = time.time()` 不动。

- [ ] **Step 4: 跑测试确认通过**

```bash
PYTHONIOENCODING=utf-8 rtk python -m pytest tests/test_deep_redo_gate.py -v
```

Expected: 12 passed

- [ ] **Step 5: 提交**

```bash
printf '%s\n' 'feat(scripts): deep_redo_gate.py 补 Phase B 与 review 闸门' '' 'Phase B 查【待锚】/TODO 占位残留 + valuation 块（对应「主体+填锚」抗中断设计）；' 'review 查规格段与质量段两个结论都在文件里（审查是只回 idle / 只写一段的重灾区）。' > .git/MSG-gate-b-20260822.txt
rtk git add scripts/deep_redo_gate.py tests/test_deep_redo_gate.py && rtk git commit -F .git/MSG-gate-b-20260822.txt
```

---

### Task 3: `deep_redo_anchor_audit.py` 跨日锚点审计

**Files:**
- Create: `scripts/deep_redo_anchor_audit.py`
- Test: `tests/test_deep_redo_anchor_audit.py`

**Interfaces:**
- Consumes: 无（独立脚本）
- Produces:
  - `scan(text: str, old: str | None = None) -> list[tuple[int, list[str], str]]` —— 返回 `(行号, 标签列表, 该行原文截 120 字)`
  - `main(argv: list[str] | None = None) -> int` —— **退出码恒为 0**（报告工具，不裁定）
  - 模块常量 `DERIVED_PATTERNS: list[tuple[str, re.Pattern]]`

- [ ] **Step 1: 写失败测试**

创建 `tests/test_deep_redo_anchor_audit.py`：

```python
"""deep_redo_anchor_audit.py：列出「派生数」句子供逐句手算。

雷赛轮遗漏的 5 处派生数共同特征是**句子里不含任何旧锚的字面量**（前瞻 PE、
市价隐含期权价值、反推所需 owner earnings…），grep 旧价扫不到——所以主判据
是句式而非字面量，--old 只是顺带兜底。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.deep_redo_anchor_audit import main, scan

DOC = """# 雷赛智能

主业估值区间 240~280 亿元。
市价隐含的机器人期权价值 50~90 亿元。
反推现价所需的正常化 owner earnings 为 9.13 亿元。
对照当前市值，相当于 2.85 倍。
现价 60.64 元，较上一交易日无变化。
这一行没有任何派生表述。
"""


def test_scan_finds_derived_sentences():
    rows = scan(DOC)
    linenos = [r[0] for r in rows]
    assert linenos == [4, 5, 6]
    tags = {r[0]: r[1] for r in rows}
    assert '隐含' in tags[4]
    assert '反推' in tags[5]
    assert '对照当前市值' in tags[6] and '相当于N倍' in tags[6]


def test_scan_flags_stale_literal():
    rows = scan(DOC, old='60.64')
    tagged = {r[0]: r[1] for r in rows}
    assert 7 in tagged and tagged[7] == ['STALE-LITERAL']
    assert len(rows) == 4


def test_clean_line_never_reported():
    rows = scan(DOC, old='60.64')
    assert 8 not in [r[0] for r in rows]


def test_main_exit_code_always_zero(tmp_path, capsys):
    doc = tmp_path / 'doc.md'
    doc.write_text(DOC, encoding='utf-8')
    rc = main([str(doc), '--old', '60.64'])
    out = capsys.readouterr().out
    assert rc == 0
    assert 'STALE-LITERAL' in out
    assert '合计 4 行待手算' in out


def test_main_on_clean_doc(tmp_path, capsys):
    doc = tmp_path / 'clean.md'
    doc.write_text('# 标题\n\n没有任何派生表述的正文。\n', encoding='utf-8')
    rc = main([str(doc)])
    assert rc == 0
    assert '合计 0 行待手算' in capsys.readouterr().out
```

- [ ] **Step 2: 跑测试确认失败**

```bash
PYTHONIOENCODING=utf-8 rtk python -m pytest tests/test_deep_redo_anchor_audit.py -v
```

Expected: 5 FAIL，`ModuleNotFoundError: No module named 'scripts.deep_redo_anchor_audit'`

- [ ] **Step 3: 写实现**

创建 `scripts/deep_redo_anchor_audit.py`：

```python
"""stock-deep-redo 跨日锚点审计：列出正文里所有「派生数」句子供逐句手算。

用法：
    python scripts/deep_redo_anchor_audit.py <档路径>
    python scripts/deep_redo_anchor_audit.py <档路径> --old 60.64 --new 54.20

**它不算数，只保证逐句过一遍。** 雷赛轮跨 3 天中断后控制者做了 71 处字面量
替换并 grep 自查干净，审查仍抓出 4 处 Major、复核又自查出第 5 处——五处全部是
用旧市值反推的派生数，句子里不含任何旧锚的字面量，grep 扫不到。所以主判据是
**句式**（反推/隐含/对照当前市值/÷/相当于 N 倍/前瞻 PE），`--old` 的字面量
匹配只是顺带兜底。

退出码恒为 0（报告工具，不裁定）。
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

DERIVED_PATTERNS: list[tuple[str, re.Pattern]] = [
    ('反推', re.compile(r'反推')),
    ('隐含', re.compile(r'隐含')),
    ('对照当前市值', re.compile(r'(对照|按)当前市值')),
    ('市值除法', re.compile(r'市值\s*[/÷]|[/÷]\s*市值')),
    ('相当于N倍', re.compile(r'相当于\s*\d+(?:\.\d+)?\s*倍')),
    ('前瞻PE', re.compile(r'前瞻\s*PE|P/E')),
    ('N倍乘法', re.compile(r'[×x]\s*\d+(?:\.\d+)?\s*倍')),
]
SNIPPET_LEN = 120


def scan(text: str, old: str | None = None) -> list[tuple[int, list[str], str]]:
    rows = []
    for lineno, line in enumerate(text.splitlines(), 1):
        tags = [name for name, pat in DERIVED_PATTERNS if pat.search(line)]
        if old and old in line:
            tags.append('STALE-LITERAL')
        if tags:
            rows.append((lineno, tags, line.strip()[:SNIPPET_LEN]))
    return rows


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description='列出档内派生数句子供逐句手算（不算数、不裁定）',
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('doc', help='buffett 深度档路径')
    ap.add_argument('--old', help='旧价/旧市值字面量，命中即标 STALE-LITERAL')
    ap.add_argument('--new', help='新价/新市值，仅打印在表头供人工比对')
    args = ap.parse_args(argv)
    doc = Path(args.doc)
    if not doc.exists():
        ap.error(f'档不存在: {doc}')
    rows = scan(doc.read_text(encoding='utf-8'), args.old)
    if args.old or args.new:
        print(f'锚点刷新：{args.old or "?"} → {args.new or "?"}')
    for lineno, tags, snippet in rows:
        print(f'{lineno:>5} | {",".join(tags):<24} | {snippet}')
    print(f'合计 {len(rows)} 行待手算（本工具不算数，逐句核对派生关系）')
    return 0


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    sys.exit(main())
```

- [ ] **Step 4: 跑测试确认通过**

```bash
PYTHONIOENCODING=utf-8 rtk python -m pytest tests/test_deep_redo_anchor_audit.py -v
```

Expected: 5 passed

- [ ] **Step 5: 提交**

```bash
printf '%s\n' 'feat(scripts): deep_redo_anchor_audit.py 跨日锚点派生数审计' '' '雷赛轮跨 3 天中断，控制者做了 71 处字面量替换并 grep 自查干净，审查仍抓出' '4 处 Major、复核又自查出第 5 处——全部是用旧市值反推的派生数，句中不含旧锚' '字面量，grep 扫不到。本脚本按句式（反推/隐含/对照当前市值/相当于N倍/前瞻PE）' '列出待手算清单；它不算数，只保证逐句过一遍。退出码恒 0。' > .git/MSG-anchor-audit-20260822.txt
rtk git add scripts/deep_redo_anchor_audit.py tests/test_deep_redo_anchor_audit.py && rtk git commit -F .git/MSG-anchor-audit-20260822.txt
```

---

### Task 4: 脚本合回 main 并清理 worktree

**Files:**
- Modify: 无新改动，只做分支合并

**Interfaces:**
- Consumes: Task 1-3 的三个 commit
- Produces: `main` 上存在 `scripts/deep_redo_gate.py`、`scripts/deep_redo_anchor_audit.py` 及两个测试文件（Task 6 的 SKILL.md 要引用这两个路径并当场验证）

- [ ] **Step 1: 在 worktree 里跑一次两个测试文件的全量**

```bash
PYTHONIOENCODING=utf-8 rtk python -m pytest tests/test_deep_redo_gate.py tests/test_deep_redo_anchor_audit.py -v > /tmp_out.txt 2>&1; grep -E "passed|failed" /tmp_out.txt; rm -f /tmp_out.txt
```

Expected: `17 passed`
（**注意**：结果重定向到文件再 grep，别用 `| tail`——Windows bash 管道会静默吞 stdout，见 `.claude/rules/dev-environment.md`）

- [ ] **Step 2: 合回 main**

```bash
cd /d/Git/stock && rtk git merge --no-ff feat/deep-redo-gate -m "merge: stock-deep-redo 放行闸门与锚点审计脚本"
```

- [ ] **Step 3: 确认三个 commit 都在链上**

```bash
cd /d/Git/stock && rtk git log --oneline -5 && ls scripts/deep_redo_*.py tests/test_deep_redo_*.py
```

Expected: 四个文件都在；三个 feat commit 可见
（若怀疑脱链，用 `rtk git merge-base --is-ancestor <SHA> HEAD` 判定，别靠 `git log -N` 短列表——并行 session 的 commit 会交错插入）

- [ ] **Step 4: 在 main 上重跑测试确认合并没坏**

```bash
cd /d/Git/stock && PYTHONIOENCODING=utf-8 rtk python -m pytest tests/test_deep_redo_gate.py tests/test_deep_redo_anchor_audit.py > /tmp_out2.txt 2>&1; grep -E "passed|failed" /tmp_out2.txt; rm -f /tmp_out2.txt
```

Expected: `17 passed`

- [ ] **Step 5: 删 worktree 与分支**

```bash
cd /d/Git/stock && rtk git worktree remove ../stock-deepredo-gate && rtk git branch -d feat/deep-redo-gate
```

---

### Task 5: 建 `references/lessons.md` 案例库

**Files:**
- Create: `.claude/skills/stock-deep-redo/references/lessons.md`
- Read-only 源: `.claude/skills/stock-deep-redo/SKILL.md`（当前版 L193–352）、5 条待删 memory

**Interfaces:**
- Consumes: Task 1-3 产出的脚本名（写进各条的「机制」段）
- Produces: `L1`–`L15` 十五个 `## Ln <规则标题>` 标题 + 一个 `## 附录：分棒耗时明细` 节。**Task 6 的 SKILL.md 用 `[Ln]` 引用这些编号；Task 8 的 memory 用 `lessons.md L3/L6/L7` 引用。**

- [ ] **Step 1: 写文件头与格式约定**

创建 `.claude/skills/stock-deep-redo/references/lessons.md`，开头固定为：

```markdown
# stock-deep-redo 实测教训库

十三轮实跑沉淀的控制者教训。**SKILL.md 只保留规则句与 `[Ln]` 引用，案例原文在这里**——
控制者日常不必读本文件，只在闸门判据存疑、或复盘某一轮时按编号翻。

**格式**：每条三段式。
**编号规则**：`Ln` 一旦分配**永久不复用、不重排**（SKILL.md 与 memory 里都有 `[Ln]` 引用）。
新一轮有教训时**只追加**，不动既有编号。

| 编号 | 规则摘要 | 机制 |
|---|---|---|
| L1 | Phase A 放行看 evidence mtime 稳定，不看 report 是否存在 | `deep_redo_gate.py --quiet-min` |
| L2 | 校准消息在途 ≠ 已闭合；要么发完等回复，要么主动接受重叠 | 仅措辞 |
| L3 | 自报时间戳与自报善后动作均不可信，亲验对象永远是文件 | 仅措辞 |
| L4 | 跨路校准是常态非例外，Phase A 按「最慢路 + 1~2 轮校准」预估 | 仅措辞 |
| L5 | 控制者派发时给出的前提本身可能错，一律写成「待核实假设」且三路都给 | 仅措辞 |
| L6 | 会话中断杀掉全部 subagent；别把「到点再做」交给它；能亲自接棒就别等 | 仅措辞 |
| L7 | 静默失败须配探测点，else 分支也要发信号 | `deep_redo_gate.py` + `until` 包装 |
| L8 | 跨日价格锚刷新的盲区是二次计算而非字面量，派生句必须逐句手算 | `deep_redo_anchor_audit.py` |
| L9 | 「撞财报日」的代价取决于财报落在 Phase A 之前还是之中 | 仅措辞 |
| L10 | 财报盘后披露 + 次日盘前采证：市值分母整段留空、开盘后补锚 | `deep_redo_gate.py --phase B` 占位检查 |
| L11 | 「等收盘」是可选自费项，对财报日标的值得 | 仅措辞 |
| L12 | 附件型（.docx/.pdf）二值事实缺口由控制者亲自补证 | 仅措辞 |
| L13 | 亲验用精确锚点（tail + 关键词计数 + mtime + `end:`），别用模糊 grep | `deep_redo_gate.py` |
| L14 | Phase B 拆「主体 + 填锚」两段本身就是抗中断设计 | `deep_redo_gate.py --phase B` 占位检查 |
| L15 | 非权威路的数字须送 A1 逐条核定量级/科目/期间/主体四项 | 仅措辞 |
```

- [ ] **Step 2: 逐条搬运案例原文**

每条按此三段式写，**案例段是从源处整段搬运的原文，保留轮次日期与全部具体数字，不做概括**：

```markdown
## L1 Phase A 放行看 evidence mtime 稳定，不看 report 是否存在

**规则**：report 是一次性产物、evidence 是累积产物——校准轮只追加 evidence 不重写 report，
所以「report 已存在」对「这一路是否真的收工」没有判别力。收工判据是 evidence 文件 mtime
连续数分钟不变 + 比对行数。**别在任何一路仍可能被追加时放行 Phase B。**

**机制**：`python scripts/deep_redo_gate.py <股票名> <日期> --phase A --quiet-min 3`

**案例**：<搬运当前 SKILL.md「Phase A 的放行闸门要看 evidence 的 mtime 稳定性」整段原文>
```

搬运对照表（源行号以本任务开工时的 `SKILL.md` 为准，用小节标题定位更稳）：

| 条目 | 案例来源 |
|---|---|
| L1 | SKILL.md「**Phase A 的放行闸门要看 evidence 的 mtime 稳定性，不是 report 是否存在**」整段 |
| L2 | SKILL.md「**发出跨路校准后，不能只凭「它说收工了」就过汇合闸门**」整段 + memory `cross-lane-debate-converge-before-relay.md` 正文（含"不得转发未收敛的中间结论"四条 How to apply）|
| L3 | SKILL.md「收尾（控制者本人）」里「**先算耗时账**」段的自报失真部分 + playbook §9.0「⚠️ 自报时间戳不可信」段 + memory `subagent-message-contradicts-its-own-file.md` 的核心判断 |
| L4 | SKILL.md「**两轮校准把 A1 从约 13min 拉到 26.8min，但两轮都必要**」+「**控制者追加的跨路校准轮会打破 Phase A 的深度上限**」两段 |
| L5 | SKILL.md「**控制者派发时给出的「前提」本身可能是错的**」+「**光智轮是迄今最强的一次印证**」两段 |
| L6 | SKILL.md「**会话中断会杀掉全部 subagent，控制者必须能亲自接棒**」整段 |
| L7 | SKILL.md「**subagent 与后台任务都会静默失败，探测点必须覆盖失败路径**」整段（含那段 until 探测脚本）|
| L8 | SKILL.md「**跨日重启时，价格锚刷新的盲区是「二次计算」而非字面量**」整段（五处派生数逐条保留）|
| L9 | SKILL.md「**「撞财报日」的代价取决于财报落在 Phase A 之前还是之中**」+「**「撞财报发布当日」是目前观察到最贵的单一情形**」两段 |
| L10 | SKILL.md「**「财报盘后披露 + 次日盘前采证」是比海光轮更省的窗口**」整段 |
| L11 | SKILL.md「**「等收盘」是可选的自费项，但对财报日标的值得**」整段 |
| L12 | SKILL.md「**「二值事实缺口」应由控制者亲自补证**」整段 |
| L13 | SKILL.md「**控制者的亲验方法本身也会出错，锚点要精确**」整段 |
| L14 | SKILL.md「会话中断」段的后半「**Phase B 若被中断，续跑不必重派完整写手**」（与 L6 交叉引用，各留各的重点：L6 讲中断本身，L14 讲抗中断的拆棒设计）|
| L15 | memory `phasea-numbers-need-authority-lane-adjudication.md` 正文全文（SkyHigh 轮 10 倍量级+科目双错、两个法律主体的假冲突、四项核定）|

- [ ] **Step 3: 追加分棒耗时明细附录**

在文件末尾加：

```markdown
## 附录：分棒耗时明细

SKILL.md 的基线表只留合计列（用于派发时预估），逐棒明细在此备查。
```

其下搬运当前 SKILL.md 里「分棒（瑞联）」到「分棒（光迅）」共 8 行原文，一行不改。

- [ ] **Step 4: 校验编号与格式**

```bash
cd /d/Git/stock && grep -c "^## L" .claude/skills/stock-deep-redo/references/lessons.md
grep -n "^## L" .claude/skills/stock-deep-redo/references/lessons.md
PYTHONIOENCODING=utf-8 python -c "print(sum(1 for _ in open('.claude/skills/stock-deep-redo/references/lessons.md',encoding='utf-8')))"
```

Expected: 15 个 `## L` 标题、编号连续 L1–L15 无重复；行数打印成功（不关心具体值）

- [ ] **Step 5: 提交**

```bash
cd /d/Git/stock && printf '%s\n' 'docs(skill): stock-deep-redo 新增 lessons.md 教训案例库（L1-L15）' '' '十三轮实跑教训编号化：每条三段式（规则/机制/案例），案例保留原始轮次与数字。' '编号 Ln 永久不复用不重排——SKILL.md 与 memory 都靠它引用。' '分棒耗时明细 8 行移入附录，SKILL.md 基线表只留合计列。' > .git/MSG-lessons-20260822.txt
rtk git add .claude/skills/stock-deep-redo/references/lessons.md && rtk git commit -F .git/MSG-lessons-20260822.txt
```

---

### Task 6: 重写 SKILL.md 为编排手册

**Files:**
- Modify: `.claude/skills/stock-deep-redo/SKILL.md`（378 行 → ≤260 行，实际 247）

**Interfaces:**
- Consumes: Task 5 的 `L1`–`L15` 编号、Task 1-3 的两个脚本路径与命令行签名
- Produces: 一份 ≤260 行的编排手册（实际 247 行）。**Task 7 的 playbook §9.0 会引用它的「质量红线」节仍在原处这一事实；Task 9 的验收检查它的行数与 `[Ln]` 双向可解析。**

- [ ] **Step 1: 原样保留的部分**

以下五块**一字不改**，从旧文件原位搬运：
1. frontmatter（`---` 到 `---`，含 `name` 与 `description`）
2. 标题 + 开篇两段（「把一只股票的投资结论"重新承做一遍"…」「这个 skill 的价值不在"写得长"…」）
3. `## 何时用 / 何时不用`
4. `## 默认参数（烘进流程，不必每次问）` 全节（含表格与「只有这些情况才回头问用户」歧义门三条）
5. `## 质量红线（这套流程的灵魂，审查重点查这些）` 全节 8 条 —— **必须留在 SKILL.md 内**，因为 Phase B 与审查提示要从这里原文内联

- [ ] **Step 2: 重写编排主体为四段式**

`## 总编排` 到 `### 收尾（控制者本人）` 全部重写。每阶段固定四段：`做什么` / `必内联` / `放行闸门` / `预估`。

「先做（控制者本人）」保留原 5 条 + 避坑门，措辞不变，末尾加一行：

```markdown
6. **建 artifacts 目录**：`mkdir -p .omc/artifacts`（闸门脚本要求该目录存在，否则报 exit 2）。
```

Phase A 节写成：

```markdown
### Phase A — 联网采证（3 路并行，均 opus）

**做什么**：A1 数据锚 / A2 论点验证 / A3 lens 专项，三路各写各的 evidence 片段与 report，
**不派合并 agent**。文件名统一 `.omc/artifacts/<股票名>-<日期>-<后缀>`。

<原表格三行原样保留>

**必内联**（控制者摘原文进 prompt，不给路径让它自读，铁律见 playbook §9.1）：
- 三路深度上限各一条（A1 跑完必查清单即收 / A2 每论点取到能定性即止 / A3 逐条回应即可）
- 「A1 是所有硬数字唯一权威源」+ A2/A3 以定性表述为主、冲突以 A1 为准 [L15]
- 命中 lens 的【必查清单】原文（进 A3）
- 控制者的前置观察**一律写成「我的推断是 X，请核实 X 是否成立」，且三路都给** [L5]
- 证据分级（硬/软/缺）+ 不造数 + §9.0 汇报文件协议

**放行闸门**：

```bash
python scripts/deep_redo_gate.py <股票名> <日期> --phase A --quiet-min 3
```

exit 0 **且**所有在途校准项已收到「已闭合」回复 → 才派 Phase B [L1][L2]
exit 1 → 输出会指明哪一路缺什么 / 仍在写，不许提前放行
需要等待时包一层（超时分支也发信号，否则分不清 crashloop 与"还没好"）[L7]：

```bash
T=1800; E=0
until python scripts/deep_redo_gate.py <股票名> <日期> --phase A || [ $E -ge $T ]; do sleep 30; E=$((E+30)); done
[ $E -ge $T ] && echo "TIMEOUT ${E}s — 可能静默失败，控制者接管"
```

**预估**：按「最慢路 + 1~2 轮校准」，**不是三路取最大**——十三轮里跨路校准出现四次，是常态 [L4]。
A+H / 多业务线 / 多 lens 命中往上取。

**"相对旧档变化清单"不由三路写**（需全局视野）→ 移交 Phase B。
```

Phase B 节的放行闸门写成：

```bash
python scripts/deep_redo_gate.py <股票名> <日期> --phase B --doc <新档路径>
```

并说明：占位检查对应「主体 + 填锚」抗中断设计——主体先落盘，中断只损失填空那一小段 [L14]；
财报盘后披露 + 次日盘前采证时，市值分母整段留 `【待锚】`、开盘后补锚再过闸 [L10]。

审查节的放行闸门写成 `--phase review`，并在「必内联」里补两条（来自待删的两条 memory）：
- 「反向对称与 refs lint 归 Phase C、尚未运行，不必判为缺陷，但**可以**指出哪些兄弟档的 note 数字已被新档推翻」——否则每轮必收一个假 Critical
- 镜像同步类检查写成「**所有含数字的 frontmatter 字段**（valuation 块 + watch_reason/exclude_reason + thesis）都要与正文 §0/§9 逐个比对」，**别只点名 valuation**——审查范围严格等于清单措辞

Phase C 节：动作清单原样保留（删旧档 / 反向链改指 / 双 lint / valuations 同步 / quality 星级 / commodity 字段 / 提交铁律），只把段落压紧，不删任何一条动作。

- [ ] **Step 3: 压缩「收尾（控制者本人）」节**

保留三块：
1. 耗时账口径（以控制者侧派发/收回记录为准，自报仅作交叉参考 [L3]）与一行格式示例
2. 基线表**只留合计列**（13 行，标的/形态/返修/合计四列），**分棒明细不写**（在 lessons.md 附录）
3. 「读法」压成 5 条，逐条带 `[Ln]`：

```markdown
**读法**：
- 三路并行只在配深度上限时才省墙钟（无上限 12.8min 慢于单 agent 的 7min，加上限 6.0min）。
- **上限管住"每条查多深"，管不住"有多少条要查"**——派发前先粗数必查条数，别套用上一轮墙钟。
- Phase B 墙钟由**成稿长度**驱动、不由标的复杂度驱动，且不可并行（拆写手会断"论点→估值→评级"链）。
- 首建档比重做档少两块活（B 无需读旧档+写变化清单、C 无需删旧档+反向链改指），粗估 3-5min。
- **按 40-60min 预估**：十三轮中位数 56.6min、区间 32.3-86min。下限只在「单市场 + 首建档 +
  无跨路校准 + 无附件型缺口」齐备时出现；A+H 标的两轮都在中位数之上 [L9][L11][L12]。
```

末尾保留原有的 `git log --oneline` + `git status` 确认与「不主动 push」一句。

- [ ] **Step 4: 新增「维护规则」节**

在「质量红线」节之后、「参考文件」节之前插入（**这节是防回归的核心**）：

```markdown
## 维护规则（防止本文件长回编年体）

新一轮跑完有教训时：
1. **只在 `references/lessons.md` 追加 `Ln`**（编号顺延，永不复用、不重排），三段式写全。
2. 在本文件对应的闸门/预估处加一个 `[Ln]` 引用，**不写叙事**。
3. 基线表**只加一行**（合计列）；分棒明细写进 lessons.md 附录。
4. 若该教训能机械化，优先落成 `scripts/deep_redo_*.py` 的一个检查项，再在闸门段引用它——
   **措辞管不住的判据要变成命令**（L1/L7/L8 三条就是这么来的）。

本文件的目标是 **≤260 行**。超了先问一句：是不是又把某一轮的教训叙事写回正文了？是就搬去 lessons.md；不是（确属新增的操作步骤）就照实加，并在这里更新数字。
```

- [ ] **Step 5: 更新「参考文件」节**

加一行 lessons.md，并标注控制者与 subagent 的读法差异：

```markdown
- `references/lessons.md` — 十三轮实测教训案例库（L1–L15）+ 分棒耗时明细附录。
  **控制者按需按编号翻，不必通读；subagent 一律不读**（它们拿到的是控制者内联的具体指令）。
```

- [ ] **Step 6: 验行数与闸门命令可跑**

```bash
cd /d/Git/stock && PYTHONIOENCODING=utf-8 python -c "print(sum(1 for _ in open('.claude/skills/stock-deep-redo/SKILL.md',encoding='utf-8')))"
mkdir -p .omc/artifacts && python scripts/deep_redo_gate.py 测试股 2026-08-22 --phase A; echo "EXIT=$?"
```

Expected: 行数 ≤ 260；闸门命令打印三路 MISSING 且 `EXIT=1`（证明 SKILL.md 里写的命令真能跑，不是纸面命令）

- [ ] **Step 7: 提交**

```bash
cd /d/Git/stock && printf '%s\n' 'docs(skill): stock-deep-redo SKILL.md 重构为编排手册（378 -> 247 行）' '' '每阶段改四段式：做什么/必内联/放行闸门/预估，闸门给可执行命令而非措辞。' '150 行编年体教训移入 lessons.md，正文只留 [Ln] 引用。' '新增「维护规则」节防止本文件再长回编年体。' '并入两条原 memory 的审查提示（假 Critical 预声明、镜像同步写字段类别而非枚举）。' > .git/MSG-skillmd-20260822.txt
rtk git add .claude/skills/stock-deep-redo/SKILL.md && rtk git commit -F .git/MSG-skillmd-20260822.txt
```

---

### Task 7: playbook.md §9.0 去重

**Files:**
- Modify: `.claude/skills/stock-deep-redo/references/playbook.md`（§9.0 内「⚠️ 自报时间戳不可信」段）

**Interfaces:**
- Consumes: Task 5 的 `L3` 编号
- Produces: playbook §9.0 不再重复叙述紫金轮案例，改为一句引用

- [ ] **Step 1: 定位待改段**

```bash
cd /d/Git/stock && grep -n "自报时间戳不可信" .claude/skills/stock-deep-redo/references/playbook.md
```

Expected: 命中 §9.0 内一处

- [ ] **Step 2: 替换为引用**

把「**⚠️ 自报时间戳不可信**：2026-08-09 紫金实跑中……并在耗时账里注明该棒自报失真。」整段（约 6 行）替换为：

```markdown
**⚠️ 自报时间戳不可信**：`start`/`end` 头只作交叉参考，**耗时账一律以控制者侧记录的派发/收回
时刻为准**；两者相差超过 2 倍时在耗时账里注明该棒自报失真。案例见 `lessons.md` L3。
```

**保留不动**：同节的「**为什么顺带加固了可信度**」段与「**控制者侧**」段——那两段讲的是机制设计理由与操作要求，不是案例。

- [ ] **Step 3: 确认没误删汇报协议本体**

```bash
cd /d/Git/stock && grep -n "汇报**必须**用 Write\|阶段标识固定六种\|lessons.md L3" .claude/skills/stock-deep-redo/references/playbook.md
```

Expected: 三处都命中（协议本体在、引用已加）

- [ ] **Step 4: 提交**

```bash
cd /d/Git/stock && printf '%s\n' 'docs(skill): playbook §9.0 自报时间戳段去重，改引用 lessons.md L3' '' '紫金轮案例原文已在 lessons.md L3，playbook 只留一句判据与引用。' '汇报文件协议本体、机制设计理由、控制者侧操作要求均保留不动。' > .git/MSG-playbook-20260822.txt
rtk git add .claude/skills/stock-deep-redo/references/playbook.md && rtk git commit -F .git/MSG-playbook-20260822.txt
```

---

### Task 8: memory 去重

**Files:**
- Delete: `memory/cross-lane-debate-converge-before-relay.md`、`memory/phasea-numbers-need-authority-lane-adjudication.md`、`memory/review-before-phasec-false-critical.md`、`memory/review-scope-follows-checklist-wording.md`、`memory/subagent-report-needs-explicit-request.md`
- Modify: `memory/session-boundary-kills-subagents.md`、`memory/silent-failure-needs-probe.md`、`memory/subagent-message-contradicts-its-own-file.md`、`memory/MEMORY.md`

memory 根目录：`C:\Users\kaven\.claude\projects\D--Git-stock\memory\`（**不在 git 仓库内，无需 commit**）

**Interfaces:**
- Consumes: Task 5 的 lessons.md（L2/L3/L6/L7/L15 必须已写好，否则删 memory 会丢内容）、Task 6 的 SKILL.md 审查节（已并入两条 memory 的要点）
- Produces: memory 从 24 条降到 19 条，3 条保留项带 lessons.md 引用

- [ ] **Step 1: 删前核对内容确已落地**

```bash
cd /d/Git/stock && grep -c "SkyHigh\|21.42\|量级、科目、期间、主体" .claude/skills/stock-deep-redo/references/lessons.md
grep -c "未收敛的中间结论\|停手令" .claude/skills/stock-deep-redo/references/lessons.md
grep -c "反向对称与 refs lint 归 Phase C\|所有含数字的 frontmatter 字段" .claude/skills/stock-deep-redo/SKILL.md
```

Expected: 三条命令都 > 0。**任一为 0 就停下回 Task 5/6 补，不许先删**（CLAUDE.md 铁律：删除前看目标）。

- [ ] **Step 2: 删 5 条**

```bash
cd "C:/Users/kaven/.claude/projects/D--Git-stock/memory" && rm -f cross-lane-debate-converge-before-relay.md phasea-numbers-need-authority-lane-adjudication.md review-before-phasec-false-critical.md review-scope-follows-checklist-wording.md subagent-report-needs-explicit-request.md && ls | wc -l
```

Expected: 剩 19 个文件（含 MEMORY.md）

- [ ] **Step 3: 3 条保留项加 lessons 引用**

在各文件正文末尾追加一行（保持原有 frontmatter 与正文不动）：

| 文件 | 追加行 |
|---|---|
| `session-boundary-kills-subagents.md` | `本条在 stock-deep-redo 里的完整案例（天岳轮 60min 空档、B-2 填锚棒）见该 skill 的 references/lessons.md L6、L14。` |
| `silent-failure-needs-probe.md` | `本条在 stock-deep-redo 里的完整案例（光迅轮 64min 空转、until 探测模板）见该 skill 的 references/lessons.md L7；闸门已脚本化为 scripts/deep_redo_gate.py。` |
| `subagent-message-contradicts-its-own-file.md` | `本条在 stock-deep-redo 里的完整案例（自报时间戳失真、自报善后不可信）见该 skill 的 references/lessons.md L3。` |

同时把这三个文件正文里指向已删 memory 的 `[[...]]` 链接删掉（`[[subagent-report-needs-explicit-request]]` 等），避免死链。

- [ ] **Step 4: 同步 MEMORY.md 索引**

删掉「工作流约定」节里对应的 5 行（`cross-lane-debate-converge-before-relay` / `phasea-numbers-need-authority-lane-adjudication` / `review-before-phasec-false-critical` / `review-scope-follows-checklist-wording` / `subagent-report-needs-explicit-request`），并在该节末尾加一行：

```markdown
- stock-deep-redo 的十三轮实跑教训已编号化在该 skill 的 `references/lessons.md`（L1–L15），此处不再逐条索引
```

- [ ] **Step 5: 验证无死链**

```bash
cd "C:/Users/kaven/.claude/projects/D--Git-stock/memory" && grep -rn "cross-lane-debate\|phasea-numbers-need\|review-before-phasec\|review-scope-follows\|subagent-report-needs" . || echo "NO-DANGLING-REF"
```

Expected: `NO-DANGLING-REF`

---

### Task 9: 验收

**Files:**
- 只读检查，无修改（除非发现问题需回改）

**Interfaces:**
- Consumes: Task 1-8 全部产出
- Produces: 一份验收结论

- [ ] **Step 1: 行数与编号双向可解析**

用一次性脚本检查（**跑完必删，一次性脚本不入库**）。**用 Write 工具创建 `scripts/_check_lessons_refs.py`，不要用 heredoc**——Windows bash 下多行 python 的 heredoc 易 `EOF` 失配（见 `.claude/rules/dev-environment.md`）：

```python
import re
from pathlib import Path
skill = Path('.claude/skills/stock-deep-redo/SKILL.md').read_text(encoding='utf-8')
lessons = Path('.claude/skills/stock-deep-redo/references/lessons.md').read_text(encoding='utf-8')
defined = set(re.findall(r'^## (L\d+) ', lessons, re.M))
used = set(re.findall(r'\[(L\d+)\]', skill))
lines = sum(1 for _ in Path('.claude/skills/stock-deep-redo/SKILL.md').open(encoding='utf-8'))
print('SKILL.md 行数:', lines, '(<=260)' if lines <= 260 else '*** 超标 ***')
print('lessons 定义:', len(defined), sorted(defined, key=lambda s: int(s[1:])))
print('SKILL 引用:', sorted(used, key=lambda s: int(s[1:])))
print('引用了但未定义:', sorted(used - defined) or '无')
print('定义了但未被引用:', sorted(defined - used) or '无')
```

写好后跑，跑完立刻删：

```bash
cd /d/Git/stock && PYTHONIOENCODING=utf-8 python scripts/_check_lessons_refs.py; rm -f scripts/_check_lessons_refs.py
```

Expected: 行数 ≤ 260；「引用了但未定义」为「无」。
（「定义了但未被引用」允许非空——L11/L12 这类纯经验条目可能只在「读法」里合并引用，但需人工确认不是漏引）

- [ ] **Step 2: 两个脚本的全量测试**

```bash
cd /d/Git/stock && PYTHONIOENCODING=utf-8 rtk python -m pytest tests/test_deep_redo_gate.py tests/test_deep_redo_anchor_audit.py -v > /tmp_acc.txt 2>&1; grep -E "passed|failed" /tmp_acc.txt; rm -f /tmp_acc.txt
```

Expected: `17 passed`

- [ ] **Step 3: 全量回归（确认没碰坏别的）**

```bash
cd /d/Git/stock && PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/ -q > /tmp_full.txt 2>&1; grep -E "passed|failed|error" /tmp_full.txt | tail -3; rm -f /tmp_full.txt
```

Expected: 与本任务开工前基线一致，无新增 failed
（**结果重定向到文件再 grep**——crawl4ai 进度条走 stdout，`2>/dev/null | tail` 挡不住，会把 pytest 摘要顶出可见区）

- [ ] **Step 4: 锚点审计脚本在真档上冒烟**

```bash
cd /d/Git/stock && D=$(ls docs/stock-analytics/**/*buffett*.md 2>/dev/null | head -1); echo "档: $D"; PYTHONIOENCODING=utf-8 python scripts/deep_redo_anchor_audit.py "$D" | tail -5
```

Expected: 打印若干派生句 + `合计 N 行待手算`，退出码 0
（这是"在真实 buffett 档上确实能命中派生句"的证据，不是纸面正则）

- [ ] **Step 5: git 链确认**

```bash
cd /d/Git/stock && rtk git log --oneline -8 && rtk git status --short
```

Expected: 能看到 Task 1-3 的三个 feat、Task 4 的 merge、Task 5/6/7 的三个 docs；工作区干净（memory 不在仓库内故不出现）

- [ ] **Step 6: 汇报验收结论**

按此格式向用户汇报：

```
SKILL.md 378 → N 行（目标 ≤260）
lessons.md L1–L15 + 分棒附录，SKILL 引用 M 处全部可解析
脚本 17 passed；全量 pytest 无新增 failed
memory 24 → 19 条，3 条加 lessons 引用，无死链
commit: <三个 feat SHA> / <merge SHA> / <三个 docs SHA>
```

---

## Self-Review

**Spec 覆盖核对**：spec 八节 → 计划任务映射
- §一 文件结构 → File Structure 表（8 个文件全覆盖）
- §二 SKILL.md 新骨架 → Task 6（四段式、收尾压缩、维护规则、参考文件）
- §三 lessons.md 归档规则 → Task 5（三段式、L1–L15 表、搬运对照表、附录）
- §四 脚本接口 → Task 1（phase A）、Task 2（phase B/review）、Task 3（anchor audit），退出码与 `until` 模板均落到实处
- §五 memory 处置 → Task 8（删 5 / 改 3 / MEMORY.md 索引）
- §六 测试与验证 → Task 1-3 的 TDD 步骤 + Task 9（行数、双向引用、全量回归、真档冒烟）
- §七 提交计划 → Task 1-3 在 worktree、Task 4 合并、Task 5-7 在 main；`.git/MSG-<后缀>.txt` 同链提交贯穿
- §八 验收标准 → Task 9 六步逐条对应

**无遗漏**：spec 提到的「playbook §9.0 微调」独立成 Task 7（spec 只在文件结构表里带过一句，此处补成完整任务）。

**类型一致性**：`main(argv)` 在三处测试中签名一致；`check_phase_a/b/review` 返回类型统一为 `list[str]`；`scan()` 返回 `list[tuple[int, list[str], str]]` 与测试解包一致；`_check_report(path, tag)` 在 Task 1 定义、Task 2 复用，参数顺序一致。
