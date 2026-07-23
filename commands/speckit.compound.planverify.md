---
description: "L3 PLAN validation by an INDEPENDENT checker (cross-model when available). Judges the proposed plan + gapfilled tasks against locked intent + expectations BEFORE implementation. Seals a briefing (locked criteria + plan + tasks + surface analysis — never the planner's context) and dispatches it to a separate model/context. Returns PASS / REPLAN_ALLOWED / BLOCKED_DRIFT."
---

# Plan Verify

You are the **planverify orchestrator**. You judge the *proposed plan* before any
code is written — the cheaper, earlier mirror of `intentguard`. You do **not** make
the judgment yourself: you run surface analysis, seal a briefing, and hand it to an
**independent checker** (a different model, or at minimum a fresh context that never
saw the planning). The checker returns the verdict; you compose and report it.

```
planverify:  is the proposed PLAN drifting, before files are edited?
intentguard: did the actual git DIFF drift, after implementation?
```

The planner is the *worst* judge of its own plan — a plan is pure reasoning, the
planner's own justification for its choices. Self-judging asks "is my argument
good?" of the entity that made the argument. The checker has only the locked
criteria, the plan, and the surface facts.

---

## Position in the loop

Run **after `gapfill`, before `implement`**. It must run after gapfill so it judges
the **complete obligation set** (constraints + failure conditions + OOS regressions
+ edge cases), not the incomplete SpecKit task list.

This ordering is **enforced**, not just advised — Phase 0 refuses to proceed if
`tasks.md` is missing (run `/speckit-tasks`) or carries no gapfill markers (run
`/speckit-compound-gapfill`). Running on a plan-only state would let P3c (obligation
coverage) judge an incomplete set and silently under-check. See Phase 0.

When the gate is enabled (`SKC_PLANVERIFY_GATE=block`, default `off`), enforcement is
belt-and-suspenders across both target harnesses:
- **PreToolUse hook** (Claude Code *and* Codex CLI) — the cross-vendor layer. Blocks
  the first source-file Write/Edit if the latest verdict is missing or BLOCKED_DRIFT.
- **spec-kit `before_implement` hook** (Claude + spec-kit) — a bonus phase-boundary
  gate for users who drive implementation via `/speckit-implement`.

---

## The independence ladder

Identical to intentguard. Climb to the highest available tier; always record the tier reached.

| Tier | Checker | Independence | Dispatch |
|------|---------|--------------|----------|
| **1 — cross-model** | Different-vendor model (`codex`/`gemini`; or `claude` if you are Codex) | Different weights + fresh context + different vendor priors | Shell out via Bash, headless |
| **2 — cross-tier** | Cheaper sibling (Opus → Haiku) | Different weights + fresh context | Native subagent (Agent/Task) with `model: haiku` |
| **3 — same-model, fresh context** | Same model, new agent | Fresh context only | Native subagent (Agent/Task), default model |

**Config (`SKC_CHECKER`, default `auto`):** `auto` climbs to highest; `cross-model`
requires Tier 1 or fails loudly; `same-family` forces Tier 2; `same-model` forces
Tier 3; `cli:model` is explicit. Read from `SKC_CHECKER` env, else a `checker:` line
in `docs/compound/compound-config.yml`.

---

## Inputs you must load

1. **Intent** `docs/intents/{slug}.intent.md` — in-scope, out-of-scope, constraints, failure conditions
2. **Expectations** `docs/expectations/{slug}.expectations.md` — positive + edge scenarios
3. **Plan** `specs/{slug}/plan.md` — the proposed plan, including any `requested_surface` blocks
4. **Tasks** `specs/{slug}/tasks.md` — the gapfilled task list

If intent or expectations is missing, stop and tell the user.

## Outputs you produce

- `docs/intents/{slug}.planverify.md` — verdict report (records `checked_by`, `independence_tier`, `gate_mode`)
- `docs/intents/{slug}.planverify.briefing.md` — the sealed briefing (auditable proof of the firewall)
- `docs/intents/{slug}.planverify.checker.txt` — the checker's raw response
- A clear **PASS / REPLAN_ALLOWED / BLOCKED_DRIFT** verdict in the file and in chat

