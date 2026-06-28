# Spec-Kit Compound Roadmap: Planning Verification + Live Loop Telemetry

This roadmap folds Vinay's planning-verification loop into Spec-Kit Compound.

The core idea: planners may drift during planning, but drift must be judged before execution. Execution should only happen after the proposed plan has been verified against locked intent, locked expectations, and the complete task obligation set.

## Target Workflow

```text
SPEC-KIT COMPOUND + VINAY LOOP
────────────────────────────────────────────────────────────────

  1. LOAD
     Load committed compound memory.

        /speckit-compound-load

        docs/compound/
        ├─ ADRs
        ├─ corrections
        └─ patterns


  2. INTENT
     User defines what is allowed and not allowed.

        /speckit-compound-intent

        docs/intents/foo.intent.md
        ├─ Goal
        ├─ In scope
        ├─ Out of scope
        ├─ Constraints
        └─ Failure conditions


  3. EXPECTATIONS
     Validator-only success and edge cases.

        /speckit-compound-expectations

        docs/expectations/foo.expectations.md
        ├─ Positive scenarios
        └─ Edge scenarios


  4. SPEC-KIT PLANNING
     Normal SpecKit creates spec, plan, and tasks.

        /speckit-specify
        /speckit-plan
        /speckit-tasks

        specs/foo/
        ├─ spec.md
        ├─ plan.md
        └─ tasks.md


  5. GAPFILL
     Compound completes missing guardrail tasks.

        /speckit-compound-gapfill

        tasks.md now includes:
        ├─ happy-path tasks
        ├─ constraint checks
        ├─ failure-condition checks
        ├─ out-of-scope regression checks
        └─ edge-case checks


  6. PLANVERIFY
     Judge the plan before execution.

        /speckit-compound-planverify

        Inputs:
        ├─ intent.md
        ├─ expectations.md
        ├─ plan.md
        └─ gapfilled tasks.md

        Output:
        ┌─────────────────────┐
        │ PASS                │ no drift
        │ REPLAN_ALLOWED      │ small justified drift
        │ BLOCKED_DRIFT       │ bad scope expansion
        └─────────────────────┘


  7. IMPLEMENT
     Executor can only run an approved plan.

        /speckit-implement


  8. INTENTGUARD
     Judge the actual git diff after implementation.

        /speckit-compound-intentguard

        Checks:
        ├─ Did implementation stay in scope?
        ├─ Did it satisfy expectations?
        ├─ Did it violate constraints?
        └─ Did it touch out-of-scope areas?


  9. WRITEBACK
     Save lessons into compound memory.

        /speckit-compound-writeback
```

## Control Loop Mapping

```text
Vinay loop:
  plan → verify → exec → judge → checkpoint

Spec-Kit Compound:
  plan/tasks/gapfill → planverify → implement → intentguard → writeback
```

```text
┌────────────┐
│   PLAN     │  /speckit-plan + /speckit-tasks + gapfill
└─────┬──────┘
      │
      ▼
┌────────────┐
│  VERIFY    │  planverify catches planning drift
└─────┬──────┘
      │
      ▼
┌────────────┐
│   EXEC     │  implement runs only approved scope
└─────┬──────┘
      │
      ▼
┌────────────┐
│   JUDGE    │  intentguard catches implementation drift
└─────┬──────┘
      │
      ▼
┌────────────┐
│ CHECKPOINT │  writeback records lessons
└────────────┘
```

## Why Planverify Runs After Gapfill

Before `gapfill`, the SpecKit task list may be incomplete. It may cover the happy path while missing constraints, failure conditions, edge cases, and out-of-scope regression checks.

`gapfill` completes `tasks.md` with the full obligation set derived from intent and expectations. `planverify` must run after that because it should judge the proposed execution plan against the complete set of obligations, not just the initial SpecKit task list.

```text
Before gapfill:
  planverify sees an incomplete contract

After gapfill:
  planverify sees the real contract
```

## Planning Drift Policy

Planning drift is not automatically bad. Sometimes the planner discovers that the declared surface is insufficient to satisfy the intent.

```text
PLANNER DRIFT REQUEST
────────────────────────────────────────────

Planner says:
  "I need to touch files outside the original surface."

Verifier asks:
  "Is this necessary, bounded, and still inside intent?"
```

Decision table:

