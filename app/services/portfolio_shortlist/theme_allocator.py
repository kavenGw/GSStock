"""入选股按打分归一化分配主题内 StockWeight，触顶截顶 + 溢出回流。

spec §3.1, §4
"""

from collections import defaultdict
from math import floor


def _round_shares(value: float, price: float, unit: int) -> int:
    if price <= 0:
        return 0
    raw = value / price
    return int(floor(raw / unit + 1e-6) * unit)


def _allocate_in_theme(
    stocks: list,
    theme_budget: float,
    cap_pct: float,
    share_unit: int,
) -> tuple:
    """主题内按 score 归一化分配 + 触顶截顶 + 溢出回流。"""
    if not stocks:
        return [], theme_budget

    cap_value = theme_budget * cap_pct
    total_score = sum(s['score'] for s in stocks)
    if total_score <= 0:
        return [], theme_budget

    targets = {s['stock_code']: theme_budget * s['score'] / total_score for s in stocks}
    capped = set()
    overflow = 0.0

    for code in list(targets):
        if targets[code] > cap_value:
            overflow += targets[code] - cap_value
            targets[code] = cap_value
            capped.add(code)

    while overflow > 1e-3:
        remaining = [s for s in stocks if s['stock_code'] not in capped]
        if not remaining:
            break
        rem_total = sum(s['score'] for s in remaining)
        new_cap_hits = []
        for s in remaining:
            share = overflow * s['score'] / rem_total
            new_target = targets[s['stock_code']] + share
            if new_target > cap_value:
                new_cap_hits.append((s['stock_code'], new_target - cap_value))
                targets[s['stock_code']] = cap_value
                capped.add(s['stock_code'])
            else:
                targets[s['stock_code']] = new_target
        if not new_cap_hits:
            overflow = 0
        else:
            overflow = sum(o for _, o in new_cap_hits)

    allocations = []
    allocated_value = 0.0
    for s in stocks:
        code = s['stock_code']
        tv = targets[code]
        shares = _round_shares(tv, s['current_price'], share_unit)
        actual_value = shares * s['current_price']
        allocations.append({
            'stock_code': code,
            'theme': s['theme'],
            'weight': round(tv / theme_budget, 6) if theme_budget > 0 else 0,
            'target_value': round(tv, 2),
            'target_shares': shares,
            'actual_value': round(actual_value, 2),
            'current_price': s['current_price'],
            'score': s['score'],
            'capped': code in capped,
        })
        allocated_value += actual_value

    cash_buffer = round(theme_budget - allocated_value, 2)
    return allocations, cash_buffer


def allocate_weights(
    selected: list,
    themes_config: dict,
    target_value: float,
    rules: dict,
) -> dict:
    cap_pct = rules.get('single_stock_max_pct_of_theme', 0.50)
    share_unit = rules.get('share_unit', 100)

    by_theme = defaultdict(list)
    for s in selected:
        by_theme[s['theme']].append(s)

    all_allocations = []
    theme_summary = []
    warnings = []

    for theme_key, cfg in themes_config.items():
        budget = target_value * cfg['weight']
        stocks = by_theme.get(theme_key, [])
        if not stocks:
            warnings.append(
                f'主题 {theme_key} ({cfg.get("name", theme_key)}) 当前 0 只入选 — '
                f'¥{budget:,.0f} 预算需用户决策（合并到其他主题 / 保留 cash buffer）'
            )
            theme_summary.append({
                'theme': theme_key, 'name': cfg.get('name', theme_key),
                'target_value': budget, 'allocated_value': 0,
                'cash_buffer': budget, 'n_selected': 0,
            })
            continue

        allocs, buffer = _allocate_in_theme(stocks, budget, cap_pct, share_unit)
        all_allocations.extend(allocs)
        theme_summary.append({
            'theme': theme_key, 'name': cfg.get('name', theme_key),
            'target_value': budget,
            'allocated_value': round(budget - buffer, 2),
            'cash_buffer': buffer, 'n_selected': len(stocks),
        })

    return {
        'allocations': all_allocations,
        'theme_summary': theme_summary,
        'warnings': warnings,
    }
