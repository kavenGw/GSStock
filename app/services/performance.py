"""研究档中的正式季度业绩；金额统一为亿元人民币。"""
from datetime import date
import math
from pathlib import Path
import re

import yaml


ANALYTICS_ROOT = Path(__file__).resolve().parents[2] / 'docs' / 'stock-analytics'
METRICS = ('revenue', 'adjusted_profit', 'inventory')
PERIOD_PATTERN = re.compile(r'^\d{4}Q[1-4]$')


def previous_period(period):
    year, quarter = int(period[:4]), int(period[-1])
    return f'{year}Q{quarter - 1}' if quarter > 1 else f'{year - 1}Q4'


def quarter_change(current, previous, profit=False):
    if current is None or previous is None:
        return {'value': None, 'label': '—'}
    if profit and (previous <= 0 or current < 0):
        if previous <= 0 < current:
            label = '扭亏' if previous < 0 else '上季为零'
        elif previous >= 0 > current:
            label = '转亏'
        elif current > previous:
            label = '减亏'
        elif current < previous:
            label = '增亏'
        else:
            label = '持平'
        return {'value': None, 'label': label}
    if previous <= 0:
        return {'value': None, 'label': '上季为零'}
    return {'value': (current / previous - 1) * 100, 'label': None}


def research_path(document, root=ANALYTICS_ROOT):
    root = Path(root).resolve()
    path = (root / document).resolve()
    if not path.is_relative_to(root / 'sectors') or path.suffix != '.md' or not path.is_file():
        raise ValueError(f'研究档不存在或路径非法：{document}')
    return path


def validate_company(data, doc_dir):
    if not isinstance(data, dict) or data.get('schema_version') != 1:
        raise ValueError('业绩文件 schema_version 必须为 1')
    if data.get('unit') != 'CNY_100M':
        raise ValueError('业绩金额必须为亿元人民币（CNY_100M）')
    for key in ('stock_code', 'stock_name'):
        if not isinstance(data.get(key), str) or not data[key].strip():
            raise ValueError(f'{key} 必须是非空字符串')
    index = Path(doc_dir) / 'index.md'
    text = index.read_text(encoding='utf-8')
    if not text.startswith('---\n'):
        raise ValueError(f'{index} 缺少 frontmatter')
    meta = yaml.safe_load(text.split('---', 2)[1])
    if not isinstance(meta, dict):
        raise ValueError(f'{index} frontmatter 必须为对象')
    if str(meta.get('stock_code')) != data['stock_code'] or meta.get('stock_name') != data['stock_name']:
        raise ValueError('业绩公司代码/名称与研究档不一致')
    if not isinstance(data.get('periods'), list) or not data['periods']:
        raise ValueError('periods 必须是非空季度记录列表')
    seen = set()
    for row in data['periods']:
        if not isinstance(row, dict):
            raise ValueError('季度记录必须是对象')
        period = row.get('period', '')
        if not isinstance(period, str) or not PERIOD_PATTERN.fullmatch(period) or period in seen:
            raise ValueError(f'季度非法或重复：{period}')
        seen.add(period)
        if row.get('report_type') != 'formal':
            raise ValueError(f'{period} 只接受正式财报')
        try:
            row['updated_at'] = date.fromisoformat(str(row.get('updated_at', ''))).isoformat()
        except ValueError as exc:
            raise ValueError(f'{period} 缺少有效 updated_at 日期') from exc
        missing = row.get('missing_reasons', {})
        if not isinstance(missing, dict):
            raise ValueError(f'{period} missing_reasons 必须是对象')
        for metric in METRICS:
            if metric not in row:
                raise ValueError(f'{period} 缺少字段 {metric}，未取得请显式填 null')
            value = row[metric]
            if value is None:
                reason = missing.get(metric)
                if not isinstance(reason, str) or not reason.strip():
                    raise ValueError(f'{period} {metric} 缺失但未解释原因')
            elif isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError(f'{period} {metric} 必须为有限数值或 null')
            elif metric != 'adjusted_profit' and value < 0:
                raise ValueError(f'{period} {metric} 不得为负')
        sources = row.get('sources')
        if not isinstance(sources, list) or not sources:
            raise ValueError(f'{period} 缺少正式财报来源')
        for source in sources:
            if not isinstance(source, dict) or not all(
                isinstance(source.get(key), str) and source[key].strip()
                for key in ('title', 'url', 'locator')
            ) or not re.match(r'^https?://[^/\s]+', source['url']):
                raise ValueError(f'{period} 来源须包含 title、http(s) url、页码/科目 locator')
    return data


def load_companies(root=ANALYTICS_ROOT):
    companies = []
    codes = set()
    for path in sorted((Path(root) / 'sectors').rglob('performance.yaml')):
        try:
            data = validate_company(yaml.safe_load(path.read_text(encoding='utf-8')), path.parent)
        except (OSError, ValueError, yaml.YAMLError) as exc:
            raise ValueError(f'{path}: {exc}') from exc
        if data['stock_code'] in codes:
            raise ValueError(f'重复的公司业绩文件：{data["stock_code"]}')
        codes.add(data['stock_code'])
        companies.append({**data, 'source_doc': (path.parent / 'index.md').relative_to(root).as_posix()})
    return companies


def performance_rows(companies):
    rows = []
    for company in companies:
        periods = {row['period']: row for row in company['periods']}
        for period, raw in periods.items():
            previous = periods.get(previous_period(period), {})
            row = {
                **raw,
                'stock_code': company['stock_code'],
                'stock_name': company['stock_name'],
                'source_doc': company['source_doc'],
            }
            for metric in METRICS:
                row[f'{metric}_qoq'] = quarter_change(
                    raw[metric], previous.get(metric), profit=metric == 'adjusted_profit',
                )
            rows.append(row)
    return sorted(rows, key=lambda row: (row['period'], row['stock_code']), reverse=True)
