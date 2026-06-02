---
description: "Load the compound store (ADRs, corrections, patterns from docs/compound/) into agent context at the start of a feature. Auto-scaffolds docs/compound/ if missing."
---

# Load Compound Store

You load the committed compound store at `docs/compound/` and inject its contents into the current session's agent context. Settled decisions, past mistakes, and approved patterns should constrain everything the agent does for the rest of the session.

---

## What to do

**1. Detect or create the compound store.**

If `docs/compound/` does not exist, create the scaffold:

```
docs/compound/
├── README.md         (explains the structure)
├── adr/              (empty)
├── corrections/      (empty)
└── patterns/         (empty)
```

Then tell the user: *"Compound store initialized at `docs/compound/`. Empty for now — it will fill over the next few features via `/speckit-compound-writeback`."*

**2. Read all files** in `docs/compound/adr/`, `docs/compound/corrections/`, and `docs/compound/patterns/`.

**3. Inject a context summary** at the start of the agent's working memory:

```
COMPOUND STORE LOADED

ADRs (settled decisions, do not re-debate):
- ADR-001 {title} — Rule for AI: {one-liner}
- ADR-002 {title} — Rule for AI: {one-liner}
...

Corrections (past mistakes, do not repeat):
- {date}-{slug}: {derived rule}
...

Patterns (approved approaches, reach for these by default):
- {slug}: {one-line description, when to use}
...
```

**4. Confirm to user**:

*"Compound store loaded: {N} ADRs, {N} corrections, {N} patterns. Settled decisions will be respected; known corrections will be avoided; patterns will be reached for during the rest of this session."*

---

## Notes for the rest of the session

After loading, when the agent makes design decisions during `/speckit-compound-intent`, `/speckit-implement`, `/speckit-compound-intentguard`, etc., it should:

- **Reference relevant ADRs** when constraints are being chosen — don't propose a constraint that contradicts a settled ADR
- **Avoid known correction patterns** — if the agent is about to do something that matches a correction note, stop and warn
- **Reach for established patterns** by default rather than inventing fresh approaches

---

## Re-loading after context compaction

If the session's context is compacted by the harness, the compound store summary may be dropped. The user can re-run `/speckit-compound-load` to restore it.

---

## Hook behavior

When invoked as a `before_constitution` hook, this command runs silently at project start, scaffolding the directory if needed and confirming "loaded N items" briefly. The full summary injection is the same; only the user-facing prompt is shorter.

---

## Tool choices

- **Read** for scanning compound store files
- **Bash** (`mkdir`, `ls`) for scaffold creation if missing
- **Write** for the auto-created `docs/compound/README.md` if scaffolding

---

## What you do NOT do

- **Modify any compound store file during load** — load is strictly read-only. Edits happen via `/speckit-compound-writeback`.
- **Re-load mid-session unsolicited** — load happens at the start of a feature; only re-run if the user explicitly invokes it after context compaction.
- **Block the rest of the session if the store is empty** — empty store is normal on a fresh project; just confirm scaffold and continue.
