# Planverify — Judge the Plan Before Execution

**Date:** 2026-06-29
**Scope:** Roadmap Milestones 1 + 2 + 5
**Branch:** `planverify-dashboard-roadmap`

## Problem

Spec-Kit Compound catches *implementation* drift after the fact (`intentguard`
judges the git diff). But planners drift during planning too — proposing to touch
files outside the declared surface, or quietly skipping obligations. By the time
`intentguard` fires, code has already been written against a drifted plan. That is
expensive to catch and messy to unwind.

`planverify` adds the missing gate: **judge the proposed plan against locked intent
+ expectations before any code is written.** It is the cheaper, earlier mirror of
`intentguard`.

```
planverify:  is the proposed PLAN drifting, before files are edited?
intentguard: did the actual git DIFF drift, after implementation?
```

## Position in the loop

After `gapfill`, before `implement`. It must run *after* gapfill so it judges the
**complete obligation set** (constraints + failure conditions + OOS regressions +
edge cases), not the incomplete SpecKit task list.

```
load → intent → expectations → specify → plan → tasks → gapfill
     → PLANVERIFY → implement → intentguard → writeback
```

## Design decision: full independence (mirror intentguard)

planverify delegates judgment to an **independent checker** via the same sealed-
briefing firewall and Tier 1/2/3 ladder as `intentguard`. Rationale:

- A plan is *pure reasoning* — the planner's own justification for its choices.
  Self-judging a plan is asking "is my argument good?" of the entity that made the
  argument. Zero distance, maximal motivated reasoning.
- The expensive failure mode (BLOCKED_DRIFT slipping through as PASS) is exactly
  what a self-judge rationalizes away. An independent checker seeing only
  `intent says auth is out-of-scope` + `plan touches auth` returns BLOCKED with no
  rationalization path.
- Consistency: `intentguard` already pays the firewall cost. The earlier, cheaper
  gate should not be the weaker one.

The `REPLAN_ALLOWED` verdict (judging whether drift is *necessary, bounded, and
inside intent*) is precisely the nuanced call best made by a checker holding only
the locked criteria + the structured drift-request — not the planner's enthusiasm.

## Architecture (mirror of intentguard, adapted)

### Inputs
1. `docs/intents/{slug}.intent.md` — in-scope, out-of-scope, constraints, failure conditions
2. `docs/expectations/{slug}.expectations.md` — positive + edge scenarios
3. `specs/{slug}/plan.md` — the proposed plan (incl. any drift-request blocks, see M2)
4. `specs/{slug}/tasks.md` — the gapfilled task list

If intent or expectations is missing → stop, tell the user.

### Mechanical layer (orchestrator runs) — Surface Analysis
There is no L1/L2 (nothing is built). The mechanical layer is **surface analysis**:
- Extract the file/path surface the plan proposes to touch (from plan.md prose +
  any `requested_surface` blocks + tasks.md file references).
- Compare against intent's declared in-scope / out-of-scope.
- Every proposed path outside declared in-scope → a **drift candidate** handed to
  the checker as a plain fact (not a verdict).

### Judgment layer (independent checker runs)
Sealed briefing → Tier 1/2/3 ladder (`SKC_CHECKER`, default `auto`) → verdict.
Briefing contains ONLY: goal sentence, locked intent (verbatim OOS + constraints +
failure conditions), locked expectations (verbatim), plan.md, tasks.md, the
surface-analysis drift candidates, relevant compound ADRs/corrections, and the
verdict contract. NONE of the planner's chat/reasoning narration.

Checker grades:
- **P3a — Surface drift** *(blocking)*: plan touches out-of-scope paths? Clear match → BLOCKED_DRIFT.
- **P3b — Drift requests** *(the REPLAN_ALLOWED path)*: for each `requested_surface` block, is it necessary, bounded, and inside intent? → REPLAN_ALLOWED | BLOCKED_DRIFT.
- **P3c — Obligation coverage**: does plan + tasks plan to satisfy every constraint / failure condition / expectation? Missing coverage → REPLAN_ALLOWED (plan must grow *inward*, not drift outward).
- **P3d — Constraint pre-check**: does the planned approach already contradict a constraint? → BLOCKED_DRIFT.

### Verdict
- **PASS** — no drift, full coverage. Safe to `/speckit-implement`.
- **REPLAN_ALLOWED** — small justified drift OR an inward coverage gap to fix. Reports what to fix; does NOT auto-patch the plan (validator, not fixer). User re-runs `/speckit-plan` or edits, then re-runs planverify.
- **BLOCKED_DRIFT** — unjustified scope expansion OR constraint contradiction.

### Drift decision table (the checker applies this)
| Planner behavior | Example | Verdict |
|---|---|---|
| No drift | Uses planned files | PASS |
| Small useful drift | Adds sibling screen with the same bug | REPLAN_ALLOWED |
| Heavy bad drift | Adds auth/schema/nav/analytics | BLOCKED_DRIFT |

