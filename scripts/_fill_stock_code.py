"""补 quarterly/ 文件缺失的 stock_code。一次性，Stage 5 删除。"""
from __future__ import annotations
import re
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts._docs_schema import parse_frontmatter

ROOT = Path(__file__).resolve().parent.parent
STOCK = ROOT / 'docs' / 'stock-analytics'

# stock_name -> stock_code（A 股 6 位 + 美股 ticker）
SUPPLEMENTAL_CODES = {
    '长电科技': '600584',
    '雅克科技': '002409',
    '东吴证券': '601555',
    '华天科技': '002185',
    '胜宏科技': '300476',
    '通富微电': '002156',
    '深科技': '000021',
    '沪电股份': '002463',
    '盛合晶微': '688361',
    '南亚新材': '688519',
    '生益科技': '600183',
    '金安国纪': '002636',
    '立讯精密': '002475',
    '中微公司': '688012',
    '华虹半导体': '688347',
}


def _yaml_dump(fm: dict) -> str:
    order = ['doc_type', 'stock_code', 'stock_codes', 'stock_name', 'stock_names',
             'sector', 'subsector', 'period', 'date', 'conviction_date',
             'themes', 'theme_name', 'related_codes',
             'rating', 'thesis', 'watch_reason', 'exclude_reason',
             'data_source', 'tags', 'related_docs']
    ordered = {k: fm[k] for k in order if k in fm}
    for k, v in fm.items():
        if k not in ordered:
            ordered[k] = v
    return yaml.safe_dump(ordered, allow_unicode=True, sort_keys=False, default_flow_style=False, width=200)


def main():
    filled = 0
    for p in sorted((STOCK / 'quarterly').rglob('*.md')):
        fm, body = parse_frontmatter(p)
        if fm.get('stock_code'):
            continue
        name = fm.get('stock_name')
        code = SUPPLEMENTAL_CODES.get(name)
        if not code:
            print(f"STILL MISS: {p.relative_to(ROOT)} ({name})")
            continue
        fm['stock_code'] = code
        new_text = f"---\n{_yaml_dump(fm)}---\n{body}"
        p.write_text(new_text, encoding='utf-8')
        filled += 1
        print(f"filled {p.relative_to(ROOT)} -> {code}")
    print(f"\nFilled {filled} files")


if __name__ == '__main__':
    main()
