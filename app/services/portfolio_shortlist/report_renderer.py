"""HTML / markdown 渲染。CSS 风格对齐 .claude/skills/portfolio-init/report-template.html。"""

from html import escape


_CSS = """
* { box-sizing: border-box; }
body { font-family: -apple-system, "PingFang SC", sans-serif; max-width: 1180px;
  margin: 0 auto; padding: 0 20px 20px; color: #1f2937; line-height: 1.6; background: #fafafa; }
h1 { font-size: 24px; border-bottom: 2px solid #1f2937; padding-bottom: 8px; margin: 24px 0 4px; }
h2 { font-size: 18px; margin-top: 32px; color: #111827; border-left: 4px solid #2563eb; padding-left: 10px; }
table { border-collapse: collapse; width: 100%; margin: 12px 0; font-size: 13px; background: #fff; }
th, td { border: 1px solid #e5e7eb; padding: 7px 11px; text-align: left; vertical-align: top; }
th { background: #f3f4f6; font-weight: 600; }
.summary { background: #f0f9ff; border: 1px solid #bae6fd; padding: 14px 18px; border-radius: 6px; margin: 14px 0; }
.warn-box { background: #fef3c7; border: 1px solid #fde68a; padding: 12px 16px; border-radius: 6px; margin: 12px 0; }
.tag { display: inline-block; padding: 1px 6px; border-radius: 3px; font-size: 11px; }
.tag-core { background: #dcfce7; color: #166534; }
.tag-config { background: #dbeafe; color: #1e40af; }
.decision-keep { color: #16a34a; font-weight: 600; }
.decision-demote { color: #d97706; }
.decision-capped { color: #dc2626; }
.score-cell { font-weight: 600; color: #1f2937; }
"""


def _e(s) -> str:
    return escape(str(s if s is not None else ''))


def _decision_class(d: str) -> str:
    return {'keep': 'decision-keep', 'demote': 'decision-demote',
            'capped_out': 'decision-capped'}.get(d, '')


def _shortlist_rows(items):
    rows = []
    for s in items:
        b = s['breakdown']
        rating_tag = f'<span class="tag tag-{_e(s["rating"])}">{_e(s["rating"])}</span>'
        doc_links = ' '.join(
            f'<a href="file:///{_e(p)}">&#128196;</a>' for p in s.get('doc_paths', [])
        )
        rows.append(
            f'<tr><td>{_e(s["stock_code"])}</td>'
            f'<td>{_e(s["stock_name"])} {doc_links}</td>'
            f'<td>{_e(s["theme"])}</td>'
            f'<td>{rating_tag}</td>'
            f'<td class="score-cell">{b["total"]}</td>'
            f'<td>{b["base"]}/{b["logic"]}/{b["valuation"]}/{b["catalyst"]}/'
            f'{b["theme_fit"]}/{b["realized"]}/{b["technical"]}</td>'
            f'<td class="{_decision_class(s["decision"])}">{_e(s["decision"])}</td>'
            f'<td>{_e(s["evidence"])}</td></tr>'
        )
    return '\n'.join(rows)


def _allocations_rows(allocs, name_by_code):
    return '\n'.join(
        f'<tr><td>{_e(name_by_code.get(a["stock_code"], a["stock_code"]))}</td>'
        f'<td>{a["weight"]:.1%}</td>'
        f'<td>&#165;{a["target_value"]:,.0f}</td>'
        f'<td>{a["target_shares"]:,}</td>'
        f'<td>&#165;{a["current_price"]:.2f}</td>'
        f'<td>&#165;{a["actual_value"]:,.0f}</td>'
        f'<td>{"&#9888;&#65039; 触顶" if a["capped"] else ""}</td></tr>'
        for a in allocs
    )


def _theme_rows(summary):
    return '\n'.join(
        f'<tr><td>{_e(t["name"])}</td>'
        f'<td>&#165;{t["target_value"]:,.0f}</td>'
        f'<td>&#165;{t["allocated_value"]:,.0f}</td>'
        f'<td>&#165;{t["cash_buffer"]:,.0f}</td>'
        f'<td>{t["n_selected"]}</td></tr>'
        for t in summary
    )


