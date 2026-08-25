"""lens 拆分的内容守恒与结构完整性。

拆分的目的不是省 token，而是让「subagent 自读会挑错节」的前提消失：
原 sector-lenses.md 261 行是大杂烩（实测单轮只命中约 70 行），拆成精确粒度
后自读不可能挑错节，于是控制者不必再摘原文内联（内联铁律降级为混合口径）。
"""
from pathlib import Path

import pytest

LENSES = Path(__file__).resolve().parent.parent / '.claude' / 'skills' / \
    'stock-research' / 'references' / 'lenses'

CROSS_CUTTING = ('x-ai.md', 'x-growth.md', 'x-dividend-value.md')
SECTOR_SPECIFIC = ('pcb-ccl.md', 'storage-dram-nand.md',
                   'storage-nor-flash.md', 'metals-copper.md')
ALL_LENSES = CROSS_CUTTING + SECTOR_SPECIFIC

REQUIRED_SECTIONS = ('【识别信号】', '【必查清单（采证 face）】',
                     '【撰写落点（撰写 face）】', '【双面必答】', '【监控指标模板】')


@pytest.mark.parametrize('name', ALL_LENSES)
def test_lens_file_exists(name):
    assert (LENSES / name).exists(), f'缺 {name}'


@pytest.mark.parametrize('name', ALL_LENSES)
def test_lens_has_all_required_sections(name):
    """每份 lens 必须自包含四节，否则自读的 agent 会拿到残缺清单。"""
    text = (LENSES / name).read_text(encoding='utf-8')
    for sec in REQUIRED_SECTIONS:
        assert sec in text, f'{name} 缺 {sec}'


def test_old_monolith_removed():
    """旧大杂烩必须删除，否则控制者会去读一个已废弃的文件。"""
    old = LENSES.parent / 'sector-lenses.md'
    assert not old.exists(), '拆分后 sector-lenses.md 必须删除'


def test_cross_cutting_prefix_convention():
    """x- 前缀是 sr-a3-lens 判断「是否默认加载」的依据，不能乱改。"""
    for name in CROSS_CUTTING:
        assert name.startswith('x-')
    for name in SECTOR_SPECIFIC:
        assert not name.startswith('x-')


def test_readme_carries_maintenance_rules():
    """拆分前的头部说明含一条维护铁律（不写死会过时的事实），拆分后必须有归宿，
    否则 lens 迟早退化成过时报价的仓库。"""
    text = (LENSES / 'README.md').read_text(encoding='utf-8')
    assert '绝不写死会过时的事实' in text
    assert '可叠加多选' in text
    assert '五段式' in text or '【识别信号】' in text
