"""共享 schema 定义：docs/stock-analytics/**/*.md 的 frontmatter 约定与解析工具。
被 lint_docs_frontmatter.py / lint_docs_refs.py / 一次性迁移脚本共用。
"""
from __future__ import annotations
import re
from datetime import date
from pathlib import Path
from typing import Any

import yaml

DOC_TYPES: set[str] = {'buffett', 'quarterly', 'cross-sector', 'theme', 'comps'}

SECTORS: set[str] = {
    'semiconductor', 'electronics', 'consumer', 'materials',
    'energy', 'healthcare', 'media', 'financial', 'industrial',
    'ai-application', 'other',
}

RATINGS: set[str] = {'core', 'config', 'watch', 'exclude'}

REQUIRED_FIELDS_BY_TYPE: dict[str, set[str]] = {
    'buffett':      {'doc_type', 'stock_code', 'stock_name', 'sector', 'subsector',
                     'themes', 'rating', 'conviction_date', 'thesis'},
    'quarterly':    {'doc_type', 'stock_code', 'stock_name', 'sector', 'subsector',
                     'period', 'date'},
    'cross-sector': {'doc_type', 'stock_codes', 'stock_names', 'themes', 'date'},
    'theme':        {'doc_type', 'theme_name', 'themes', 'date'},
    'comps':        {'doc_type', 'stock_codes', 'stock_names', 'themes', 'period', 'date'},
}

_FRONTMATTER_RE = re.compile(r'^---\s*\n(.*?)\n---\s*\n(.*)$', re.DOTALL)
_DATE_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')


def parse_frontmatter(path: Path) -> tuple[dict[str, Any], str]:
    text = path.read_text(encoding='utf-8')
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    fm = yaml.safe_load(m.group(1)) or {}
    if not isinstance(fm, dict):
        return {}, text
    return fm, m.group(2)


def _as_str_date(v: Any) -> str:
    if isinstance(v, date):
        return v.isoformat()
    return str(v) if v is not None else ''


def validate_frontmatter(fm: dict[str, Any], path: Path) -> list[str]:
    violations: list[str] = []
    p = str(path)

    dt = fm.get('doc_type')
    if dt not in DOC_TYPES:
        violations.append(f"{p}: doc_type '{dt}' not in {sorted(DOC_TYPES)}")
        return violations

    required = REQUIRED_FIELDS_BY_TYPE[dt]
    for field in sorted(required):
        if field not in fm or fm[field] in (None, '', []):
            violations.append(f"{p}: missing required field '{field}' for doc_type={dt}")

    if 'sector' in fm and fm['sector'] not in SECTORS:
        violations.append(f"{p}: sector '{fm['sector']}' not in {sorted(SECTORS)}")

    if dt == 'buffett':
        if fm.get('rating') not in RATINGS:
            violations.append(f"{p}: rating '{fm.get('rating')}' not in {sorted(RATINGS)}")
        if fm.get('rating') == 'watch' and not fm.get('watch_reason'):
            violations.append(f"{p}: rating=watch requires watch_reason")
        if fm.get('rating') == 'exclude' and not fm.get('exclude_reason'):
            violations.append(f"{p}: rating=exclude requires exclude_reason")

    if 'stock_code' in fm and not isinstance(fm['stock_code'], str):
        violations.append(f"{p}: stock_code must be str (got {type(fm['stock_code']).__name__})")

    for field in ('stock_codes', 'stock_names', 'themes', 'related_codes'):
        if field in fm:
            v = fm[field]
            if not isinstance(v, list):
                violations.append(f"{p}: {field} must be a list (got {type(v).__name__})")
            else:
                for i, c in enumerate(v):
                    if not isinstance(c, str):
                        violations.append(f"{p}: {field}[{i}] must be str (got {type(c).__name__})")

    for field in ('conviction_date', 'date'):
        if field in fm:
            v = _as_str_date(fm[field])
            if not _DATE_RE.match(v):
                violations.append(f"{p}: {field} '{v}' not YYYY-MM-DD")

    if 'period' in fm:
        parts = path.parts
        for i, seg in enumerate(parts):
            if seg == 'quarterly' and i + 1 < len(parts):
                dir_period = parts[i + 1]
                if dir_period.lower() != str(fm['period']).lower():
                    violations.append(
                        f"{p}: period '{fm['period']}' != dir '{dir_period}'")
                break

    return violations
