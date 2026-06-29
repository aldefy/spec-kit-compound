# Planverify Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `/speckit-compound-planverify` — an independent checker that judges the proposed plan against locked intent + expectations before `/speckit-implement`, returning PASS / REPLAN_ALLOWED / BLOCKED_DRIFT.

**Architecture:** A markdown command file mirroring `speckit.compound.intentguard.md` (sealed-briefing firewall + Tier 1/2/3 independence ladder), adapted to judge `plan.md` + gapfilled `tasks.md` instead of a git diff. Mechanical layer is *surface analysis* (plan's file surface vs intent in/out-of-scope) since nothing is built yet. A config-gated `before_implement` shell hook (default `off`) optionally blocks implement on BLOCKED_DRIFT. Docs + extension registration round it out.

**Tech Stack:** Markdown command files (spec-kit extension convention), Bash gate script, YAML (`extension.yml`), `bats`-style shell assertions for the gate test (or plain bash `set -e` harness — match existing `scripts/` style).

## Global Constraints

- Command files are **agent-prompt** instructions, not executable code — they instruct the orchestrator (verbatim convention from existing `commands/*.md`).
- Gate logic MUST be a **shell script**, never an agent-prompt hook — agent-prompt hooks silently no-op under spec-kit's executor (verified, v0.2.1). Copy the `require-intent.sh` pattern.
- Slug convention: `{slug}` throughout; artifacts live at `docs/intents/{slug}.X.md`, `specs/{slug}/{plan,tasks}.md`.
- The checker NEVER sees planner chat/reasoning — only locked criteria + plan + tasks + surface facts (the firewall).
- Verdict vocabulary is exactly `PASS` / `REPLAN_ALLOWED` / `BLOCKED_DRIFT` (not intentguard's PASS/REVIEW/BLOCKED).
- `SKC_CHECKER` (default `auto`) selects the independence tier; `SKC_PLANVERIFY_GATE` (default `off`) selects gate enforcement. Both read env-first, then `docs/compound/compound-config.yml`.
- planverify is a **validator, not a fixer** — it reports, never auto-patches `plan.md`.
- extension.yml `version` bumps to `0.6.0`.

---

### Task 1: The planverify command file

**Files:**
- Create: `commands/speckit-compound-planverify.md`
- Reference (read, do not modify): `commands/speckit-compound-intentguard.md`, `commands/speckit-compound-gapfill.md`

**Interfaces:**
- Consumes: `docs/intents/{slug}.intent.md`, `docs/expectations/{slug}.expectations.md`, `specs/{slug}/plan.md`, `specs/{slug}/tasks.md`
- Produces: `docs/intents/{slug}.planverify.md` (verdict report), `docs/intents/{slug}.planverify.briefing.md` (sealed briefing), `docs/intents/{slug}.planverify.checker.txt` (raw checker output). The `.planverify.md` frontmatter key `verdict:` is consumed by Task 2's gate script.

This is a documentation/prompt artifact, not code, so it has no unit test cycle of its own — its "test" is the end-to-end fixture run in Task 4. Treat the whole file as one deliverable.

- [ ] **Step 1: Write the command file**

Create `commands/speckit-compound-planverify.md` with this exact content:

````markdown
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

### Phase 0 — Load all inputs

Read all four sources. Compute: number of constraints, failure conditions, OOS
items; number of positive + edge scenarios; number of tasks.

Confirm: *"Loaded intent ({Nc} constraints, {Nf} failure conditions, {No} OOS), expectations ({Np}+{Ne} scenarios), plan, and {Nt} tasks. Running surface analysis here, then dispatching plan judgment to an independent checker."*

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

Identical to intentguard Phase 3: identify your own family, resolve `SKC_CHECKER`,
probe availability (`command -v codex` / `command -v gemini` for Tier 1; native
subagent with `model: haiku` for Tier 2; default subagent for Tier 3). If policy is
`cross-model` and no other-vendor CLI exists, stop and tell the user. Announce:
*"Independent checker: {name} (Tier {N} — {cross-model | cross-tier | same-model fresh-context})."*

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
- **BLOCKED_DRIFT**: *"Verdict: BLOCKED_DRIFT (checked by {checker}). {N} unjustified expansions:"* — list each with the bounded alternative. If gate is `block`, `/speckit-implement` is now blocked until this resolves.

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
````

- [ ] **Step 2: Verify the file is well-formed**

Run: `head -3 commands/speckit-compound-planverify.md && grep -c '^### Phase' commands/speckit-compound-planverify.md`
Expected: frontmatter `---` / `description:` lines, and `7` phases (Phase 0–6).

- [ ] **Step 3: Commit**

```bash
git add commands/speckit-compound-planverify.md
git commit -m "feat(planverify): add /speckit-compound-planverify command"
```

---

### Task 2: The config-gated before_implement gate script

**Files:**
- Create: `scripts/bash/planverify-gate.sh`
- Reference: `scripts/bash/require-intent.sh` (the pattern to copy)

**Interfaces:**
- Consumes: `SKC_PLANVERIFY_GATE` env or `planverify_gate:` in `docs/compound/compound-config.yml`; the `verdict:` frontmatter line of the latest `docs/intents/*.planverify.md`.
- Produces: exit 0 (allow `/speckit-implement`) or exit 1 with a message (block). Registered as a `before_implement` hook in Task 3.

- [ ] **Step 1: Write the gate script**

Create `scripts/bash/planverify-gate.sh` with this exact content:

```bash
#!/bin/bash
# scripts/bash/planverify-gate.sh
#
# Config-gated before_implement hook: optionally blocks /speckit-implement
# until the latest planverify verdict is acceptable.
#
# Default behavior is OFF (no-op) — consistent with every other compound
# command being advisory. The user opts into enforcement via:
#   SKC_PLANVERIFY_GATE=block   (env), or
#   planverify_gate: block      (in docs/compound/compound-config.yml)
#
# When 'block':
#   - missing planverify report           -> exit 1 (run planverify first)
#   - verdict: BLOCKED_DRIFT               -> exit 1 (replan first)
#   - verdict: PASS | REPLAN_ALLOWED       -> exit 0 (proceed)
#
# Shell script, not an agent-prompt hook: agent-prompt hooks silently no-op
# under spec-kit's executor (verified v0.2.1). Mirrors require-intent.sh.

set -u

# Find project root by walking up from cwd
PROJECT_ROOT="$(pwd)"
while [ "$PROJECT_ROOT" != "/" ] && [ ! -d "$PROJECT_ROOT/.specify" ]; do
  PROJECT_ROOT="$(dirname "$PROJECT_ROOT")"
done

if [ ! -d "$PROJECT_ROOT/.specify" ]; then
  echo "ERROR: not in a spec-kit project (.specify/ not found in any parent of $(pwd))"
  exit 1
fi

cd "$PROJECT_ROOT"

# Resolve gate mode: env first, then config file, default off
GATE="${SKC_PLANVERIFY_GATE:-}"
if [ -z "$GATE" ] && [ -f "docs/compound/compound-config.yml" ]; then
  GATE="$(grep -E '^[[:space:]]*planverify_gate:' docs/compound/compound-config.yml \
          | head -1 | sed -E 's/.*planverify_gate:[[:space:]]*//' | tr -d '"'"'"' \r')"
fi
GATE="${GATE:-off}"

# Default (off): no-op, let implement proceed
if [ "$GATE" != "block" ]; then
  exit 0
fi

# block mode: find the most recent planverify report
LATEST="$(find docs/intents -maxdepth 1 -name '*.planverify.md' -type f 2>/dev/null \
          | sort | tail -1)"

if [ -z "$LATEST" ]; then
  echo ""
  echo "  ⚠  SKC_PLANVERIFY_GATE=block but no planverify report exists."
  echo ""
  echo "  Run /speckit-compound-planverify before /speckit-implement."
  echo ""
  exit 1
fi

VERDICT="$(grep -E '^verdict:' "$LATEST" | head -1 | sed -E 's/^verdict:[[:space:]]*//' | tr -d ' \r')"

if [ "$VERDICT" = "BLOCKED_DRIFT" ]; then
  echo ""
  echo "  ⛔ Plan verdict is BLOCKED_DRIFT ($LATEST)."
  echo ""
  echo "  The proposed plan drifts outside locked intent. Replan before"
  echo "  implementing: re-run /speckit-plan, then /speckit-compound-planverify."
  echo ""
  exit 1
fi

echo "✓ planverify verdict: ${VERDICT:-unknown} — /speckit-implement may proceed."
exit 0
```

- [ ] **Step 2: Make it executable**

Run: `chmod +x scripts/bash/planverify-gate.sh`

- [ ] **Step 3: Write the gate test harness**

Create `tests/planverify-gate.test.sh` with this exact content:

```bash
#!/bin/bash
# tests/planverify-gate.test.sh — assertions for planverify-gate.sh
set -u
FAILS=0
GATE_SCRIPT="$(cd "$(dirname "$0")/.." && pwd)/scripts/bash/planverify-gate.sh"

# Build a throwaway spec-kit project root in a temp dir
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
mkdir -p "$WORK/.specify" "$WORK/docs/intents" "$WORK/docs/compound"

run_gate() { ( cd "$WORK" && env "$@" bash "$GATE_SCRIPT" >/dev/null 2>&1 ); echo $?; }
assert_eq() { # $1=actual $2=expected $3=label
  if [ "$1" = "$2" ]; then echo "ok   - $3";
  else echo "FAIL - $3 (got $1, want $2)"; FAILS=$((FAILS+1)); fi
}

# 1. default (no env, no config) -> off -> exit 0
assert_eq "$(run_gate SKC_PLANVERIFY_GATE=)" 0 "default off => allow"

# 2. block + no report -> exit 1
assert_eq "$(run_gate SKC_PLANVERIFY_GATE=block)" 1 "block + no report => deny"

# 3. block + BLOCKED_DRIFT report -> exit 1
printf 'verdict: BLOCKED_DRIFT\n' > "$WORK/docs/intents/foo.planverify.md"
assert_eq "$(run_gate SKC_PLANVERIFY_GATE=block)" 1 "block + BLOCKED_DRIFT => deny"

# 4. block + PASS report -> exit 0
printf 'verdict: PASS\n' > "$WORK/docs/intents/foo.planverify.md"
assert_eq "$(run_gate SKC_PLANVERIFY_GATE=block)" 0 "block + PASS => allow"

# 5. block + REPLAN_ALLOWED report -> exit 0
printf 'verdict: REPLAN_ALLOWED\n' > "$WORK/docs/intents/foo.planverify.md"
assert_eq "$(run_gate SKC_PLANVERIFY_GATE=block)" 0 "block + REPLAN_ALLOWED => allow"

# 6. config file planverify_gate: block + BLOCKED_DRIFT -> exit 1 (no env)
printf 'planverify_gate: block\n' > "$WORK/docs/compound/compound-config.yml"
printf 'verdict: BLOCKED_DRIFT\n' > "$WORK/docs/intents/foo.planverify.md"
assert_eq "$(run_gate SKC_PLANVERIFY_GATE=)" 1 "config block + BLOCKED_DRIFT => deny"

# 7. env overrides config: env off beats config block
assert_eq "$(run_gate SKC_PLANVERIFY_GATE=off)" 0 "env off overrides config block"

echo "---"
[ "$FAILS" -eq 0 ] && { echo "ALL PASS"; exit 0; } || { echo "$FAILS FAILED"; exit 1; }
```

- [ ] **Step 4: Run the test, verify it passes**

Run: `chmod +x tests/planverify-gate.test.sh && bash tests/planverify-gate.test.sh`
Expected: 7 `ok` lines then `ALL PASS`.

- [ ] **Step 5: Commit**

```bash
git add scripts/bash/planverify-gate.sh tests/planverify-gate.test.sh
git commit -m "feat(planverify): config-gated before_implement gate script + tests"
```

---

### Task 3: Register command + gate hook in extension.yml

**Files:**
- Modify: `extension.yml` (add command under `provides.commands`, add `before_implement` under `hooks`, bump `version`)

**Interfaces:**
- Consumes: the command file (Task 1) and gate script (Task 2) by path.
- Produces: extension metadata that surfaces the command and wires the optional gate.

- [ ] **Step 1: Bump the version**

In `extension.yml`, change:
```yaml
  version: "0.5.0"
```
to:
```yaml
  version: "0.6.0"
```

- [ ] **Step 2: Register the command**

In `extension.yml`, immediately after the `speckit.compound.gapfill` command entry (before `speckit.compound.intentguard`), insert:

```yaml
    - name: speckit.compound.planverify
      file: commands/speckit-compound-planverify.md
      description: "L3 PLAN validation by an INDEPENDENT checker (v0.6+): judges the proposed plan + gapfilled tasks against locked intent + expectations BEFORE implementation. Seals locked criteria + plan + tasks + surface analysis into a briefing the planner's context never touches, dispatches to a different model/context (Codex/Gemini → cross-tier Haiku → same-model fresh context). Returns PASS / REPLAN_ALLOWED / BLOCKED_DRIFT. The earlier, cheaper mirror of intentguard."
```

- [ ] **Step 3: Register the gate hook**

In `extension.yml`, under the `hooks:` block, after the `before_specify:` entry, add:

```yaml
  before_implement:
    command: scripts/bash/planverify-gate.sh
    optional: true
    description: "Config-gated (SKC_PLANVERIFY_GATE / planverify_gate:, default off): when 'block', refuses /speckit-implement if the latest planverify verdict is missing or BLOCKED_DRIFT. No-op by default."
```

- [ ] **Step 4: Validate the YAML parses**

Run: `python3 -c "import yaml; d=yaml.safe_load(open('extension.yml')); print(d['extension']['version']); print([c['name'] for c in d['provides']['commands']]); print(list(d['hooks'].keys()))"`
Expected: `0.6.0`, a command list including `speckit.compound.planverify`, and hook keys including `before_specify` and `before_implement`.

- [ ] **Step 5: Commit**

```bash
git add extension.yml
git commit -m "feat(planverify): register command + before_implement gate (v0.6.0)"
```

---

### Task 4: End-to-end fixtures proving the three verdicts

**Files:**
- Create: `tests/fixtures/planverify/README.md` (documents how to run the manual e2e check)
- Create: `tests/fixtures/planverify/{pass,replan,blocked}/` fixture sets

**Interfaces:**
- Consumes: the command file (Task 1).
- Produces: three minimal intent+expectations+plan+tasks fixtures whose surface analysis deterministically yields PASS / REPLAN_ALLOWED / BLOCKED_DRIFT, so a human (or CI driving the command via `claude -p`) can confirm the verdicts.

Surface analysis (Phase 1) is deterministic shell-extractable, so this task tests
*that* layer end-to-end; the checker's LLM judgment is exercised by a human running
the command against these fixtures.

- [ ] **Step 1: Write the PASS fixture**

Create `tests/fixtures/planverify/pass/intent.md`:
```markdown
# Intent: refresh expense list after edit
## In scope
- src/screens/EditExpenseScreen.tsx
## Out of scope
- src/auth/**
- src/db/schema.ts
## Constraints
- C1: no new network calls
## Failure conditions
- F1: list shows stale data after edit
```
Create `tests/fixtures/planverify/pass/plan.md`:
```markdown
# Plan
Touch only src/screens/EditExpenseScreen.tsx to call onSaved() after a 200.
```
Create `tests/fixtures/planverify/pass/expectations.md`:
```markdown
# Expectations
## Positive
- E1: editing an expense refreshes the list
## Edge
- E2: save fails -> list unchanged, error shown
```
Create `tests/fixtures/planverify/pass/tasks.md`:
```markdown
- [ ] T1: call onSaved() in EditExpenseScreen after successful save (covers F1, E1)
- [ ] T2: on save error keep list, show toast (covers E2)
```

- [ ] **Step 2: Write the REPLAN_ALLOWED fixture**

Create `tests/fixtures/planverify/replan/intent.md` (same as pass, plus the sibling is undeclared):
```markdown
# Intent: refresh expense list after edit
## In scope
- src/screens/EditExpenseScreen.tsx
## Out of scope
- src/auth/**
- src/db/schema.ts
## Constraints
- C1: no new network calls
## Failure conditions
- F1: list shows stale data after edit
```
Create `tests/fixtures/planverify/replan/plan.md` (drift request for a sibling with the same bug):
```markdown
# Plan
Fix src/screens/EditExpenseScreen.tsx. While investigating, found the same
swallowed-save bug in EditCompletedSessionScreen.

requested_surface:
  files: [src/screens/EditCompletedSessionScreen.tsx]
  reason: identical onSaved() omission causes the same stale-list failure
  risk_class: behavioral
  bounded_by: F1
```
Create `tests/fixtures/planverify/replan/expectations.md` and `tasks.md` (copy the pass versions verbatim).

- [ ] **Step 3: Write the BLOCKED_DRIFT fixture**

Create `tests/fixtures/planverify/blocked/intent.md` (same intent — auth is explicitly out of scope):
```markdown
# Intent: refresh expense list after edit
## In scope
- src/screens/EditExpenseScreen.tsx
## Out of scope
- src/auth/**
- src/db/schema.ts
## Constraints
- C1: no new network calls
## Failure conditions
- F1: list shows stale data after edit
```
Create `tests/fixtures/planverify/blocked/plan.md` (heavy unjustified drift into out-of-scope auth + schema):
```markdown
# Plan
Refactor navigation, change src/db/schema.ts, add analytics, and modify
src/auth/middleware.ts while fixing the save flow.
```
Create `tests/fixtures/planverify/blocked/expectations.md` and `tasks.md` (copy the pass versions verbatim).

- [ ] **Step 4: Write the fixtures README**

Create `tests/fixtures/planverify/README.md`:
```markdown
# planverify fixtures

Three minimal feature snapshots whose surface analysis deterministically
drives each verdict. To verify end-to-end, copy a fixture into a scratch
spec-kit project as docs/intents/foo.intent.md, docs/expectations/foo.expectations.md,
specs/foo/plan.md, specs/foo/tasks.md, then run /speckit-compound-planverify
and confirm the verdict:

| Fixture   | Expected verdict | Why |
|-----------|------------------|-----|
| pass/     | PASS             | surface ⊆ in-scope, full coverage |
| replan/   | REPLAN_ALLOWED   | one bounded requested_surface for a sibling file |
| blocked/  | BLOCKED_DRIFT    | touches out-of-scope src/auth/** + src/db/schema.ts, unrequested |
```

- [ ] **Step 5: Verify fixtures are internally consistent**

Run: `grep -l 'src/auth' tests/fixtures/planverify/blocked/plan.md && grep -l 'requested_surface' tests/fixtures/planverify/replan/plan.md && ! grep -lq 'out of scope\|requested_surface' tests/fixtures/planverify/pass/plan.md && echo "fixtures consistent"`
Expected: prints the two file paths then `fixtures consistent` (pass fixture has no drift markers).

- [ ] **Step 6: Commit**

```bash
git add tests/fixtures/planverify/
git commit -m "test(planverify): pass/replan/blocked e2e fixtures"
```

---

### Task 5: Docs — README, CHANGELOG (M5)

**Files:**
- Modify: `README.md` (insert planverify in the workflow; add planverify-vs-intentguard section)
- Modify: `CHANGELOG.md` (v0.6.0 entry)

**Interfaces:**
- Consumes: nothing in code.
- Produces: user-facing documentation of the new step + gate config.

- [ ] **Step 1: Find the workflow list in README**

Run: `grep -n 'speckit-compound-gapfill\|speckit-implement\|speckit.compound.gapfill' README.md`
Expected: line number(s) where the per-feature workflow lists gapfill → implement. (If the README uses a different ordering format, adapt the next step to match it.)

- [ ] **Step 2: Insert planverify into the workflow**

In `README.md`, in the per-feature workflow list, insert a `/speckit-compound-planverify` line between the gapfill step and the `/speckit-implement` step. Match the existing list's exact formatting (bullets vs numbered vs code block). Add this one-line gloss next to it:

> `/speckit-compound-planverify` — judge the proposed plan against locked intent before implementing (PASS / REPLAN_ALLOWED / BLOCKED_DRIFT). Independent checker; gate is opt-in via `SKC_PLANVERIFY_GATE=block`.

- [ ] **Step 3: Add the planverify-vs-intentguard section**

In `README.md`, after the section that describes `intentguard` (find it: `grep -n -i intentguard README.md`), add:

```markdown
### planverify vs intentguard

Both use the same independent-checker firewall, but guard different moments:

| | planverify | intentguard |
|---|---|---|
| **When** | after gapfill, before implement | after implement |
| **Judges** | the proposed plan + tasks | the actual git diff |
| **Catches** | planning drift (before any code) | implementation drift (after code) |
| **Verdicts** | PASS / REPLAN_ALLOWED / BLOCKED_DRIFT | PASS / REVIEW NEEDED / BLOCKED |

planverify is the cheaper, earlier gate — catching drift before code is written
is far cheaper than unwinding it from a diff. The gate is opt-in: set
`SKC_PLANVERIFY_GATE=block` (env) or `planverify_gate: block` (in
`docs/compound/compound-config.yml`) to block `/speckit-implement` on
BLOCKED_DRIFT. Default is advisory (report only).
```

- [ ] **Step 4: Add the CHANGELOG entry**

In `CHANGELOG.md`, add a new entry at the top (match the existing entry format):

```markdown
## 0.6.0

### Added — planverify: judge the plan before execution

- **`/speckit-compound-planverify`** — the earlier, cheaper mirror of intentguard.
  Runs after gapfill, before implement. Seals a briefing of locked intent +
  expectations + plan + gapfilled tasks + surface analysis (never the planner's
  context) and dispatches it to an independent checker via the same Tier 1/2/3
  ladder (`SKC_CHECKER`). Returns **PASS / REPLAN_ALLOWED / BLOCKED_DRIFT**.
- **Surface analysis** mechanical layer — compares the plan's proposed file surface
  against intent's in/out-of-scope, flags drift candidates for the checker.
- **Drift-request contract** — planners declare bounded scope expansion via a
  `requested_surface:` block (files / reason / risk_class / bounded_by); unrequested
  drift is judged more strictly.
- **Config-gated `before_implement` hook** (`SKC_PLANVERIFY_GATE`, default `off`).
  When `block`, refuses `/speckit-implement` if the latest verdict is missing or
  BLOCKED_DRIFT. Shell-script gate mirroring `require-intent.sh`.
```

- [ ] **Step 5: Verify the edits landed**

Run: `grep -c 'planverify' README.md && grep -q '0.6.0' CHANGELOG.md && echo "docs updated"`
Expected: a count ≥ 3 for README, then `docs updated`.

- [ ] **Step 6: Commit**

```bash
git add README.md CHANGELOG.md
git commit -m "docs(planverify): workflow + planverify-vs-intentguard + v0.6.0 changelog"
```

---

### Task 6: Verify the gate hook actually fires (the open hedge)

**Files:**
- Modify (only if the hook does NOT fire): `commands/speckit-compound-planverify.md`, `README.md`, `extension.yml`

**Interfaces:**
- Consumes: the registered `before_implement` hook (Task 3).
- Produces: either confirmation the hook fires, or a documented manual-invocation fallback.

The spec flagged this: spec-kit's documented hook points are `before_specify` and
`after_implement` — `before_implement` is **unverified**. This task resolves it.

- [ ] **Step 1: Check whether spec-kit dispatches before_implement**

Run: `grep -riE 'before_implement|before_plan|after_implement|hook_points|valid.*hook' .specify/ 2>/dev/null | head; echo "---"; find .specify -name '*.py' -o -name '*.toml' 2>/dev/null | xargs grep -liE 'before_|hook' 2>/dev/null | head`
Expected: either evidence `before_implement` is a recognized hook point, or nothing (meaning it is not).

- [ ] **Step 2: Decide based on the evidence**

- **If `before_implement` is recognized:** the registration in Task 3 is sufficient. Add to `commands/speckit-compound-planverify.md` (end of the "Position in the loop" section) one line: *"When `SKC_PLANVERIFY_GATE=block`, a `before_implement` hook enforces this automatically."* Done.
- **If it is NOT recognized:** the `optional: true` registration is harmless but inert. Update the gate's documentation to a verified path:
  - In `README.md` planverify-vs-intentguard section, change the gate sentence to: *"set `SKC_PLANVERIFY_GATE=block` and run `scripts/bash/planverify-gate.sh` before `/speckit-implement` (or wire it as a `PreToolUse` hook via `/speckit-compound-install-hooks`)."*
  - In `extension.yml`, keep the `before_implement` entry (forward-compatible) but extend its `description:` with `"(no-op until spec-kit exposes before_implement; invoke the script manually or via PreToolUse meanwhile)"`.

- [ ] **Step 3: Commit whichever path applies**

```bash
git add -A
git commit -m "docs(planverify): confirm/adjust before_implement gate dispatch path"
```

---

## Notes for the executor

- Tasks 1–5 are independent enough to review separately; Task 6 depends on Task 3 being committed.
- The command file (Task 1) is a prompt artifact — its real exercise is Task 4's fixtures run by a human/CI, not a unit test.
- Keep the verdict vocabulary exact everywhere: `PASS` / `REPLAN_ALLOWED` / `BLOCKED_DRIFT`. A typo here breaks the gate script's `grep`.
- Match existing `scripts/bash/*.sh` conventions (the `set -u`, project-root walk, `✓`/`⚠` message style) — copy from `require-intent.sh`.
