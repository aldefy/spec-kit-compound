---
description: "Persist learnings from the just-completed feature, each encoded at the strongest level that fits (test/lint rule > standards line > store doc), then refresh the store (prune stale, duplicate, superseded entries). Requires intent guard PASS first."
---

# Writeback to Compound Store

After `/speckit-compound-intentguard` returns PASS (or REVIEW NEEDED that a human has cleared), you persist the learnings of this feature so the next feature is easier. This is what makes the system compound.

Two rules shape everything below (v0.8+):

1. **Encode each lesson as strongly as it will go.** A markdown note can be ignored; a failing test cannot. Every lesson climbs the **encoding ladder** and lands on the highest rung that fits.
2. **Writeback also refreshes.** A store that only grows rots. After writing, scan the whole store and propose pruning what is stale, duplicated, or now enforced elsewhere. There is no separate refresh command to remember.

---

## The encoding ladder

| Rung | Encoding | Who it stops | Where it lives |
|---|---|---|---|
| **1. Test or lint rule** | A regression test that fails on the mistaken code, or a lint rule in the project's linter config | Every contributor, human or agent, in CI | The project's own test suite / linter config |
| **2. Hook-enforced correction** | A correction note with v0.3+ frontmatter (`paths` / `match` / `rule` / `context`) | Agent Write/Edit, before the code exists | `docs/compound/corrections/` |
| **3. Standards line** | One imperative line in the project's always-loaded standards doc (`.specify/memory/constitution.md`, `AGENTS.md`, or `CLAUDE.md`, whichever the project uses) | Any agent that reads the standards | That file |
| **4. Store doc** | ADR, pattern, or context-only correction | Agents that run `/speckit-compound-load` | `docs/compound/{adr,patterns,corrections}/` |

Pick the **highest** rung that honestly fits:

- **Rung 1 fits** when the mistake has an observable, checkable outcome: a wrong value, a missing guard clause, a forbidden import, a call that must never happen, a file that must not exist. Prefer this over everything else: it protects the codebase from humans too, and it survives anyone uninstalling this extension.
- **Rung 2 fits** when the mistake has a recognizable *syntactic* form (a regex can spot it in proposed content) but a test would be awkward: style, an API that is legal but banned here, a config key.
- **Rung 3 fits** when the lesson is a convention with no syntactic signature, short enough to be one line (naming, file placement, "ask before X").
- **Rung 4** is the fallback: architectural decisions with context and consequences (always an ADR, see below), multi-step approaches (patterns), and judgement calls nothing can check.

Rungs stack where useful: a correction can be rung 1 *and* rung 2 (CI catches humans, the hook catches the agent earlier). Record the strongest one in the ledger.

**ADRs are always written as store docs.** A decision record is history and must exist even when its rule is enforced. If the ADR's *Rule for AI* is enforceable, also encode it on rung 1–3 and fill the ADR's `Enforced by:` line.

---

## What to do

**1. Verify intent guard passed.**

Read `docs/intents/{slug}.intentguard.md`. If verdict is:
- **BLOCKED**: refuse: *"Intent guard verdict is BLOCKED. Resolve violations before writeback."*
- **REVIEW NEEDED**: ask the user: *"Verdict is REVIEW NEEDED. Has a human reviewed the {N} items? [yes / no]"* Refuse if no.
- **PASS**: proceed.

**2. Scan the session for lesson candidates.**

**Decisions** (ADR candidates): non-obvious architectural choices made during `/speckit-compound-intent` or `/speckit-implement`: library or framework selection that locks in a pattern, storage approach, API contracts, cross-cutting choices (auth, errors, logging, theming).

**Mistakes** (correction candidates): moments the user pushed back on the agent, or the agent caught its own bug:
- *"No, don't use X, use Y because Z"*
- *"Wrong — the convention here is W"*
- A bug found during implement or intentguard, and the class of bug it belongs to
- Repeated agent mistakes in the same session

**Approaches** (pattern candidates): a technique that satisfied a constraint and could apply again, a test pattern that worked, a refactor approach worth templating.

**3. Climb the ladder for each candidate.**

For every candidate, decide its rung and draft the encoding:

**Rung 1 — test or lint rule.**
- Find the project's test runner and an existing test file nearest the code involved. Put the test there; match the file's style. Name it after the behavior, not the incident (`rejects_empty_token`, not `fix_for_bug_42`).
- For a lint rule, add it to the existing linter config (`.eslintrc*`, `detekt.yml`, `ruff.toml`, `.swiftlint.yml`, ...). Do not introduce a new linter for one rule.
- **Prove it guards.** Run the test or linter on the current tree: it must pass. Then show it would have caught the mistake: either revert the fix locally, or run it against a minimal snippet of the mistaken code, and confirm it fails. A guard that was never seen failing is not a guard; drop to a lower rung instead of shipping it.

