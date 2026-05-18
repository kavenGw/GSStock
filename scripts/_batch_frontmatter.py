"""批量补 frontmatter：处理 buffett (sectors/) 和 quarterly (quarterly/)。
对 buffett：从路径反推 sector/subsector，stock_code 转 str。
对 quarterly：从 0 构建 YAML（stock_code 从同名 buffett 反查 + SECTOR_MAPPING）。
一次性，Stage 5 删除。
"""
from __future__ import annotations
import re
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts._docs_schema import parse_frontmatter
from scripts._migration_mapping import SECTOR_MAPPING

ROOT = Path(__file__).resolve().parent.parent
STOCK = ROOT / 'docs' / 'stock-analytics'

_NAME_RE = re.compile(r'^(\d{4}-\d{2}-\d{2})-(.+?)\.md$')


def _stock_code_lookup() -> dict[str, str]:
    """{stock_name: stock_code} 从已有 sectors/ buffett 文档 frontmatter 抽取"""
    out: dict[str, str] = {}
    for p in (STOCK / 'sectors').rglob('*.md'):
        if p.name == 'README.md':
            continue
        fm, _ = parse_frontmatter(p)
        name = fm.get('stock_name')
        code = fm.get('stock_code')
        if name and code:
            out[str(name)] = str(code)
    return out


def _yaml_dump(fm: dict) -> str:
    """生成 YAML 头，保持字段顺序"""
    # 字段顺序：doc_type, stock_code(s), stock_name(s), sector, subsector, themes, ...
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


def _process_buffett(path: Path) -> bool:
    """sectors/<sector>/<subsector>/...md：补 sector/subsector + 修 stock_code 类型"""
    fm, body = parse_frontmatter(path)
    if not fm:
        print(f"WARN: buffett no YAML: {path}")
        return False

    parts = path.relative_to(STOCK).parts
    if len(parts) < 4 or parts[0] != 'sectors':
        print(f"WARN: not in sectors/<sector>/<subsector>/: {path}")
        return False
    sector, subsector = parts[1], parts[2]

    changed = False
    if fm.get('doc_type') != 'buffett':
        fm['doc_type'] = 'buffett'
        changed = True
    if fm.get('sector') != sector:
        fm['sector'] = sector
        changed = True
    if fm.get('subsector') != subsector:
        fm['subsector'] = subsector
        changed = True
    if 'stock_code' in fm and not isinstance(fm['stock_code'], str):
        fm['stock_code'] = str(fm['stock_code']).zfill(6)
        changed = True
    if 'related_docs' not in fm:
        fm['related_docs'] = []
        changed = True

    if changed:
        new_text = f"---\n{_yaml_dump(fm)}---\n{body}"
        path.write_text(new_text, encoding='utf-8')
    return changed


def _process_quarterly(path: Path, code_lookup: dict[str, str]) -> bool:
    """quarterly/<NNqN>/...md：从 0 构建 YAML"""
    fm, body = parse_frontmatter(path)
    if fm.get('doc_type'):
        return False  # 已有

    m = _NAME_RE.match(path.name)
    if not m:
        print(f"WARN: bad filename: {path}")
        return False
    date_str, stem = m.group(1), m.group(2)

    # 第一段股票名 + 后续作为类型描述
    parts_stem = stem.split('-', 1)
    stock_name = parts_stem[0]
    doc_kind = parts_stem[1] if len(parts_stem) > 1 else ''

    sector_info = SECTOR_MAPPING.get(stock_name)
    if not sector_info:
        print(f"WARN: '{stock_name}' not in SECTOR_MAPPING ({path.name})")
        return False
    sector, subsector = sector_info

    stock_code = code_lookup.get(stock_name, '')

    period = path.parent.name  # e.g. '26q1'

    new_fm: dict = {
        'doc_type': 'quarterly',
        'stock_code': stock_code,
        'stock_name': stock_name,
        'sector': sector,
        'subsector': subsector,
        'period': period,
        'date': date_str,
    }
    # tag 标记非纯季报点评（单股专题）
    if '专题' in doc_kind or '行情验证' in doc_kind or '业绩说明会' in doc_kind:
        new_fm['tags'] = [doc_kind.replace('专题', '').strip() or 'special-topic']
    new_fm['related_docs'] = []

    new_text = f"---\n{_yaml_dump(new_fm)}---\n{body}"
    path.write_text(new_text, encoding='utf-8')
    return True


def main():
    code_lookup = _stock_code_lookup()
    print(f"stock_code lookup: {len(code_lookup)} entries")

    n_buffett = 0
    for p in sorted((STOCK / 'sectors').rglob('*.md')):
        if _process_buffett(p):
            n_buffett += 1
    print(f"buffett updated: {n_buffett}")

    n_q = 0
    miss_codes = []
    for p in sorted((STOCK / 'quarterly').rglob('*.md')):
        if _process_quarterly(p, code_lookup):
            n_q += 1
            fm, _ = parse_frontmatter(p)
            if not fm.get('stock_code'):
                miss_codes.append(p)
    print(f"quarterly created: {n_q}")
    if miss_codes:
        print(f"\nMISS stock_code ({len(miss_codes)}):")
        for p in miss_codes:
            print(f"  {p.relative_to(ROOT)}")


if __name__ == '__main__':
    main()
