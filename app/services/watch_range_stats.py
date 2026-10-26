"""盯盘区间统计（7d/30d 最高/最低/VWAP/区间位置）— 纯函数，供每日推送使用"""

WINDOWS = (('7d', 7), ('30d', 30))
MARKET_LABELS = {'A': 'A股', 'HK': '港股', 'KR': '韩股', 'US': '美股'}


def compute_range_stats(rows: list[dict], window: int) -> dict | None:
    """rows 为日 K（date/high/low/close/volume），取最近 window 个交易日"""
    rows = sorted((r for r in rows if r.get('close') is not None), key=lambda r: r['date'])[-window:]
    if not rows:
        return None

    high = max(r['high'] if r.get('high') is not None else r['close'] for r in rows)
    low = min(r['low'] if r.get('low') is not None else r['close'] for r in rows)
    current = rows[-1]['close']

    # VWAP：典型价 (H+L+C)/3 按成交量加权，缺量的日子跳过
    pv = vol = 0.0
    for r in rows:
        v = r.get('volume')
        if not v or r.get('high') is None or r.get('low') is None:
            continue
        pv += (r['high'] + r['low'] + r['close']) / 3 * v
        vol += v
    vwap = pv / vol if vol else None

    position = (current - low) / (high - low) * 100 if high > low else None

    return {
        'high': high, 'low': low, 'current': current, 'vwap': vwap,
        'position': position, 'days': len(rows), 'end_date': rows[-1]['date'],
    }


def fmt_price(value) -> str:
    if value is None:
        return '—'
    return f"{value:,.0f}" if abs(value) >= 1000 else f"{value:.2f}"


def _window_line(label: str, window: int, s: dict) -> str:
    tag = label if s['days'] >= window else f"{label}({s['days']}日)"
    pos = '—' if s['position'] is None else f"{s['position']:.0f}%"
    return (f"  · {tag} 高 {fmt_price(s['high'])} | 低 {fmt_price(s['low'])}"
            f" | 均 {fmt_price(s['vwap'])} | 位置 {pos}")


def format_range_stats(entries: list[dict]) -> list[str]:
    """entries: [{code, name, market, expected_date, stats: {'7d': {...}, '30d': {...}}}]

    expected_date 为该市场最近交易日（'YYYY-MM-DD'），K 线截止早于它时标注截至日期。
    """
    messages = []
    for label, window in WINDOWS:
        group = [e for e in entries if e['stats'].get(label)]
        if not group:
            continue
        group.sort(key=lambda e: (
            e['stats'][label]['position'] is None,
            e['stats'][label]['position'] if e['stats'][label]['position'] is not None else 0,
        ))
        as_of = max(e['stats'][label]['end_date'] for e in group)
        lines = [f"📊 *盯盘区间统计 · {window} 天*（最近 {window} 个交易日，截至 {as_of}）",
                 '按区间位置从低到高排序']
        for e in group:
            main = e['stats'][label]
            stale = ''
            if e.get('expected_date') and main['end_date'] < e['expected_date']:
                stale = f" (截至 {main['end_date'][5:]})"
            market = MARKET_LABELS.get(e['market'], e['market'])
            lines.append(f"*{e['name']}({e['code']})* [{market}]{stale} 当前 {fmt_price(main['current'])}")
            lines.append(_window_line(label, window, main))
        messages.append('\n'.join(lines))
    return messages
