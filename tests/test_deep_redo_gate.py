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


def test_phase_a_lanes_a1_only(tmp_path, capsys):
    """模式 2（财报）只派 A1：--lanes A1 时 A2/A3 缺失不算问题。"""
    art = _make_phase_a(tmp_path, lanes=('A1',))
    rc = main([STOCK, DATE, '--phase', 'A', '--lanes', 'A1', '--artifacts', str(art)])
    assert rc == 0, capsys.readouterr().out
    rc = main([STOCK, DATE, '--phase', 'A', '--artifacts', str(art)])
    assert rc == 1
    out = capsys.readouterr().out
    assert 'A2 MISSING' in out and 'A3 MISSING' in out


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


def test_phase_a_stale_but_green_still_ready(tmp_path, capsys):
    """evidence mtime 很旧但其余全绿：不能因「沉默」就判失败（L7），只提示核实。"""
    art = _make_phase_a(tmp_path, age_min=30.0)
    rc = main([STOCK, DATE, '--phase', 'A', '--quiet-min', '3', '--artifacts', str(art)])
    out = capsys.readouterr().out
    assert rc == 0
    assert 'A READY' in out
    assert 'NOTE' in out and '卡住' in out


def _make_folder(tmp_path: Path, names=('business', 'thesis', 'valuation', 'sources')) -> Path:
    d = tmp_path / STOCK
    d.mkdir()
    _write(d / 'index.md', DOC_FRONTMATTER)
    for n in names:
        _write(d / f'{n}.md', f'---\ndoc_type: buffett-section\nsection: {n}\n---\n# x\n正文')
    _write(d / 'events.md', '---\ndoc_type: buffett-events\nrelated_docs: []\n---\n# 事件\n')
    _write(d / 'related.md', '---\ndoc_type: buffett-related\nrelated_docs: []\n---\n# 关联文档\n')
    return d


def test_phase_b_folder_doc(tmp_path, capsys):
    art, _ = _make_phase_b(tmp_path)
    d = _make_folder(tmp_path)
    rc = main([STOCK, DATE, '--phase', 'B', '--doc', str(d), '--artifacts', str(art)])
    assert rc == 0 and 'B READY' in capsys.readouterr().out


def test_phase_b_folder_missing_file_and_placeholder(tmp_path, capsys):
    art, _ = _make_phase_b(tmp_path)
    d = _make_folder(tmp_path, names=('thesis',))
    _write(d / 'thesis.md', '---\ndoc_type: buffett-section\nsection: thesis\n---\n# x\n市值【待锚】')
    rc = main([STOCK, DATE, '--phase', 'B', '--doc', str(d), '--artifacts', str(art)])
    out = capsys.readouterr().out
    assert rc == 1
    assert 'business.md' in out and 'sources.md' in out
    assert 'thesis.md 1 处' in out


def test_phase_b_folder_missing_related(tmp_path, capsys):
    art, _ = _make_phase_b(tmp_path)
    d = _make_folder(tmp_path)
    (d / 'related.md').unlink()
    rc = main([STOCK, DATE, '--phase', 'B', '--doc', str(d), '--artifacts', str(art)])
    out = capsys.readouterr().out
    assert rc == 1
    assert 'related.md' in out


# ---------- 合并格式（evidence + report 单文件）----------

def _merged_body(lines: int = 30, *, with_end: bool = True,
                 with_conclusion: bool = True) -> str:
    parts = ['start: 2026-08-22 08:30:00', '', '## 明细层', '']
    parts += [f'- 证据行 {i}：https://example.com/{i} （2026-08-22）' for i in range(lines)]
    if with_conclusion:
        parts += ['', '## 结论层', '', '对账：证实 3 / 证伪 1 / 无信息 2。']
    if with_end:
        parts += ['', 'end: 2026-08-22 08:52:00']
    return '\n'.join(parts) + '\n'


def _make_merged_a(tmp_path: Path, *, lanes=('A1', 'A2', 'A3'), age_min=5.0, **kw):
    art = tmp_path / 'artifacts'
    art.mkdir(exist_ok=True)
    for lane in lanes:
        _write(art / f'{STOCK}-{DATE}-{lane}.md', _merged_body(**kw), age_min)
    return art


def test_merged_phase_a_all_green(tmp_path, capsys):
    art = _make_merged_a(tmp_path)
    rc = main([STOCK, DATE, '--phase', 'A', '--artifacts', str(art)])
    assert rc == 0, capsys.readouterr().out
    assert 'A READY' in capsys.readouterr().out


def test_merged_missing_end_stamp(tmp_path, capsys):
    """end: 戳写在文件最末，它的存在即「全文写完」——这是合并格式的核心判据。"""
    art = _make_merged_a(tmp_path, with_end=False)
    rc = main([STOCK, DATE, '--phase', 'A', '--artifacts', str(art)])
    out = capsys.readouterr().out
    assert rc == 1
    assert 'end:' in out


def test_merged_missing_conclusion_section(tmp_path, capsys):
    """只有明细层没有结论层 = 采证完了但没做对账，不许放行。"""
    art = _make_merged_a(tmp_path, with_conclusion=False, with_end=False)
    rc = main([STOCK, DATE, '--phase', 'A', '--artifacts', str(art)])
    out = capsys.readouterr().out
    assert rc == 1
    assert '结论层' in out


def test_merged_no_end_and_stale_reports_died_before_delivery(tmp_path, capsys):
    """明细层有内容、无 end 戳、且很久没动 = 大概率死在交付前（L22）。"""
    art = _make_merged_a(tmp_path, with_end=False, age_min=30.0)
    rc = main([STOCK, DATE, '--phase', 'A', '--stale-min', '20',
               '--artifacts', str(art)])
    out = capsys.readouterr().out
    assert rc == 1
    assert '死在交付前' in out


def test_merged_format_takes_precedence_over_legacy(tmp_path, capsys):
    """两种格式同时存在时以合并格式为准，避免读到上一轮的残留旧文件。"""
    art = _make_phase_a(tmp_path)                      # 旧格式，全绿
    _write(art / f'{STOCK}-{DATE}-A1.md',
           _merged_body(with_end=False), 5.0)          # 新格式 A1 未完成
    rc = main([STOCK, DATE, '--phase', 'A', '--artifacts', str(art)])
    out = capsys.readouterr().out
    assert rc == 1
    assert 'A1' in out and 'end:' in out


def test_default_quiet_min_is_half_minute(tmp_path, capsys):
    """合并后 end 戳是主判据，mtime 只作保险 —— 默认从 3.0 降到 0.5。"""
    from scripts.deep_redo_gate import build_parser
    assert build_parser().parse_args([STOCK, DATE, '--phase', 'A']).quiet_min == 0.5


def test_merged_phase_b_and_review(tmp_path, capsys):
    art = tmp_path / 'artifacts'
    art.mkdir()
    _write(art / f'{STOCK}-{DATE}-B.md', _merged_body(), 5.0)
    d = _make_folder(tmp_path)
    rc = main([STOCK, DATE, '--phase', 'B', '--doc', str(d), '--artifacts', str(art)])
    assert rc == 0, capsys.readouterr().out

    body = _merged_body().replace(
        '对账：证实 3 / 证伪 1 / 无信息 2。',
        'SPEC-COMPLIANT\n\nAPPROVED-WITH-NITS')
    _write(art / f'{STOCK}-{DATE}-review.md', body, 1.0)
    rc = main([STOCK, DATE, '--phase', 'review', '--artifacts', str(art)])
    assert rc == 0, capsys.readouterr().out
