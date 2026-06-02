# ref.md
# spec-kit-compound — Conceptual Reference

Everything discussed, reasoned through, and decided in the original design session.
Use this to understand *why* the workflow is designed the way it is.

---

## The three concepts and their roles

Three separate paradigms brought together. They are compatible but not the same thing.

### 1. SpecKit — Execution mechanism

GitHub's open-source Spec-Driven Development toolkit.
Repo: https://github.com/github/spec-kit

**What it actually is:**
- A `specify` CLI that installs prompt template files into your project
- Slash commands: `/speckit-constitution` → `/speckit-specify` → `/speckit-clarify` → `/speckit-plan` → `/speckit-tasks` → `/speckit-implement`
- These are markdown prompt files the agent reads and executes — no API surface, no library

**What it does well:**
- Generates specs, plans, and task breakdowns from a feature description
- Drives the agentic implementation loop
- Works with 30+ AI coding agents (Claude Code, Copilot, Cursor, Gemini CLI, etc.)

**What it does not do:**
- Capture *why* something is being built or what its boundaries are
- Generate constraint-derived or negative test cases reliably
- Validate that implementation stayed within declared scope
- Persist memory across sessions (local memory files die between sessions)

**Known limitations in SpecKit's own templates:**

**P1. The auto-fill trap.** SpecKit's `/speckit-specify` template instructs the agent to *"make informed guesses,"* use *"common patterns"* to *"fill gaps,"* and caps it at *"Maximum 3 [NEEDS CLARIFICATION] markers."* Where the description goes silent, the agent invents the goal — and the tool limits how often it has to admit it is guessing. This converts spec ambiguity directly into unsupervised model choices.

**P2. Internal contradictions across templates.** SpecKit's manifesto declares test-first development *"NON-NEGOTIABLE."* Its task template, shipped in the same repo in the same week, says *"Tests are OPTIONAL, only include them if explicitly requested."* Its implement template says *"Follow the TDD approach."* A goal-seeking model handed three contradictory rules picks one and improvises — the exact behavior the rigid method was supposed to prevent.

These are not bugs in our extension scope, but they explain why intent doc + expectations doc + gapfill are needed: they are the structural defense against templates that silently hedge.

**The key insight:**
The `/speckit-tasks` output IS the "expectations" node in the Activated Thinker agentic loop model. SpecKit is the tool that generates the right side of the intent/expectations diagram.

---

### 2. Intent + Expectations — Input quality layer

From the Activated Thinker framework (the agentic loop model):

```
YOU PROVIDE                 HARNESS RUNS THE LOOP
────────────                ──────────────────────────────
INTENT       ─────────────→ run work
(what the                        ↓
user wants)                 pull context
                                 ↓
EXPECTATIONS ─────────────→ validate → met? → merge
(what counts                     ↑ no ──────┘
as done)
```

**Intent** = the left side of the diagram. What you provide.
**Expectations** = also what you provide. SpecKit generates *task-level* expectations from your intent, but `/speckit-expectations` captures the user-level "done" boundary that the validator (not the builder) consumes.
**The harness** = runs the loop. Could be Claude Code, Copilot Workspace, Cursor, etc.

**Alternative framing: ICE in IDSD.** Kapil Viren Ahuja's "Intent-Driven Software Development" (IDSD) frames this layer as **ICE — Intent, Context, Expectations**:

| ICE leg | What it is | Who owns it |
|---|---|---|
| **Intent** | Goal + constraints + failure conditions | Human |
| **Context** | The surround (stack, codebase, prior decisions), fed progressively | Harness |
| **Expectations** | Success scenarios + boundary of done, compartmented from Intent | Human |

The compartmentation rule from IDSD: success scenarios must not appear in the artifact the builder reads, because LLMs reward-hack — the builder will optimize for the validator's checks if both come from the same file. Our `/speckit-intent` and `/speckit-expectations` split implements this.

**The gap SpecKit leaves:**
SpecKit asks "what do you want to build?" but doesn't structure:
- Scope boundaries (what should NOT be touched)
- Constraints (technical, UX, performance limits) — directional, unconditional, in business language
- Failure conditions (binary, post-output, observable)
- Success scenarios — kept separate from intent for reward-hack defense

These are the things that prevent AI overreach and define what "done" really means.

**Our two committed artifacts** fill this gap:
- `docs/intents/{slug}.intent.md` — goal + constraints + failure conditions
- `docs/expectations/{slug}.expectations.md` — success scenarios + done boundary

---

### 3. Compound Engineering — Memory layer

From a discussion in the #gen-ai-wtf Slack channel about "compound engineering" (kenkyee, Ricardo Costeira), aligned with Every's `/ce-compound` plugin pattern (Kevin Rose, Dan Shipper).

