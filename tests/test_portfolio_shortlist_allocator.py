import pytest

from app.services.portfolio_shortlist.theme_allocator import allocate_weights


THEMES = {
    'ai': {'weight': 0.30, 'name': 'AI'},
    'memory': {'weight': 0.20, 'name': '存储'},
    'gold': {'weight': 0.10, 'name': '黄金'},
}
RULES = {'single_stock_max_pct_of_theme': 0.50, 'share_unit': 100}
TARGET = 100_000


def _by_code(allocations):
    return {a['stock_code']: a for a in allocations}


def test_two_stocks_same_theme_split_by_score():
    # Add a third stock so no single stock exceeds the 50% cap by score proportion
    # scores 40/30/30 → A=40%, B=30%, C=30%; all under 50% cap, proportional split
    selected = [
        {'stock_code': 'A', 'theme': 'ai', 'score': 40, 'current_price': 50},
        {'stock_code': 'B', 'theme': 'ai', 'score': 30, 'current_price': 50},
        {'stock_code': 'C', 'theme': 'ai', 'score': 30, 'current_price': 50},
    ]
    out = allocate_weights(selected, THEMES, TARGET, RULES)
    by = _by_code(out['allocations'])
    assert pytest.approx(by['A']['target_value'], rel=0.05) == 30000 * 40 / 100
    assert pytest.approx(by['B']['target_value'], rel=0.05) == 30000 * 30 / 100
    assert pytest.approx(by['C']['target_value'], rel=0.05) == 30000 * 30 / 100


def test_share_rounding_floors_to_unit():
    selected = [{'stock_code': 'A', 'theme': 'ai', 'score': 100, 'current_price': 33.33}]
    out = allocate_weights(selected, THEMES, TARGET, RULES)
    by = _by_code(out['allocations'])
    assert by['A']['target_shares'] % 100 == 0


def test_single_stock_cap_50pct():
    selected = [{'stock_code': 'A', 'theme': 'ai', 'score': 100, 'current_price': 10}]
    out = allocate_weights(selected, THEMES, TARGET, RULES)
    by = _by_code(out['allocations'])
    assert by['A']['target_value'] <= 15000 + 1
    assert by['A']['capped'] is True
    summary = {s['theme']: s for s in out['theme_summary']}
    assert summary['ai']['cash_buffer'] >= 14000


def test_theme_with_zero_selected_emits_warning():
    selected = [{'stock_code': 'A', 'theme': 'ai', 'score': 80, 'current_price': 50}]
    out = allocate_weights(selected, THEMES, TARGET, RULES)
    warnings_text = ' | '.join(out['warnings'])
    assert 'memory' in warnings_text or '存储' in warnings_text
    assert 'gold' in warnings_text or '黄金' in warnings_text


def test_overflow_redistributes_within_theme():
    selected = [
        {'stock_code': 'A', 'theme': 'ai', 'score': 90, 'current_price': 10},
        {'stock_code': 'B', 'theme': 'ai', 'score': 30, 'current_price': 10},
    ]
    out = allocate_weights(selected, THEMES, TARGET, RULES)
    by = _by_code(out['allocations'])
    assert by['A']['target_value'] <= 15001
    assert by['B']['target_value'] <= 15001
    assert by['A']['capped'] is True
