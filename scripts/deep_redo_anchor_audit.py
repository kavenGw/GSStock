"""stock-deep-redo 跨日锚点审计：列出正文里所有「派生数」句子供逐句手算。

用法：
    python scripts/deep_redo_anchor_audit.py <档路径|文件夹>
    python scripts/deep_redo_anchor_audit.py <档路径> --old 60.64 --new 54.20

**它不算数，只保证逐句过一遍。** 雷赛轮跨 3 天中断后控制者做了 71 处字面量
替换并 grep 自查干净，审查仍抓出 4 处 Major、复核又自查出第 5 处——五处全部是
用旧市值反推的派生数，句子里不含任何旧锚的字面量，grep 扫不到。所以主判据是
**句式**（反推/隐含/对照当前市值/÷/相当于 N 倍/前瞻 PE），`--old` 的字面量
匹配只是顺带兜底。

退出码：扫描完成时恒为 0（无论命中多少行——它是报告工具，不裁定）；
档路径不存在等参数错误走 argparse 的 2。
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

DERIVED_PATTERNS: list[tuple[str, re.Pattern]] = [
    ('反推', re.compile(r'反推')),
    ('隐含', re.compile(r'隐含')),
    ('对照当前市值', re.compile(r'(对照|按)当前市值')),
    ('市值除法', re.compile(r'市值\s*[/÷]|[/÷]\s*市值')),
    ('相当于N倍', re.compile(r'相当于\s*\d+(?:\.\d+)?\s*倍')),
    ('前瞻PE', re.compile(r'前瞻\s*P/?E')),
    ('N倍乘法', re.compile(r'[×x]\s*\d+(?:\.\d+)?\s*倍')),
    ('折溢价', re.compile(r'(折价|溢价)\s*\d+(?:\.\d+)?\s*%')),
    ('股本除法', re.compile(r'[/÷]\s*(总股本|股本|总股数)')),
    ('数式推导', re.compile(r'=\s*\d+(?:\.\d+)?\s*[/÷]\s*\d+')),
]
SNIPPET_LEN = 120


def scan(text: str, old: str | None = None) -> list[tuple[int, list[str], str]]:
    rows = []
    for lineno, line in enumerate(text.splitlines(), 1):
        tags = [name for name, pat in DERIVED_PATTERNS if pat.search(line)]
        if old and old in line:
            tags.append('STALE-LITERAL')
        if tags:
            rows.append((lineno, tags, line.strip()[:SNIPPET_LEN]))
    return rows


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description='列出档内派生数句子供逐句手算（不算数、不裁定）',
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('doc', help='buffett 深度档路径（平铺 .md 或 <股票名>/ 文件夹）')
    ap.add_argument('--old', help='旧价/旧市值字面量，命中即标 STALE-LITERAL')
    ap.add_argument('--new', help='新价/新市值，仅打印在表头供人工比对')
    args = ap.parse_args(argv)
    doc = Path(args.doc)
    if not doc.exists():
        ap.error(f'档不存在: {doc}')
    files = sorted(doc.glob('*.md')) if doc.is_dir() else [doc]
    if args.old or args.new:
        print(f'锚点刷新：{args.old or "?"} → {args.new or "?"}')
    total = 0
    for f in files:
        rows = scan(f.read_text(encoding='utf-8'), args.old)
        prefix = f'{f.name}:' if doc.is_dir() else ''
        for lineno, tags, snippet in rows:
            print(f'{prefix}{lineno:>5} | {",".join(tags):<24} | {snippet}')
        total += len(rows)
    print(f'合计 {total} 行待手算（本工具不算数，逐句核对派生关系）')
    return 0


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    sys.exit(main())