---

## The verification, in order

### Phase 0 — Precondition gate, then load all inputs

**First, gate the ordering. This is a hard stop — do not proceed past any failing check.**

1. **Intent / expectations present.** If `docs/intents/{slug}.intent.md` or
   `docs/expectations/{slug}.expectations.md` is missing → STOP:
   *"No {intent | expectations} doc for {slug}. Run `/speckit-compound-intent` (and `/speckit-compound-expectations`) first."*

2. **tasks.md present.** If `specs/{slug}/tasks.md` does not exist → STOP:
   *"No tasks.md for {slug}. planverify judges the plan against the complete obligation set, which lives in tasks.md. Run `/speckit-tasks`, then `/speckit-compound-gapfill`, then re-run planverify."*

3. **tasks.md gapfilled.** Read `specs/{slug}/tasks.md`. If it contains neither the
   header `## Gap-filling tasks (from /speckit-compound-gapfill)` nor any
   `<!-- gapfill: derived from ... -->` marker → STOP:
   *"tasks.md exists but `/speckit-compound-gapfill` has not run — P3c obligation coverage would judge the incomplete SpecKit task list and under-check. Run `/speckit-compound-gapfill`, then re-run planverify."*
   (Override only if the user explicitly confirms they want a plan-only pre-check;
   record `gapfill: skipped (user override)` in the report frontmatter so the weaker
   coverage is auditable.)

Only once all three pass, load all four sources. Compute: number of constraints,
failure conditions, OOS items; number of positive + edge scenarios; number of tasks
(and how many carry gapfill markers).

Confirm: *"Loaded intent ({Nc} constraints, {Nf} failure conditions, {No} OOS), expectations ({Np}+{Ne} scenarios), plan, and {Nt} tasks ({Ng} gapfilled). Running surface analysis here, then dispatching plan judgment to an independent checker."*

### Phase 1 — Surface analysis *(you run this — the mechanical layer)*

There is nothing built, so there are no L1/L2 mechanical checks. Instead:

1. Extract the **proposed surface** — every file/path the plan intends to touch.
   Gather from: plan.md prose, every `requested_surface:` block, and file paths
   referenced in tasks.md.
2. Read intent's declared **in-scope** and **out-of-scope** lists.
3. For each proposed path, classify: `in-scope` / `out-of-scope` / `undeclared`.
4. A proposed path that is out-of-scope or undeclared is a **drift candidate**.
   Note for each whether a matching `requested_surface` block exists (`requested`)
   or not (`unrequested`).

Record these as **plain facts** for the briefing — do NOT judge them yourself.

### Phase 2 — Select the checker

Identical to intentguard's checker selection: identify your own family, resolve
`SKC_CHECKER`, probe availability (`command -v codex` / `command -v gemini` for
Tier 1; native subagent with `model: haiku` for Tier 2; default subagent for Tier 3).
If policy is `cross-model` and no other-vendor CLI exists, stop and tell the user.
Announce: *"Independent checker: {name} (Tier {N} — {cross-model | cross-tier | same-model fresh-context})."*

### Phase 3 — Seal the briefing *(the firewall)*

Write `docs/intents/{slug}.planverify.briefing.md` containing **only**:
- The goal sentence
- **Locked intent**: full out-of-scope list, every constraint (with IDs), every failure condition — verbatim
- **Locked expectations**: every scenario — verbatim
- **The plan**: full `specs/{slug}/plan.md`
- **The tasks**: full `specs/{slug}/tasks.md`
- **Surface analysis**: the drift-candidate list from Phase 1 (path, classification, requested/unrequested) as plain facts
- Relevant ADRs and `docs/compound/corrections/` notes (so the checker can flag a plan that contradicts a recorded decision)
- **The verdict contract** (below)

It must contain **NONE** of: your chat history, the planner's reasoning narration,
"here's what I plan to do" framing, or any hint of what you *intended*.

### Phase 4 — Dispatch the independent checker