`risk_class` of `auth-security | schema | migration` raises the bar — those default
toward BLOCKED unless `bounded_by` ties tightly to a named intent item.

## M2 — Drift-request contract

A parseable block the planner emits in `plan.md` to *request* expanded surface
instead of silently drifting:

```yaml
requested_surface:
  files: [path/a, path/b]
  reason: concrete causal reason
  risk_class: behavioral | public-contract | schema | auth-security | migration | unknown
  bounded_by: <intent item / task id / constraint id>
```

The checker grades each block against the decision table. A drift candidate found
by surface analysis that has NO matching `requested_surface` block is treated as
*unrequested* drift — heavier scrutiny, defaults toward BLOCKED_DRIFT.

## Outputs (auditable trio, mirror intentguard)
- `docs/intents/{slug}.planverify.md` — verdict report (records `checked_by`, `independence_tier`, `gate_mode`)
- `docs/intents/{slug}.planverify.briefing.md` — the sealed briefing (proof the checker saw no planner context)
- `docs/intents/{slug}.planverify.checker.txt` — checker's raw response

### Verdict file format
Mirror `intentguard.md` exactly: YAML frontmatter (`slug`, `verdict`,
`checked_by`, `independence_tier`, `run`, `surface_files`, `drift_candidates`,
`gate_mode`) + sectioned markdown (Surface Analysis, P3a–P3d, Recommendations,
Orchestrator meta-notes).

### Verdict contract (checker returns exactly this)
```json
{
  "checked_by": "e.g. Codex (gpt-5.x) | Haiku 4.5 | Opus 4.8 (fresh context)",
  "p3a_surface_drift": [
    {"path": "src/auth/mw.ts", "in_scope": false, "requested": false, "verdict": "BLOCKED_DRIFT"}
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

## Gating — config-driven, default advisory

The gate is **opt-in**. Knob alongside `SKC_CHECKER`:
- `SKC_PLANVERIFY_GATE` env var, or `planverify_gate:` in `docs/compound/compound-config.yml`
- `off` *(default)* — advisory; planverify writes the verdict and tells the user, never blocks. Consistent with every other compound command.
- `block` — a `before_implement` spec-kit hook blocks `/speckit-implement` when the latest `.planverify.md` is missing or `verdict: BLOCKED_DRIFT`.

### Gate mechanism
A `before_implement` spec-kit hook wrapping a shell script, mirroring how
`require-intent` wraps `before_specify`. The script:
1. Anchors to the spec-kit project root (`.specify/`).
2. Reads `SKC_PLANVERIFY_GATE` (env, then `compound-config.yml`, default `off`).
3. If not `block` → exit 0 silently (no-op). `/speckit-implement` proceeds.
4. If `block`: find the latest `docs/intents/*.planverify.md`.
   - Missing → exit 1: "Run /speckit-compound-planverify before implementing."
   - `verdict: BLOCKED_DRIFT` → exit 1: "Plan is BLOCKED_DRIFT — replan before implementing."
   - `PASS` or `REPLAN_ALLOWED` → exit 0.

(If spec-kit does not expose a `before_implement` hook point, fall back to shipping
the gate script + documenting manual `SKC_PLANVERIFY_GATE=block` enforcement; verify
the hook point exists during implementation before committing to it.)

## M5 — Docs + install flow
- **README** — insert planverify into the per-feature workflow between gapfill and implement; add a short planverify-vs-intentguard section.
- **CHANGELOG** — new version entry.
- **extension.yml** — register `speckit.compound.planverify` command; register the `before_implement` gate hook as `optional: true` (so it is harmless when the gate is `off`).

## Files to create / modify
- **NEW** `commands/speckit-compound-planverify.md` — the command (mirror intentguard's structure)
- **NEW** `scripts/bash/planverify-gate.sh` — the config-gated `before_implement` gate script
- **EDIT** `extension.yml` — register command + before_implement hook
- **EDIT** `README.md` — workflow + planverify-vs-intentguard
- **EDIT** `CHANGELOG.md` — version entry

## Out of scope (deferred milestones)
- M3 — `/speckit-compound-driftprobe` (synthetic-bad-plan test)
- M4 — dashboard live loop telemetry (event stream rows)

## Testing
- A PASS fixture: plan whose surface ⊆ intent in-scope, full obligation coverage.
- A REPLAN_ALLOWED fixture: plan with one `requested_surface` block for a sibling file, tightly `bounded_by` intent.
- A BLOCKED_DRIFT fixture: plan touching an out-of-scope path (e.g. auth) with no/weak justification.
- Gate script: assert no-op when `off`; assert exit 1 on missing + BLOCKED_DRIFT, exit 0 on PASS/REPLAN_ALLOWED when `block`.
- Independence-ladder degradation: assert it records the tier actually reached, never claims higher.
