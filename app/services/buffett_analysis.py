"""巴菲特分析文件索引与渲染

递归扫描 docs/stock-analytics/sectors/ 下的 `YYYY-MM-DD-{股票名称}-buffett分析.md` 平铺档
与 `{股票名称}/index.md` 文件夹档，按股票名称索引；同名多份取日期最新，文件夹档优先。仅提供只读读取与 markdown 渲染。
"""
from __future__ import annotations

import re
from pathlib import Path

import markdown

from scripts._docs_schema import _as_str_date, parse_frontmatter

ANALYSIS_DIR = Path('docs/stock-analytics/sectors')
FILENAME_RE = re.compile(r'^(\d{4}-\d{2}-\d{2})-(.+?)-buffett分析\.md$')


class BuffettAnalysisService:

    @classmethod
    def build_index(cls, base_dir: Path | None = None) -> dict[str, Path]:
        directory = base_dir or ANALYSIS_DIR
        if not directory.exists():
            return {}

        latest: dict[str, tuple[str, Path]] = {}
        for path in directory.rglob('*.md'):
            if not path.is_file():
                continue
            if path.name == 'index.md':
                fm, _ = parse_frontmatter(path)
                if fm.get('doc_type') != 'buffett':
                    continue
                name = path.parent.name
                date_str = _as_str_date(fm.get('conviction_date')) or '9999-99-99'
            else:
                m = FILENAME_RE.match(path.name)
                if not m:
                    continue
                date_str, name = m.group(1), m.group(2)
            prev = latest.get(name)
            if prev is None or date_str > prev[0] or path.name == 'index.md':
                latest[name] = (date_str, path)

        return {name: pair[1] for name, pair in latest.items()}

    @classmethod
    def get_html(cls, stock_name: str, base_dir: Path | None = None) -> dict | None:
        index = cls.build_index(base_dir)
        path = index.get(stock_name)
        if path is None:
            return None

        text = path.read_text(encoding='utf-8')
        html = markdown.markdown(
            text,
            extensions=['tables', 'fenced_code', 'toc', 'sane_lists'],
            output_format='html5',
        )
        return {
            'html': html,
            'title': stock_name,
            'source': str(path).replace('\\', '/'),
        }
