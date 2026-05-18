import re

from app.services.portfolio_shortlist.report_renderer import render_html, render_markdown


SAMPLE = {
    'date': '2026-05-10',
    'target_value': 433765,
    'shortlist': [
        {
            'stock_code': '601138', 'stock_name': '工业富联', 'theme': 'ai_compute',
            'rating': 'core',
            'breakdown': {'total': 92.5, 'base': 50, 'logic': 13, 'valuation': 8,
                          'catalyst': 9, 'theme_fit': 5, 'realized': 2.5, 'technical': 5},
            'decision': 'keep',
            'evidence': '工业富联 × ORCL 走势相关性 465 配对交易日',
            'doc_paths': ['docs/stock-analytics/cross-sector/2026-05-09-工业富联-甲骨文-走势相关性专题.md'],
        },
    ],
    'demoted': [
        {'stock_code': '600600', 'stock_name': '青岛啤酒', 'reason': '主题外溢，估值偏中性',
         'score': 55.0},
    ],
    'capped_out': [
        {'stock_code': '300476', 'stock_name': '胜宏科技',
         'reason': '100 股市值 ¥35,866 < 主题上限 ¥65,065 但优先级低于其他 core'},
    ],
    'allocations': [
        {'stock_code': '601138', 'theme': 'ai_compute', 'weight': 0.34,
         'target_value': 44296, 'target_shares': 700, 'actual_value': 44296,
         'current_price': 63.28, 'score': 92.5, 'capped': False},
    ],
    'theme_summary': [
        {'theme': 'ai_compute', 'name': 'AI 算力', 'target_value': 130130,
         'allocated_value': 44296, 'cash_buffer': 85834, 'n_selected': 1},
    ],
    'warnings': ['主题 gold_defense (黄金防御) 当前 0 只入选 — ¥43,376 预算需用户决策'],
}


def test_render_html_returns_valid_doc():
    html = render_html(SAMPLE)
    assert html.startswith('<!DOCTYPE html>')
    assert '工业富联' in html
    assert '92.5' in html
    assert '主题 gold_defense' in html
    assert 'docs/stock-analytics/cross-sector/2026-05-09-工业富联' in html


def test_render_html_demoted_section():
    html = render_html(SAMPLE)
    assert '青岛啤酒' in html
    assert '主题外溢' in html


def test_render_markdown_has_tables():
    md = render_markdown(SAMPLE)
    assert '|' in md
    assert '工业富联' in md
    assert '## ' in md


def test_warning_block_visible():
    html = render_html(SAMPLE)
    assert re.search(r'class="[^"]*warn', html)


def test_allocations_table_shows_stock_name():
    html = render_html(SAMPLE)
    m = re.search(r'<h2>个股分配</h2>(.*?)<h2>', html, re.DOTALL)
    assert m, '个股分配 section not found'
    section = m.group(1)
    assert '工业富联' in section, 'stock name missing in allocations table'
    assert '601138' not in section, 'stock code should not appear in allocations row'


def test_allocations_table_fallbacks_to_code_when_name_missing():
    payload = {**SAMPLE, 'allocations': [
        {'stock_code': '999999', 'theme': 'x', 'weight': 0.1,
         'target_value': 1000, 'target_shares': 100, 'actual_value': 1000,
         'current_price': 10.0, 'score': 1, 'capped': False},
    ]}
    html = render_html(payload)
    m = re.search(r'<h2>个股分配</h2>(.*?)<h2>', html, re.DOTALL)
    assert '999999' in m.group(1)
