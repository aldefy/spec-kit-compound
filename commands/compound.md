# /speckit.compound

You manage the **compound store** at `docs/compound/`. Two subactions:

- `/speckit.compound load` — pull ADRs, corrections, and patterns into the agent's context at the start of a feature
- `/speckit.compound writeback` — persist new learnings from the just-completed feature back into the store

Pick the subaction from the user's invocation. If no subaction is specified, ask:

*"Subaction? [load / writeback]"*

---

## Subaction: load

### Purpose
Inject the durable, cross-feature memory of this codebase into the current session's context. Settled decisions, past mistakes, and approved patterns should constrain everything the agent does in the rest of the session.

### What to do

**1. Detect or create the compound store.**

If `docs/compound/` does not exist, create the scaffold:

```
docs/compound/
├── README.md         (explains the structure)
├── adr/              (empty)
├── corrections/      (empty)
└── patterns/         (empty)
```

Then tell the user: *"Compound store initialized at `docs/compound/`. Empty for now — it will fill over the next few features via `/speckit.compound writeback`."*

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

### Notes for the rest of the session

After loading, when the agent makes design decisions during `/speckit.intent`, `/speckit.implement`, `/speckit.intentguard`, etc., it should:

- **Reference relevant ADRs** when constraints are being chosen — don't propose a constraint that contradicts a settled ADR
- **Avoid known correction patterns** — if the agent is about to do something that matches a correction note, stop and warn
- **Reach for established patterns** by default rather than inventing fresh approaches

### Re-loading after context compaction

If the session's context is compacted by the harness, the compound store summary may be dropped. The user can re-run `/speckit.compound load` to restore it. Future versions may add a hook to auto-restore.

---

## Subaction: writeback

### Purpose
After `/speckit.intentguard` returns PASS (or REVIEW NEEDED that the human has cleared), persist the learnings of this feature back into the compound store. This is what makes the system compound — every feature contributes to the next.

### What to do

**1. Verify intent guard passed.**

Read `docs/intents/{slug}.intentguard.md`. If verdict is:
- **BLOCKED**: refuse — *"Intent guard verdict is BLOCKED. Resolve violations before writeback."*
- **REVIEW NEEDED**: ask the user — *"Verdict is REVIEW NEEDED. Has a human reviewed the {N} items? [yes / no]"* Refuse if no.
- **PASS**: proceed.

**2. Scan the session for writeback candidates:**

**ADR candidates** — non-obvious architectural choices made during `/speckit.intent` or `/speckit.implement`:
- Library/framework selection that locks in a pattern
- Storage / persistence approach decisions
- API contract decisions
- Cross-cutting decisions (auth, error handling, logging, theming) that affect future features

**Correction candidates** — moments where the user pushed back on the agent during `/speckit.implement`:
- *"No, don't use X, use Y because Z"*
- *"Wrong — the convention here is W"*
- Repeated agent mistakes in the same session

**Pattern candidates** — approaches used that proved out:
- A technique used to satisfy a constraint that could apply to future features
- A test pattern that worked well
- A refactor approach that could be templated

**3. Draft proposed files** for each candidate.

**ADR template:**
```markdown
# ADR-{NNN}: {title}

## Status
Accepted

## Context
{what the situation was, what forces were at play}

## Decision
{what was decided}

## Consequences
{what this implies for future work — positive and negative}

## Rule for AI
{a one-line rule that future agents should follow because of this ADR}
```

**Correction template:**
```markdown
# Correction: {YYYY-MM-DD}-{slug}

## What happened
{agent action and user correction, verbatim if possible}

## Derived rule
{one-line rule to avoid repeat}

## Related ADRs
{any ADRs that codify this correction long-term}
```

**Pattern template:**
```markdown
# Pattern: {slug}

## When to use
{trigger conditions — what kind of feature or constraint calls for this pattern}

## How
{the approach, with a small code skeleton if relevant}

## Why this works here
{one-line rationale, often references an ADR}

## Examples in this repo
- `docs/intents/{slug}.intent.md` (feature {slug})
- ...
```

**4. Present drafts to user.**

Show each draft and ask (use AskUserQuestion per draft):
- **accept** — write the file as drafted
- **edit** — open for inline edit, then write
- **reject** — drop this draft
- **defer** — save to a scratch file `docs/compound/_drafts/` for later review

**5. Write accepted files** to `docs/compound/adr/`, `docs/compound/corrections/`, `docs/compound/patterns/`.

- For ADRs: use sequential numeric IDs, auto-incrementing from the highest existing ID. Format: `{NNN}-{slug}.md`.
- For corrections: prefix with date. Format: `{YYYY-MM-DD}-{slug}.md`.
- For patterns: use slug only. Format: `{slug}.md`.

**6. Update intent doc status.**

In the corresponding `docs/intents/{slug}.intent.md`, change the frontmatter:
```yaml
status: active   →   status: completed
completed: {YYYY-MM-DD}
```

**7. Summary**:

*"Writeback complete. {N} ADRs, {N} corrections, {N} patterns committed. Intent `{slug}` marked completed. Total compound store size: {N} ADRs / {N} corrections / {N} patterns."*

---

## Tool choices

- **Read** for scanning compound store and session history
- **Write** for new compound files
- **Edit** for updating intent doc status (frontmatter only)
- **AskUserQuestion** for per-draft accept/edit/reject/defer

---

## What you do NOT do

- **Auto-create ADRs without user approval** — every ADR draft must be approved
- **Auto-elevate patterns** — patterns require explicit user approval; corrections can auto-capture without approval if the correction was made by the user mid-session
- **Modify existing ADRs** — if a decision changes, create a new ADR that supersedes the old one (don't edit the old; the historical record matters)
- **Re-load the store mid-session** — load happens once at the start of a feature; if compaction drops it, the user can re-run `/speckit.compound load`