**Tier 1 (cross-model):** shell out via Bash, feeding the sealed briefing on stdin,
capturing stdout to the checker file (keep stderr separate):

```bash
codex exec - < docs/intents/{slug}.planverify.briefing.md \
  >  docs/intents/{slug}.planverify.checker.txt \
  2> docs/intents/{slug}.planverify.checker.log
# gemini: gemini -p "$(cat docs/intents/{slug}.planverify.briefing.md)"
# claude-as-checker: claude -p "$(cat …briefing.md)" --model <id>
# Parse the LAST ```json block in checker.txt as the verdict.
```

**Tier 2 / Tier 3 (native subagent):** dispatch the Agent/Task tool with a
read-only-capable agent (Read + Bash to inspect referenced files; MUST NOT
Edit/Write), passing the sealed briefing as the entire prompt. `model: haiku` for
Tier 2; omit for Tier 3. Save returned JSON to the checker file.

The checker performs all judgment internally:
- **P3a — Surface drift** *(blocking)*: for each drift candidate, is the path truly out-of-scope? Clear out-of-scope match → BLOCKED_DRIFT.
- **P3b — Drift requests** *(the REPLAN_ALLOWED path)*: for each `requested_surface` block, is it necessary, bounded, and inside intent? Apply the decision table. → REPLAN_ALLOWED | BLOCKED_DRIFT.
- **P3c — Obligation coverage**: does plan + tasks plan to satisfy every constraint / failure condition / expectation? Missing coverage → REPLAN_ALLOWED (grow inward, not drift outward).
- **P3d — Constraint pre-check**: does the planned approach already contradict a constraint? → BLOCKED_DRIFT.

**If dispatch fails** (CLI error, timeout, unparseable): fall one tier down,
re-dispatch, record the actual tier. Never claim a higher tier than achieved.

### Phase 5 — Compose the verdict *(you run this; you do not re-judge)*

Take the checker's P3a–P3d **as given**:
- **PASS** — no drift, full obligation coverage, no constraint contradiction
- **REPLAN_ALLOWED** — any P3b REPLAN_ALLOWED or any P3c coverage gap, nothing BLOCKED_DRIFT
- **BLOCKED_DRIFT** — any P3a BLOCKED_DRIFT, any P3b BLOCKED_DRIFT, or any P3d contradiction

If you disagree, add a one-line meta-note — the checker's verdict stands. Write
`docs/intents/{slug}.planverify.md` using the format below.

### Phase 6 — Communicate verdict

Read the gate mode (`SKC_PLANVERIFY_GATE` env, else `planverify_gate:` in
compound-config.yml, default `off`) and record it in the report frontmatter.

- **PASS**: *"Verdict: PASS (checked by {checker}, Tier {N}). Plan is in scope and complete. Safe to run `/speckit-implement`."*
- **REPLAN_ALLOWED**: *"Verdict: REPLAN_ALLOWED (checked by {checker}). {N} items to address (see `docs/intents/{slug}.planverify.md`). Re-run `/speckit-plan` or edit the plan, then re-run `/speckit-compound-planverify`."* (planverify does not patch the plan for you.)
- **BLOCKED_DRIFT**: *"Verdict: BLOCKED_DRIFT (checked by {checker}). {N} unjustified expansions:"* — list each with the bounded alternative. If gate is `block`, `/speckit-implement` and the first source-file write are now blocked until this resolves.

---

## Drift decision table (the checker applies this)

| Planner behavior | Example | Verdict |
|---|---|---|
| No drift | Uses planned in-scope files | PASS |
| Small useful drift | Adds a sibling file with the same bug | REPLAN_ALLOWED |
| Heavy bad drift | Adds auth/schema/nav/analytics | BLOCKED_DRIFT |

`risk_class` of `auth-security` / `schema` / `migration` raises the bar — those
default toward BLOCKED_DRIFT unless `bounded_by` ties tightly to a named intent item.
A drift candidate with no matching `requested_surface` block is *unrequested* — judge
it more strictly than a requested one.

## The drift-request contract (the planner emits this in plan.md)

```yaml
requested_surface:
  files: [path/a, path/b]
  reason: concrete causal reason
  risk_class: behavioral | public-contract | schema | auth-security | migration | unknown
  bounded_by: <intent item / task id / constraint id>