**Rung 2 — hook-enforced correction.** Draft the correction with full v0.3+ frontmatter (see `docs/compound/CORRECTIONS-SCHEMA.md`). Before accepting:
- `echo '<mistaken snippet>' | grep -E '<match>'` must match.
- Run `python3 scripts/compound_refresh.py` after writing it: a new `fires-on-tree` finding on this correction means the regex hits current, correct code. Tighten the regex or the `paths:` globs.

**Rung 3 — standards line.** Draft one imperative line and the file it goes in. Keep the line under ~120 characters; if it needs more, it is a pattern (rung 4).

**Rung 4 — store doc.** Use the templates below.

**Every mistake must ship a guard.** A correction candidate lands on rung 1 or 2. It may only fall to rung 3–4 with a one-line `unenforceable_reason:` in its frontmatter saying why nothing can check it (e.g. *"naming judgement; no syntactic form"*). The refresh scan flags corrections that have neither a guard nor a reason.

**4. Present drafts to the user.**

Show each draft **with its chosen rung and the evidence** (test red→green output, grep dry-run, or why lower rungs were needed). Ask per draft (AskUserQuestion):
- **accept**: write it as drafted
- **change rung**: move it up or down the ladder, then redraft
- **edit**: adjust inline, then write
- **reject**: drop it
- **defer**: save to `docs/compound/_drafts/` for later

**5. Write accepted lessons.**

- **Rung 1**: write the test or lint rule into the project. Do **not** also write a store doc for it (except ADRs). Instead add a ledger row (step 6).
- **Rung 2**: `docs/compound/corrections/{YYYY-MM-DD}-{slug}.md`. If it also has a rung 1 guard, add `guarded_by: <path>` to its frontmatter.
- **Rung 3**: append the line to the standards file, under an existing section when one fits. Add a ledger row.
- **Rung 4**: ADRs `docs/compound/adr/{NNN}-{slug}.md` (sequential, from the highest existing ID), patterns `docs/compound/patterns/{slug}.md`, context-only corrections `docs/compound/corrections/{YYYY-MM-DD}-{slug}.md`.

**6. Update the enforcement ledger.**

Rung 1 and rung 3 lessons leave no store doc, so record them in `docs/compound/ENFORCED.md`, creating it with this header if missing:

```markdown
# Enforced lessons

Lessons encoded outside the store (as tests, lint rules, or standards lines).
`/speckit-compound-load` lists these by one line each; the refresh scan checks every guard still exists.

| Lesson | Tier | Guard | Feature | Date |
|---|---|---|---|---|
```

Append one row per lesson:

```markdown
| reject empty auth token | test | `tests/auth/test_token.py::test_rejects_empty_token` | {slug} | {YYYY-MM-DD} |
| no wildcard imports | lint | `.eslintrc.json` | {slug} | {YYYY-MM-DD} |
| feature flags live in flags.ts | standards | `AGENTS.md` | {slug} | {YYYY-MM-DD} |
```

`Tier` is `test`, `lint`, or `standards`. `Guard` is a repo-relative path, optionally `::name` for a specific test.

**7. Refresh the store.**

Run the read-only scanner from the project root:

```bash
python3 .specify/extensions/compound/scripts/compound_refresh.py
```

(When running inside the spec-kit-compound repo itself, the path is `scripts/compound_refresh.py`.)

It reports findings of these kinds. Propose one action for each and ask the user (AskUserQuestion, batched where several share an action):

| Finding | Meaning | Proposed action |
|---|---|---|
| `superseded` | ADR marked Superseded still in `adr/` | **archive** it (the superseding ADR carries the rule) |
| `dup-rule` | Two corrections share a regex or rule | **merge** into the older slug, keep both `paths:` sets, archive the newer |
| `no-guard` | Correction has no frontmatter and no `unenforceable_reason` | **upgrade**: climb the ladder for it now (rung 1 or 2), or add the reason |
| `fires-on-tree` | Correction's regex matches current code (reported as `file:line`) | Read the line, then ask which of three it is: **live violation** (fix the code, or add `compound-allow: <slug>` if intended), **regex too broad** (it hits correct code such as a comment explaining the rule, or the sanctioned wrapper itself; **tighten** `match:` or narrow `paths:`, because the hook will otherwise block the agent from rewriting that file), or **stale rule** (**archive**). |
| `dead-paths` | Correction's globs match no file | The code it guarded is gone: **archive**, unless it is a deliberate sample |
| `bad-regex` | `grep -E` rejects the regex | **fix** the regex (POSIX ERE, see the schema doc) |
| `stale-guard` | Ledger row's guard file no longer exists | Ask whether the guard moved (**update** the row) or was dropped (**re-encode** the lesson or delete the row) |
| `dead-example` | Pattern cites a file that no longer exists | **update** the example list; archive the pattern if no examples remain |

