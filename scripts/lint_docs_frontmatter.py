"""扫 docs/stock-analytics/**/*.md，校验 frontmatter schema。退出码 0=全过，非 0=有违例。

用法：
    python scripts/lint_docs_frontmatter.py
    python scripts/lint_docs_frontmatter.py --root docs/stock-analytics
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts._docs_schema import parse_frontmatter, validate_frontmatter


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', default='docs/stock-analytics',
                    help='扫描根目录（默认 docs/stock-analytics）')
    args = ap.parse_args()

    root = Path(args.root)
    if not root.exists():
        print(f"ERROR: root not found: {root}")
        return 2

    all_violations: list[str] = []
    file_count = 0
    for md in sorted(root.rglob('*.md')):
        if md.name == 'README.md':
            continue
        file_count += 1
        try:
            fm, _ = parse_frontmatter(md)
        except Exception as e:
            all_violations.append(f"{md}: yaml parse error: {e}")
            continue
        if not fm:
            all_violations.append(f"{md}: no YAML frontmatter")
            continue
        all_violations.extend(validate_frontmatter(fm, md))

    if all_violations:
        for v in all_violations:
            print(v)
        print(f"\nFAIL: {len(all_violations)} violation(s) across {file_count} file(s)")
        return 1

    print(f"OK: {file_count} file(s) passed")
    return 0


if __name__ == '__main__':
    sys.exit(main())