```text
┌──────────────────────┬──────────────────────┬────────────────┐
│ Planner behavior     │ Example              │ Verdict        │
├──────────────────────┼──────────────────────┼────────────────┤
│ No drift             │ Uses planned files    │ PASS           │
│ Small useful drift   │ Adds sibling screen   │ REPLAN_ALLOWED │
│ Heavy bad drift      │ Adds auth/schema/nav  │ BLOCKED_DRIFT  │
└──────────────────────┴──────────────────────┴────────────────┘
```

Acceptable drift example:

```text
Intent:
  Fix save flow so the list refreshes after editing an expense.

Planner discovers:
  EditExpenseScreen swallows successful saves.
  EditCompletedSessionScreen has the same callback issue.

Verdict:
  REPLAN_ALLOWED
```

Blocked drift example:

```text
Intent:
  Fix save flow so the list refreshes after editing an expense.

Planner proposes:
  Refactor navigation.
  Change expense schema.
  Add analytics.
  Redesign completed session UX.
  Modify auth middleware.

Verdict:
  BLOCKED_DRIFT
```

## Planverify Versus Intentguard

`planverify` and `intentguard` guard different moments in the loop.

```text
planverify:
  Is the proposed plan already drifting before files are edited?

intentguard:
  Did the actual git diff drift after implementation?
```

Both are needed. `planverify` prevents expensive or messy execution. `intentguard` confirms that the executor actually stayed inside the approved plan and locked intent.

## Live Dashboard Direction

The existing dashboard shows artifact status and stage progress. Vinay's screenshot points toward live control-loop telemetry: the dashboard should show what the agents are doing, when they request drift, why that drift is requested, and how the verifier responds.

Target live activity stream:

```text
LIVE ACTIVITY
────────────────────────────────────────────────────────────────

8:27:55  role_start       planner
8:27:55  expand_request   + src/screens/EditExpenseScreen.tsx
                          + src/screens/EditCompletedSessionScreen.tsx

                          reason:
                          save succeeds with 200,
                          but edit screens do not call onSaved()

8:27:55  auto_replan      reason=surface
8:27:55  planverify       verdict=REPLAN_ALLOWED
8:27:55  role_done        planner

8:28:10  role_start       executor
8:29:40  role_done        executor

8:29:41  role_start       intentguard
8:30:05  verdict          PASS
8:30:05  checkpoint       step=1
```

The dashboard should eventually display:

```text
drift_request
  phase: planning
  requested_files: [...]
  reason: ...
  verdict: REPLAN_ALLOWED | BLOCKED_DRIFT
  checker: codex | claude | gemini | fresh-context
  independence_tier: 1 | 2 | 3
```

## Proposed Milestones

### Milestone 1: Planverify Command

Add `/speckit-compound-planverify` as a new command after `gapfill` and before `implement`.

Required outputs:

```text
docs/intents/{slug}.planverify.md
docs/intents/{slug}.planverify.briefing.md
docs/intents/{slug}.planverify.checker.txt
```

Verdict contract:

```text
PASS
REPLAN_ALLOWED
BLOCKED_DRIFT
```

### Milestone 2: Drift Request Contract

Define a structured way for the planner to request expanded scope.

Suggested shape:

```text
requested_surface:
  files:
    - path/to/file-a
    - path/to/file-b
  reason: concrete causal reason
  risk_class: behavioral | public-contract | schema | auth-security | migration | unknown
  bounded_by: intent item / task id / constraint id
```

### Milestone 3: Drift Probe

Add `/speckit-compound-driftprobe` to intentionally create a synthetic bad plan and prove `planverify` blocks it. This command must never run implementation.

Purpose:

```text
Force planner drift.
Freeze the bad plan.
Verify that planverify returns BLOCKED_DRIFT.
Confirm the loop does not stall.
```

### Milestone 4: Dashboard Telemetry

Extend the dashboard from artifact status into live loop telemetry.

Add event rows for:

```text
role_start
expand_request
auto_replan
planverify
role_done
intentguard
verdict
checkpoint
```

### Milestone 5: Documentation and Install Flow

Update README and command docs so the per-feature workflow becomes:

```text
/speckit-compound-load
/speckit-compound-intent
/speckit-compound-expectations
/speckit-specify
/speckit-plan
/speckit-tasks
/speckit-compound-gapfill
/speckit-compound-planverify
/speckit-implement
/speckit-compound-intentguard
/speckit-compound-writeback
```

## Summary

```text
Intent + expectations define the boundary.
Gapfill completes the obligation set.
Planverify catches planning drift.
Implement executes only approved scope.
Intentguard catches implementation drift.
Writeback compounds the lesson.
Dashboard shows the loop in motion.
```
