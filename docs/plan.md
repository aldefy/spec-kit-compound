# plan.md
# spec-kit-compound — Implementation & Launch Plan

---

## What we are building

A SpecKit extension that fills systematic gaps in Spec-Driven Development:

| Gap | Solution |
|---|---|
| SpecKit doesn't capture *why* or scope boundaries | `/speckit-intent` — goal, constraints, failure conditions |
| SpecKit fuses what-to-build with what-counts-as-done, enabling reward-hacking | `/speckit-expectations` — success scenarios, compartmented from intent |
| SpecKit tasks miss negative cases and constraint tests | `/speckit-gapfill` — cross-references intent + expectations against tasks |
| No validation that implementation stayed in scope | `/speckit-intentguard` — L3 intent guard before merge |
| AI memory dies between sessions; corrections are lost | `/speckit-compound-load` and `/speckit-compound-writeback` — committed compound store, two separate commands per spec-kit convention |

---

## Extension structure

```
spec-kit-compound/
├── extension.yml                        ← manifest (dotted command names, hooks)
├── README.md
├── LICENSE
├── CHANGELOG.md
└── commands/
    ├── speckit.intent.md                ← /speckit-intent
    ├── speckit.expectations.md          ← /speckit-expectations
    ├── speckit.compound.load.md         ← /speckit-compound-load
    ├── speckit.compound.writeback.md    ← /speckit-compound-writeback
    ├── speckit.gapfill.md               ← /speckit-gapfill
    └── speckit.intentguard.md           ← /speckit-intentguard
```

All 10 files to scaffold and push. Source filenames use dots (`speckit.X.Y.md`) per spec-kit convention; slash commands use hyphens (`/speckit-X-Y`). The dot→hyphen conversion happens at install time.

---

## Full per-feature workflow

Run these commands in order for every feature:

### Step 1 — Load compound store
```
/speckit-compound-load
```
Reads ADRs, correction notes, and patterns from `docs/compound/` into the agent context.
This is what makes the system compound — every session inherits past learnings.

### Step 2 — Write intent document
```
/speckit-intent
```
Creates `docs/intents/{feature-slug}.intent.md` with:
- Goal (one sentence, no "and", no tools, no patterns — passes the two-implementations test)
- Why now
- In scope (explicit list)
- Out of scope (explicit list — the guard)
- Constraints (5–7 qualities in business language, directional, unconditional)
- Failure conditions (binary checks the validator runs — observable, post-output)

### Step 2b — Write expectations document
```
/speckit-expectations
```
Creates `docs/expectations/{feature-slug}.expectations.md` with:
- Success scenarios (the "done" boundary)
- Negative/edge scenarios
- Limits the implementation must stay inside, written in user-recognizable terms

**Compartmentation note (v0.2 — soft).** This file is consumed by `/speckit-intentguard`, not by `/speckit-implement`. The builder reads the intent doc; the validator reads the expectations doc. Same agent, separate artifacts — structural defense against reward-hacking the validator's success criteria. Hard compartmentation (separate agents, encrypted evals) is deferred to v0.3+ if we see evidence of gaming.

### Step 3 — Run SpecKit
```
/speckit-specify    ← paste goal + in-scope from intent doc
/speckit-clarify    ← optional but recommended
/speckit-plan       ← add tech stack here
/speckit-tasks      ← generates the task list
```

Standard SpecKit flow. The task list SpecKit generates IS the task-level expectations the harness validates against on every iteration.

### Step 4 — Fill gaps SpecKit missed
```
/speckit-gapfill
```
Cross-references intent doc + expectations doc against the tasks file.
Adds missing:
- Constraint violation tests (does a task exist that would fail if a constraint were broken?)
- Out-of-scope regression checks (is there a check that the out-of-scope area was not touched?)
- Negative / error paths (SpecKit is happy-path biased)
- Cross-cutting concerns (analytics, accessibility, empty states)

