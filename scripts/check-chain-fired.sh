#!/bin/bash
# scripts/check-chain-fired.sh
#
# Verifies which steps of the spec-kit-compound chain actually wrote their
# artifacts. Run this after /speckit-implement (or after any partial run)
# to see which commands ran and which were silently skipped.
#
# v0.2.1 added this because spec-kit's hook system does not dispatch
# agent-prompt hooks under Claude Code — our commands install fine but
# may not fire when expected, leaving zero artifacts behind. This script
# is the eval that catches that.
#
# Usage:
#   ./scripts/check-chain-fired.sh <feature-slug>
#
# Example:
#   ./scripts/check-chain-fired.sh pro-feature-gating
#
# Output: one line per chain step with ✓ (artifact exists) or
#         ✗ MISSING — <which command didn't run>.
#
# Exit code: 0 if all four artifacts exist, 1 if any are missing.

set -u

SLUG="${1:-}"
if [ -z "$SLUG" ]; then
  echo "Usage: $0 <feature-slug>"
  echo "Example: $0 pro-feature-gating"
  exit 1
fi

SPEC_DIR=$(ls -d "specs/"*"${SLUG}"* 2>/dev/null | head -1)

echo "Compound chain artifacts for '${SLUG}':"

MISSING=0

if [ -f "docs/intents/${SLUG}.intent.md" ]; then
  echo "  ✓ intent.md                    (docs/intents/${SLUG}.intent.md)"
else
  echo "  ✗ intent.md MISSING            — /speckit-compound-intent didn't run or didn't write its artifact"
  MISSING=$((MISSING + 1))
fi

if [ -f "docs/expectations/${SLUG}.expectations.md" ]; then
  echo "  ✓ expectations.md              (docs/expectations/${SLUG}.expectations.md)"
else
  echo "  ✗ expectations.md MISSING      — /speckit-compound-expectations didn't run or didn't write its artifact"
  MISSING=$((MISSING + 1))
fi

if [ -n "$SPEC_DIR" ] && [ -f "$SPEC_DIR/tasks.md" ] && grep -q 'gapfill: derived from' "$SPEC_DIR/tasks.md" 2>/dev/null; then
  echo "  ✓ gapfill additions in tasks.md ($SPEC_DIR/tasks.md)"
else
  echo "  ✗ gapfill additions MISSING    — /speckit-compound-gapfill didn't run (or tasks.md doesn't exist yet)"
  MISSING=$((MISSING + 1))
fi

if [ -f "docs/intents/${SLUG}.intentguard.md" ]; then
  echo "  ✓ intentguard.md               (docs/intents/${SLUG}.intentguard.md)"
else
  echo "  ✗ intentguard.md MISSING       — /speckit-compound-intentguard didn't run or didn't write its verdict"
  MISSING=$((MISSING + 1))
fi

echo ""
echo "Note: /speckit-compound-load and /speckit-compound-writeback don't have"
echo "      single-artifact signals — load injects into context (no file written),"
echo "      writeback drafts ADRs/corrections/patterns under docs/compound/{adr,corrections,patterns}/"
echo "      (check those folders manually for new entries since the last run)."

if [ "$MISSING" -gt 0 ]; then
  echo ""
  echo "Result: $MISSING of 4 chain artifacts missing. Type the missing slash commands manually."
  exit 1
else
  echo ""
  echo "Result: all 4 chain artifacts present. Chain ran end-to-end ✓"
  exit 0
fi
