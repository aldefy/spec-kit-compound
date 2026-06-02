# /speckit.intentguard

You are running the **L3 intent guard** — the validation that most harnesses skip. Your job is to decide whether the implementation actually stayed within the declared intent and expectations, beyond just "tests pass and build is clean."

This is the most **LLM-judgment-heavy** command in the extension. You read the intent doc, the expectations doc, and the git diff, and you make a verdict: **PASS**, **REVIEW NEEDED**, or **BLOCKED**.

---

## The three levels of validation

- **L1** — tests pass, build clean, lint clean. *(Mechanical, run via Bash.)*
- **L2** — output matches the augmented task list. *(Check tasks.md completion + diff evidence.)*
- **L3** — implementation stayed within intent scope and constraints; expectations are satisfied. *(LLM judgment over the diff.)*

A failure at L1 or L2 is mechanical and easy to communicate. The contribution of this command is **L3** — comparing the diff against the locked intent and expectations.

---

## Inputs you must load

1. **Intent doc** at `docs/intents/{slug}.intent.md` — out-of-scope items, constraints, failure conditions
2. **Expectations doc** at `docs/expectations/{slug}.expectations.md` — positive and edge scenarios
3. **Tasks file** at `specs/{slug}/tasks.md` — including gapfill additions
4. **Git diff** of the current branch vs the merge base — use `git diff $(git merge-base HEAD main)...HEAD`

If the intent or expectations doc is missing, stop and tell the user.

## Output you produce

- One file: `docs/intents/{slug}.intentguard.md` — the verdict report
- A clear **PASS / REVIEW NEEDED / BLOCKED** verdict in the file and in chat

---

## The validation, in order

### Phase 0 — Load all inputs

Read all four sources. Compute basic stats: lines changed in diff, files touched in diff, number of tasks marked complete.

Confirm to user: *"Loaded intent, expectations, tasks ({N} of {M} complete), and diff ({N} lines across {M} files). Running L1 → L2 → L3."*

### Phase 1 — L1: Mechanical checks

Run via Bash (detect the language/build system from the repo):
- Build: `npm run build` / `cargo build` / `go build ./...` / `pytest --collect-only` / etc.
- Tests: `npm test` / `cargo test` / `go test ./...` / `pytest` / etc.
- Lint: `npm run lint` / `cargo clippy` / `golangci-lint run` / `ruff check` / etc.

Record pass/fail for each. **If any L1 check fails**, the final verdict is **BLOCKED at L1** and you don't need to run L2/L3 — fix L1 first.

### Phase 2 — L2: Task completion check

For each task in `specs/{slug}/tasks.md`:
- Is it marked complete (checkbox checked)?
- Does the diff contain evidence the task was actually executed (not just checked off)?

Record any task that is marked complete but has no diff evidence as a **L2 concern**. If 80%+ of tasks are complete with diff evidence, L2 passes. Below that, L2 raises REVIEW NEEDED.

### Phase 3 — L3a: Out-of-scope check *(BLOCKING)*

For each out-of-scope item in the intent doc:
- Read the item carefully (e.g., *"Ghost admin panel"*, *"RSS feed"*, *"Email newsletter rendering"*)
- Inspect the diff for file paths, code symbols, or strings that match this area
- If clear matches found, this is a **BLOCKING violation**: the diff touched something declared out-of-scope

For each out-of-scope item, output:
- Item name
- Match found? (yes / no / borderline)
- Specific file paths or line numbers if matched

If any out-of-scope item has clear matches (not borderline), the final verdict is **BLOCKED**.

### Phase 4 — L3b: Constraint check *(BLOCKING for hard violations, REVIEW for borderline)*

For each constraint in the intent doc:
- Read the constraint
- Decide whether the diff respects it. This requires **actual code reading**, not keyword matching.

Examples of decisions you must make:
- *C1 "No FOUC on initial paint"* — does the diff include a synchronous head-script that resolves the theme before render? If no, **BLOCKED**.
- *C4 "localStorage persistence"* — does the diff use cookies instead of localStorage? If yes, **BLOCKED**.
- *C5 "Lighthouse ≥ 90"* — can you tell from the diff alone? Usually not — mark as **REVIEW NEEDED** and reference the L1 Lighthouse check (if added).

For each constraint, output:
- Constraint ID and text
- Verdict: PASS / BLOCKED / REVIEW NEEDED
- One-sentence rationale citing specific diff evidence

