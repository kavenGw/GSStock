"""校验全部业绩，或合并研究产物到本公司 performance.yaml，保留历史季度。"""
import argparse
import json
import os
from pathlib import Path
import re
import sys
import tempfile

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.performance import ANALYTICS_ROOT, load_companies, validate_company


def load_input(path):
    text = Path(path).read_text(encoding='utf-8')
    if Path(path).suffix == '.md':
        blocks = re.findall(r'^```performance\s*\n(.*?)^```\s*$', text, re.MULTILINE | re.DOTALL)
        if len(blocks) != 1:
            raise ValueError('A1 底稿必须包含且只包含一个 performance 代码块')
        text = blocks[0]
    return yaml.safe_load(text)


def merge_performance(incoming, doc_dir):
    doc_dir = Path(doc_dir)
    validate_company(incoming, doc_dir)
    target = doc_dir / 'performance.yaml'
    periods = {}
    if target.exists():
        old = validate_company(yaml.safe_load(target.read_text(encoding='utf-8')), doc_dir)
        periods.update({row['period']: row for row in old['periods']})
    periods.update({row['period']: row for row in incoming['periods']})
    merged = {**incoming, 'periods': [periods[key] for key in sorted(periods)]}
    validate_company(merged, doc_dir)
    content = yaml.safe_dump(merged, allow_unicode=True, sort_keys=False)
    if target.exists() and target.read_text(encoding='utf-8') == content:
        return target
    # 原子替换，页面不会读到写入一半的 YAML。
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', newline='\n',
                                         dir=doc_dir, suffix='.tmp', delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(content)
        os.replace(temporary, target)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, help='JSON/YAML 数据或含 performance 代码块的 A1.md')
    parser.add_argument('--doc', type=Path, help='本公司七文件研究档目录')
    parser.add_argument('--check', action='store_true', help='只读校验，不写文件')
    args = parser.parse_args()
    if args.input:
        if not args.doc:
            parser.error('--input 需要 --doc')
        doc_dir = args.doc.resolve()
        if not doc_dir.is_relative_to(ANALYTICS_ROOT / 'sectors'):
            parser.error('--doc 必须位于 docs/stock-analytics/sectors/')
        data = load_input(args.input)
        validate_company(data, doc_dir)
        if not args.check:
            print(merge_performance(data, doc_dir))
    else:
        if args.doc:
            parser.error('--doc 需要 --input')
        companies = load_companies()
        print(json.dumps({'companies': len(companies),
                          'periods': sum(len(item['periods']) for item in companies)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
