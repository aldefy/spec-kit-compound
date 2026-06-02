# spec-kit-compound

A SpecKit extension that adds **intent-driven scoping** (ICE), **compound engineering memory**, and **L3 intent guard validation** to the Spec-Driven Development workflow.

> **Positioning.** This is an *extension*, not a *harness*. We sit on top of whatever harness SpecKit drives (Claude Code, Cursor, Copilot, Gemini CLI, etc.) and inject the missing intent / expectations / compound discipline before, during, and after the standard SpecKit chain. We are not a competitor to harness frameworks like Garura — we complement them.

---

## What this gives you

Five new commands that wrap the vanilla SpecKit workflow:

| Command | Phase | Adds |
|---|---|---|
| `/speckit.intent` | Before `specify` | Interview-driven goal + constraints + failure conditions; refuses to terminate until quality tests pass |
| `/speckit.expectations` | After intent, before `specify` | Success scenarios in a separate file (validator-only — soft compartmentation against reward-hacking) |
| `/speckit.compound load` | Start of feature | Reads committed ADRs / corrections / patterns into agent context |
| `/speckit.gapfill` | After `tasks`, before `implement` | Appends missing constraint-violation, failure-condition, and edge tests to tasks.md |
| `/speckit.intentguard` | After `implement`, before merge | L3 validation: diff vs intent scope. Returns PASS / REVIEW / BLOCKED |
| `/speckit.compound writeback` | After intentguard PASS | Persists new ADRs, corrections, and patterns back to the compound store |

---

## Install

Local dev:
```bash
specify extension add --dev /path/to/spec-kit-compound
```

Once published:
```bash
specify extension add --from https://github.com/aldefy/spec-kit-compound/archive/refs/tags/v0.1.0.zip
```

---

## The cheat sheet (10-step flow)

```
/speckit.compound load        # NEW — pull past ADRs/corrections/patterns into context
/speckit.intent               # NEW — interview-driven goal, constraints, failure conditions
/speckit.expectations         # NEW — success scenarios (validator-only)
/speckit.specify              # vanilla — paste intent's goal + in-scope here
/speckit.plan                 # vanilla
/speckit.tasks                # vanilla
/speckit.gapfill              # NEW — add constraint-violation + negative tests to tasks.md
/speckit.implement            # vanilla
/speckit.intentguard          # NEW — L3 gate before merge
/speckit.compound writeback   # NEW — commit learnings from this run
```

Three commands wrap **before** SpecKit, one **mid** (gapfill, between tasks and implement), two **after** (intentguard, writeback). SpecKit's vanilla chain is unchanged.

Mental shortcut:

```
load → intent → expectations → [specify, plan, tasks] → gapfill → implement → intentguard → writeback
```

The two surfaces:
- **Standard mode** — call `/speckit.intent` once; it chains the rest with checkpoints. You only answer the interview and approve a couple of "commit?" prompts.
- **Power-user mode** — call each command individually for surgical re-runs (e.g., revise just the expectations).

---

## Why this exists

SpecKit is excellent at generating specs and driving the agentic implementation loop, but it leaves three systematic gaps:

1. **It doesn't separate intent from spec.** Goals, constraints, and failure conditions get fused into one document. SpecKit's own `/speckit.specify` template instructs the agent to *"make informed guesses"* and *"fill gaps"*, capped at *"Maximum 3 [NEEDS CLARIFICATION] markers"* — converting spec ambiguity directly into unsupervised model choices.

2. **It doesn't compartment expectations from intent.** Success scenarios live in the same artifact the builder reads, which enables **reward-hacking**: the builder optimizes for the validator's checks if both come from the same file.

3. **It doesn't persist memory across sessions.** Claude Code's memory files live locally, not in the project's `.claude` folder under version control. New sessions, new machines, and new teammates start with zero context.

This extension fixes each:

1. `/speckit.intent` runs an **interview** that refuses to terminate until the intent passes a strict quality rubric (G1–G5 for goal, C1–C5 for constraints, F1–F4 for failure conditions). No silent gap-filling, no "informed guesses."
2. `/speckit.expectations` writes success scenarios to a **separate file** the builder doesn't read — soft compartmentation against reward-hacking. The validator (`/speckit.intentguard`) reads it; the builder (`/speckit.implement`) does not.
3. `/speckit.compound load` / `writeback` make the agent's memory a **committed, version-controlled** artifact under `docs/compound/`, similar to Architecture Decision Records but extended for AI-specific learnings (corrections, patterns).

For the full design rationale and the IDSD framing, see [`docs/ref.md`](docs/ref.md).
For the implementation and launch plan, see [`docs/plan.md`](docs/plan.md).

---

## The compound store

After a few features, your repo grows a `docs/compound/` directory:

```
docs/compound/
├── adr/           ← architectural decisions; do not re-debate
├── corrections/   ← past AI mistakes; do not repeat
└── patterns/      ← approaches proven in this codebase; reach for these
```

Every feature contributes back via `/speckit.compound writeback`. Every feature inherits the accumulated store via `/speckit.compound load`. This is the "compound" in compound engineering: each engineering cycle makes the next one easier.

SpecKit's `/speckit.constitution` is a **one-time, static** governance document. The compound store is a **living, growing** one. After 20 features, the compound store has more applied wisdom than any constitution doc you could write upfront — because it was derived from real work, not imagined ahead of time.

---

## Project status

**v0.1 — early.** The extension is functional but unbattle-tested.

- Soft compartmentation only (separate files in separate folders; same agent reads both, with the implement command instructed not to load expectations). Hard compartmentation (separate agents, encrypted evals) is deferred to v0.2+ if evidence of gaming emerges.
- No integration tests against a real SpecKit installation yet.
- Roadmap:
  - Battle-test on 2–3 real features (Travv World, Equal AI, aditlal.dev)
  - Submit to SpecKit's [Community Friends](https://github.github.io/spec-kit/community/friends.html) page
  - Apply for verified extension status in the [SpecKit catalog](https://github.com/github/spec-kit/blob/main/extensions/EXTENSION-PUBLISHING-GUIDE.md)

---

## License

MIT. See [LICENSE](LICENSE).

---

## Credits

- **GitHub SpecKit** — the toolkit this extends. <https://github.com/github/spec-kit>
- **Kapil Viren Ahuja** — the IDSD / ICE framework. *Activated Thinker* publication on Medium.
- **Every (Kevin Rose, Dan Shipper)** — the compound engineering pattern. <https://every.to/guides/compound-engineering>
- **#gen-ai-wtf Slack** — kenkyee and Ricardo Costeira, the conversation that crystallized the committed-vs-local memory distinction.
