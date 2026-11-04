# Compound Store

This directory is the **committed memory** of the codebase — the layer that makes spec-kit-compound *compound*.

Every feature contributes back via `/speckit-compound-writeback`. Every feature inherits the accumulated store via `/speckit-compound-load`. Over time, the store outweighs any static constitution document you could write upfront.

---

## Structure

```
docs/compound/
├── adr/           ← Architecture Decision Records (settled decisions)
├── corrections/   ← AI correction notes (past mistakes and derived rules)
├── patterns/      ← Approved patterns (proven approaches for this codebase)
├── ENFORCED.md    ← Ledger of lessons encoded as tests / lint rules / standards lines (v0.8+)
├── _archive/      ← Entries pruned by the writeback refresh (ignored by load + hook)
└── _drafts/       ← Deferred writeback drafts (not loaded)
```

### The encoding ladder (v0.8+)

A markdown note is the weakest way to keep a lesson. `/speckit-compound-writeback` puts each lesson on the highest rung that fits:

1. **Test or lint rule** in the project itself (catches humans and agents, in CI)
2. **Hook-enforced correction** in `corrections/` (blocks the agent's Write/Edit)
3. **Standards line** in the constitution / `AGENTS.md` / `CLAUDE.md`
4. **Store doc** (ADR, pattern, or context-only correction)

Rungs 1 and 3 leave no store doc, so they get a row in `ENFORCED.md`. ADRs are always written as docs: they are the decision history.

### Refresh

Every writeback ends with a read-only scan (`scripts/compound_refresh.py`) for superseded ADRs, duplicate or unguarded corrections, rules that fire on current code or match no files, ledger guards that no longer exist, and dead pattern examples. Proposed fixes are approved one by one; pruned entries move to `_archive/` with `git mv`, never deleted. Run `/speckit-compound-writeback refresh` to do only this step.

### `adr/`

Architecture decisions made during real features. Each file:

- Numeric ID (auto-incremented): `001-{slug}.md`, `002-{slug}.md`, ...
- Frontmatter with status (Accepted / Superseded)
- Context → Decision → Consequences → **Rule for AI** (one-line directive for future agents)

The "Rule for AI" line is what `/speckit-compound-load` injects into context. Future agents are instructed not to re-debate these decisions.

### `corrections/`

Captured during `/speckit-implement` when the user pushes back on the agent. Each file:

- Date-prefixed slug: `2026-06-02-no-css-filters.md`
- "What happened" — the exchange, verbatim if possible
- "Derived rule" — the one-line lesson to avoid repeat
- Frontmatter guard: the v0.3+ hook fields, a `guarded_by:` test, or an `unenforceable_reason:` (v0.8+, see `CORRECTIONS-SCHEMA.md`)

Corrections auto-capture without user approval (because the correction was already made by the user). They are reviewed at writeback time and can be promoted to ADRs if they describe a durable principle rather than a one-off.

### `patterns/`

Approaches that worked well enough to template for future features. Each file:

- Slug only: `theme-resolution-head-script.md`
- "When to use" — trigger conditions
- "How" — the approach, with a small code skeleton if relevant
- "Why this works here" — rationale, often references an ADR
- "Examples in this repo" — feature slugs that used the pattern

Patterns require explicit user approval at writeback; they are the most opinionated artifact in the store.

---

## Lifecycle

```
/speckit-compound-load                  →  reads everything here, injects into agent context
                                            (at the start of every feature)

[feature work happens — intent, plan, implement, intentguard]

/speckit-compound-writeback             →  encodes each lesson on the highest ladder rung
                                            (test/lint > hook correction > standards > doc),
                                            user approves each, then refreshes the store
                                            (at the end of every feature, after intentguard PASS)
```

---

## Why this beats Claude Code's default memory

Claude Code's memory files (`~/.claude/...`) are stored **locally**. They die when you:

- Switch machines
- Onboard a new teammate
- Start a fresh session after `--clear`
- Wipe your laptop

The compound store is **committed to the repo**. It survives all of the above and is shared across the team. It is treated as a first-class repo artifact, the same way ADRs are — because that is exactly what it is.

---

## Bootstrapping

This directory is created automatically by `/speckit-compound-load` on first invocation in a project. You do not need to pre-populate it. The store grows naturally from the first feature onward.

The first feature contributes 0–2 ADRs at most. By feature 10, expect a non-trivial set. By feature 50, the store contains more applied wisdom than any constitution doc you would have written upfront.
