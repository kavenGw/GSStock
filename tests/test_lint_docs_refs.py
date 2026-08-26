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


def test_refs_rewrite_blocks_renders_impact_tag(tmp_path):
    a = tmp_path / 'sectors' / 'semiconductor' / 'storage' / 'a.md'
    t = tmp_path / 'themes' / 't.md'
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
      - path: ../../../themes/t.md
        note: 供给侧口径确认
        impact: 动摇
        magnitude: 中
    ---
    # X
    """)
    _write(t, """\
    ---
    doc_type: theme
    theme_name: T
    themes: [t]
    date: 2026-08-22
    related_docs:
      - path: ../sectors/semiconductor/storage/a.md
        note: 回链
    ---
    # T
    """)
    code, out = run_refs(tmp_path, '--rewrite-blocks')
    assert code == 0, out
    assert '> - [t](../../../themes/t.md)【动摇·中】 — 供给侧口径确认' in a.read_text(encoding='utf-8')


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


# --- --only 作用域（多 session 并行时避开他人在写档造成的互锁）---

def _asymmetric_pair(root: Path, name: str):
    """造一份自身违规（asymmetric ref 指向 dangling）的独立档，用作「别人的在写档」。"""
    _write(root / 'sectors' / 'other' / f'{name}.md', f"""    ---
    doc_type: buffett
    stock_code: '900{len(name)}00'
    stock_name: {name}
    sector: other
    subsector: misc
    themes: [t]
    rating: watch
    conviction_date: 2026-01-01
    thesis: t
    related_docs:
      - path: ../../quarterly/26q1/b.md
        note: 单向未回链
    ---
    """)


def _clean_pair(root: Path):
    """造一对对称、自身零违规的档（模拟「本任务的档」）。"""
    _write(root / 'sectors' / 'mine' / 'x.md', """    ---
    doc_type: buffett
    stock_code: '600001'
    stock_name: X
    sector: mine
    subsector: sub
    themes: [t]
    rating: watch
    conviction_date: 2026-01-01
    thesis: t
    related_docs:
      - path: ../mine/y.md
        note: 双向
    ---
    # X
    """)
    _write(root / 'sectors' / 'mine' / 'y.md', """    ---
    doc_type: buffett
    stock_code: '600002'
    stock_name: Y
    sector: mine
    subsector: sub
    themes: [t]
    rating: watch
    conviction_date: 2026-01-01
    thesis: t
    related_docs:
      - path: ../mine/x.md
        note: 双向
    ---
    # Y
    """)


def test_only_ignores_out_of_scope_violations(tmp_path):
    """本任务的档零违规时，别人在写档的违规不得阻断本任务。"""
    _clean_pair(tmp_path)
    _asymmetric_pair(tmp_path, 'theirs')
    code, out = run_refs(tmp_path)
    assert code == 1, '前提：不加 --only 时应因他人违规而 FAIL'

    code, out = run_refs(tmp_path, '--only', str(tmp_path / 'sectors' / 'mine'))
    assert code == 0, out
    assert 'outside scope' in out


def test_only_still_blocks_in_scope_violations(tmp_path):
    """作用域内的违规必须照常阻断——--only 是收窄范围，不是放水。"""
    _clean_pair(tmp_path)
    _asymmetric_pair(tmp_path, 'theirs')
    code, out = run_refs(tmp_path, '--only', str(tmp_path / 'sectors' / 'other'))
    assert code == 1
    assert 'theirs.md' in out, '被阻断的应当正是作用域内那份档'
    assert 'FAIL: 1 violation(s)' in out, '只应报作用域内的 1 条，而非全仓所有违规'
    assert 'outside scope' not in out, '此处无作用域外违规可忽略'


def test_only_matching_nothing_is_an_error(tmp_path):
    """路径打错时必须报错退出，不能静默当成「零违规」放行。"""
    _clean_pair(tmp_path)
    code, out = run_refs(tmp_path, '--only', str(tmp_path / 'sectors' / '不存在'))
    assert code == 2
    assert 'matched 0 docs' in out


def test_only_scopes_rewrite_blocks(tmp_path):
    """--rewrite-blocks 只重写作用域内的文件，作用域外一个字节都不动。"""
    _clean_pair(tmp_path)
    _asymmetric_pair(tmp_path, 'theirs')
    theirs = tmp_path / 'sectors' / 'other' / 'theirs.md'
    before = theirs.read_text(encoding='utf-8')

    code, out = run_refs(tmp_path, '--rewrite-blocks',
                         '--only', str(tmp_path / 'sectors' / 'mine'))
    assert code == 0, out
    assert theirs.read_text(encoding='utf-8') == before, '作用域外文件被改动'
    assert 'BEGIN related_docs' in (tmp_path / 'sectors' / 'mine' / 'x.md').read_text(encoding='utf-8')


def test_no_only_behaviour_is_unchanged(tmp_path):
    """不传 --only 时行为与改动前完全一致：全仓判定、全仓重写。"""
    _clean_pair(tmp_path)
    code, out = run_refs(tmp_path, '--rewrite-blocks')
    assert code == 0, out
    assert 'outside scope' not in out
    assert 'Rewrote' in out
