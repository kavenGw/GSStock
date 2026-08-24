"""校验 docs/stock-analytics/**/*.md 的 related_docs：
1. path 指向的文件存在
2. symmetric: true 时对端反向引用
3. --rewrite-blocks 子命令根据 frontmatter 重生 markdown 块
4. --check-orphans 列零反向引用文档

用法：
    python scripts/lint_docs_refs.py
    python scripts/lint_docs_refs.py --rewrite-blocks
    python scripts/lint_docs_refs.py --check-orphans
"""
from __future__ import annotations
import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts._docs_schema import parse_frontmatter

BLOCK_BEGIN = '<!-- BEGIN related_docs (auto-generated from frontmatter, do not edit) -->'
BLOCK_END = '<!-- END related_docs -->'

_BLOCK_RE = re.compile(
    r'<!-- BEGIN related_docs.*?-->.*?<!-- END related_docs -->\n?',
    re.DOTALL,
)
_H1_RE = re.compile(r'^(# [^\n]+\n)', re.MULTILINE)
_NEVER_ORPHAN = {'buffett-section', 'buffett-events', 'buffett-related'}


def _resolve(base: Path, rel: str) -> Path:
    return (base.parent / rel).resolve()


def _folders(docs: dict[Path, dict]) -> set[Path]:
    """股票文件夹档目录集合：含 doc_type: buffett 的 index.md 的那个目录。"""
    return {p.parent for p, fm in docs.items()
            if p.name == 'index.md' and fm.get('doc_type') == 'buffett'}


def _node(p: Path, folders: set[Path]) -> Path:
    """引用节点：文件夹档内任一文件归并到文件夹本身，其余按文件自身。"""
    return p.parent if p.parent in folders else p


def _node_refs(docs: dict[Path, dict], folders: set[Path]) -> dict[Path, set[Path]]:
    """node -> 该 node 全部文件出链指向的 node 集合。"""
    out: dict[Path, set[Path]] = {}
    for path, fm in docs.items():
        bucket = out.setdefault(_node(path, folders), set())
        for r in fm.get('related_docs') or []:
            if isinstance(r, dict) and 'path' in r:
                bucket.add(_node(_resolve(path, r['path']), folders))
    return out


def _gather(root: Path) -> dict[Path, dict]:
    out: dict[Path, dict] = {}
    for md in root.rglob('*.md'):
        if md.name == 'README.md':
            continue
        fm, _ = parse_frontmatter(md)
        if fm:
            out[md.resolve()] = fm
    return out


def _check(docs: dict[Path, dict]) -> list[str]:
    violations: list[str] = []
    folders = _folders(docs)
    node_refs = _node_refs(docs, folders)
    for path, fm in docs.items():
        rels = fm.get('related_docs') or []
        if not isinstance(rels, list):
            violations.append(f"{path}: related_docs must be list")
            continue
        for i, ref in enumerate(rels):
            if not isinstance(ref, dict) or 'path' not in ref:
                violations.append(f"{path}: related_docs[{i}] missing 'path'")
                continue
            rel = ref['path']
            if rel.startswith('/'):
                violations.append(f"{path}: related_docs[{i}].path '{rel}' must be relative")
                continue
            target = _resolve(path, rel)
            if target not in docs:
                violations.append(f"{path}: related_docs[{i}].path -> '{rel}' not found")
                continue
            src, dst = _node(path, folders), _node(target, folders)
            if src == dst:
                violations.append(
                    f"{path}: related_docs[{i}].path '{rel}' 指向同一股票文件夹内部，"
                    f"应改用正文相对链接")
                continue
            if ref.get('symmetric', True) and src not in node_refs.get(dst, set()):
                violations.append(
                    f"{path}: asymmetric ref to {target} "
                    f"(set symmetric: false to allow one-way)")
    return violations


def _orphans(docs: dict[Path, dict]) -> list[Path]:
    folders = _folders(docs)
    referenced: set[Path] = set()
    for path, fm in docs.items():
        for ref in fm.get('related_docs') or []:
            if isinstance(ref, dict) and 'path' in ref:
                referenced.add(_node(_resolve(path, ref['path']), folders))
    return sorted(p for p, fm in docs.items()
                  if _node(p, folders) not in referenced
                  and fm.get('doc_type') not in _NEVER_ORPHAN)


def _render_block(fm: dict, md_path: Path) -> str:
    rels = fm.get('related_docs') or []
    if not rels:
        return ''
    lines = [BLOCK_BEGIN, '> **关联文档**']
    for ref in rels:
        if not isinstance(ref, dict) or 'path' not in ref:
            continue
        rel = ref['path']
        note = ref.get('note', '')
        title = Path(rel).stem
        tag = '·'.join(str(ref[k]) for k in ('impact', 'magnitude') if ref.get(k))
        tag = f'【{tag}】' if tag else ''
        suffix = f' — {note}' if note else ''
        lines.append(f'> - [{title}]({rel}){tag}{suffix}')
    lines.append(BLOCK_END)
    return '\n'.join(lines) + '\n'


def _rewrite_blocks(docs: dict[Path, dict]) -> int:
    changed = 0
    for path, fm in docs.items():
        text = path.read_text(encoding='utf-8')
        new_block = _render_block(fm, path)
        if _BLOCK_RE.search(text):
            new_text = _BLOCK_RE.sub(new_block, text, count=1) if new_block \
                else _BLOCK_RE.sub('', text, count=1)
        elif new_block:
            m = _H1_RE.search(text)
            if not m:
                continue
            idx = m.end()
            new_text = text[:idx] + '\n' + new_block + text[idx:]
        else:
            new_text = text
        if new_text != text:
            path.write_text(new_text, encoding='utf-8')
            changed += 1
    return changed


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', default='docs/stock-analytics')
    ap.add_argument('--rewrite-blocks', action='store_true',
                    help='根据 frontmatter 重生 h1 后的 related_docs markdown 块')
    ap.add_argument('--check-orphans', action='store_true',
                    help='列出 0 反向引用文档')
    args = ap.parse_args()

    root = Path(args.root)
    if not root.exists():
        print(f"ERROR: root not found: {root}")
        return 2

    docs = _gather(root)

    if args.check_orphans:
        orphans = _orphans(docs)
        if orphans:
            print(f"Orphan docs (no incoming refs): {len(orphans)}")
            for p in orphans:
                print(f"  {p}")
        else:
            print("No orphans")
        return 0

    violations = _check(docs)
    if violations:
        for v in violations:
            print(v)
        print(f"\nFAIL: {len(violations)} violation(s)")
        return 1

    if args.rewrite_blocks:
        changed = _rewrite_blocks(docs)
        print(f"Rewrote {changed} file(s)")

    print(f"OK: {len(docs)} file(s)")
    return 0


if __name__ == '__main__':
    sys.exit(main())
