#!/bin/sh
# PreToolUse(Bash) advisory: warn on `git add -A/.` or `git add` not chained with commit.
# 本仓多 session 并行会在两次工具调用间清空 staged / 裹挟他人在写档（见 dev-environment.md）。
# 纯提醒，不阻断（永远 exit 0，不输出 deny）。
input=$(cat)
cmd=$(printf '%s' "$input" | python -c "import sys,json
try: d=json.load(sys.stdin)
except Exception: d={}
print(d.get('tool_input',{}).get('command',''))" 2>/dev/null)

case "$cmd" in
  *"git add"*) ;;
  *) exit 0 ;;
esac

# "git add ." 仅当 . 后为空格/行尾才算"加当前目录"，避免误判 "git add .claude/..." 等以点开头的精确路径
case "$cmd" in
  *"git add -A"*|*"git add --all"*|*"git add ."|*"git add . "*)
    printf '%s' '{"hookSpecificOutput":{"hookEventName":"PreToolUse","additionalContext":"⚠ 检测到 git add -A/. — 本仓多 session 并行会裹挟他人在写档。铁律：用精确路径，且与 git commit 放进同一条命令链（dev-environment.md）。"}}'
    exit 0 ;;
esac

case "$cmd" in
  *commit*) exit 0 ;;
  *)
    printf '%s' '{"hookSpecificOutput":{"hookEventName":"PreToolUse","additionalContext":"⚠ git add 未与 commit 同链 — 并行 session 会在两次工具调用间清空 staged 导致漏提交。请改为 git add <精确路径> && git commit ...（dev-environment.md）。"}}'
    exit 0 ;;
esac
