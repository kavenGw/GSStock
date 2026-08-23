#!/usr/bin/env python3
"""扫描 docs/stock-analytics 全部文档的 frontmatter，输出一份紧凑 JSON 索引。

这是 stock-research 模式 3（新闻影响）的匹配底料：一次扫描代替逐个读 161 篇 doc，
让新闻→标的的映射在一个小 JSON 上完成，省 token 且不漏标的。

用法：
    python pool_index.py                 # 全池索引打印到 stdout
    python pool_index.py --out idx.json  # 写文件
    python pool_index.py --out m.json match --keywords "MCU,功率半导体" [--codes 603986] \
        [--sector semiconductor --subsector mcu] [--wide]   # 分档候选清单 T1-T4（--out 在 match 前）

输出每条记录字段：
    path        相对 docs/stock-analytics 的路径
    doc_type    buffett / quarterly / cross-sector / theme / comps
    codes       该 doc 涉及的股票代码列表（统一成 list）
    names       股票名列表
    sector / subsector
    themes      主题关键词列表
    rating      仅 buffett 档有（core/config/watch/exclude）
    thesis      一句话论点（buffett 档）
    date        conviction_date 或 date
"""
import argparse
import json
import sys
from datetime import date
from pathlib import Path

import yaml


def _to_str(v):
    if isinstance(v, date):
        return v.isoformat()
    return str(v) if v is not None else ''


def _as_list(v):
    if v is None:
        return []
    if isinstance(v, list):
        return [str(x) for x in v]
    return [str(v)]


def parse_doc(path: Path, root: Path):
    text = path.read_text(encoding='utf-8')
    if not text.startswith('---'):
        return None
    end = text.find('\n---', 3)
    if end == -1:
        return None
    try:
        fm = yaml.safe_load(text[3:end]) or {}
    except yaml.YAMLError:
        return None
    if not isinstance(fm, dict):
        return None
    if fm.get('doc_type') in ('buffett-section', 'buffett-events'):
        return None

    # 代码/名字：单档用 stock_code/stock_name，多档用 stock_codes/stock_names，
    # theme 档用 related_codes
    codes = _as_list(fm.get('stock_code')) or _as_list(fm.get('stock_codes')) \
        or _as_list(fm.get('related_codes'))
    names = _as_list(fm.get('stock_name')) or _as_list(fm.get('stock_names'))

    return {
        'path': str(path.relative_to(root)).replace('\\', '/'),
        'doc_type': fm.get('doc_type', ''),
        'codes': codes,
        'names': names,
        'sector': fm.get('sector', ''),
        'subsector': fm.get('subsector', ''),
        'themes': _as_list(fm.get('themes')),
        'rating': fm.get('rating', ''),
        'thesis': _to_str(fm.get('thesis')),
        'date': _to_str(fm.get('conviction_date') or fm.get('date')),
    }


def build_index(root: Path):
    records = []
    for p in sorted(root.rglob('*.md')):
        if p.name.upper() == 'README.MD':
            continue
        rec = parse_doc(p, root)
        if rec:
            records.append(rec)
    return records


THESIS_PREVIEW = 80
_STOCK_DOC_TYPES = {'buffett', 'quarterly'}


def _dedup_by_code(records):
    """每只票保留一条权威记录：最新 buffett 档优先，其次最新任意单股档。"""
    best = {}
    for r in records:
        if r['doc_type'] not in _STOCK_DOC_TYPES or len(r['codes']) != 1:
            continue
        code = r['codes'][0]
        key = (r['doc_type'] == 'buffett', r['date'])
        cur = best.get(code)
        if cur is None or key > (cur['doc_type'] == 'buffett', cur['date']):
            best[code] = r
    return best


def _compact(r):
    return {
        'code': r['codes'][0], 'name': r['names'][0] if r['names'] else '',
        'rating': r['rating'], 'date': r['date'], 'path': r['path'],
        'sector': r['sector'], 'subsector': r['subsector'],
        'thesis': r['thesis'][:THESIS_PREVIEW],
    }


