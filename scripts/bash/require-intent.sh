#!/bin/bash
# scripts/bash/require-intent.sh
#
# Gate hook: refuses to let /speckit-specify proceed if no intent doc exists.
# Registered as before_specify hook in extension.yml (v0.2.2+).
#
# Spec-kit's hook executor dispatches shell-script hooks cleanly under
# Claude Code (verified: bundled git extension's hooks fire correctly).
# Agent-prompt hooks (our interactive /speckit-compound-intent) do NOT
# dispatch under the same executor. By making this gate a shell script,
# we get reliable hook firing — the gate blocks /speckit-specify, the
# user types /speckit-compound-intent manually, then re-runs /speckit-specify.
#
# Behavior:
#   - Walks up from cwd to find the spec-kit project root (.specify/)
#   - Checks docs/intents/ for any *.intent.md file
#   - Exits 0 if at least one exists; exits 1 with message otherwise

set -u

# Find project root by walking up from cwd
PROJECT_ROOT="$(pwd)"
while [ "$PROJECT_ROOT" != "/" ] && [ ! -d "$PROJECT_ROOT/.specify" ]; do
  PROJECT_ROOT="$(dirname "$PROJECT_ROOT")"
done

if [ ! -d "$PROJECT_ROOT/.specify" ]; then
  echo "ERROR: not in a spec-kit project (.specify/ not found in any parent of $(pwd))"
  exit 1
fi

cd "$PROJECT_ROOT"

# Check for any intent doc
if [ ! -d "docs/intents" ]; then
  echo ""
  echo "  ⚠  No intent docs found (docs/intents/ does not exist)."
  echo ""
  echo "  Run /speckit-compound-intent BEFORE /speckit-specify to capture"
  echo "  the goal, constraints, and failure conditions for this feature."
  echo ""
  echo "  This is mandatory per the spec-kit-compound extension's discipline."
  echo "  /speckit-specify will not proceed until at least one intent doc exists."
  echo ""
  exit 1
fi

INTENT_COUNT=$(find docs/intents -maxdepth 1 -name "*.intent.md" -type f 2>/dev/null | wc -l | tr -d ' ')

if [ "$INTENT_COUNT" -eq 0 ]; then
  echo ""
  echo "  ⚠  docs/intents/ exists but contains no *.intent.md files."
  echo ""
  echo "  Run /speckit-compound-intent BEFORE /speckit-specify."
  echo ""
  exit 1
fi

# At least one intent doc exists; let /speckit-specify proceed
echo "✓ Found $INTENT_COUNT intent doc(s) in docs/intents/ — /speckit-specify may proceed."
exit 0
