#!/bin/bash
# tests/correction-hook.test.sh — assertions for the active-corrections PreToolUse hook.
set -u
FAILS=0
REPO="$(cd "$(dirname "$0")/.." && pwd)"
HOOK="$REPO/.claude/hooks/compound-correction-match.sh"

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
mkdir -p "$WORK/.specify" "$WORK/docs/compound/corrections"
C="$WORK/docs/compound/corrections"

# usage: run_hook <file_path> <content>  -> prints "<exit>|<stderr>"
run_hook() {
  local json err code
  json="$(jq -n --arg fp "$1" --arg c "$2" '{tool_name:"Write",tool_input:{file_path:$fp,content:$c}}')"
  err="$( cd "$WORK" && printf '%s' "$json" | bash "$HOOK" 2>&1 >/dev/null )"; code=$?
  printf '%s|%s' "$code" "$err"
}

assert_eq() { # actual expected label
  if [ "$1" = "$2" ]; then echo "ok   - $3";
  else echo "FAIL - $3 (got '$1', want '$2')"; FAILS=$((FAILS+1)); fi
}

cat > "$C/2026-01-01-no-filter.md" <<'EOF'
---
slug: 2026-01-01-no-filter
paths:
  - "**/*.css"
match: 'filter:[[:space:]]*brightness'
rule: "No CSS brightness filters."
context: "Past mistake."
---
# Correction
EOF

echo "# enforceable correction"
R="$(run_hook src/a.css 'img { filter: brightness(0.8) }')"
assert_eq "${R%%|*}" 2 "matching write is blocked"
R="$(run_hook src/a.css 'img { color: red }')"
assert_eq "$R" "0|" "non-matching write passes silently"
R="$(run_hook src/a.css '/* compound-allow: 2026-01-01-no-filter */ img { filter: brightness(0.8) }')"
assert_eq "${R%%|*}" 0 "compound-allow bypass passes"

echo "# context-only correction (v0.8 unenforceable_reason)"
cat > "$C/2026-01-02-judgement.md" <<'EOF'
---
slug: 2026-01-02-judgement
unenforceable_reason: "Naming judgement; no syntactic form."
---
# Correction
EOF
R="$(run_hook src/a.css 'img { color: red }')"
assert_eq "$R" "0|" "unenforceable_reason correction is skipped without warning"

echo "# malformed correction still warns (F12)"
cat > "$C/2026-01-03-broken.md" <<'EOF'
---
slug: 2026-01-03-broken
paths:
  - "**/*.css"
---
# Correction
EOF
R="$(run_hook src/a.css 'img { color: red }')"
assert_eq "${R%%|*}" 0 "malformed correction does not block"
case "$R" in *"incomplete frontmatter"*) echo "ok   - malformed correction warns";;
  *) echo "FAIL - malformed correction warns (got '$R')"; FAILS=$((FAILS+1));; esac

echo "---"
[ "$FAILS" -eq 0 ] && { echo "ALL PASS"; exit 0; } || { echo "$FAILS FAILED"; exit 1; }
