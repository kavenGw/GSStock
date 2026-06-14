#!/bin/sh
# PostToolUse(Write|Edit) advisory: 改了 docs/stock-analytics 分析档时，提醒收尾跑 lint。
# 不执行 lint（避免半成品误报）、不阻断、无 loop —— 仅在正确时机抬高 lint 的存在感。
input=$(cat)
fp=$(printf '%s' "$input" | python -c "import sys,json
try: d=json.load(sys.stdin)
except Exception: d={}
print(d.get('tool_input',{}).get('file_path',''))" 2>/dev/null)

case "$fp" in
  *docs/stock-analytics*)
    printf '%s' '{"hookSpecificOutput":{"hookEventName":"PostToolUse","additionalContext":"📝 改了 docs/stock-analytics 分析档 — 收尾前跑 lint：PYTHONIOENCODING=utf-8 python scripts/lint_docs_frontmatter.py 与 scripts/lint_docs_refs.py；只精确 git add 本任务档（勿 -A）；related_docs symmetric=true 需补兄弟档反向条目（先 grep 防重复）。"}}'
    ;;
esac
exit 0
