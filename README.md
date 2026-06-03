# spec-kit-compound

A SpecKit extension that adds **intent-driven scoping** (ICE), **compound engineering memory**, and **L3 intent guard validation** to the Spec-Driven Development workflow.

> **Positioning.** This is an *extension*, not a *harness*. We sit on top of whatever harness SpecKit drives (Claude Code, Cursor, Copilot, Gemini CLI, etc.) and inject the missing intent / expectations / compound discipline before, during, and after the standard SpecKit chain. We are not a competitor to harness frameworks like Garura — we complement them.

---

## The concepts

Two ideas this extension wires together. Neither is mine — both came from people doing real work and writing it up.

### Compound engineering

Coined by [Every](https://every.to/guides/compound-engineering) (Kevin Rose, Dan Shipper). The idea: **every engineering cycle should make the next one easier.** You do this by writing durable notes back into the repo as you work — architectural decisions, AI corrections, reusable patterns — and loading them as context before the next cycle.

The **compound store** (committed under `docs/compound/`) holds three things:

- **ADRs** — architectural decisions; do not re-debate
- **Corrections** — past AI mistakes and the rules derived from them; do not repeat
- **Patterns** — proven approaches for this codebase; reach for these by default

After 20 features the compound store has more applied wisdom than any constitution doc you could write up front — because it was derived from real work, not imagined ahead of time. SpecKit's `/speckit-constitution` is a one-time static document; the compound store is a **living, growing** one. That's the "compound" in compound engineering.

### ICE — Intent, Context, Expectations

Coined by Kapil Viren Ahuja (Activated Thinker on Medium) as the building blocks of **intent-driven software development** (IDSD). The frame splits what you give an agent into three slots:

| Slot | What it is | Who owns it |
|---|---|---|
| **Intent** | Goal + constraints + failure conditions — what only you can write | You |
| **Context** | The surround (stack, codebase, prior decisions) — fed progressively | The harness |
| **Expectations** | Success scenarios + boundary of done — compartmented from Intent | You |

**The compartmentation is the critical bit.** Success scenarios must not appear in the artifact the builder reads, because LLMs reward-hack — the builder will optimize for the validator's checks if both come from the same file. That's why this extension writes intent and expectations to **separate files** (`docs/intents/` vs `docs/expectations/`) and instructs `/speckit-implement` to only load the intent doc, not the expectations doc.

### How this extension combines them

```
COMPOUND STORE
  (loaded into context at session start)
       │
       ▼
  /speckit-compound-intent          (Intent: goal + constraints + failure conditions)
       │
  /speckit-compound-expectations    (Expectations: success scenarios, separate file)
       │
  /speckit-specify → /speckit-plan → /speckit-tasks  (SpecKit's standard flow)
       │
  /speckit-compound-gapfill         (constraint-violation + edge tests added to tasks.md)
       │
  /speckit-implement                (SpecKit's standard implementation loop)
       │
  /speckit-compound-intentguard     (L3 validation: diff vs intent's OOS / constraints / failures)
       │
  /speckit-compound-writeback       (persist new ADRs / corrections / patterns)
       │
       ▼
COMPOUND STORE (now richer — next feature inherits)
```

**ICE** provides the input discipline. **Compound engineering** provides the memory loop. **SpecKit** provides the execution mechanism. This extension is the wiring that makes the three work together as one system.

For the full design rationale, see [`docs/ref.md`](docs/ref.md).

---

## What this gives you

**Six commands you type during a feature** that wrap the vanilla SpecKit workflow:

| Command | Phase | Adds |
|---|---|---|
| `/speckit-compound-intent` | Before `specify` | Interview-driven goal + constraints + failure conditions; refuses to terminate until quality tests pass |
| `/speckit-compound-expectations` | After intent, before `specify` | Success scenarios in a separate file (validator-only — soft compartmentation against reward-hacking) |
| `/speckit-compound-load` | Start of feature | Reads committed ADRs / corrections / patterns into agent context |
| `/speckit-compound-gapfill` | After `tasks`, before `implement` | Appends missing constraint-violation, failure-condition, and edge tests to tasks.md |
| `/speckit-compound-intentguard` | After `implement`, before merge | L3 validation: diff vs intent scope. Returns PASS / REVIEW / BLOCKED |
| `/speckit-compound-writeback` | After intentguard PASS | Persists new ADRs, corrections, and patterns back to the compound store |

**Plus infrastructure** (run once per project / never typed by hand during a feature):

| Command | When | What |
|---|---|---|
| `/speckit-compound-install-hooks` | One-time, per project | Installs the v0.3+ Claude Code `PreToolUse` hook that blocks Write/Edit on documented past mistakes (opt-in, see [tool-level enforcement](#v03-tool-level-enforcement-opt-in) below) |
| `/speckit-compound-require-intent` | Auto-fires `before_specify` | Gate hook (v0.2.2+) — refuses to let `/speckit-specify` proceed if no intent doc exists. Shell-script wrapper; dispatches reliably under SpecKit's hook executor. |

---

## Install

Local dev:
```bash
specify extension add --dev /path/to/spec-kit-compound
```

Latest tagged release:
```bash
specify extension add --from https://github.com/aldefy/spec-kit-compound/archive/refs/tags/v0.3.1.zip
```

After install, **one-time per project**, opt into the v0.3+ tool-level hook:
```
/speckit-compound-install-hooks
```
(See [tool-level enforcement](#v03-tool-level-enforcement-opt-in) for what this adds.)

---

## The cheat sheet (10-step flow)

```
/speckit-compound-load        # NEW — pull past ADRs/corrections/patterns into context
/speckit-compound-intent               # NEW — interview-driven goal, constraints, failure conditions
/speckit-compound-expectations         # NEW — success scenarios (validator-only)
/speckit-specify              # vanilla — paste intent's goal + in-scope here
/speckit-plan                 # vanilla
/speckit-tasks                # vanilla
/speckit-compound-gapfill              # NEW — add constraint-violation + negative tests to tasks.md
/speckit-implement            # vanilla
/speckit-compound-intentguard          # NEW — L3 gate before merge
/speckit-compound-writeback   # NEW — commit learnings from this run
```

Three commands wrap **before** SpecKit, one **mid** (gapfill, between tasks and implement), two **after** (intentguard, writeback). SpecKit's vanilla chain is unchanged.

Mental shortcut:

```
load → intent → expectations → [specify, plan, tasks] → gapfill → implement → intentguard → writeback
```

**The chain has two automatic segments and two manual injection points.**

**Auto-chain (3 hops via in-prompt handoffs):** start with `/speckit-compound-intent`. On completion, its Phase 8 prompt hands off to `/speckit-compound-expectations`. On completion, that hands off to `/speckit-specify`. Claude dispatches the next slash command directly — no user typing required between these three.

After `/speckit-specify`, you're in spec-kit's own chain: `/speckit-clarify` (optional), `/speckit-plan`, `/speckit-tasks`.

**Manual injection #1 — after `/speckit-tasks`:** type `/speckit-compound-gapfill`. Spec-kit's `/speckit-tasks` is not our prompt, so we can't auto-trigger from inside it. You drive this hop.

**Standard spec-kit continues:** `/speckit-implement` runs as normal.

**Manual injection #2 — after `/speckit-implement`:** type `/speckit-compound-intentguard`. Returns PASS / REVIEW NEEDED / BLOCKED.

**Suggested by intentguard's own prompt (PASS only):** `/speckit-compound-writeback`.

So the user-typed surface is: **3 commands** total — the entry point, the post-tasks injection, the post-implement injection (with writeback prompted automatically). The other 3 of our 6 commands run via in-prompt chain dispatch.

### Why not full automation via spec-kit hooks?

v0.2.0 registered `before_*` / `after_*` hooks in `extension.yml`. They installed cleanly into `.specify/extensions.yml` but silently no-op'd at run time. Spec-kit's hook executor dispatches **shell-script** hooks cleanly (like the bundled `git` extension's branch-creation script) but does **not** dispatch **agent-prompt** hooks like ours under Claude Code — the agent reads `EXECUTE_COMMAND` as descriptive text and continues with the parent command. v0.2.1 drops the misleading hooks and relies on in-prompt Phase 8 handoffs, which **do** fire correctly.

### Verify each step landed its artifact

After the run (or any partial run):

```bash
./scripts/check-chain-fired.sh <feature-slug>
```

A ✗ per step means that step was skipped or didn't write its artifact — type it manually.

### v0.3+ tool-level enforcement (opt-in)

In addition to the slash-command chain above, v0.3 adds a **Claude Code `PreToolUse` hook layer** that runs on every Write/Edit — regardless of whether SpecKit is in the loop. Install once per project with `/speckit-compound-install-hooks`. After install:

- Every agent Write/Edit checks the proposed file path + content against `docs/compound/corrections/*.md`
- If any correction with a `paths:` glob matching the file path **and** `match:` regex matching the content fires, the tool call is blocked (exit 2) with structured stderr: correction file path + matched rule + one-line context
- The agent reads the stderr and adjusts its plan rather than proceeding
- Two bypass mechanisms: per-file `// compound-allow: <correction-slug>` comment (audit trail in diff) or `COMPOUND_BYPASS=1` env var (session-wide sledgehammer)

This is the **two-layer enforcement** model:

| Layer | Trigger | Mechanism | Since |
|---|---|---|---|
| **L1** | User types `/speckit-specify` | SpecKit `before_specify` gate refuses without an intent doc | v0.2.2 |
| **L2** | Agent attempts Write/Edit | Claude Code `PreToolUse` hook refuses on correction match | v0.3 |

L2 catches everything L1 catches, plus everything L1 misses (the user who skips SpecKit entirely and codes directly with the agent).

See [`docs/compound/CORRECTIONS-SCHEMA.md`](docs/compound/CORRECTIONS-SCHEMA.md) for the v0.3+ correction schema (frontmatter fields `paths:`, `match:`, `rule:`, `context:`), gotchas (POSIX ERE only — no `\s`, watch double-quoted YAML escapes), and a worked example.

---

## Why this exists

SpecKit is excellent at generating specs and driving the agentic implementation loop, but it leaves four systematic gaps:

1. **It doesn't separate intent from spec.** Goals, constraints, and failure conditions get fused into one document. SpecKit's own `/speckit-specify` template instructs the agent to *"make informed guesses"* and *"fill gaps"*, capped at *"Maximum 3 [NEEDS CLARIFICATION] markers"* — converting spec ambiguity directly into unsupervised model choices.

2. **It doesn't compartment expectations from intent.** Success scenarios live in the same artifact the builder reads, which enables **reward-hacking**: the builder optimizes for the validator's checks if both come from the same file.

3. **It doesn't persist memory across sessions.** Claude Code's memory files live locally, not in the project's `.claude` folder under version control. New sessions, new machines, and new teammates start with zero context.

4. **Even when memory is persisted, it's passive.** ADR-style notes and AI correction records are loaded as context but the agent can ignore them. The same mistake gets repeated, the same architectural decision gets re-debated. The store doesn't *enforce* anything.

This extension fixes each:

1. `/speckit-compound-intent` runs an **interview** that refuses to terminate until the intent passes a strict quality rubric (G1–G5 for goal, C1–C5 for constraints, F1–F4 for failure conditions). No silent gap-filling, no "informed guesses."
2. `/speckit-compound-expectations` writes success scenarios to a **separate file** the builder doesn't read — soft compartmentation against reward-hacking. The validator (`/speckit-compound-intentguard`) reads it; the builder (`/speckit-implement`) does not.
3. `/speckit-compound-load` / `writeback` make the agent's memory a **committed, version-controlled** artifact under `docs/compound/`, similar to Architecture Decision Records but extended for AI-specific learnings (corrections, patterns).
4. **v0.3+ adds a Claude Code `PreToolUse` hook** that turns the compound store into **active enforcement**. When the agent tries to Write/Edit a file that matches a documented past mistake, the tool call is blocked at the moment of the attempt — before any code is written. Two bypass mechanisms (per-file comment + session env var) keep the discipline overridable when the user knows what they're doing.

For the full design rationale and the IDSD framing, see [`docs/ref.md`](docs/ref.md).
For the implementation and launch plan, see [`docs/plan.md`](docs/plan.md).

---

## Roadmap

Tracked direction beyond v0.3.

### v0.3.1+ — sibling tool-level gates

Other 3 hook designs from `docs/hooks-research.md`:

- `active-out-of-scope` — block any Write/Edit to a file path declared out-of-scope in the active intent doc
- `active-intent-existence` — block any Write under `src/` or `app/` when no intent doc exists for the current feature
- `active-complexity-gate` — block any Write whose proposed function exceeds cyclomatic complexity threshold

### v0.4 — multi-model orchestration, structured outputs, drift

- **Multi-model orchestration** — Codex as a first-class subprocess. Phase config routes tools per phase (e.g. CC plans, Codex adversarially verifies, CC executes, Codex reviews). Cross-vendor verification breaks self-preferential bias structurally: Claude reviewing Claude shares training distribution; Codex reviewing Claude doesn't.
- **Structured expectation outputs** — JSON-schema-typed expectations instead of free-form markdown. Insight from translating SRE skills to dynamic workflows: the schema is what forces the synthesizer to defer claims (emit `candidates`) so a separate verifier can adjudicate. Prose can ask for structural separation; only schema enforces it.
- **CLAUDE.md auto-distillation** (`/speckit.compound.distill`) — promotes a shipped feature's convention constraints from `expectations.md` into project-level CLAUDE.md rules. Each feature compounds its learned conventions into the next — the literal "compound" in compound engineering.
- **Adversarial verification as a formal phase** — not implicit. Inputs: intent + plan + codebase. Output: structured drift report. Configurable drift threshold gate halts execution above the threshold.
- **PR-time drift check** — CI workflow template that loads relevant `intent.md` constraints on every PR touching a feature area, adversarially checks whether constraints still hold, comments on the PR if drift is detected.

### v0.4+ — multi-CLI portability

For the tool-level gates. The bash hook scripts themselves are CLI-agnostic; only the settings translation differs.

- Codex CLI (`~/.codex/config`)
- Cursor 1.7+ (`beforeReadFile`, `afterFileEdit`)
- Gemini CLI (`.gemini/settings.json` with `BeforeTool` matcher)

### v0.5 — server-side enforcement

`.git/hooks/pre-commit` template and a GitHub Action template wrapping `scripts/check-chain-fired.sh`, for belt-and-braces enforcement when the agent runs outside a harness with hook support (raw API calls, CI bots, etc.).

### v0.5+ — multi-repo + compound infrastructure

- **Multi-repo workspace** — root-intent → per-repo children → cross-repo boundary verification at API contracts and shared schemas. Workspace shape: e.g. KMP app + backend + CMS as one feature, three plans, one root intent.
- **Drift-audit scheduled workflow** — weekly run that walks every shipped feature's spec, adversarially asks "does this still hold?", produces a backlog of violations ranked by severity.
- **Decision-log knowledge base** — after each ship, write `.claude/feature-knowledge/{feature}/decisions.md` capturing the "why" behind chosen constraints. Future AI sessions read this before touching the feature.
- **Orchestrator script** — `compound.workflow.js` running the full pipeline (brainstorm → classify → per-repo fan-out → plan → cross-plan coherence → adversarial verify → gate → execute → review → integration review → synthesize → PR) with explicit gates.
- **Eval framework** — tests that the verifier catches what it should. Without this we can't measure whether v0.4 changes are actually improvements.

### Other

- **Pre-v0.3 correction migration helper** — one-shot command that walks existing corrections and prompts the user to add the v0.3+ frontmatter (`paths:`, `match:`, `rule:`, `context:`). Out-of-scope for v0.3 per the intent doc; revisit when there's real volume of pre-v0.3 corrections in the wild.
- **SpecKit Friends listing + extension catalog submission** — after 2–3 successful real-feature runs.

### Open architecture questions (resolve before v0.4)

- **Intent capture path** — `/speckit.compound.intent` vs `superpowers:brainstorming`. Currently overlapping. Unify (delegate intent capture to the skill), keep distinct (`intent.md` as the spec-kit-compound artifact), or compose (brainstorming produces a draft, `intent.md` formalizes)?
- **Spec file format** — free-form markdown (today) vs frontmatter + machine-readable constraint IDs. Affects every downstream consumer (verifier, distiller, drift-check).
- **Per-phase model + token budget** — global config, per-workflow config, or both? How does it interact with per-phase model routing from multi-model orchestration?
- **Codex invocation surface** — subprocess (`codex exec`) vs HTTP (OpenAI SDK directly). Subprocess inherits Codex's harness/skills; HTTP is more portable but loses harness benefits.

For the design rationale behind the v0.3.1+ gates, see [`docs/hooks-research.md`](docs/hooks-research.md) and [`docs/intents/active-corrections.intent.md`](docs/intents/active-corrections.intent.md).

---

## Project status

**v0.3.1 — active enforcement, smoke-tested.** The extension is functional, conventions match real spec-kit (hyphenated slash commands, dotted filenames, dual hook layers), and the v0.3 PreToolUse correction-enforcement hook is verified end-to-end (6/6 smoke tests pass). Battle-testing on real features still pending — looking for 2–3 early adopters; reach out via the [SpecKit Friends](https://github.github.io/spec-kit/community/friends.html) channels or open a GitHub issue.

What's verified:
- Live install in a real spec-kit-initialized project (`specify init . --integration claude` → `specify extension add <path> --dev` → all 8 commands register, gate hook merges into `.specify/extensions.yml` cleanly alongside the bundled `git` extension)
- v0.2.2 `before_specify` gate hook fires correctly under Claude Code (shell-script wrapper pattern)
- v0.3 `PreToolUse` correction-enforcement hook: 6 scenarios verified — match blocks with structured stderr; non-match allows; subdir paths match the `**/*.ext` glob; both bypass mechanisms (`// compound-allow:` comment + `COMPOUND_BYPASS=1` env var) work
- Static validation (`scripts/validate.sh`) — 30/30 checks pass

What's not yet verified:
- Real-feature end-to-end run (intent → spec → plan → tasks → gapfill → implement → intentguard → writeback) on a production codebase. The chain shape is proven via paper tests + the retrofit run; the full feature run is the next milestone.
- Multi-CLI support (Codex CLI, Cursor, Gemini CLI) — see [Roadmap](#roadmap)
- Hard compartmentation (separate agents, encrypted evals) — deferred to v0.4+ if evidence of reward-hacking emerges with the soft (file-separation) version

Known limitations:
- Soft compartmentation only. Same agent reads both intent and expectations docs; the separation is enforced by file location and by `/speckit-implement`'s prompt instructions, not by structural isolation.
- v0.3 PreToolUse hook is Claude Code only. Other CLIs use the same shell-script contract but different settings file paths — ports planned for v0.4+.
- Pre-v0.3 corrections (markdown body only, no frontmatter) load as context but are not actively enforced until upgraded to the v0.3 schema.

---

## License

MIT. See [LICENSE](LICENSE).

---

## Credits

- **GitHub SpecKit** — the toolkit this extends. <https://github.com/github/spec-kit>
- **Kapil Viren Ahuja** — the IDSD / ICE framework. *Activated Thinker* publication on Medium.
- **Every (Kevin Rose, Dan Shipper)** — the compound engineering pattern. <https://every.to/guides/compound-engineering>
- **#gen-ai-wtf Slack** — kenkyee and Ricardo Costeira, the conversation that crystallized the committed-vs-local memory distinction.
