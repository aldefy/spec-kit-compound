---
description: "Gate hook for before_implement: when SKC_PLANVERIFY_GATE=block, refuses /speckit-implement if the latest planverify verdict is missing or BLOCKED_DRIFT. No-op by default. The Claude+spec-kit half of the gate; the cross-vendor half is the PreToolUse hook."
---

# Planverify Gate (before_implement)

This command is registered as a `before_implement` hook. It is a **thin
shell-script wrapper** — not an interactive prompt — so it dispatches cleanly
through spec-kit's hook executor (the same pattern `speckit.compound.require-intent`
uses for `before_specify`, and that bundled git's hooks use).

Its job: optionally gate `/speckit-implement` on the latest planverify verdict.

This is the **spec-kit phase-boundary** half of the planverify gate (fires under
Claude + spec-kit). The **cross-vendor** half — a `PreToolUse` hook that works
under both Claude Code and Codex CLI — is installed separately via
`/speckit.compound.install-hooks`.

---

## What you must do

Run the gate script via Bash:

```bash
.specify/extensions/compound/scripts/bash/planverify-gate.sh
```

The script:

1. Walks up from cwd to find the spec-kit project root (the directory containing `.specify/`)
2. Resolves the gate mode — `SKC_PLANVERIFY_GATE` env, else `planverify_gate:` in `docs/compound/compound-config.yml`, default `off`
3. If mode is not `block` → exits 0 silently — `/speckit-implement` proceeds normally
4. If mode is `block`:
   - No planverify report exists → exits 1 (run `/speckit.compound.planverify` first)
   - Latest verdict is `BLOCKED_DRIFT` → exits 1 (replan first)
   - Latest verdict is `PASS` or `REPLAN_ALLOWED` → exits 0 (proceed)

If the script exits non-zero, **do not continue with `/speckit-implement`**. Relay
the script's message to the user:

> *"planverify gate is ON and the plan is not cleared. Run `/speckit.compound.planverify` (and replan if it returned BLOCKED_DRIFT) before `/speckit-implement`."*

---

## Why this is a shell script and not an interview

Spec-kit's hook executor dispatches **shell-script** command files cleanly under
both Claude Code and Codex; **agent-prompt** hooks silently no-op (verified in
v0.2.1). Mirroring `speckit.compound.require-intent`, the gate is a script-runner
so it fires reliably whether invoked directly or as part of the chain.

---

## Tool choices

- **Bash** to invoke the gate script
- No Read, Write, or Edit needed
