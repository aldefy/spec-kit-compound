#!/bin/bash
# .claude/hooks/compound-correction-match.sh
#
# Claude Code PreToolUse hook for spec-kit-compound v0.3+ (active-corrections).
#
# Reads tool_input JSON via stdin. For Write/Edit operations, checks the
# proposed file path + content against every correction in
# docs/compound/corrections/{*.md}. If any correction matches (paths: glob
# matches the file path AND match: regex matches the content), blocks the
# tool call (exit 2) and writes a structured stderr message Claude can read
# and act on.
#
# Implements:
#   C1 — Hook execution time < 250ms p95 (achieved via early-exit on
#         non-matching paths and avoiding LLM calls)
#   C3 — stderr block message includes correction file path + matched rule
#         text + one-line context
#   C4 — Honors per-file `// compound-allow: <correction-slug>` escape
#         hatch + `COMPOUND_BYPASS=1` env var session bypass
#   C5 — Correction-note schema: YAML frontmatter with `paths:` glob array,
#         `match:` regex string, `rule:` one-line directive, `context:` one
#         line of background
#
# Failure conditions covered:
#   F11 — Graceful no-op when docs/compound/corrections/ is empty/missing
#   F12 — Warns (does not silently skip) on correction with malformed
#         frontmatter

set -u
set -o pipefail

# ─────────────────────────────────────────────────────────────────
# Session-wide bypass (C4)
# ─────────────────────────────────────────────────────────────────
if [ "${COMPOUND_BYPASS:-0}" = "1" ]; then
  exit 0
fi

# ─────────────────────────────────────────────────────────────────
# Project root anchor (v0.2.2 cwd fix applies here too)
# ─────────────────────────────────────────────────────────────────
PROJECT_ROOT="$(pwd)"
while [ "$PROJECT_ROOT" != "/" ] && [ ! -d "$PROJECT_ROOT/.specify" ]; do
  PROJECT_ROOT="$(dirname "$PROJECT_ROOT")"
done
if [ ! -d "$PROJECT_ROOT/.specify" ]; then
  # Not a spec-kit project; no corrections to check; let the write proceed.
  exit 0
fi
cd "$PROJECT_ROOT"

CORRECTIONS_DIR="docs/compound/corrections"

# ─────────────────────────────────────────────────────────────────
# Graceful no-op when no corrections exist (F11)
# ─────────────────────────────────────────────────────────────────
if [ ! -d "$CORRECTIONS_DIR" ]; then
  exit 0
