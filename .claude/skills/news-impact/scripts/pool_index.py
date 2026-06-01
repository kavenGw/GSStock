#!/usr/bin/env python3
"""扫描 docs/stock-analytics 全部文档的 frontmatter，输出一份紧凑 JSON 索引。

这是 news-impact skill 的匹配底料：一次扫描代替逐个读 161 篇 doc，
让新闻→标的的映射在一个小 JSON 上完成，省 token 且不漏标的。

用法：
    python pool_index.py                 # 打印到 stdout
    python pool_index.py --out idx.json  # 写文件
    python pool_index.py --root D:/Git/stock/docs/stock-analytics

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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', default='docs/stock-analytics',
                    help='docs/stock-analytics 根目录')
    ap.add_argument('--out', default=None, help='输出 JSON 文件路径（默认 stdout）')
    args = ap.parse_args()

    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f'ERROR: 目录不存在: {root}', file=sys.stderr)
        sys.exit(1)

    records = build_index(root)
    payload = json.dumps(records, ensure_ascii=False, indent=1)

    if args.out:
        Path(args.out).write_text(payload, encoding='utf-8')
        print(f'wrote {len(records)} records -> {args.out}', file=sys.stderr)
    else:
        sys.stdout.write(payload)


if __name__ == '__main__':
    main()
