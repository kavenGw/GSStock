"""stock-deep-redo 阶段放行闸门：检查 subagent 产物是否真的就绪。

用法：
    python scripts/deep_redo_gate.py <股票名> <日期> --phase A [--quiet-min 3]
    python scripts/deep_redo_gate.py <股票名> <日期> --phase B --doc <新档路径>
    python scripts/deep_redo_gate.py <股票名> <日期> --phase review

退出码：0=全绿可放行 / 1=有项未就绪 / 2=参数错。

本脚本**不轮询**（保持无状态可单测），等待由控制者包一层：

    T=1800; E=0
    until python scripts/deep_redo_gate.py 光智科技 2026-08-22 --phase A || [ $E -ge $T ]; do
      sleep 30; E=$((E+30)); done
    [ $E -ge $T ] && echo "TIMEOUT ${E}s — 可能静默失败，控制者接管"

`||` 短路保证超时分支也发信号（lessons.md L7：只报成功的探测器无法区分
crashloop 与"还没好"）。
"""
from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path

LANES = ('A1', 'A2', 'A3')
MIN_EVIDENCE_LINES = 20
END_STAMP_RE = re.compile(r'^end:\s*\S', re.M)


def _read(path: Path) -> str:
    return path.read_text(encoding='utf-8')


def _count_lines(path: Path) -> int:
    with path.open(encoding='utf-8') as fh:
        return sum(1 for _ in fh)


def _age_min(path: Path, now: float) -> float:
    return (now - path.stat().st_mtime) / 60.0


def _find_one(artifacts: Path, pattern: str) -> Path | None:
    hits = sorted(artifacts.glob(pattern))
    return hits[0] if hits else None


def _check_report(path: Path, tag: str) -> list[str]:
    if not path.exists():
        return [f'{tag} MISSING: report']
    if not END_STAMP_RE.search(_read(path)):
        return [f'{tag} NOT-READY: report 缺 end: 时间戳']
    return []


def check_phase_a(artifacts: Path, stock: str, date: str,
                  quiet_min: float, now: float) -> list[str]:
    problems: list[str] = []
    prefix = f'{stock}-{date}'
    for lane in LANES:
        evidence = _find_one(artifacts, f'{prefix}-evidence-{lane}-*.md')
        if evidence is None:
            problems.append(f'{lane} MISSING: evidence')
        else:
            lines = _count_lines(evidence)
            if lines < MIN_EVIDENCE_LINES:
                problems.append(
                    f'{lane} NOT-READY: evidence only {lines} lines (<{MIN_EVIDENCE_LINES})')
            age = _age_min(evidence, now)
            if age < quiet_min:
                problems.append(
                    f'{lane} NOT-READY: evidence mtime {age:.1f}min ago (<{quiet_min})')
        problems += _check_report(artifacts / f'{prefix}-phase{lane}-report.md', lane)
    return problems


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description='stock-deep-redo 阶段放行闸门',
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('stock', help='股票名（与 .omc/artifacts 文件名前缀一致）')
    ap.add_argument('date', help='日期，形如 2026-08-22')
    ap.add_argument('--phase', required=True, choices=['A', 'B', 'review'])
    ap.add_argument('--quiet-min', type=float, default=3.0,
                    help='evidence mtime 至少多少分钟不变才算收工（默认 3）')
    ap.add_argument('--doc', help='--phase B 必给：新档路径')
    ap.add_argument('--artifacts', default='.omc/artifacts')
    return ap


def main(argv: list[str] | None = None) -> int:
    ap = build_parser()
    args = ap.parse_args(argv)
    artifacts = Path(args.artifacts)
    if not artifacts.is_dir():
        ap.error(f'artifacts 目录不存在: {artifacts}')
    now = time.time()
    problems = check_phase_a(artifacts, args.stock, args.date, args.quiet_min, now)
    if problems:
        for p in problems:
            print(p)
        return 1
    print(f'{args.phase} READY')
    return 0


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    sys.exit(main())
