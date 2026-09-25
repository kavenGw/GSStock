"""重算 timing-baseline.md 的统计表（轮数 / 中位数 / 四分位 / 区间 / 均值）。

用法：
    PYTHONIOENCODING=utf-8 python .claude/skills/stock-research/scripts/timing_stats.py [--file <path>] [--check]

数据源是同目录 `../references/timing-baseline.md` 里的两张汇总表（早期 21 轮 + 逐轮记录）。
标的列以 `*` 包裹、或形态列含「不计入」的行不计入完整轮。净耗时取该列第一个数字。
`--check` 把算出的值与文件「统计」表里写的值比对，不一致退出码 1——收尾漏了重算即被抓住。
"""
from __future__ import annotations

import argparse
import re
import statistics
import sys
from pathlib import Path

DEFAULT_FILE = Path(__file__).resolve().parent.parent / 'references' / 'timing-baseline.md'
NUM_RE = re.compile(r'\d+(?:\.\d+)?')


def parse_rounds(text: str) -> tuple[list[float], list[str]]:
    included: list[float] = []
    excluded: list[str] = []
    in_summary = False
    for line in text.splitlines():
        if line.startswith('## '):
            in_summary = line.startswith('## 全轮次汇总')
            continue
        if not in_summary or not line.startswith('|'):
            continue
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        if len(cells) < 3 or set(cells[0]) <= set('-: ') or cells[0] in ('标的', '日期'):
            continue
        name, shape, minutes = (cells[0], cells[1], cells[2]) if len(cells) == 3 else (cells[1], cells[2], cells[3])
        if name.startswith('*') or '不计入' in shape:
            excluded.append(name.strip('*'))
            continue
        m = NUM_RE.search(minutes)
        if not m:
            raise ValueError(f'净耗时列无数字: {line}')
        included.append(float(m.group()))
    return included, excluded


def _percentile(sorted_vals: list[float], q: float) -> float:
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    pos = (len(sorted_vals) - 1) * q
    lo, hi = int(pos), min(int(pos) + 1, len(sorted_vals) - 1)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (pos - lo)


def compute(vals: list[float]) -> dict[str, float]:
    s = sorted(vals)
    return {
        'count': len(s),
        'median': statistics.median(s),
        'p25': _percentile(s, 0.25),
        'p75': _percentile(s, 0.75),
        'min': s[0],
        'max': s[-1],
        'mean': sum(s) / len(s),
    }


def parse_written(text: str) -> dict[str, float]:
    def grab(label: str) -> list[float]:
        m = re.search(rf'^\|\s*{label}[^|]*\|\s*(.+?)\s*\|\s*$', text, re.M)
        if not m:
            raise ValueError(f'统计表缺「{label}」行')
        return [float(x) for x in NUM_RE.findall(m.group(1).split('（')[0])]

    count = grab('完整轮数')[0]
    median = grab('中位数')[0]
    p25, p75 = grab('四分位')[:2]
    lo, hi = grab('区间')[:2]
    mean = grab('均值')[0]
    return {'count': count, 'median': median, 'p25': p25, 'p75': p75, 'min': lo, 'max': hi, 'mean': mean}


def fmt(stats: dict[str, float], excluded: list[str]) -> str:
    return (
        f"| 完整轮数 | **{int(stats['count'])}**（另有 {len(excluded)} 轮不计入：{' / '.join(excluded)}）|\n"
        f"| 中位数 | **{stats['median']:.1f}min** |\n"
        f"| 四分位（P25 / P75） | **{stats['p25']:.1f} / {stats['p75']:.1f}min** |\n"
        f"| 区间 | **{stats['min']:.0f}** – {stats['max']:.0f}min |\n"
        f"| 均值 | {stats['mean']:.1f}min |"
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--file', default=str(DEFAULT_FILE))
    ap.add_argument('--check', action='store_true', help='与文件里写的统计表比对，不一致退出码 1')
    args = ap.parse_args(argv)
    text = Path(args.file).read_text(encoding='utf-8')
    included, excluded = parse_rounds(text)
    stats = compute(included)
    print(fmt(stats, excluded))
    if not args.check:
        return 0
    written = parse_written(text)
    drift = [k for k in stats if abs(stats[k] - written[k]) > 0.05]
    if drift:
        print('DRIFT: ' + ', '.join(f"{k} 文件={written[k]:g} 实算={stats[k]:.1f}" for k in drift))
        return 1
    print('统计表与汇总表一致')
    return 0


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    sys.exit(main())
