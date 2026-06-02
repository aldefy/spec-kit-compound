# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] — 2026-06-02

Initial release. Five new slash commands wrapping the vanilla SpecKit workflow.

### Added

**Commands:**
- `/speckit.intent` — interview-driven intent capture (goal, constraints, failure conditions) with G1–G5, C1–C5, F1–F4 quality rubrics. Refuses to terminate until intent passes all tests. Includes batch quick-pick pattern for power users.
- `/speckit.expectations` — compartmented success and edge scenarios with E1–E4 rubric. Written to a separate folder (`docs/expectations/`) from intent docs to enforce soft compartmentation against reward-hacking. Includes worked examples for E3 calibration and a soft cap at 12 scenarios.
- `/speckit.compound` with `load` and `writeback` subactions — committed ADR / corrections / patterns store under `docs/compound/`. Auto-scaffolds the directory on first load.
- `/speckit.gapfill` — cross-references intent + expectations against SpecKit's `tasks.md`; appends missing constraint-violation, failure-condition, out-of-scope-regression, and edge tests with source comments. High-risk gap pushback.
- `/speckit.intentguard` — L3 validation: git diff vs intent out-of-scope, constraints, failure conditions, and expectations scenarios. Returns PASS / REVIEW NEEDED / BLOCKED with detailed report at `docs/intents/{slug}.intentguard.md`.

**Extension scaffolding:**
- `extension.yml` manifest for the SpecKit extension catalog
- `README.md` with cheat sheet, positioning (extension, not harness), and credits
- `LICENSE` (MIT)
- `docs/plan.md` — implementation and launch plan
- `docs/ref.md` — conceptual reference (the three concepts, design decisions, references, known SpecKit template limitations P1 / P2)

### Known limitations

- **Soft compartmentation only.** Same agent reads both intent and expectations docs (separate files in separate folders, with `/speckit.implement` instructed not to load expectations). Hard compartmentation (separate agents, encrypted evals, builder structurally unable to read the expectations file) is deferred to v0.2+ if evidence of gaming emerges.
- **Untested as an installed extension.** Battle-testing planned over the next 2–3 real features before submitting to SpecKit Friends / catalog.
- **No automated test suite.** Command prompts are markdown; correctness is verified via paper tests and live runs only.

### Notes

- Repo name is `spec-kit-compound` (working directory). The earlier draft name `spec-kit-intent-compound` was retired during design.
- Five-command surface (not six). Earlier draft separated `/speckit.writeback` from `/speckit.compound`; these were merged into one command with two subactions per the actual semantics.

[0.1.0]: https://github.com/aldefy/spec-kit-compound/releases/tag/v0.1.0
