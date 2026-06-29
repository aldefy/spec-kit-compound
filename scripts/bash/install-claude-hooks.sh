#!/bin/bash
# scripts/bash/install-claude-hooks.sh
#
# Installer for spec-kit-compound v0.3+ Claude Code hooks.
#
# Invoked by the /speckit-compound-install-hooks slash command.
# Does three things:
#   1. Anchors to the spec-kit project root (.specify/ ancestor)
#   2. Copies the correction-match.sh hook script into the project's
#      .claude/hooks/ directory (creating the dir if needed) and marks it
#      executable
#   3. Merges the hook registration entry into the project's
#      .claude/settings.json (preserving all non-compound entries — C6
#      pragmatic merge)
#
# Idempotent: re-running upgrades our entries to the current template but
# does not duplicate or modify any other user/extension entries.

set -u
set -o pipefail

# ─────────────────────────────────────────────────────────────────
# Anchor to spec-kit project root
# ─────────────────────────────────────────────────────────────────
PROJECT_ROOT="$(pwd)"
while [ "$PROJECT_ROOT" != "/" ] && [ ! -d "$PROJECT_ROOT/.specify" ]; do
  PROJECT_ROOT="$(dirname "$PROJECT_ROOT")"
done
if [ ! -d "$PROJECT_ROOT/.specify" ]; then
  echo "ERROR: not in a spec-kit project (.specify/ not found in any parent of $(pwd))" >&2
  exit 1
fi
cd "$PROJECT_ROOT"

# Locate the installed spec-kit-compound extension dir (has hook source)
EXTENSION_DIR=".specify/extensions/compound"
if [ ! -d "$EXTENSION_DIR" ]; then
  echo "ERROR: spec-kit-compound extension not found at $EXTENSION_DIR" >&2
  echo "Install the extension first: specify extension add <path-or-url>" >&2
  exit 1
fi

HOOK_SRC="$EXTENSION_DIR/.claude/hooks/compound-correction-match.sh"
if [ ! -f "$HOOK_SRC" ]; then
  echo "ERROR: hook source not found at $HOOK_SRC" >&2
  echo "Extension may be installed at an older version that did not ship v0.3 hooks." >&2
  exit 1
fi

# v0.6: planverify PreToolUse gate + its shared lib
PV_HOOK_SRC="$EXTENSION_DIR/.claude/hooks/planverify-pretooluse.sh"
PV_LIB_SRC="$EXTENSION_DIR/scripts/bash/planverify-lib.sh"

# ─────────────────────────────────────────────────────────────────
# Copy hook scripts into project's .claude/hooks/
# ─────────────────────────────────────────────────────────────────
mkdir -p .claude/hooks
cp "$HOOK_SRC" .claude/hooks/compound-correction-match.sh
chmod +x .claude/hooks/compound-correction-match.sh
echo "✓ Installed .claude/hooks/compound-correction-match.sh"

# planverify gate is optional — only present in v0.6+ extensions
if [ -f "$PV_HOOK_SRC" ] && [ -f "$PV_LIB_SRC" ]; then
  cp "$PV_HOOK_SRC" .claude/hooks/planverify-pretooluse.sh
  cp "$PV_LIB_SRC" .claude/hooks/planverify-lib.sh
  chmod +x .claude/hooks/planverify-pretooluse.sh
  echo "✓ Installed .claude/hooks/planverify-pretooluse.sh (+ planverify-lib.sh)"
  INSTALL_PV=1
else
  INSTALL_PV=0
fi

# ─────────────────────────────────────────────────────────────────
# Merge hook entry into .claude/settings.json (C6 pragmatic merge)
# ─────────────────────────────────────────────────────────────────
SETTINGS=".claude/settings.json"
COMPOUND_CMD=".claude/hooks/compound-correction-match.sh"

if ! command -v jq >/dev/null 2>&1; then
  echo "ERROR: jq is required for the installer (settings.json merge)" >&2
  echo "Install with: brew install jq  (macOS) or apt-get install jq  (Debian/Ubuntu)" >&2
  exit 1
fi

# Build the list of compound command paths to (re)install. The planverify
# gate is included only when its hook was copied above.
PV_CMD=".claude/hooks/planverify-pretooluse.sh"
CMDS_JSON=$(jq -n --arg c1 "$COMPOUND_CMD" --arg c2 "$PV_CMD" --argjson pv "$INSTALL_PV" '
  [$c1] + (if $pv == 1 then [$c2] else [] end)
')

# Fresh PreToolUse entries for each command (all match Write|Edit).
NEW_ENTRIES=$(jq -n --argjson cmds "$CMDS_JSON" '
  $cmds | map({ matcher: "Write|Edit", hooks: [{ type: "command", command: . }] })
')

if [ ! -f "$SETTINGS" ]; then
  # First install — create from scratch
  jq -n --argjson entries "$NEW_ENTRIES" '{
    hooks: { PreToolUse: $entries }
  }' > "$SETTINGS"
  echo "✓ Created $SETTINGS with compound hook entries"
else
  # Existing file — pragmatic merge:
  #   1. Drop any existing PreToolUse entry whose command is one of ours
  #   2. Append our fresh entries
  #   3. Preserve everything else byte-for-byte
  TMP="${SETTINGS}.tmp.$$"
  jq --argjson entries "$NEW_ENTRIES" --argjson cmds "$CMDS_JSON" '
    .hooks //= {} |
    .hooks.PreToolUse = (
      ((.hooks.PreToolUse // []) | map(
        select((.hooks // []) | map(.command // "") | any(. as $c | $cmds | index($c)) | not)
      ))
      + $entries
    )
  ' "$SETTINGS" > "$TMP"

  # Validate the result parses
  if ! jq empty < "$TMP" 2>/dev/null; then
    rm -f "$TMP"
    echo "ERROR: merge produced invalid JSON; .claude/settings.json untouched" >&2
    exit 1
  fi

  mv "$TMP" "$SETTINGS"
  echo "✓ Merged compound hook entries into $SETTINGS (other entries preserved)"
fi

echo ""
echo "Active-corrections hook is now wired."
echo ""
echo "Test it:"
echo "  1. Write a correction note in docs/compound/corrections/ with paths: + match: frontmatter"
echo "     (see docs/compound/CORRECTIONS-SCHEMA.md for the format)"
echo "  2. Ask the agent to Write a file matching the correction's paths and content"
echo "  3. The hook should block the Write with the correction's rule + context"
echo ""
echo "Bypass mechanisms:"
echo "  - Per-file:    add a comment '// compound-allow: <correction-slug>' in the file content"
echo "  - Per-session: export COMPOUND_BYPASS=1"

if [ "$INSTALL_PV" = "1" ]; then
  echo ""
  echo "planverify gate (cross-vendor: Claude Code + Codex CLI) is also wired but"
  echo "OFF by default. To enforce it, block source writes until the plan is verified:"
  echo "  export SKC_PLANVERIFY_GATE=block        (or set planverify_gate: block"
  echo "                                           in docs/compound/compound-config.yml)"
  echo "Then a source-file Write/Edit is blocked when the latest /speckit.compound.planverify"
  echo "verdict is missing or BLOCKED_DRIFT. Doc/spec writes are never blocked."
fi
