# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.1] — 2026-06-03

**Two discoveries from the first live run in `~/TravvIdea/backend-springboot/`:**

1. **Spec-kit hooks don't dispatch agent-prompt commands.** Our four `before_*`/`after_*` hooks installed correctly into `.specify/extensions.yml` but silently no-op'd. Spec-kit's hook executor dispatches **shell-script** hooks cleanly (like the bundled `git` extension's branch-creation script) but does **not** dispatch **agent-prompt** hooks like ours under Claude Code. The user ran `/speckit-specify`, the spec generated in vanilla shape, and no intent/expectations docs were created.

2. **In-prompt Phase 8 handoffs DO dispatch.** When the user typed `/speckit-compound-intent` directly, Claude completed the interview (in retrofit mode against the existing spec), wrote the intent file, then on Phase 8 confirmation invoked `Skill(speckit-compound-expectations) Successfully loaded skill` — dispatching the next slash command directly from inside the first command's prompt. The chain works, just via a different mechanism than hooks.

**So the chain has three real shapes:** auto-dispatched (in-prompt handoffs for the first 3 hops), user-typed (the 2 manual injection points after spec-kit's own commands), and prompt-suggested (writeback after intentguard PASS).

### Removed

- **`hooks:` block in `extension.yml`** — the four hook registrations (`before_constitution`, `before_specify`, `after_tasks`, `after_implement`) installed correctly but never executed under Claude Code. Removing them stops silently misleading users into expecting them to do work they cannot do.

### Added

- **`scripts/check-chain-fired.sh`** — post-flight eval. After running `/speckit-specify` through `/speckit-implement` (or any partial chain), run `./scripts/check-chain-fired.sh <slug>` to see a ✓/✗ per chain step. Each ✗ tells you which command was skipped and needs to be typed manually. Exit code 1 if any artifact is missing.

### Changed

- **README** — replaced the "Standard mode (chained) / Power-user mode" framing with **"The chain has two automatic segments and two manual injection points."** Documents the actual mechanism: in-prompt Phase 8 handoffs dispatch the next slash command directly (verified live), so the entry point `/speckit-compound-intent` chains to `/speckit-compound-expectations` and then to `/speckit-specify` automatically. After `/speckit-tasks`, the user manually types `/speckit-compound-gapfill`. After `/speckit-implement`, the user manually types `/speckit-compound-intentguard`. The intentguard prompt suggests `/speckit-compound-writeback` on PASS.
- **`extension.yml`** — version bumped to `0.2.1`. Comment block added in place of the removed `hooks:` section explaining what was tried and why it was removed.
- **Command descriptions in `extension.yml`** — `speckit.compound.intent` and `speckit.compound.intentguard` descriptions reference their in-prompt chain handoff targets honestly.

### Notes

- v0.2.2 may introduce a single **shell-script gate hook** on `before_specify` that fails with a clear message if `docs/intents/{slug}.intent.md` does not exist. This would use the same pattern git's hooks use (which DO fire) but for gating rather than chaining — enforcing the discipline by refusing to let `/speckit-specify` proceed without an intent doc. Deferred until v0.2.1 is verified in real use.
- Upstream issue to file: spec-kit's hook executor should dispatch agent-prompt hooks under Claude Code (and other agent harnesses) the same way it dispatches shell-script hooks. Without this, extensions like ours that ship prompt-based commands cannot use the hook system at all.

### Verification

Re-installing v0.2.1 in `~/TravvIdea/backend-springboot/`:
```bash
specify extension remove compound
specify extension add /Users/aditlal/Documents/Projects/spec-kit-compound --dev
```

After the next `/speckit-specify`, run:
```bash
./scripts/check-chain-fired.sh <slug>
```

Expect all four ✗ because the chain is now explicitly manual. Type each missing command in order to flip them to ✓.

[0.2.1]: https://github.com/aldefy/spec-kit-compound/releases/tag/v0.2.1

---

## [0.2.0] — 2026-06-02

Rework of v0.1.0 to match real spec-kit conventions, discovered during the first live install test against a fresh `specify init` project.

### Changed

- **Slash command form** — hyphenated, not dotted. `/speckit.intent` → `/speckit-compound-intent`, `/speckit.compound load` → `/speckit-compound-load`, etc. Real spec-kit converts dots to hyphens at install time; we now match the convention end-to-end.
- **Source command filenames use dots**: `commands/speckit.intent.md`, `commands/speckit.compound.load.md`, etc. Matches the bundled git extension's format (`speckit.git.commit.md`).
- **Source command frontmatter** simplified to a single field: `--- description: "..." ---`. The install process derives `name`, `compatibility`, and `metadata` automatically.
- **`/speckit.compound` split into two commands.** Spec-kit's extension system does not support subactions; each slash command is its own file. `/speckit-compound-load` and `/speckit-compound-writeback` are now two registered commands. Semantics unchanged.
- **Extension `id` changed to `compound`.** Spec-kit enforces that all extension commands live under the extension's `id` namespace (the bundled git extension uses `id: git` with commands `speckit.git.X`). We landed on `id: compound`, which means all our slash commands carry a `/speckit-compound-` prefix (longer than v0.1's `/speckit-X` form, but spec-kit-idiomatic).
- **`extension.yml` schema** aligned with the bundled git extension: dotted command names in `provides.commands[].name`, `requires.speckit_version: ">=0.2.0"`, and a `hooks:` section using dict format (single command per phase, not list).

### Added

