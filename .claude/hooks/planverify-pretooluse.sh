#!/bin/bash
# .claude/hooks/planverify-pretooluse.sh
#
# Cross-vendor PreToolUse gate for planverify (Claude Code AND Codex CLI —
# both ship a PreToolUse event with the same stdin-JSON / exit-2 contract;
# Gemini's BeforeTool is compatible too). This is the PRIMARY enforcement
# path because spec-kit's before_implement hook only fires under Claude +
# spec-kit, whereas this fires for any harness on any source-file write.
#
# Behavior (only when block-mode is on):
#   - acts on Write/Edit to a SOURCE file (docs/, specs/, .specify/, .claude/,
#     and dotfiles are exempt so we never block writing the plan itself or the
#     planverify artifacts)
#   - if the latest planverify verdict is missing or BLOCKED_DRIFT -> exit 2
#     (blocks the write; stderr explains why and how to proceed)
#   - otherwise -> exit 0
#
# Default (gate off) and every non-source / non-Write path -> exit 0 (no-op).
# Fail-open on anything we can't evaluate so we never wedge the agent loop.
#
# Opt in via SKC_PLANVERIFY_GATE=block (env) or planverify_gate: block
# (docs/compound/compound-config.yml). Session bypass: COMPOUND_BYPASS=1.

set -u

# Session-wide bypass (shared with the corrections hook)
if [ "${COMPOUND_BYPASS:-0}" = "1" ]; then
  exit 0
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# planverify-lib.sh lives in the extension's scripts/bash/. When this hook is
# installed into a project's .claude/hooks/, the lib is copied alongside it.
if [ -f "$SCRIPT_DIR/planverify-lib.sh" ]; then
  . "$SCRIPT_DIR/planverify-lib.sh"
elif [ -f "$SCRIPT_DIR/../../scripts/bash/planverify-lib.sh" ]; then
  . "$SCRIPT_DIR/../../scripts/bash/planverify-lib.sh"
else
  # Lib missing — cannot evaluate; fail open.
  exit 0
fi

ROOT="$(pv_find_root)"
if [ -z "$ROOT" ]; then
  exit 0  # not a spec-kit project; nothing to gate
fi
cd "$ROOT"

GATE="$(pv_gate_mode "$ROOT")"
if [ "$GATE" != "block" ]; then
  exit 0  # advisory mode (default): never block
fi

# Parse the tool call from stdin (Claude & Codex both pass JSON on stdin).
if ! command -v jq >/dev/null 2>&1; then
  exit 0  # can't parse; fail open
fi

INPUT="$(cat)"
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // ""' 2>/dev/null)
case "$TOOL_NAME" in
  Write|Edit) ;;
  *) exit 0 ;;
esac

FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // ""' 2>/dev/null)
[ -z "$FILE_PATH" ] && exit 0

# Normalize to a path relative to project root
FILE_REL="$FILE_PATH"
if [[ "$FILE_REL" == "$ROOT"* ]]; then
  FILE_REL="${FILE_REL#$ROOT/}"
fi

# Exempt non-source paths: writing the plan, the planverify artifacts, specs,
# the spec-kit/harness config, and dotfiles must never be blocked.
case "$FILE_REL" in
  docs/*|specs/*|.specify/*|.claude/*|.codex/*|.gemini/*|.*) exit 0 ;;
esac

# This is a source-file write under block mode. Check the verdict.
VERDICT="$(pv_latest_verdict "$ROOT")"

if [ -z "$VERDICT" ]; then
  {
    echo ""
    echo "Blocked: planverify gate is ON (block) but no plan has been verified."
    echo "Proposed $TOOL_NAME on source file: $FILE_REL"
    echo ""
    echo "Run /speckit.compound.planverify to judge the plan against locked intent"
    echo "before writing source. To bypass for this session: COMPOUND_BYPASS=1."
  } >&2
  exit 2
fi

if [ "$VERDICT" = "BLOCKED_DRIFT" ]; then
  {
    echo ""
    echo "Blocked: planverify verdict is BLOCKED_DRIFT."
    echo "Proposed $TOOL_NAME on source file: $FILE_REL"
    echo ""
    echo "The proposed plan drifts outside locked intent. Replan first:"
    echo "re-run /speckit-plan, then /speckit.compound.planverify."
    echo "To bypass for this session: COMPOUND_BYPASS=1."
  } >&2
  exit 2
fi

# PASS or REPLAN_ALLOWED -> allow the write
exit 0
