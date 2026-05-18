"""扫 docs/stock-analytics/**/*.md，重写形如 (../analysis/...) (../financial-analysis/...)
的 markdown 相对链接到新路径。
一次性，Stage 5 删除。
"""
from __future__ import annotations
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STOCK = ROOT / 'docs' / 'stock-analytics'

_LINK_RE = re.compile(r'\[([^\]]+)\]\(([^)]+)\)')


def _all_md() -> dict[str, Path]:
    """{filename: abs_path}"""
    out: dict[str, Path] = {}
    for p in STOCK.rglob('*.md'):
        if p.name == 'README.md':
            continue
        if p.name in out:
            print(f"WARN: duplicate filename {p.name}")
        else:
            out[p.name] = p.resolve()
    return out


def _rewrite_file(path: Path, by_name: dict[str, Path]) -> int:
    text = path.read_text(encoding='utf-8')
    changed = [0]

    def repl(m: re.Match) -> str:
        label, url = m.group(1), m.group(2)
        if '../analysis/' not in url and '../financial-analysis/' not in url:
            return m.group(0)
        if url.startswith(('http', '#', 'mailto:')):
            return m.group(0)
        target_name = Path(url).name
        if not target_name.endswith('.md'):
            return m.group(0)
        new_abs = by_name.get(target_name)
        if not new_abs:
            print(f"WARN: {path.relative_to(ROOT)}: cannot resolve link '{url}'")
            return m.group(0)
        new_rel = os.path.relpath(new_abs, path.parent.resolve())
        changed[0] += 1
        return f'[{label}]({new_rel.replace(os.sep, "/")})'

    new = _LINK_RE.sub(repl, text)
    if new != text:
        path.write_text(new, encoding='utf-8')
    return changed[0]


def main():
    by_name = _all_md()
    print(f"index: {len(by_name)} files")
    total = 0
    for p in sorted(STOCK.rglob('*.md')):
        if p.name == 'README.md':
            continue
        n = _rewrite_file(p, by_name)
        if n:
            print(f"  {p.relative_to(ROOT)}: {n} link(s) rewritten")
            total += n
    print(f"\nDone: {total} link(s) rewritten")


if __name__ == '__main__':
    main()
