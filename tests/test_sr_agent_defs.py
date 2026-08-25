"""六份 sr-* agent 定义的 frontmatter 契约。

它们承载了原本每轮重写进 prompt 的约 15KB 固定内容；字段写错会静默退化成
默认 model/effort（没有报错），因此必须有断言守着。
"""
import re
from pathlib import Path

import pytest

AGENTS_DIR = Path(__file__).resolve().parent.parent / '.claude' / 'agents'

EXPECTED = {
    'sr-a1-anchor': {'model': 'opus', 'effort': 'high'},
    'sr-a2-thesis': {'model': 'opus', 'effort': 'medium'},
    'sr-a3-lens': {'model': 'opus', 'effort': 'medium'},
    'sr-writer': {'model': 'opus', 'effort': 'high'},
    'sr-reviewer': {'model': 'sonnet', 'effort': 'high'},
    'sr-finalize': {'model': 'sonnet', 'effort': 'low'},
}

VALID_MODELS = {'opus', 'sonnet', 'haiku', 'fable'}
VALID_EFFORTS = {'low', 'medium', 'high', 'xhigh', 'max'}


def _frontmatter(path: Path) -> dict:
    text = path.read_text(encoding='utf-8')
    m = re.match(r'^---\n(.*?)\n---\n', text, re.S)
    assert m, f'{path.name} 缺 frontmatter'
    out = {}
    for line in m.group(1).split('\n'):
        if ':' in line and not line.startswith((' ', '-')):
            k, _, v = line.partition(':')
            out[k.strip()] = v.strip()
    return out


@pytest.mark.parametrize('name', sorted(EXPECTED))
def test_agent_def_exists_and_fields_valid(name):
    path = AGENTS_DIR / f'{name}.md'
    assert path.exists(), f'缺 {path}'
    fm = _frontmatter(path)
    assert fm['name'] == name
    assert fm['model'] == EXPECTED[name]['model']
    assert fm['effort'] == EXPECTED[name]['effort']
    assert fm['model'] in VALID_MODELS
    assert fm['effort'] in VALID_EFFORTS


@pytest.mark.parametrize('name', sorted(EXPECTED))
def test_description_declares_dispatch_only(name):
    """agent 定义会进全局列表，必须声明只由 stock-research 派发，防误触发。"""
    fm = _frontmatter(AGENTS_DIR / f'{name}.md')
    assert 'stock-research' in fm['description']
    assert '勿直接调用' in fm['description']


def test_writer_and_reviewer_prebind_doc_spec():
    """写手/审查员预绑 buffett-doc-spec，省掉每轮 prompt 里叮嘱 Skill 加载。"""
    for name in ('sr-writer', 'sr-reviewer'):
        fm = _frontmatter(AGENTS_DIR / f'{name}.md')
        assert 'buffett-doc-spec' in fm.get('skills', '')


def test_a1_body_requires_quote_guard_and_backtest():
    """A1 的两条防返工要求必须写死在定义里，不依赖控制者每轮记得叮嘱。"""
    body = (AGENTS_DIR / 'sr-a1-anchor.md').read_text(encoding='utf-8')
    assert 'quote_guard' in body
    assert '上年同期' in body