**Core concept:**
Self-documenting code + AI planning notes + user correction notes all committed to the repo as durable context. Similar to Architecture Decision Records (ADRs) but extended to include AI-specific learnings.

**The problem it solves:**
Claude Code's memory files are stored locally, not permanently in the project's `.claude` folder. This means:
- Memory is lost when you switch machines
- Teammates don't benefit from corrections you made
- A new AI session starts with zero context about past mistakes
- Settled architectural decisions get re-debated on every session

**The compound store (committed, version-controlled):**
```
docs/compound/
├── adr/           ← architectural decisions + "rule for AI" in each
├── corrections/   ← what AI did wrong + derived rule to avoid repeat
└── patterns/      ← reusable implementation patterns for this codebase
```

**The compounding effect:**
Each feature run writes back learnings (corrections, patterns, ADRs) to the compound store.
The next feature loads that store before starting.
Over time: fewer loop iterations, fewer corrections, faster merge.

In v0.2 we expose this as two separate commands (spec-kit's extension system does not support subactions):
- `/speckit-compound-load` — pull store into agent context at the start of a feature
- `/speckit-compound-writeback` — persist learnings after intentguard passes

---

## How the three concepts connect

They map onto specific parts of the Activated Thinker / ICE diagram:

| Concept | Role in the loop |
|---|---|
| Compound store | `pull context` step — loaded before every loop iteration via `/speckit-compound-load` |
| Intent doc | `INTENT` node — what you provide on the left (goal + constraints + failure conditions) |
| Expectations doc | `EXPECTATIONS` node — what you provide on the right (success scenarios, compartmented) |
| SpecKit tasks | Task-level expectations the harness loops against |
| SpecKit implement | The harness — runs work → validate → loop |
| Intentguard | Validates the `met?` decision beyond just tests (L3) |
| Compound writeback | Updates compound store after loop exits, via `/speckit-compound-writeback` |

**The summary in one sentence:**
We are automating SpecKit with smarter inputs (intent + expectations layer, compartmented), making its outputs more complete (gapfill), and making the whole system compound over time (compound engineering store).

---

## Key design decisions made in the session

### SpecKit is not a programmatic dependency
SpecKit exposes no API or library. Its integration surface is slash command prompt templates installed into the project via the `specify` CLI.

This means the extension is not code that calls SpecKit — it is additional prompt templates that sit alongside SpecKit's own templates and extend the workflow before and after SpecKit's steps.

### Compound store must be committed, not local
The most critical architectural decision.

SpecKit/Claude Code store agent memory locally. This breaks across sessions, machines, and team members.

The compound store (`docs/compound/`) is version-controlled and committed. It is treated as a first-class repo artifact, the same way ADRs are — because that is exactly what it is.

### Intent and Expectations are separate commands (soft compartmentation, v0.2)
Per IDSD's compartmentation principle, success scenarios must not appear in the same artifact the builder reads, because LLMs reward-hack — the builder will optimize for the scenarios the validator checks if both come from the same file.

For v0.2, we ship **soft compartmentation**: separate `/speckit-intent` and `/speckit-expectations` commands writing to separate files. The builder (during `/speckit-implement`) reads the intent doc; the validator (during `/speckit-intentguard`) reads the expectations doc. Same agent, different artifacts.

Hard compartmentation (separate agents, encrypted evals, builder structurally unable to read the expectations file) is deferred until we have evidence the soft version is being gamed.

### Compound load and writeback are two separate commands (spec-kit convention)
v0.1 drafts considered a single `/speckit-compound` command with `load` and `writeback` subactions, matching Every's `/ce-compound` shape. When we ran the first live install test in v0.2, we discovered spec-kit's extension system does not support subactions — each slash command must be its own file (the bundled git extension exposes `speckit.git.commit`, `.feature`, `.initialize`, `.remote`, `.validate` as five separate commands, not one with subactions). We split accordingly: `/speckit-compound-load` and `/speckit-compound-writeback` are two halves of one mechanism, registered separately. The compartmentation and semantics are unchanged; only the surface shape differs.

### The intent + expectations docs are the gapfill input
SpecKit generates tasks (expectations) from a feature description. But it generates primarily happy-path tasks.

The intent doc's **out-of-scope** and **constraints** sections, plus the expectations doc's **negative scenarios**, are the inputs that `/speckit-gapfill` uses to generate the missing tests — constraint violation checks, scope regression checks, negative paths.

Without these docs, gapfill has no reference to know what constraints exist or what's out of scope.

### Validation Level 3 (Intent Guard)
Most harnesses validate at:
- L1: Tests pass, build is clean
- L2: Output matches the spec

L3 is new: did the implementation **stay within the intent document's declared scope and constraints, and satisfy the expectations doc**?

This requires comparing the git diff against the intent doc's out-of-scope and constraints sections, and against the expectations doc's success scenarios — something that requires a separate LLM call, not just test execution.

The intentguard prompt specifically checks:
1. Were any out-of-scope items touched? (BLOCKED if yes)
2. Were any constraints violated? (BLOCKED if yes)
3. Were any failure conditions tripped? (BLOCKED if yes)
4. Do the success scenarios pass? (REVIEW if uncertain)

### Extension, not fork; extension, not harness
Built as a SpecKit community extension using the official extension mechanism (`extension.yml` + command templates + `specify extension add`).

This means:
- Zero dependency on SpecKit's internals — extension templates are standalone markdown files
- Publishable to the community catalog
- Installable with one command
- Works with any harness SpecKit supports (not just Claude Code)

We are an **extension**, not a harness. Kapil's Garura is a harness — it owns context assembly, eval compartmentation, and checkpointing end to end. We sit on top of an existing harness (whichever spec-kit drives) and inject the missing intent/expectations/compound discipline. The README will state this positioning in one line.

---

## The Friends listing approach

The community site has four contribution types:
- Extensions — commands, hooks, capabilities (requires full extension.yml + catalog PR)
- Presets — template and terminology overrides
- Walkthroughs — end-to-end SDD scenarios
- **Friends** — projects that extend or build on Spec Kit (just a README entry + link)

**Strategy:** Submit to Friends first (lower friction, immediate visibility), then upgrade to verified extension after battle-testing on 2-3 real features.

Existing Friends entries for reference format:
- cc-spex: Claude Code plugin with composable traits on top of SpecKit
- Spec Kit Assistant: VS Code extension with visual orchestrator
- SpecKit Companion: VS Code extension with GUI
- cc-spec-kit: Community-maintained Claude Code / Copilot CLI plugin

---

## Positioning and content angle

**One-line description:**
"A SpecKit extension that adds intent-driven scoping (ICE), compound engineering memory, and intent guard validation to the SDD workflow."

**The story for GDE content:**
- SpecKit generates expectations but misses intent (scope, constraints, non-goals)
- The Activated Thinker / IDSD model shows why: intent and expectations are separate inputs that must be compartmented
- Compound engineering solves the memory problem that SpecKit and harnesses leave unsolved
- This extension wires all three together as a publishable SpecKit extension

**What makes it novel:**
- Intent Guard (L3 validation) — not done by any existing SpecKit extension
- Compound store as committed repo artifacts — solves the local-memory limitation
- Intent/Expectations split with soft compartmentation — defense against reward-hacking
- Gapfill driven by intent + expectations docs — not generic, purpose-built

---

## SpecKit slash commands reference

| Command | Phase | What it does |
|---|---|---|
| `/speckit-constitution` | Init | Create project governing principles |
| `/speckit-specify` | Spec | Generate spec from feature description |
| `/speckit-clarify` | Spec | Clarify underspecified areas |
| `/speckit-plan` | Plan | Generate technical implementation plan |
| `/speckit-tasks` | Tasks | Generate task breakdown (= task-level expectations) |
| `/speckit-implement` | Implement | Execute tasks via agentic loop |
| `/speckit-analyze` | Optional | Cross-artifact consistency check |
| `/speckit-checklist` | Optional | Generate quality checklists |
| `/speckit-taskstoissues` | Optional | Convert tasks to GitHub issues |
| `/speckit-intent` | **Extension** | Goal, constraints, failure conditions (this extension) |
| `/speckit-expectations` | **Extension** | Success scenarios, definition of done — compartmented (this extension) |
| `/speckit-compound-load` | **Extension** | Load ADRs, corrections, patterns into context (this extension) |
| `/speckit-compound-writeback` | **Extension** | Persist learnings back to compound store (this extension) |
| `/speckit-gapfill` | **Extension** | Fill SpecKit task gaps with constraint/negative tests (this extension) |
| `/speckit-intentguard` | **Extension** | L3 scope and constraint validation (this extension) |

---

## Sources and references

- SpecKit repo: https://github.com/github/spec-kit
- SpecKit community friends: https://github.github.io/spec-kit/community/friends.html
- SpecKit extension publishing guide: https://github.com/github/spec-kit/blob/main/extensions/EXTENSION-PUBLISHING-GUIDE.md
- Activated Thinker framework: Kapil Viren Ahuja's IDSD / ICE pieces on Activated Thinker (Medium)
- Compound engineering concept: #gen-ai-wtf Slack thread — @kenkyee and @Ricardo Costeira discussion on self-documenting code + ADRs + AI correction notes
- Every's compound engineering plugin: https://every.to/guides/compound-engineering