- **Hooks section in `extension.yml`** — four hook registrations wire the commands into spec-kit's lifecycle so the user can run `/speckit-specify` once and most of the rest fires automatically:
  - `before_constitution`: `speckit.compound.load` (optional, prompted)
  - `before_specify`: `speckit.compound.intent` (mandatory; intent's own prompt chains to `/speckit-compound-expectations` on completion)
  - `after_tasks`: `speckit.compound.gapfill` (mandatory)
  - `after_implement`: `speckit.compound.intentguard` (mandatory L3 gate; intentguard's prompt suggests `/speckit-compound-writeback` on PASS)
- **In-prompt chaining** for the second-hook-per-phase cases (expectations after intent; writeback after intentguard). Spec-kit's hook system accepts only one command per phase per extension, so the chain logic lives in the prompts themselves rather than the manifest.
- **Hook-behavior section** in each command prompt explaining how it adapts when invoked as a hook vs interactively (e.g., shorter confirmation when chained, refusal to proceed if upstream verdict was BLOCKED).
- **Updated `docs/plan.md` extension tree** to show the 6 dotted command filenames and explain the dot→hyphen install conversion.
- **Updated `docs/ref.md` design-decision section** explaining why subactions were dropped in favor of two separate commands (spec-kit convention discovered at live-install time).

### Fixed

- All in-document slash command references across `README.md`, `CHANGELOG.md`, `docs/plan.md`, `docs/ref.md`, `docs/compound/README.md`, and the 6 command prompts now use hyphenated form (zero `/speckit.X` references remain).

### Notes

- v0.1.0 (the initial scaffold) is preserved in git history at commit `f797fb2` on `main` as a record of what we tried first. The conventions mismatch was caught only at live-install diagnostic; this is the value of running the test before catalog submission.
- Soft compartmentation still — same agent reads intent + expectations files in v0.2.0. Hard compartmentation deferred to v0.3+ if reward-hacking evidence emerges.
- v0.2.0 went through three pivots before installing cleanly: (1) hyphenated slash commands + dotted filenames + frontmatter; (2) split compound into two commands (no subactions); (3) namespace commands under `id: compound` (spec-kit enforces this). Each pivot was caught by `specify extension add --dev` returning a validation error. The live-install loop turned out to be the right development inner-loop for extension authoring.

### Verified install

Live `specify extension add /path --dev` against a fresh `specify init . --integration claude` scratch project produced:
- 6 skills installed at `.claude/skills/speckit-compound-{intent,expectations,load,writeback,gapfill,intentguard}/SKILL.md`
- Extension files mirrored to `.specify/extensions/compound/`
- Hooks merged into `.specify/extensions.yml` (4 entries across `before_constitution`, `before_specify`, `after_tasks`, `after_implement`) coexisting cleanly with the bundled `git` extension's hooks

[0.2.0]: https://github.com/aldefy/spec-kit-compound/releases/tag/v0.2.0

---

## [0.1.0] — 2026-06-02

Initial release. Five new slash commands wrapping the vanilla SpecKit workflow.

### Added

**Commands:**
- `/speckit-compound-intent` — interview-driven intent capture (goal, constraints, failure conditions) with G1–G5, C1–C5, F1–F4 quality rubrics. Refuses to terminate until intent passes all tests. Includes batch quick-pick pattern for power users.
- `/speckit-compound-expectations` — compartmented success and edge scenarios with E1–E4 rubric. Written to a separate folder (`docs/expectations/`) from intent docs to enforce soft compartmentation against reward-hacking. Includes worked examples for E3 calibration and a soft cap at 12 scenarios.
- `/speckit-compound` with `load` and `writeback` subactions — committed ADR / corrections / patterns store under `docs/compound/`. Auto-scaffolds the directory on first load.
- `/speckit-compound-gapfill` — cross-references intent + expectations against SpecKit's `tasks.md`; appends missing constraint-violation, failure-condition, out-of-scope-regression, and edge tests with source comments. High-risk gap pushback.
- `/speckit-compound-intentguard` — L3 validation: git diff vs intent out-of-scope, constraints, failure conditions, and expectations scenarios. Returns PASS / REVIEW NEEDED / BLOCKED with detailed report at `docs/intents/{slug}.intentguard.md`.

**Extension scaffolding:**
- `extension.yml` manifest for the SpecKit extension catalog
- `README.md` with cheat sheet, positioning (extension, not harness), and credits
- `LICENSE` (MIT)
- `docs/plan.md` — implementation and launch plan
- `docs/ref.md` — conceptual reference (the three concepts, design decisions, references, known SpecKit template limitations P1 / P2)

### Known limitations

- **Soft compartmentation only.** Same agent reads both intent and expectations docs (separate files in separate folders, with `/speckit-implement` instructed not to load expectations). Hard compartmentation (separate agents, encrypted evals, builder structurally unable to read the expectations file) is deferred to v0.2+ if evidence of gaming emerges.
- **Untested as an installed extension.** Battle-testing planned over the next 2–3 real features before submitting to SpecKit Friends / catalog.
- **No automated test suite.** Command prompts are markdown; correctness is verified via paper tests and live runs only.

### Notes

- Repo name is `spec-kit-compound` (working directory). The earlier draft name `spec-kit-intent-compound` was retired during design.
- Five-command surface (not six). Earlier draft separated `/speckit-writeback` from `/speckit-compound`; these were merged into one command with two subactions per the actual semantics.

[0.1.0]: https://github.com/aldefy/spec-kit-compound/releases/tag/v0.1.0