### Phase 5 — L3c: Failure condition coverage check

For each failure condition in the intent doc, confirm a covering check exists (in tasks.md after gapfill, or in CI). If a failure condition has no covering check, raise **REVIEW NEEDED**.

This is mostly cross-referencing against L1 results and the tasks.md gapfill additions.

### Phase 6 — L3d: Expectations satisfaction check

For each scenario in the expectations doc:
- **Positive scenarios**: does the diff plus the L1 tests demonstrate this scenario passes?
- **Edge scenarios**: does the diff include the graceful-degradation behavior described?

Each scenario gets **PASS / REVIEW NEEDED / BLOCKED** with a one-sentence rationale. The expectations file is the validator's ground truth — this is the central L3 check.

### Phase 7 — Compose verdict

Aggregate:
- **PASS** — all L1, L2, L3a, L3b, L3c, L3d are PASS (with at most a few minor REVIEW items the user can scan)
- **REVIEW NEEDED** — any L3 check is REVIEW, no L1 fails, no BLOCKED at L3
- **BLOCKED** — any L1 fails, OR any L3a/L3b is BLOCKED, OR any expectations scenario is BLOCKED

Write `docs/intents/{slug}.intentguard.md` using the format below.

### Phase 8 — Communicate verdict

Show the verdict in chat with the level of urgency it warrants:

- **PASS**: *"Verdict: PASS. Safe to merge. Run `/speckit.compound writeback` to persist learnings before merging."*
- **REVIEW NEEDED**: *"Verdict: REVIEW NEEDED. {N} items need human review (see `docs/intents/{slug}.intentguard.md`). Do not merge until reviewed."*
- **BLOCKED**: *"Verdict: BLOCKED. {N} violations:"* — list each violation with the required fix.

---

## Output format — `docs/intents/{slug}.intentguard.md`

```markdown
---
slug: {slug}
verdict: PASS | REVIEW NEEDED | BLOCKED
run: {YYYY-MM-DD HH:MM}
diff_lines: {N}
diff_files: {N}
---

# Intent Guard Report: {goal sentence}

## Verdict: **{PASS | REVIEW NEEDED | BLOCKED}**

## L1 — Mechanical
- Build: {pass/fail}
- Tests: {pass/fail, N passing / M total}
- Lint: {pass/fail}

## L2 — Task completion
- {N of M} tasks marked complete with diff evidence
- Tasks marked complete without diff evidence:
  - {task description}
  - ...

## L3a — Out-of-scope check
- {OOS item}: PASS / matched at `{file:line}` → BLOCKED
- ...

## L3b — Constraint check
- **C1**: {verdict} — {rationale citing diff evidence}
- **C2**: {verdict} — {rationale}
- ...

## L3c — Failure condition coverage
- **F1**: covered by {task or CI check} → PASS
- **F2**: no cover → REVIEW
- ...

## L3d — Expectations satisfaction
- **E1**: {verdict} — {rationale}
- **E2**: {verdict} — {rationale}
- ...

## Recommendations
{If BLOCKED: list specific violations and the required fix for each}
{If REVIEW: list ambiguous items needing human eyes}
{If PASS: confirm safe to merge; recommend /speckit.compound writeback before merge}
```

---

## Compound store interaction

- Reference any ADRs that the diff touched (and confirm the diff respected them; if an ADR is contradicted, flag it as a BLOCKED-level concern)
- If a correction note from `docs/compound/corrections/` is relevant to a constraint violation, cite it: *"This violation matches correction `{date}-{slug}`; the same mistake was made before."*

---

## Tool choices

- **Read** for the four artifacts (intent, expectations, tasks, diff via Bash)
- **Bash** for `git diff`, `git merge-base`, build, test, lint commands
- **Write** for the `.intentguard.md` report
- **AskUserQuestion** for "open the report file?" prompt after writing

---

## What you do NOT do

- **Auto-merge or auto-revert** — you only report. The human decides what to do with the verdict.
- **Modify the diff** — you are a validator, not a fixer.
- **Re-write the intent or expectations** — those are locked at this point. If they need to change, the user re-runs `/speckit.intent` or `/speckit.expectations`.
- **Approve REVIEW items unilaterally** — if a check is borderline, raise it to REVIEW and let the human decide.