def _demoted_rows(items):
    return '\n'.join(
        f'<tr><td>{_e(s["stock_code"])}</td>'
        f'<td>{_e(s["stock_name"])}</td>'
        f'<td>{_e(s.get("score", ""))}</td>'
        f'<td>{_e(s["reason"])}</td></tr>'
        for s in items
    )


def render_html(payload: dict) -> str:
    warnings_html = ''
    if payload.get('warnings'):
        warnings_html = (
            '<div class="warn-box"><strong>&#9888; 告警</strong><ul>'
            + ''.join(f'<li>{_e(w)}</li>' for w in payload['warnings'])
            + '</ul></div>'
        )

    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8">
<title>持仓精选 — {_e(payload['date'])}</title>
<style>{_CSS}</style></head><body>
<h1>持仓精选 — {_e(payload['date'])}</h1>
<div class="summary">目标总市值 <strong>&#165;{payload['target_value']:,.0f}</strong> |
入选 <strong>{len(payload['shortlist'])}</strong> 只 |
降级观察池 {len(payload['demoted'])} 只 | 硬约束出局 {len(payload['capped_out'])} 只</div>
{warnings_html}

<h2>入选 Top {len(payload['shortlist'])}</h2>
<table><thead><tr><th>代码</th><th>名称</th><th>主题</th><th>评级</th>
<th>总分</th><th>基/逻辑/估/催/题/兑/技</th><th>决定</th><th>证据</th></tr></thead>
<tbody>{_shortlist_rows(payload['shortlist'])}</tbody></table>

<h2>主题分配</h2>
<table><thead><tr><th>主题</th><th>预算</th><th>已分配</th><th>cash buffer</th><th>入选数</th></tr></thead>
<tbody>{_theme_rows(payload['theme_summary'])}</tbody></table>

<h2>个股分配</h2>
<table><thead><tr><th>名称</th><th>权重</th><th>目标市值</th><th>目标股数</th>
<th>现价</th><th>实际市值</th><th>触顶</th></tr></thead>
<tbody>{_allocations_rows(payload['allocations'], {s['stock_code']: s['stock_name'] for s in payload['shortlist']})}</tbody></table>

<h2>降级观察池（未入 Top）</h2>
<table><thead><tr><th>代码</th><th>名称</th><th>得分</th><th>原因</th></tr></thead>
<tbody>{_demoted_rows(payload['demoted'])}</tbody></table>

<h2>硬约束出局（100 股触顶）</h2>
<table><thead><tr><th>代码</th><th>名称</th><th>得分</th><th>原因</th></tr></thead>
<tbody>{_demoted_rows(payload['capped_out'])}</tbody></table>

<footer style="margin-top:48px;color:#9ca3af;font-size:12px;text-align:center">
生成时间 {_e(payload['date'])} | 数据源 data/private.db | 由 portfolio_shortlist 模块生成
</footer>
</body></html>"""


def render_markdown(payload: dict) -> str:
    lines = [
        f"# 持仓精选 — {payload['date']}",
        '',
        f"目标总市值 **¥{payload['target_value']:,.0f}** | "
        f"入选 **{len(payload['shortlist'])}** 只 | "
        f"降级 {len(payload['demoted'])} 只 | 出局 {len(payload['capped_out'])} 只",
        '',
    ]
    if payload.get('warnings'):
        lines.append('## ⚠️ 告警')
        for w in payload['warnings']:
            lines.append(f'- {w}')
        lines.append('')

    lines.extend([
        f"## 入选 Top {len(payload['shortlist'])}", '',
        '| 代码 | 名称 | 主题 | 评级 | 总分 | 决定 | 证据 |',
        '|---|---|---|---|---|---|---|',
    ])
    for s in payload['shortlist']:
        lines.append(
            f"| {s['stock_code']} | {s['stock_name']} | {s['theme']} | "
            f"{s['rating']} | {s['breakdown']['total']} | "
            f"{s['decision']} | {s['evidence']} |"
        )
    lines.append('')

    lines.extend([
        '## 主题分配', '',
        '| 主题 | 预算 | 已分配 | cash buffer | 入选数 |',
        '|---|---|---|---|---|',
    ])
    for t in payload['theme_summary']:
        lines.append(
            f"| {t['name']} | ¥{t['target_value']:,.0f} | "
            f"¥{t['allocated_value']:,.0f} | ¥{t['cash_buffer']:,.0f} | {t['n_selected']} |"
        )
    return '\n'.join(lines)
