"""Slack 数值列表表格及纯文本回退。"""

PAGE_SIZE = 20


def table_messages(title: str, headers: list[str], rows: list[list[str]],
                   left_columns=(0,), subtitle='') -> list[dict]:
    messages = []
    pages = (len(rows) + PAGE_SIZE - 1) // PAGE_SIZE
    for start in range(0, len(rows), PAGE_SIZE):
        page = rows[start:start + PAGE_SIZE]
        heading = title + (f' · {start // PAGE_SIZE + 1}/{pages}' if pages > 1 else '')
        text = '\n'.join(filter(None, [heading, subtitle, ' | '.join(headers),
                                      *(' | '.join(row) for row in page)]))
        blocks = [{'type': 'section', 'text': {'type': 'mrkdwn',
                   'text': '\n'.join(filter(None, [heading, subtitle]))}}, {
            'type': 'table',
            'column_settings': [
                {'align': 'left' if i in left_columns else 'right', 'is_wrapped': True}
                for i in range(len(headers))
            ],
            'rows': [[{'type': 'raw_text', 'text': cell} for cell in row]
                     for row in [headers, *page]],
        }]
        messages.append({'text': text, 'blocks': blocks})
    return messages


def format_volume(value, unit: str) -> str:
    if value is None:
        return '—'
    if abs(value) >= 100_000_000:
        return f'{value / 100_000_000:.2f}亿{unit}'
    if abs(value) >= 10_000:
        return f'{value / 10_000:.2f}万{unit}'
    return f'{value:,.0f}{unit}'


def format_volume_alerts(alerts: list[dict], title: str) -> list[dict]:
    rows = []
    for a in sorted(alerts, key=lambda a: abs(a['volume_change_pct']), reverse=True):
        unit = a.get('volume_unit') or ''
        price_change = a.get('price_change_pct')
        rows.append([
            '⚠️' if a['priority'] == 'HIGH' else '🟡',
            f"{a['stock_name']}({a['stock_code']})",
            f"{a['volume_change_pct']:+.0%}",
            '—' if price_change is None else f'{price_change:+.2f}%',
            format_volume(a.get('today_volume'), unit),
            format_volume(a.get('previous_volume'), unit),
        ])
    return table_messages(title, ['等级', '股票', '量变化', '涨跌幅', '今日量', '昨日量'],
                          rows, left_columns=(0, 1), subtitle='按量变化幅度绝对值降序 · 正值放量，负值缩量')
