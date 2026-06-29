#!/bin/bash
# scripts/bash/planverify-gate.sh
#
# spec-kit before_implement gate (Claude + spec-kit). Optionally blocks
# /speckit-implement until the latest planverify verdict is acceptable.
#
# This is the phase-boundary half of the belt-and-suspenders gate. The
# cross-vendor half (works for BOTH Claude Code and Codex CLI) is the
# PreToolUse hook planverify-pretooluse.sh. spec-kit before_* hooks fire
# only when the user runs spec-kit slash commands under a harness that
# dispatches them — i.e. Claude + spec-kit — so this gate is a bonus, not
# the primary enforcement path.
#
# Default behavior is OFF (no-op) — consistent with every other compound
# command being advisory. Opt in via:
#   SKC_PLANVERIFY_GATE=block   (env), or
#   planverify_gate: block      (docs/compound/compound-config.yml)
#
# When 'block':
#   - missing planverify report           -> exit 1 (run planverify first)
#   - verdict: BLOCKED_DRIFT               -> exit 1 (replan first)
#   - verdict: PASS | REPLAN_ALLOWED       -> exit 0 (proceed)
#
# Shell script, not an agent-prompt hook: agent-prompt hooks silently no-op
# under spec-kit's executor (verified v0.2.1). Mirrors require-intent.sh.

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/bash/planverify-lib.sh
. "$SCRIPT_DIR/planverify-lib.sh"

ROOT="$(pv_find_root)"
if [ -z "$ROOT" ]; then
  echo "ERROR: not in a spec-kit project (.specify/ not found in any parent of $(pwd))"
  exit 1
fi
cd "$ROOT"

GATE="$(pv_gate_mode "$ROOT")"

# Default (off): no-op, let implement proceed
if [ "$GATE" != "block" ]; then
  exit 0
fi

VERDICT="$(pv_latest_verdict "$ROOT")"

if [ -z "$VERDICT" ]; then
  echo ""
  echo "  ⚠  SKC_PLANVERIFY_GATE=block but no planverify report exists."
  echo ""
  echo "  Run /speckit.compound.planverify before /speckit-implement."
  echo ""
  exit 1
fi

if [ "$VERDICT" = "BLOCKED_DRIFT" ]; then
  echo ""
  echo "  ⛔ Plan verdict is BLOCKED_DRIFT."
  echo ""
  echo "  The proposed plan drifts outside locked intent. Replan before"
  echo "  implementing: re-run /speckit-plan, then /speckit.compound.planverify."
  echo ""
  exit 1
fi

echo "✓ planverify verdict: ${VERDICT} — /speckit-implement may proceed."
exit 0