def match_pool(records, keywords=(), codes=(), sector=None, subsector=None, wide=False):
    """新闻要素 → 分档候选清单。

    T1 直接命中（名称含关键词 / 代码相等）
    T2 与 T1 同 subsector（或显式 --subsector / 关键词 == subsector 名）
    T3 themes 关键词命中
    T4 仅与 T1 同 sector（或显式 --sector）——面太宽，默认只给 T4_count，--wide 才列出
    各档互斥，按 T1>T2>T3>T4 优先归档。
    """
    keywords = [k.strip().lower() for k in keywords if k and k.strip()]
    codes = {c.strip() for c in codes if c and c.strip()}
    pool = _dedup_by_code(records)

    tiers = {'T1': [], 'T2': [], 'T3': [], 'T4': []}
    placed = set()

    def _hit_name(r):
        return any(kw in n.lower() for n in r['names'] for kw in keywords)

    for code, r in pool.items():
        if code in codes or _hit_name(r):
            tiers['T1'].append(r); placed.add(code)

    subsectors = {(r['sector'], r['subsector']) for r in tiers['T1']}
    sectors = {r['sector'] for r in tiers['T1']}
    if sector and subsector:
        subsectors.add((sector, subsector))
    if sector:
        sectors.add(sector)
    for r in pool.values():
        if r['subsector'] and any(kw == r['subsector'].lower() for kw in keywords):
            subsectors.add((r['sector'], r['subsector']))
            sectors.add(r['sector'])

    for code, r in pool.items():
        if code not in placed and (r['sector'], r['subsector']) in subsectors:
            tiers['T2'].append(r); placed.add(code)

    for code, r in pool.items():
        if code not in placed and any(kw in t.lower() for t in r['themes'] for kw in keywords):
            tiers['T3'].append(r); placed.add(code)

    for code, r in pool.items():
        if code not in placed and r['sector'] in sectors:
            tiers['T4'].append(r); placed.add(code)

    out = {t: [_compact(r) for r in rs] for t, rs in tiers.items()}
    out['T4_count'] = len(out['T4'])
    if not wide:
        out['T4'] = []
    return out


def _split_csv(v):
    return [x for x in (v or '').split(',') if x.strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', default='docs/stock-analytics',
                    help='docs/stock-analytics 根目录')
    ap.add_argument('--out', default=None, help='输出 JSON 文件路径（默认 stdout）')
    sub = ap.add_subparsers(dest='cmd')
    m = sub.add_parser('match', help='按新闻要素输出分档候选清单（T1-T4）')
    m.add_argument('--keywords', default='', help='逗号分隔：公司名片段/产品/主题关键词')
    m.add_argument('--codes', default='', help='逗号分隔：新闻点名的股票代码')
    m.add_argument('--sector', default=None)
    m.add_argument('--subsector', default=None)
    m.add_argument('--wide', action='store_true', help='连同 T4（仅同 sector）一起列出')
    args = ap.parse_args()

    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f'ERROR: 目录不存在: {root}', file=sys.stderr)
        sys.exit(1)

    records = build_index(root)
    if args.cmd == 'match':
        result = match_pool(records, _split_csv(args.keywords), _split_csv(args.codes),
                            args.sector, args.subsector, args.wide)
        payload = json.dumps(result, ensure_ascii=False, indent=1)
        summary = ' '.join(f'{t}={len(result[t])}' for t in ('T1', 'T2', 'T3')) \
            + f" T4(same-sector)={result['T4_count']}{'' if args.wide else ' (hidden, --wide)'}"
    else:
        payload = json.dumps(records, ensure_ascii=False, indent=1)
        summary = f'{len(records)} records'

    if args.out:
        Path(args.out).write_text(payload, encoding='utf-8')
        print(f'wrote {summary} -> {args.out}', file=sys.stderr)
    else:
        sys.stdout.write(payload)


if __name__ == '__main__':
    main()
