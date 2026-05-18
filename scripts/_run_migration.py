"""一次性物理迁移：docs/analysis + docs/financial-analysis -> docs/stock-analytics。
按 SECTOR_MAPPING / SPECIAL_FILES 路由，用 git mv 保 history。
"""
from __future__ import annotations
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts._migration_mapping import SECTOR_MAPPING, SPECIAL_FILES

ROOT = Path(__file__).resolve().parent.parent
SRC_ANALYSIS = ROOT / 'docs' / 'analysis'
SRC_FINANCIAL = ROOT / 'docs' / 'financial-analysis'
DST = ROOT / 'docs' / 'stock-analytics'

_QUARTER_RE = re.compile(r'^\d{2}q\d$', re.IGNORECASE)
_NAME_RE = re.compile(r'^\d{4}-\d{2}-\d{2}-(.+?)\.md$')


def git_mv(src: Path, dst: Path):
    dst.parent.mkdir(parents=True, exist_ok=True)
    rel_src = src.relative_to(ROOT).as_posix()
    rel_dst = dst.relative_to(ROOT).as_posix()
    print(f"git mv {rel_src} -> {rel_dst}")
    res = subprocess.run(['git', 'mv', rel_src, rel_dst],
                         cwd=ROOT, capture_output=True, text=True, encoding='utf-8')
    if res.returncode != 0:
        print(f"FAIL: {res.stderr}")
        sys.exit(1)


def _match_special(filename: str) -> str | None:
    for key, dest in SPECIAL_FILES.items():
        if key in filename:
            return dest
    return None


def _decide_buffett(src: Path, in_quarterly: bool) -> Path | None:
    """单股 buffett 文件 → sectors/<sector>/<subsector>/"""
    m = _NAME_RE.match(src.name)
    if not m:
        print(f"WARN: bad filename: {src.name}")
        return None
    stem = m.group(1)  # 如 '兆易创新-buffett分析' or '兆易创新-26Q1季报点评'
    # 提取首段股票名（first '-' 之前）
    stock_name = stem.split('-', 1)[0]
    sector_info = SECTOR_MAPPING.get(stock_name)
    if not sector_info:
        print(f"ABORT: '{stock_name}' not in SECTOR_MAPPING (file: {src.name})")
        sys.exit(1)
    sector, subsector = sector_info
    return DST / 'sectors' / sector / subsector / src.name


def migrate_analysis_root():
    for src in sorted(SRC_ANALYSIS.glob('*.md')):
        dest = _match_special(src.name)
        if dest:
            git_mv(src, DST / dest / src.name)
        else:
            # 单股 buffett 或 板块分析 / 专题，需进一步判断
            # 文件名结构 YYYY-MM-DD-<X>-<type>.md；type 包含 'buffett' / '专题' / '板块' / etc.
            target = _decide_buffett(src, in_quarterly=False)
            if target:
                git_mv(src, target)


def migrate_analysis_quarterly():
    """docs/analysis/<NNqN>/*.md → quarterly/<nnqn>/  or 按 SPECIAL_FILES 改投"""
    for sub in sorted(SRC_ANALYSIS.iterdir()):
        if not sub.is_dir() or not _QUARTER_RE.match(sub.name):
            continue
        for src in sorted(sub.glob('*.md')):
            dest = _match_special(src.name)
            if dest:
                git_mv(src, DST / dest / src.name)
                continue
            # buffett 分析意外在 quarterly/ 下（如宏和科技）→ 改投 sectors/
            if 'buffett分析' in src.name:
                target = _decide_buffett(src, in_quarterly=True)
                if target:
                    git_mv(src, target)
                continue
            # 正常季报点评 + 单股同期专题 → quarterly/
            git_mv(src, DST / 'quarterly' / sub.name.lower() / src.name)


def migrate_financial_root():
    for src in sorted(SRC_FINANCIAL.glob('*.md')):
        dest = _match_special(src.name)
        if dest:
            git_mv(src, DST / dest / src.name)
        else:
            git_mv(src, DST / 'comps' / src.name)


def migrate_financial_quarterly():
    for sub in sorted(SRC_FINANCIAL.iterdir()):
        if not sub.is_dir() or not _QUARTER_RE.match(sub.name):
            continue
        for src in sorted(sub.glob('*.md')):
            dest = _match_special(src.name)
            if dest:
                git_mv(src, DST / dest / src.name)
                continue
            git_mv(src, DST / 'comps' / 'quarterly' / sub.name.lower() / src.name)


def main():
    if not SRC_ANALYSIS.exists():
        print("docs/analysis/ already migrated, abort")
        return
    migrate_analysis_root()
    migrate_analysis_quarterly()
    migrate_financial_root()
    migrate_financial_quarterly()
    print("\nDone.")


if __name__ == '__main__':
    main()
