---
description: "One-shot installer (shell-script wrapper): copies the v0.3 PreToolUse hook script into .claude/hooks/ and merges the hook registration into .claude/settings.json with a pragmatic merge that preserves all other entries."
---

# Install Claude Code Hooks

This command installs the spec-kit-compound v0.3+ active-corrections hook system into the user's project. It is a **thin shell-script wrapper** (the pattern that DOES dispatch under Claude Code's hook executor; see v0.2.1 / v0.2.2 release notes for why agent-prompt hooks silently no-op).

After running, the user's `.claude/settings.json` registers a `PreToolUse` hook that fires on every `Write` or `Edit` tool call, runs `.claude/hooks/compound-correction-match.sh`, and blocks the call (exit 2) if any correction in `docs/compound/corrections/` matches the proposed write.

---

## What you must do

Run the installer script via Bash:

```bash
.specify/extensions/compound/scripts/bash/install-claude-hooks.sh
```

The script:

1. Anchors to the spec-kit project root (the directory containing `.specify/`)
2. Copies `.specify/extensions/compound/.claude/hooks/compound-correction-match.sh` into the project's `.claude/hooks/` directory; creates the directory if it does not exist; marks the script executable.
3. Merges a `PreToolUse` hook entry into `.claude/settings.json`:
   - If the file does not exist, creates it with only our entry
   - If it exists, removes any prior compound entry (matched by command path), then appends a fresh one
   - All non-compound entries (user's own hooks, other extensions' hooks) are preserved byte-for-byte
4. Validates the resulting JSON parses; aborts atomically if it does not
5. Prints a confirmation block showing test instructions and the two bypass mechanisms (`// compound-allow:` comment per-file, `COMPOUND_BYPASS=1` env var per-session)

After the script returns 0, tell the user:

> *"Active-corrections hook is now wired. Next agent Write/Edit will be checked against `docs/compound/corrections/`. To test, commit a correction note with `paths:` + `match:` frontmatter (see `docs/compound/CORRECTIONS-SCHEMA.md`), then ask me to write a file that matches it."*

If the script exits non-zero, show the stderr output to the user and stop — do not retry blindly. Most likely causes: not in a spec-kit project (no `.specify/`), `jq` not installed (`brew install jq` or equivalent), or the extension is installed at an older version than v0.3 (which does not ship the hook script).

---

## Why this is a shell-script wrapper (not an interview)

Spec-kit's hook executor dispatches shell-script command files cleanly under Claude Code — confirmed by both the bundled `git` extension's hooks (which fire reliably) and spec-kit-compound's own `speckit.compound.require-intent` gate (v0.2.2). Agent-prompt command files (which ask the agent to do interactive work) silently no-op under the same executor. That's why this installer is a deterministic shell-script wrapper rather than an interactive prompt — it dispatches reliably whether invoked directly by the user or as part of a chain.

The actual hook script itself (`compound-correction-match.sh`) is also a shell script for the same reason: it runs as part of Claude Code's `PreToolUse` dispatch, which expects a shell command with stdin JSON / exit code / stderr message contract.

---

## Tool choices

- **Bash** to invoke the installer script
- No Read, Write, Edit, or other tools needed — the installer handles all file operations

---

## What you do NOT do

- **Do not manually merge `.claude/settings.json` from prompt-level Bash commands.** The installer's `jq`-based merge handles dedup, preservation, and atomicity. Hand-editing breaks idempotency.
- **Do not install the hook script in any path other than `.claude/hooks/`** — the registered command in `settings.json` references this exact path.
- **Do not register the hook under any matcher other than `Write|Edit`** — the hook script is built around the `tool_input.file_path` and `tool_input.content` fields specific to those tools.
- **Do not run the installer in a directory without `.specify/`** — the script will refuse and exit 1.
