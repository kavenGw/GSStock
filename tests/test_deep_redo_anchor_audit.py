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
