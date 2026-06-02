# /speckit.gapfill

You are running a **gap-fill analysis**. Your job is to cross-reference the intent doc + expectations doc against the spec-kit-generated tasks list, identify coverage gaps, and append the missing tasks to `specs/{slug}/tasks.md`.

This is **not an interview**. It is automated analysis + diff review. The user's role is to approve, reject, or edit your proposed additions.

---

## Inputs you must load

1. **Intent doc** at `docs/intents/{slug}.intent.md` — for constraints, failure conditions, in-scope items, out-of-scope items
2. **Expectations doc** at `docs/expectations/{slug}.expectations.md` — for positive and edge scenarios
3. **Tasks file** at `specs/{slug}/tasks.md` — the spec-kit-generated task list to augment

If any of these are missing, stop and tell the user which to generate first.

## Output you produce

- **Append** (do not rewrite) new tasks to `specs/{slug}/tasks.md`
- Each appended task carries a source comment indicating what it derives from (e.g., `<!-- gapfill: derived from C2 -->`)
- Show the user a **diff preview** before writing

---

## The analysis, in order

### Phase 0 — Load and parse all three artifacts

- Read intent doc; extract lists of: constraints, failure conditions, in-scope items, out-of-scope items
- Read expectations doc; extract lists of: positive scenarios, edge scenarios
- Read tasks.md; extract existing tasks. Match spec-kit's formatting conventions (likely markdown checkboxes with brief descriptions).

Confirm to user: *"Loaded intent ({Nc} constraints, {Nf} failure conditions, {No} out-of-scope items), expectations ({Np} positive + {Ne} edge scenarios), and {Nt} existing tasks. Analyzing coverage..."*

### Phase 1 — Build the coverage matrix

For each constraint, failure condition, out-of-scope item, and edge scenario, decide whether an existing task adequately verifies or guards it. Use **semantic matching, not keyword matching** — a task titled "add Lighthouse CI check" covers C5 ("Lighthouse ≥ 90") even if the task doesn't mention "C5".

Output the coverage matrix in chat:

```
Source                              Covered by                  Gap?
─────────────────────────────────── ─────────────────────────── ─────
C1: No FOUC on initial paint        (none)                      ✗ GAP
C2: WCAG 2.1 AA                     T8 (accessibility audit)    ✓
C3: Default to system preference    T5 (theme resolution)       ✓
...
F1: Build fails                     T1 (CI setup)               ✓
F2: Lighthouse drops below 90       (none)                      ✗ GAP
...
OOS: RSS feed                       (none — regression check)   ✗ GAP
OOS: Ghost admin panel              (none — regression check)   ✗ GAP
...
E7: No-JS fallback                  (none)                      ✗ GAP
E8: incognito persistence           (none)                      ✗ GAP
```

### Phase 2 — Propose gap-filling tasks, grouped by source

For each GAP, draft a candidate task entry matching the existing tasks.md format. Group proposals by source category:

- **Constraint-violation tests** — tests that would FAIL if the named constraint were broken
- **Failure-condition checks** — automated checks that fire on the named failure condition
- **Out-of-scope regression checks** — automated checks (or manual review items) that confirm the named out-of-scope area was not touched
- **Negative / edge path tests** — tests that exercise the named edge scenario
- **Cross-cutting concerns** — added independent of intent/expectations: analytics fires on key user actions, accessibility audit baseline, empty-state coverage, error-state coverage

### Phase 3 — Diff preview and review

Show the user a single block containing:
- A header: *"Proposed additions to `specs/{slug}/tasks.md` — {N} new tasks across {N} categories"*
- Proposed additions grouped by source category

Then ask (use AskUserQuestion):
- **accept all** — append everything
- **by group** — toggle entire categories on/off
- **edit individual** — drop to one-at-a-time review for specific entries
- **reject all** — write nothing, end the command

### Phase 4 — Append to tasks.md

Append accepted entries. Preserve spec-kit's formatting. Add a section header before the additions:

```markdown
## Gap-filling tasks (from /speckit.gapfill)
<!-- Generated: {YYYY-MM-DD}. Sources: docs/intents/{slug}.intent.md, docs/expectations/{slug}.expectations.md -->

- [ ] {task description} <!-- gapfill: derived from C1 -->
- [ ] {task description} <!-- gapfill: derived from F2 -->
- [ ] {task description} <!-- gapfill: derived from OOS:RSS -->
- [ ] {task description} <!-- gapfill: derived from E7 -->
...
```

### Phase 5 — Confirm and offer chain

Show summary: *"Appended {N} tasks to specs/{slug}/tasks.md across {N} categories."*

Ask: *"Continue to /speckit.implement? [yes / no]"*

---

## Pushback style

This command is mostly automated. Pushback fires only when the user tries to reject a **high-risk gap**:

Define high-risk gaps as:
- **Any out-of-scope regression check** — `/speckit.intentguard` L3 will block the merge if the OOS area was touched, and you'll have to re-add this task then. Cheaper to add now.
- **Any failure condition with no covering task** — the failure condition was explicitly declared in the intent and is now untestable in CI.

If the user rejects a high-risk gap addition, push back once:

*"You're rejecting the {F1 / OOS} coverage. The intentguard at merge time will still flag the gap, and you'll have to re-add this then. Confirm reject?"*

If they confirm, accept and move on.

---

## Compound store interaction

If `docs/compound/patterns/` exists, scan for "gapfill" templates — past tasks-list augmentations that proved valuable. Propose them as additional candidates if relevant.

If `docs/compound/corrections/` exists, scan for past gap-misses that became bugs — propose tasks that would catch them. Cite the correction by slug.

---

## Tool choices

- **Read** for loading the three artifacts
- **AskUserQuestion** for the accept-all / by-group / individual / reject-all choice
- **Edit** for appending to tasks.md (preserves existing content)
- **Bash** for `date -u +%Y-%m-%d`

---

## What you do NOT do

- **Rewrite existing tasks** — only append
- **Add tasks unrelated to the intent or expectations** — every addition must trace to a specific source (C, F, OOS, E, or a named cross-cutting concern)
- **Run the tasks** — that's `/speckit.implement`
- **Validate after the fact** — that's `/speckit.intentguard`
