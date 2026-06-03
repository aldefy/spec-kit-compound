#!/bin/bash
# scripts/validate.sh
#
# Static validation of the spec-kit-compound extension repo.
# Catches the kinds of bugs v0.2.0's 3-pivot live-install loop surfaced
# (naming mismatches, missing frontmatter, orphan slash references, etc.)
# before the next live install instead of after.
#
# Run from the repo root: ./scripts/validate.sh
#
# Exit 0 if all checks pass, 1 otherwise.

set -u

cd "$(dirname "$0")/.." || exit 1

ERRORS=0
CHECKS=0

pass() {
  CHECKS=$((CHECKS + 1))
  echo "  ✓ $1"
}

fail() {
  CHECKS=$((CHECKS + 1))
  ERRORS=$((ERRORS + 1))
  echo "  ✗ $1"
}

echo "=== Validating spec-kit-compound extension ==="
echo ""

# ─────────────────────────────────────────────────────────────────
# Section 1: extension.yml
# ─────────────────────────────────────────────────────────────────
echo "extension.yml"

if [ ! -f extension.yml ]; then
  fail "extension.yml does not exist"
  echo ""
  echo "FAILED: $ERRORS of $CHECKS checks"
  exit 1
fi

if python3 -c "import yaml; yaml.safe_load(open('extension.yml'))" 2>/dev/null; then
  pass "extension.yml parses as valid YAML"
else
  fail "extension.yml does not parse as valid YAML"
fi

if grep -q "^  id: compound$" extension.yml; then
  pass "extension.id is 'compound' (matches namespace requirement)"
else
  fail "extension.id is not 'compound' — spec-kit will reject namespaced commands"
fi

# ─────────────────────────────────────────────────────────────────
# Section 2: command files exist and have frontmatter
# ─────────────────────────────────────────────────────────────────
echo ""
echo "Command files"

REFERENCED_FILES=$(grep -E "^\s+file:" extension.yml | awk '{print $2}')
for f in $REFERENCED_FILES; do
  if [ -f "$f" ]; then
    pass "$f exists"
    if head -3 "$f" | grep -q "^description:"; then
      pass "$f has description frontmatter"
    else
      fail "$f missing 'description:' line in frontmatter"
    fi
  else
    fail "$f referenced in extension.yml but does not exist on disk"
  fi
done

# ─────────────────────────────────────────────────────────────────
# Section 3: command-name namespace
# ─────────────────────────────────────────────────────────────────
echo ""
echo "Command namespace"

NON_NAMESPACED=$(grep -E "^\s+- name:" extension.yml | awk '{print $3}' | grep -v "^speckit\.compound\." || true)
if [ -z "$NON_NAMESPACED" ]; then
  pass "All command names use speckit.compound.* namespace"
else
  fail "Commands not under speckit.compound.* namespace: $NON_NAMESPACED"
fi

# ─────────────────────────────────────────────────────────────────
# Section 4: no orphan dotted slash references in markdown
# ─────────────────────────────────────────────────────────────────
echo ""
echo "Slash command references"

# Exclude CHANGELOG.md — it legitimately records historical syntax (e.g. v0.2.0
# referenced the dotted form when documenting the migration to the hyphenated form).
DOTTED=$(grep -rn "/speckit\." --include="*.md" --exclude="CHANGELOG.md" . 2>/dev/null | grep -v "node_modules\|\.git" | wc -l | tr -d ' ')
if [ "$DOTTED" -eq 0 ]; then
  pass "No dotted slash command references in active markdown (CHANGELOG excluded as historical record)"
else
  fail "Found $DOTTED dotted slash command references in active markdown; should be hyphenated"
  grep -rn "/speckit\." --include="*.md" --exclude="CHANGELOG.md" . 2>/dev/null | head -3 | sed 's/^/      /'
fi

# ─────────────────────────────────────────────────────────────────
# Section 5: scripts are executable
# ─────────────────────────────────────────────────────────────────
echo ""
echo "Scripts"

for s in scripts/check-chain-fired.sh scripts/validate.sh scripts/bash/require-intent.sh; do
  if [ ! -f "$s" ]; then
    fail "$s does not exist"
  elif [ -x "$s" ]; then
    pass "$s is executable"
  else
    fail "$s is not executable (chmod +x $s)"
  fi
done

# ─────────────────────────────────────────────────────────────────
# Section 6: hooks block declares only shell-script hooks
# ─────────────────────────────────────────────────────────────────
echo ""
echo "Hooks (v0.2.2+ pattern: shell-script gates only)"

if grep -q "^hooks:" extension.yml; then
  # Hooks block exists; check that registered commands point to script-running command files
  HOOK_COMMANDS=$(grep -A1 "command:" extension.yml | grep -E "^\s+command:" | awk '{print $2}' | sort -u)
  for hc in $HOOK_COMMANDS; do
    # Find the file for this command
    HCFILE=$(grep -B1 "^      file:" extension.yml | grep -A1 "name: $hc" | grep "file:" | awk '{print $2}')
    if [ -n "$HCFILE" ] && [ -f "$HCFILE" ]; then
      # Check that the file invokes a shell script (i.e., it's a script-runner, not an interactive prompt)
      if grep -q "scripts/bash/" "$HCFILE" 2>/dev/null; then
        pass "Hook command $hc invokes a shell script (will dispatch correctly)"
      else
        fail "Hook command $hc is an agent-prompt, not a shell-script wrapper — will silently no-op under Claude Code"
      fi
    fi
  done
else
  pass "No hooks: block declared (manual chain only — also valid)"
fi

# ─────────────────────────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────────────────────────
echo ""
echo "─────────────────────────────────"
if [ "$ERRORS" -eq 0 ]; then
  echo "All $CHECKS checks passed ✓"
  exit 0
else
  echo "FAILED: $ERRORS of $CHECKS checks"
  exit 1
fi
