---
description: "Gate hook for before_specify: refuses to let /speckit-specify proceed if no intent doc exists in docs/intents/. Forces /speckit-compound-intent to be run first."
---

# Require Intent Before Specify

This command is registered as a `before_specify` hook. It is a **thin shell-script wrapper** — not an interactive prompt — so it dispatches cleanly through spec-kit's hook executor (the pattern that bundled git's hooks use).

Its job: gate `/speckit-specify` on the existence of at least one intent doc.

---

## What you must do

Run the gate script via Bash:

```bash
.specify/extensions/compound/scripts/bash/require-intent.sh
```

The script:

1. Walks up from cwd to find the spec-kit project root (the directory containing `.specify/`)
2. Checks `docs/intents/` for any `*.intent.md` file
3. Exits 0 (silently) if at least one intent doc exists — `/speckit-specify` proceeds normally
4. Exits 1 with a clear message if none exist — `/speckit-specify` does not proceed

If the script exits non-zero, **do not continue with `/speckit-specify`**. Tell the user:

> *"No intent doc exists in `docs/intents/`. Run `/speckit-compound-intent` first to capture goal, constraints, and failure conditions. Then re-run `/speckit-specify`."*

---

## Why this is a shell script and not an interview

Spec-kit's hook executor dispatches **shell-script** hooks cleanly (verified: bundled `git`'s `speckit.git.feature` hook fires correctly because its command file invokes a bash script). It does **not** dispatch **agent-prompt** hooks like our `/speckit-compound-intent` (verified in v0.2.1's diagnostic: the hook entry installs but the interactive interview never starts).

By making this gate a script-runner, we get the discipline (refuse to spec without intent) without depending on the broken agent-prompt-hook dispatch path. The actual intent capture still happens via the interactive `/speckit-compound-intent` skill — the user types it manually after this gate blocks them.

---

## Tool choices

- **Bash** to invoke the gate script
- No Read, Write, Edit, or other tools needed
