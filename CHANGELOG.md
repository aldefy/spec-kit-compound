# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
