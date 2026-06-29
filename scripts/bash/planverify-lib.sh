#!/bin/bash
# scripts/bash/planverify-lib.sh
#
# Shared verdict/config resolution for the planverify gates. Sourced by both
# the spec-kit before_implement gate (planverify-gate.sh) and the cross-vendor
# PreToolUse gate (planverify-pretooluse.sh) so the two never drift apart.
#
# Provides:
#   pv_find_root            -> echoes the spec-kit project root, or "" if none
#   pv_gate_mode <root>     -> echoes "off" | "block"  (env first, then config)
#   pv_latest_verdict <root>-> echoes the verdict of the newest *.planverify.md,
#                              or "" if no report exists

# Walk up from cwd to the directory containing .specify/
pv_find_root() {
  local d="$(pwd)"
  while [ "$d" != "/" ] && [ ! -d "$d/.specify" ]; do
    d="$(dirname "$d")"
  done
  [ -d "$d/.specify" ] && echo "$d" || echo ""
}

# Resolve gate mode: SKC_PLANVERIFY_GATE env wins; else planverify_gate: in
# docs/compound/compound-config.yml; else "off".
pv_gate_mode() {
  local root="$1"
  local gate="${SKC_PLANVERIFY_GATE:-}"
  if [ -z "$gate" ] && [ -f "$root/docs/compound/compound-config.yml" ]; then
    gate="$(grep -E '^[[:space:]]*planverify_gate:' "$root/docs/compound/compound-config.yml" \
            | head -1 | sed -E 's/.*planverify_gate:[[:space:]]*//' | tr -d '"'"'"' \r')"
  fi
  echo "${gate:-off}"
}

# Verdict of the most recent planverify report (lexicographically last filename;
# slugs are typically date- or feature-prefixed). Empty if none exist.
pv_latest_verdict() {
  local root="$1"
  local latest
  latest="$(find "$root/docs/intents" -maxdepth 1 -name '*.planverify.md' -type f 2>/dev/null \
            | sort | tail -1)"
  [ -z "$latest" ] && { echo ""; return; }
  grep -E '^verdict:' "$latest" | head -1 | sed -E 's/^verdict:[[:space:]]*//' | tr -d ' \r'
}