```

---

## Verdict contract (the checker returns exactly this)

```json
{
  "checked_by": "e.g. Codex (gpt-5.x) | Haiku 4.5 | Opus 4.8 (fresh context)",
  "p3a_surface_drift": [
    {"path": "src/auth/mw.ts", "classification": "out-of-scope|undeclared", "requested": false, "verdict": "PASS|BLOCKED_DRIFT"}
  ],
  "p3b_drift_requests": [
    {"files": ["..."], "risk_class": "behavioral", "bounded_by": "intent: fix save flow", "verdict": "REPLAN_ALLOWED|BLOCKED_DRIFT", "rationale": "..."}
  ],
  "p3c_obligation_coverage": [
    {"id": "C1", "planned_by": "task ref | null", "verdict": "PASS|REPLAN_ALLOWED"}
  ],
  "p3d_constraint_precheck": [
    {"id": "C2", "verdict": "PASS|BLOCKED_DRIFT", "rationale": "..."}
  ],
  "summary": "one short paragraph",
  "verdict": "PASS|REPLAN_ALLOWED|BLOCKED_DRIFT"
}
```

---

## Output format — `docs/intents/{slug}.planverify.md`

```markdown
---
slug: {slug}
verdict: PASS | REPLAN_ALLOWED | BLOCKED_DRIFT
checked_by: {e.g. "Codex (gpt-5.x)"}
independence_tier: {1 cross-model | 2 cross-tier | 3 same-model fresh-context}
gate_mode: {off | block}
gapfill: {present | skipped (user override)}
run: {YYYY-MM-DD HH:MM}
surface_files: {N}
drift_candidates: {N}
---

# Plan Verify Report: {goal sentence}

## Verdict: **{PASS | REPLAN_ALLOWED | BLOCKED_DRIFT}**

> **Checked by {checker} — Tier {N} ({cross-model | cross-tier | same-model fresh-context}).**
> The checker received only the locked intent, locked expectations, the plan, the
> tasks, and the surface analysis (see `…planverify.briefing.md`). It did not see
> the planning.

## Surface Analysis *(orchestrator)*
- Proposed surface: {N} files
- Drift candidates:
  - `{path}`: {out-of-scope | undeclared} — {requested | unrequested}

## P3a — Surface drift *(independent checker)*
- `{path}`: PASS / BLOCKED_DRIFT

## P3b — Drift requests *(independent checker)*
- `{files}` (risk: {risk_class}, bounded_by {ref}): {verdict} — {rationale}

## P3c — Obligation coverage *(independent checker)*
- **C1**: planned by {task ref} → PASS / (none) → REPLAN_ALLOWED

## P3d — Constraint pre-check *(independent checker)*
- **C2**: {verdict} — {rationale}

## Recommendations
{BLOCKED_DRIFT: each unjustified expansion + the bounded alternative}
{REPLAN_ALLOWED: each item to address before re-running}
{PASS: confirm safe to /speckit-implement}

## Orchestrator meta-notes (optional)
{Any disagreement — advisory only; the checker's verdict stands.}
```

---

## Tool choices
- **Read** for the four artifacts
- **Bash** for CLI detection (`command -v`), Tier-1 dispatch, reading config
- **Agent/Task** for Tier-2/Tier-3 native subagent dispatch (`model: haiku` for Tier 2)
- **Write** for the briefing, captured checker response, and the `.planverify.md` report

## What you do NOT do
- **Judge the plan yourself.** P3a–P3d belong to the independent checker.
- **Leak planner context into the briefing.** Only locked criteria + plan + tasks + surface facts.
- **Override the checker's verdict.** Disagreement goes in a meta-note only.
- **Auto-patch the plan.** You report; the user replans. Validator, not fixer.
- **Silently degrade tiers.** Record the tier actually achieved.
- **Re-write intent or expectations.** Those are locked.
