#!/bin/bash
# tests/planverify-gate.test.sh — assertions for both planverify gates.
set -u
FAILS=0
REPO="$(cd "$(dirname "$0")/.." && pwd)"
GATE="$REPO/scripts/bash/planverify-gate.sh"            # spec-kit before_implement
HOOK="$REPO/.claude/hooks/planverify-pretooluse.sh"     # cross-vendor PreToolUse

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
mkdir -p "$WORK/.specify" "$WORK/docs/intents" "$WORK/docs/compound"

set_verdict() { printf 'verdict: %s\n' "$1" > "$WORK/docs/intents/foo.planverify.md"; }
clear_verdict() { rm -f "$WORK"/docs/intents/*.planverify.md; }

# run the before_implement gate
run_gate() { ( cd "$WORK" && env "$@" bash "$GATE" >/dev/null 2>&1 ); echo $?; }

# run the PreToolUse hook with a synthetic tool-call JSON on stdin
# usage: run_hook <file_path> ENV=val...
run_hook() {
  local fp="$1"; shift
  local json
  json="$(printf '{"tool_name":"Write","tool_input":{"file_path":"%s","content":"x"}}' "$fp")"
  ( cd "$WORK" && printf '%s' "$json" | env "$@" bash "$HOOK" >/dev/null 2>&1 ); echo $?
}

assert_eq() { # actual expected label
  if [ "$1" = "$2" ]; then echo "ok   - $3";
  else echo "FAIL - $3 (got $1, want $2)"; FAILS=$((FAILS+1)); fi
}

echo "# before_implement gate"
# 1. default off -> allow
clear_verdict
assert_eq "$(run_gate SKC_PLANVERIFY_GATE=)" 0 "gate: default off => allow"
# 2. block + no report -> deny
assert_eq "$(run_gate SKC_PLANVERIFY_GATE=block)" 1 "gate: block + no report => deny"
# 3. block + BLOCKED_DRIFT -> deny
set_verdict BLOCKED_DRIFT
assert_eq "$(run_gate SKC_PLANVERIFY_GATE=block)" 1 "gate: block + BLOCKED_DRIFT => deny"
# 4. block + PASS -> allow
set_verdict PASS
assert_eq "$(run_gate SKC_PLANVERIFY_GATE=block)" 0 "gate: block + PASS => allow"
# 5. block + REPLAN_ALLOWED -> allow
set_verdict REPLAN_ALLOWED
assert_eq "$(run_gate SKC_PLANVERIFY_GATE=block)" 0 "gate: block + REPLAN_ALLOWED => allow"
# 6. config file drives it (no env)
printf 'planverify_gate: block\n' > "$WORK/docs/compound/compound-config.yml"
set_verdict BLOCKED_DRIFT
assert_eq "$(run_gate SKC_PLANVERIFY_GATE=)" 1 "gate: config block + BLOCKED_DRIFT => deny"
# 7. env off overrides config block
assert_eq "$(run_gate SKC_PLANVERIFY_GATE=off)" 0 "gate: env off overrides config block"
rm -f "$WORK/docs/compound/compound-config.yml"

echo "# PreToolUse hook (cross-vendor)"
# 8. default off -> allow source write
clear_verdict
assert_eq "$(run_hook src/foo.ts SKC_PLANVERIFY_GATE=)" 0 "hook: default off => allow source write"
# 9. block + no report + SOURCE write -> deny (exit 2)
assert_eq "$(run_hook src/foo.ts SKC_PLANVERIFY_GATE=block)" 2 "hook: block + no report + source => deny"
# 10. block + no report + DOC write -> allow (exempt path)
assert_eq "$(run_hook docs/intents/foo.intent.md SKC_PLANVERIFY_GATE=block)" 0 "hook: block + doc path => allow (exempt)"
# 11. block + no report + specs write -> allow (exempt)
assert_eq "$(run_hook specs/foo/plan.md SKC_PLANVERIFY_GATE=block)" 0 "hook: block + specs path => allow (exempt)"
# 12. block + BLOCKED_DRIFT + source -> deny
set_verdict BLOCKED_DRIFT
assert_eq "$(run_hook src/foo.ts SKC_PLANVERIFY_GATE=block)" 2 "hook: block + BLOCKED_DRIFT + source => deny"
# 13. block + PASS + source -> allow
set_verdict PASS
assert_eq "$(run_hook src/foo.ts SKC_PLANVERIFY_GATE=block)" 0 "hook: block + PASS + source => allow"
# 14. COMPOUND_BYPASS=1 overrides block
set_verdict BLOCKED_DRIFT
assert_eq "$(run_hook src/foo.ts SKC_PLANVERIFY_GATE=block COMPOUND_BYPASS=1)" 0 "hook: COMPOUND_BYPASS overrides block"

echo "---"
[ "$FAILS" -eq 0 ] && { echo "ALL PASS"; exit 0; } || { echo "$FAILS FAILED"; exit 1; }
