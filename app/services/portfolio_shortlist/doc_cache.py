"""MD5 缓存层 — 按股票聚合多个 doc 的 md5，命中则跳过 extractor。"""

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Callable

ExtractorFn = Callable[[str, list[Path]], dict]


def _md5(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


class DocCache:
    def __init__(self, cache_dir: Path, schema_version: int = 1):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.schema_version = schema_version

    def get_or_compute(
        self,
        stock_code: str,
        stock_name: str,
        doc_paths: list[Path],
        extractor: ExtractorFn,
    ) -> dict:
        cache_file = self.cache_dir / f'{stock_code}.json'
        current_md5s = {str(p): _md5(Path(p)) for p in doc_paths}

        if cache_file.exists():
            try:
                cached = json.loads(cache_file.read_text(encoding='utf-8'))
                if (
                    cached.get('version') == self.schema_version
                    and len(cached.get('docs', [])) == len(doc_paths)
                    and all(
                        d['md5'] == current_md5s.get(d['path'])
                        for d in cached['docs']
                    )
                ):
                    return cached['summary']
            except (json.JSONDecodeError, KeyError):
                pass  # 损坏缓存视为 miss

        summary = extractor(stock_code, [Path(p) for p in doc_paths])
        cache_file.write_text(
            json.dumps(
                {
                    'stock_code': stock_code,
                    'stock_name': stock_name,
                    'docs': [
                        {
                            'path': str(p),
                            'md5': current_md5s[str(p)],
                            'extracted_at': datetime.now().isoformat(timespec='seconds'),
                        }
                        for p in doc_paths
                    ],
                    'summary': summary,
                    'version': self.schema_version,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding='utf-8',
        )
        return summary
