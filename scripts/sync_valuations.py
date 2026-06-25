"""扫 docs/stock-analytics/**/*buffett*.md 的 frontmatter valuation 块，
flatten 后 upsert 到 docs/stock-analytics/valuations.yaml。

用法：
    python scripts/sync_valuations.py                 # 全量扫描 upsert
    python scripts/sync_valuations.py --stock-code 603986   # 只同步单只
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path
from typing import Optional

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts._docs_schema import parse_frontmatter, _as_str_date

DOCS_ROOT = Path(__file__).resolve().parent.parent / 'docs' / 'stock-analytics'
YAML_PATH = DOCS_ROOT / 'valuations.yaml'

_CURRENCY_BY_MARKET = {'A': 'CNY', 'HK': 'HKD', 'US': 'USD'}


def infer_market(stock_code: str) -> str:
    """6 位纯数字→A；含 .HK 或 4-5 位纯数字→HK；字母开头→US。"""
    code = stock_code.upper()
    if '.HK' in code:
        return 'HK'
    if code.isdigit():
        return 'A' if len(code) == 6 else 'HK'
    return 'US'


def default_currency(market: str) -> str:
    return _CURRENCY_BY_MARKET.get(market, 'CNY')


def _clean_themes(raw) -> list[str]:
    if not isinstance(raw, list):
        return []
    out, seen = [], set()
    for t in raw:
        s = str(t).strip()
        if not s or s.startswith('_') or s in seen:
            continue
        seen.add(s)
        out.append(s)
    return out


def build_entry(fm: dict, source_doc: str) -> dict:
    """从 buffett frontmatter + valuation 块组装扁平 valuations.yaml 条目。"""
    val = fm.get('valuation') or {}
    market = infer_market(str(fm['stock_code']))
    currency = val.get('currency') or default_currency(market)
    entry: dict = {
        'stock_code': str(fm['stock_code']),
        'stock_name': fm.get('stock_name'),
        'market': market,
        'currency': currency,
        'sector': fm.get('sector'),
        'rating': fm.get('rating'),
    }
    if fm.get('watch_reason'):
        entry['watch_reason'] = fm['watch_reason']
    entry['bear'] = val.get('bear')
    entry['base'] = val.get('base')
    entry['bull'] = val.get('bull')
    if val.get('dividend_yield') is not None:
        entry['dividend_yield'] = val['dividend_yield']
    entry['conviction_date'] = _as_str_date(fm.get('conviction_date'))
    entry['source_doc'] = source_doc
    return entry


def backfill_themes(entries: list[dict], docs_root: Path) -> bool:
    """按 entry['source_doc'] 读对应 buffett 档 frontmatter themes 回填到每条 entry（覆盖全部条目，
    不止含 valuation 块的）。源无 themes 则删除既有 themes 键。返回是否有变更。"""
    changed = False
    for e in entries:
        sd = e.get('source_doc')
        themes: list[str] = []
        if sd:
            f = docs_root / sd
            if f.exists():
                fm, _ = parse_frontmatter(f)
                themes = _clean_themes((fm or {}).get('themes'))
        if themes:
            if e.get('themes') != themes:
                e['themes'] = themes
                changed = True
        elif 'themes' in e:
            del e['themes']
            changed = True
    return changed


def upsert(entries: list[dict], new_entry: dict) -> list[dict]:
    """按 stock_code 原地替换已有条目，不存在则追加；保留旧条目手工 note。"""
    for i, e in enumerate(entries):
        if e.get('stock_code') == new_entry['stock_code']:
            if 'note' in e and 'note' not in new_entry:
                new_entry = {**new_entry, 'note': e['note']}
            entries[i] = new_entry
            return entries
    entries.append(new_entry)
    return entries


def _load_entries(yaml_path: Path) -> list[dict]:
    if not yaml_path.exists():
        return []
    data = yaml.safe_load(yaml_path.read_text(encoding='utf-8'))
    return data if isinstance(data, list) else []


def sync(docs_root: Path, yaml_path: Path, only_code: Optional[str] = None) -> int:
    """扫 buffett 档，把含 valuation 块的（可选按 only_code 过滤）upsert 进 yaml，返回 upsert 条数。"""
    entries = _load_entries(yaml_path)
    count = 0
    for md in sorted(docs_root.rglob('*buffett*.md')):
        fm, _ = parse_frontmatter(md)
        if not fm or fm.get('doc_type') != 'buffett' or 'valuation' not in fm:
            continue
        if only_code is not None and str(fm.get('stock_code')) != str(only_code):
            continue
        source_doc = md.relative_to(docs_root).as_posix()
        upsert(entries, build_entry(fm, source_doc))
        count += 1
    changed = backfill_themes(entries, docs_root)
    if count or changed:
        yaml_path.write_text(
            yaml.dump(entries, allow_unicode=True, sort_keys=False, width=4096),
            encoding='utf-8')
    return count


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--stock-code', default=None, help='只同步该代码（默认全量扫描）')
    ap.add_argument('--docs-root', default=str(DOCS_ROOT))
    ap.add_argument('--yaml-path', default=str(YAML_PATH))
    args = ap.parse_args()
    n = sync(Path(args.docs_root), Path(args.yaml_path), only_code=args.stock_code)
    print(f"synced {n} entr{'y' if n == 1 else 'ies'} into {args.yaml_path}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
