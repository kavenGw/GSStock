"""BuffettAnalysisService 索引与渲染测试"""
from pathlib import Path

import pytest

from app.services.buffett_analysis import BuffettAnalysisService


@pytest.fixture
def analysis_dir(tmp_path: Path) -> Path:
    d = tmp_path / 'analysis'
    d.mkdir()
    return d


def _write(dir: Path, name: str, body: str = '# Title\n\ncontent') -> Path:
    p = dir / name
    p.write_text(body, encoding='utf-8')
    return p


def test_build_index_matches_chinese_names(analysis_dir):
    _write(analysis_dir, '2026-04-21-兆易创新-buffett分析.md')
    _write(analysis_dir, '2026-04-22-青岛啤酒-buffett分析.md')
    _write(analysis_dir, '2026-04-23-彤程新材-buffett分析.md')

    index = BuffettAnalysisService.build_index(analysis_dir)

    assert set(index.keys()) == {'兆易创新', '青岛啤酒', '彤程新材'}


def test_build_index_picks_latest_when_duplicate_names(analysis_dir):
    _write(analysis_dir, '2026-04-21-兆易创新-buffett分析.md', body='OLD')
    latest = _write(analysis_dir, '2026-04-25-兆易创新-buffett分析.md', body='NEW')

    index = BuffettAnalysisService.build_index(analysis_dir)

    assert index['兆易创新'] == latest


def test_build_index_ignores_unrelated_files(analysis_dir):
    _write(analysis_dir, 'README.md')
    _write(analysis_dir, '2026-04-21-something-else.md')
    _write(analysis_dir, '2026-04-21-真公司-buffett分析.md')

    index = BuffettAnalysisService.build_index(analysis_dir)

    assert list(index.keys()) == ['真公司']


def test_get_html_returns_rendered_markdown(analysis_dir):
    _write(
        analysis_dir,
        '2026-04-25-测试公司-buffett分析.md',
        body='# 标题\n\n| a | b |\n|---|---|\n| 1 | 2 |\n',
    )

    result = BuffettAnalysisService.get_html('测试公司', base_dir=analysis_dir)

    assert result is not None
    assert result['title'] == '测试公司'
    assert '<h1' in result['html'] and '标题</h1>' in result['html']
    assert '<table>' in result['html']
    assert 'source' in result and result['source'].endswith('-buffett分析.md')


def test_get_html_returns_none_when_missing(analysis_dir):
    assert BuffettAnalysisService.get_html('不存在', base_dir=analysis_dir) is None


def test_build_index_returns_empty_for_missing_dir(tmp_path):
    assert BuffettAnalysisService.build_index(tmp_path / 'nope') == {}
