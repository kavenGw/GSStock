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
    a_before = a_text
    code2, _ = run_refs(tmp_path, '--rewrite-blocks')
    assert code2 == 0
    assert a.read_text(encoding='utf-8') == a_before
