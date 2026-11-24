"""Slack 数值列表表格及纯文本回退。"""
from datetime import datetime, timedelta, timezone

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


def format_binance_summary(rows: list[dict], title: str) -> list[dict]:
    ordered = sorted(rows, key=lambda r: (not r['available'],
                                         -r['change_pct'] if r['available'] else 0))
    table_rows = []
    for row in ordered:
        if row['available']:
            price = f"{row['price']:g} {row['price_unit']}"
            change = f"{row['change_pct']:+.2f}%"
            status = '交易中'
        else:
            price = change = '—'
            updated = row.get('updated_at')
            last = (datetime.fromtimestamp(updated, timezone(timedelta(hours=8)))
                    .strftime('%m-%d %H:%M')) if updated else '暂无'
            status = f'行情不可用（最后更新 {last}）'
        table_rows.append([row['name'], row['symbol'], price, change, status])
    return table_messages(title, ['标的', '合约', '最新价', '24小时涨跌', '状态'],
                          table_rows, left_columns=(0, 1, 4),
                          subtitle='按滚动 24 小时涨跌幅降序 · 不可用行情置底')


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