fi
shopt -s nullglob
CORRECTION_FILES=("$CORRECTIONS_DIR"/*.md)
shopt -u nullglob
if [ "${#CORRECTION_FILES[@]}" -eq 0 ]; then
  exit 0
fi

# ─────────────────────────────────────────────────────────────────
# Parse tool input from stdin (Claude Code passes JSON via stdin)
# ─────────────────────────────────────────────────────────────────
if ! command -v jq >/dev/null 2>&1; then
  # jq missing — can't parse stdin; fail-open so we don't break the agent
  echo "compound-correction-match: jq not installed; skipping (install jq to enable)" >&2
  exit 0
fi

INPUT="$(cat)"
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // ""' 2>/dev/null)

# Only act on file-writing tools
case "$TOOL_NAME" in
  Write|Edit) ;;
  *) exit 0 ;;
esac

FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // ""' 2>/dev/null)
if [ "$TOOL_NAME" = "Write" ]; then
  CONTENT=$(echo "$INPUT" | jq -r '.tool_input.content // ""' 2>/dev/null)
else
  CONTENT=$(echo "$INPUT" | jq -r '.tool_input.new_string // ""' 2>/dev/null)
fi

if [ -z "$FILE_PATH" ]; then
  exit 0
fi

# Normalize file path relative to project root for glob matching
FILE_REL="$FILE_PATH"
if [[ "$FILE_REL" == "$PROJECT_ROOT"* ]]; then
  FILE_REL="${FILE_REL#$PROJECT_ROOT/}"
fi

# ─────────────────────────────────────────────────────────────────
# For each correction, parse frontmatter and check for a match
# ─────────────────────────────────────────────────────────────────
MATCHES=()
WARNINGS=()

for CORR in "${CORRECTION_FILES[@]}"; do
  CORR_BASENAME=$(basename "$CORR" .md)

  # Extract YAML frontmatter (between first two `---` lines)
  FM=$(awk '/^---$/{c++; if(c==1) next; if(c==2) exit} c==1' "$CORR" 2>/dev/null)

  if [ -z "$FM" ]; then
    # No frontmatter at all — pre-v0.3 correction; load as context only, do not match (per intent's out-of-scope: pre-v0.3 migration deferred)
    continue
  fi

  # Pull fields. Both YAML array forms are supported for `paths:`:
  #   inline:  paths: ["pattern1", "pattern2"]
  #   block:   paths:
  #              - "pattern1"
  #              - "pattern2"
  # Other fields (match, rule, context) are always inline single-value strings.

  # paths: try inline first (anything on the same line as "paths:")
  PATHS=$(echo "$FM" | sed -nE 's/^paths:[[:space:]]+(.+)$/\1/p' | head -1)
  if [ -z "$PATHS" ]; then
    # Block form — collect every "  - value" line that follows a bare "paths:" line
    PATHS=$(echo "$FM" | awk '
      /^paths:[[:space:]]*$/ { in_block=1; next }
      in_block && /^[a-zA-Z_]+:/ { exit }
      in_block && /^[[:space:]]+-[[:space:]]+/ {
        sub(/^[[:space:]]+-[[:space:]]+/, "")
        print
      }
    ')
  fi

  MATCH_REGEX=$(echo "$FM" | grep -E "^match:" | sed -E 's/^match:[[:space:]]*//' | sed -E 's/^"(.*)"$/\1/' | sed -E "s/^'(.*)'\$/\1/")
  RULE=$(echo "$FM" | grep -E "^rule:" | sed -E 's/^rule:[[:space:]]*//' | sed -E 's/^"(.*)"$/\1/' | sed -E "s/^'(.*)'\$/\1/")
  CONTEXT=$(echo "$FM" | grep -E "^context:" | sed -E 's/^context:[[:space:]]*//' | sed -E 's/^"(.*)"$/\1/' | sed -E "s/^'(.*)'\$/\1/")

  # F12: warn on malformed (must have all four required fields)
  if [ -z "$PATHS" ] || [ -z "$MATCH_REGEX" ] || [ -z "$RULE" ] || [ -z "$CONTEXT" ]; then
    WARNINGS+=("compound-correction-match: $CORR has incomplete frontmatter (need: paths, match, rule, context); skipping")
    continue
  fi

  # Check paths glob. PATHS may now be:
  #   - inline array form, still bracketed:  ["a", "b"]
  #   - block form, newline-separated already:  a\nb
  # Normalize either to one pattern per line, quotes/whitespace stripped.
  PATTERNS=$(echo "$PATHS" | sed -E 's/^\[//; s/\]$//' | tr ',' '\n' | sed -E 's/^[[:space:]]*"?//; s/"?[[:space:]]*$//' | grep -v '^$')

  PATH_MATCHED=0
  while IFS= read -r PAT; do
    [ -z "$PAT" ] && continue
    # Bash case-glob `**/*.css` requires at least one `/` in FILE_REL, so
    # it misses root-level files. We try the pattern as written, and ALSO
    # try it with a leading `**/` stripped — so `**/*.css` matches both
    # `sub/styles.css` AND `styles.css`. This mirrors git-style glob.
    case "$FILE_REL" in
      $PAT) PATH_MATCHED=1; break ;;
    esac
    if [[ "$PAT" == \*\*/* ]]; then
      STRIPPED="${PAT#**/}"
      case "$FILE_REL" in
        $STRIPPED) PATH_MATCHED=1; break ;;
      esac
    fi
  done <<< "$PATTERNS"

  if [ "$PATH_MATCHED" -eq 0 ]; then
    continue
  fi

  # Path matches. Now check content against regex.
  if ! echo "$CONTENT" | grep -Eq "$MATCH_REGEX"; then
    continue
  fi

  # Content matches. Check for per-file escape hatch (C4):
  #   // compound-allow: <correction-slug>
  if echo "$CONTENT" | grep -Eq "compound-allow:[[:space:]]*${CORR_BASENAME}"; then
    # Bypass for this specific correction acknowledged
    continue
  fi

  # MATCH stands. Record.
  MATCHES+=("$CORR|$RULE|$CONTEXT")
done

# Emit warnings (F12). Guard against `set -u` choking on empty array on bash 3.2 (macOS default).
if [ "${#WARNINGS[@]}" -gt 0 ]; then
  for W in "${WARNINGS[@]}"; do
    echo "$W" >&2
  done
fi

# ─────────────────────────────────────────────────────────────────
# Decision
# ─────────────────────────────────────────────────────────────────
if [ "${#MATCHES[@]}" -eq 0 ]; then
  # No corrections matched; let the write proceed
  exit 0
fi

# Build the structured stderr message (C3: path + rule + context per match)
{
  echo ""
  echo "Blocked by compound-store correction(s). Proposed $TOOL_NAME on $FILE_REL matches:"
  echo ""
  for M in "${MATCHES[@]}"; do
    IFS='|' read -r M_PATH M_RULE M_CTX <<< "$M"
    echo "  • $M_PATH"
    echo "    Rule:    $M_RULE"
    echo "    Context: $M_CTX"
    echo ""
  done
  echo "To override for this file: add a comment '// compound-allow: <correction-slug>' referencing the correction's basename (without .md)."
  echo "To bypass for the session: set COMPOUND_BYPASS=1 in the shell environment."
} >&2

exit 2