Appends gap additions to `specs/{feature-slug}/tasks.md`.

### Step 5 — Implement
```
/speckit-implement
```
Harness runs with: intent doc + augmented tasks + compound store context.
Loop: work → validate → met? → merge or loop back.

### Step 6 — Intent guard before merge
```
/speckit-intentguard
```
Validation Level 3 — what most harnesses skip.
Checks:
- L1: Tests pass, build clean
- L2: Output matches spec expectations
- L3: Implementation stayed within intent scope, respected constraints, satisfied expectations doc, didn't accidentally build out-of-scope items

Outputs: PASS / REVIEW NEEDED / BLOCKED verdict.
If BLOCKED: do not merge. Fix violations and re-run.

### Step 7 — Write back to compound store
```
/speckit-compound-writeback
```
After intent guard passes:
- Auto-generates correction note if AI made mistakes during the loop
- Records new architectural patterns if established
- Updates ADRs if new decisions were made
- Marks intent doc `status: completed`

Commit: `docs/intents/`, `docs/expectations/`, `docs/compound/corrections/`, `docs/compound/adr/`, `docs/compound/patterns/`

---

## Repo structure the extension creates

```
docs/
├── intents/
│   ├── {feature-slug}.intent.md        ← intent doc (committed)
│   └── {feature-slug}.intentguard.md   ← guard report (committed)
├── expectations/
│   └── {feature-slug}.expectations.md  ← success scenarios (committed, compartmented)
└── compound/
    ├── README.md
    ├── adr/
    │   └── {NNN}-{slug}.md             ← architecture decisions
    ├── corrections/
    │   └── {date}-{slug}.md            ← AI correction notes
    └── patterns/
        └── {slug}.md                   ← reusable patterns
```

**Critical**: All files committed to repo. None are local-only.
This is what makes it different from Claude Code's default local memory files.

---

## CLAUDE.md addition

Add this to your project's `CLAUDE.md` so every Claude Code session inherits context:

```markdown
## Compound Engineering Context

Before starting any task, read:
- `docs/compound/adr/` — architectural decisions already made; do not re-debate
- `docs/compound/corrections/` — past mistakes and derived rules; do not repeat
- `docs/compound/patterns/` — approved patterns for this codebase; use these

## Workflow for any new feature

1. /speckit-compound-load — load compound store
2. /speckit-intent — write intent doc (goal, constraints, failure conditions)
3. /speckit-expectations — write expectations doc (success scenarios — compartmented)
4. /speckit-specify → /speckit-plan → /speckit-tasks — SpecKit flow
5. /speckit-gapfill — augment with missing constraint/negative tests
6. /speckit-implement — run the loop
7. /speckit-intentguard — L3 validation before merge
8. /speckit-compound-writeback — commit learnings back to compound store
```

---

## Launch plan

### Now
- [ ] Create GitHub repo `spec-kit-compound`
- [ ] Push the 9 files
- [ ] Add `LICENSE` (MIT) and `CHANGELOG.md`
- [ ] Run `specify init . --integration claude` in a test project
- [ ] Install extension: `specify extension add --dev /path/to/spec-kit-compound`
- [ ] Dry run on one real feature (Travv World Visa Agent or Equal AI feature)

### This week
- [ ] Tag `v0.2.0`, create GitHub release with release notes
- [ ] Submit Friends PR to `github/spec-kit`: one-line entry in `docs/community/friends.md`
- [ ] Write GDE LinkedIn post: "Built a SpecKit extension for intent-driven compound workflows" + repo link

### After battle-testing on 2-3 real features
- [ ] Submit to `extensions/catalog.community.json` in spec-kit repo
- [ ] Apply for verified extension status

---

## Installation (once published)

```bash
specify extension add --from https://github.com/aldefy/spec-kit-compound/archive/refs/tags/v0.2.0.zip
```

Local dev:
```bash
specify extension add --dev /path/to/spec-kit-compound
```