Also check, by reading rather than scanning: a correction or pattern whose rule is now fully covered by a rung-1 guard in the ledger is redundant; propose **archive**.

**Archive, never delete.** Archiving moves the file to `docs/compound/_archive/{adr,corrections,patterns}/` with `git mv`, keeping its history. `/speckit-compound-load`, the PreToolUse hook, and the dashboard all ignore `_archive/`. Nothing is moved without the user's approval.

If the scan reports zero findings, say so in one line and move on.

**8. Update intent doc status.**

In `docs/intents/{slug}.intent.md`, change the frontmatter:
```yaml
status: active   →   status: completed
completed: {YYYY-MM-DD}
```

**9. Summary.**

*"Writeback complete. Encoded {N} lessons: {N} tests, {N} lint rules, {N} hook corrections, {N} standards lines, {N} store docs ({N} ADRs, {N} patterns). Refresh: {N} findings, {N} archived, {N} merged, {N} upgraded. Intent `{slug}` marked completed. Store: {N} ADRs / {N} corrections / {N} patterns / {N} ledger rows."*

---

## Templates

**ADR:**
```markdown
# ADR-{NNN}: {title}

## Status
Accepted

## Context
{what the situation was, what forces were at play}

## Decision
{what was decided}

## Consequences
{what this implies for future work, positive and negative}

## Rule for AI
{a one-line rule future agents follow because of this ADR}

## Enforced by
{test / lint rule / correction / standards line that enforces the rule, or "not enforceable: <why>"}
```

**Correction** (rung 2, or rung 4 with `unenforceable_reason`):
```markdown
---
slug: {YYYY-MM-DD}-{slug}
paths:
  - "{glob}"
match: '{POSIX ERE}'
rule: "{one-line imperative}"
context: "{one-line why}"
guarded_by: {optional rung-1 guard path}
---

# Correction: {YYYY-MM-DD}-{slug}

## What happened
{agent action and user correction, verbatim if possible}

## Derived rule
{the long-form rule}

## Related ADRs
{any ADRs that codify this correction long-term}
```

For a context-only correction, replace the four enforcement fields with `unenforceable_reason: "{why nothing can check this}"`.

**Pattern:**
```markdown
# Pattern: {slug}

## When to use
{trigger conditions}

## How
{the approach, with a small code skeleton if relevant}

## Why this works here
{one-line rationale, often references an ADR}

## Examples in this repo
- `docs/intents/{slug}.intent.md` (feature {slug})
```

---

## Hook behavior

When invoked as an `after_implement` hook, this command runs only AFTER `/speckit-compound-intentguard` has produced a verdict. The hook is `optional: true`: the user is prompted *"Writeback learnings from this feature? [yes / no]"*. If yes, run the full flow above. If no, skip cleanly.

To run **only the refresh** (e.g. on a schedule or in an automation), invoke `/speckit-compound-writeback refresh`: skip steps 1–6 and 8, run step 7, then summarize.

---

## Tool choices

- **Read** for the session history, intent guard verdict, and existing tests/linter config
- **Bash** to run the test/linter red→green proof, `grep -E` dry-runs, the refresh scanner, and `git mv` for archiving
- **Write / Edit** for tests, lint config, standards lines, store docs, the ledger, and intent status
- **AskUserQuestion** for per-draft and per-finding approval

---

## What you do NOT do

- **Write a store doc when a test would do.** If a lesson can be a test, a markdown note is the weaker encoding; climb the ladder first.
- **Ship an unproven guard.** A test or lint rule that was never seen failing on the mistake does not count as rung 1.
- **Add a new test framework or linter** to encode a single lesson. Use what the project has; otherwise drop a rung.
- **Auto-create ADRs, patterns, tests, or standards lines without user approval.** Every encoding is approved per draft. (Corrections the user made mid-session may be auto-captured as drafts, but still pass through step 4.)
- **Modify existing ADRs.** A changed decision gets a new ADR that supersedes the old one; the old one is archived by refresh.
- **Delete store files.** Refresh archives with `git mv`; history matters.
- **Write back if intent guard is BLOCKED.** Failure modes don't compound until resolved. (`refresh` mode is exempt: it only reads and proposes.)
