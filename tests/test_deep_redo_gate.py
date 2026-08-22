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
                  evidence_lines=30, report_body=None):
    """在 tmp_path 造一套 Phase A 产物，返回 artifacts 目录。"""
    art = tmp_path / 'artifacts'
    art.mkdir(exist_ok=True)
    suffix = {'A1': '数据锚', 'A2': '论点', 'A3': 'lens'}
    for lane in lanes:
        _write(art / f'{STOCK}-{DATE}-evidence-{lane}-{suffix[lane]}.md',
               _evidence_body(evidence_lines), age_min)
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
