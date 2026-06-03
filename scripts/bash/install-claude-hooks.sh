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

# ─────────────────────────────────────────────────────────────────
# Copy hook script into project's .claude/hooks/
# ─────────────────────────────────────────────────────────────────
mkdir -p .claude/hooks
cp "$HOOK_SRC" .claude/hooks/compound-correction-match.sh
chmod +x .claude/hooks/compound-correction-match.sh
echo "✓ Installed .claude/hooks/compound-correction-match.sh"

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

# Build the entry we want to install
NEW_ENTRY=$(jq -n --arg cmd "$COMPOUND_CMD" '{
  matcher: "Write|Edit",
  hooks: [{ type: "command", command: $cmd }]
}')

if [ ! -f "$SETTINGS" ]; then
  # First install — create from scratch
  jq -n --argjson entry "$NEW_ENTRY" '{
    hooks: { PreToolUse: [$entry] }
  }' > "$SETTINGS"
  echo "✓ Created $SETTINGS with compound hook entry"
else
  # Existing file — pragmatic merge:
  #   1. Find any existing PreToolUse entry whose hooks[0].command equals ours, remove it
  #   2. Append our fresh entry
  #   3. Preserve everything else
  TMP="${SETTINGS}.tmp.$$"
  jq --argjson entry "$NEW_ENTRY" --arg cmd "$COMPOUND_CMD" '
    .hooks //= {} |
    .hooks.PreToolUse = (
      ((.hooks.PreToolUse // []) | map(
        select((.hooks // []) | map(.command // "") | all(. != $cmd))
      ))
      + [$entry]
    )
  ' "$SETTINGS" > "$TMP"

  # Validate the result parses
  if ! jq empty < "$TMP" 2>/dev/null; then
    rm -f "$TMP"
    echo "ERROR: merge produced invalid JSON; .claude/settings.json untouched" >&2
    exit 1
  fi

  mv "$TMP" "$SETTINGS"
  echo "✓ Merged compound hook entry into $SETTINGS (other entries preserved)"
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
