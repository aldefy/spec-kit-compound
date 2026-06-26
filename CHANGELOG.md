# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.4.2] — 2026-06-26

Light-mode comfort, a shareable theme override, and README screenshots + cross-repo usage docs.

### Added

- **`?theme=light` / `?theme=dark` URL override** — forces a theme regardless of stored preference or OS setting. Useful for shareable links and for capturing screenshots.
- **Dashboard screenshots** (`docs/img/dashboard-dark.png`, `dashboard-light.png`) embedded in the README, plus explicit instructions for starting the dashboard and pointing `--repo` at another spec-kit project.

### Changed

- **Warmer, lower-glare light theme.** Replaced the bright `#F5F5F5`/white paper with a warm sand palette (`#E7E2D8` page, text off pure black) to reduce eye strain. Dark mode is unchanged.
- **`extension.yml`** version bumped to `0.4.2`.

## [0.4.1] — 2026-06-26

Dashboard redesign and a correctness fix. The pipeline view now reads documents on click, advances correctly when a spec dir's name differs from the intent slug, and is rebuilt in a monochrome instrument-panel aesthetic with dark/light modes.

### Added

- **Document viewer.** Each stage in the pipeline is clickable and opens that stage's document. Stages with parsed structure (intent, expectations, intentguard) show a summary with a toggle to the raw file; all other stages (spec, plan, tasks, gapfill) open the raw document directly. tasks.md renders as a checkbox list. Backed by a new sandboxed `/api/doc?path=` endpoint that refuses any path resolving outside the scanned repo (path-traversal and symlink-escape guarded).
- **Per-stage file map (`stage_files`)** in `scan_state` output so the UI knows which document each stage node opens.
- **Dark / light themes.** A segmented toggle (persisted to `localStorage`, defaulting to the OS preference) following the Nothing design system — OLED-black instrument panel in dark, off-white technical-manual in light.

### Fixed

- **Spec dirs no longer orphan when their name is a prefix of the intent slug.** A slug like `selective-forwarding-backend` now binds to the spec dir `255-selective-forwarding` via a hyphen-token-prefix match (exact normalized match still wins; token-level matching means `auth` does not match `oauth`). Previously the chain stalled at SPEC and the dir showed under "orphan specs" even though plan/tasks existed.

### Changed

- **Full UI redesign** to a monochrome, typographically driven layout: a master list of features beside a detail pane whose hero is the chain progress (`NN/09` in a dot-matrix display face plus the guard verdict), the 9-stage chain rendered as a segmented progress bar, and footer stat rows for the compound store and token spend. Color now encodes only state, applied to values rather than labels or backgrounds.
- **Removed the architecture diagram card** — it described the dashboard's own plumbing, not the user's pipeline.
- **`extension.yml`** version bumped to `0.4.1`.

## [0.4.0] — 2026-06-26

Ships the read-only **pipeline dashboard** as a first-class extension command. Previously `dashboard.py` was a dev-only visualization tool that scanned only this repo; it now installs into host spec-kit projects (e.g. equal) and targets the host's own pipeline.

### Added

- **`/speckit.compound.dashboard` command.** A thin shell-script wrapper (`commands/speckit.compound.dashboard.md`) that launches `dashboard.py` as a background HTTP server, prints the localhost URL, and returns immediately instead of tying up the session. Renders the full SDD chain — intent, spec, plan, tasks, expectations, intentguard drift, token usage, architecture — for whichever spec-kit project it is run in. Registered in `extension.yml` `provides.commands`.
- **`--repo PATH` flag on `dashboard.py`.** Scan an explicit spec-kit project root instead of auto-detecting. Auto-detect now resolves from the invocation cwd first, then the script's own location.
- **`TestFindRepoRoot`** test class (4 cases) covering `.specify/` anchoring, dev-mode fallback, anchor precedence, and the no-anchor case.

### Fixed

- **`find_repo_root` scanned the wrong directory when installed.** It anchored on the nearest `extension.yml`, which in an installed host resolves to `.specify/extensions/compound/` — a directory with no `docs/` or `specs/`, so the dashboard rendered an empty chain. It now anchors on the `.specify/` project root (matching the other compound scripts), keeping `extension.yml` only as a dev-mode fallback for this repo, which has no `.specify/`.
- **Two dotted `/speckit.*` slash-command references in `README.md`** (roadmap section) hyphenated to `/speckit-*`, satisfying the validate.sh rule that bans dotted references in active markdown.

### Changed

- **`scripts/dashboard.sh`** internal `REPO_ROOT` variable renamed to `SCRIPT_HOME` — it only locates `dashboard.py`; the scan target is now decided by `dashboard.py`'s `--repo`/cwd auto-detect.
- **`extension.yml`** version bumped to `0.4.0`.

## [0.3.1] — 2026-06-03

Hotfix. v0.3.0 shipped with four real bugs found during the live smoke test against the sample correction. All four are now fixed and verified end-to-end: the hook correctly blocks (exit 2) on matches, correctly allows (exit 0) on non-matches, honors both bypass mechanisms, and the structured stderr message is exactly the C3-specified format.

### Fixed

- **Multi-line YAML array parsing.** The v0.3.0 hook only handled inline form (`paths: ["a", "b"]`); block form (`paths:\n  - "a"\n  - "b"`) silently failed because the `paths:` field extracted an empty string and the correction was marked malformed. Added explicit awk-based block-form parser that runs when the inline-form sed returns empty. Both YAML forms now work.
- **`set -u` + empty bash array crash.** The "emit warnings" loop dereferenced `${WARNINGS[@]}` while `set -u` was active and the array was empty. On bash 3.2 (macOS default) this errors with "unbound variable". Guarded the loop with `if [ "${#WARNINGS[@]}" -gt 0 ]` so it only runs when there's content.
- **`**/*.css` glob missed root-level files.** Bash case-glob `**/*.css` requires at least one `/` in the candidate path, so `styles.css` at the project root didn't match. Added a fallback: if a pattern starts with `**/`, also test the candidate against the pattern with the `**/` prefix stripped. Now matches both `themes/dark/main.css` (subdir) and `styles.css` (root) — mirroring git-style glob semantics.
- **Sample correction regex used PCRE shortcuts and produced unbalanced parens.** The sample's `match:` field used `\s*` (PCRE whitespace, doesn't exist in POSIX ERE — matches literal `s`) and `\\(` (which became `\\(` literal after the bash pipeline, producing grep "parentheses not balanced"). Simplified the regex to `filter:[[:space:]]*(brightness|invert|grayscale)` — POSIX ERE compliant, no escape gymnastics needed.

### Changed

- **`docs/compound/CORRECTIONS-SCHEMA.md`** updated with **three explicit gotchas** in the `match:` field reference: POSIX ERE only (no `\s`/`\d`/`\w`), avoid backslashes inside double-quoted YAML strings (the pipeline doesn't process YAML escapes), and test regex with `echo | grep -E` before committing.
- **`extension.yml`** version bumped to `0.3.1`.

### Verified

6 smoke tests run against `/tmp/sk-compound-test/`:
1. CSS file matching path + content → blocked (exit 2) with structured stderr ✓
2. JS file (wrong path) → allowed ✓
3. CSS file with no filter property → allowed ✓
4. CSS file with `/* compound-allow: <slug> */` override → allowed ✓
5. `COMPOUND_BYPASS=1` env var set → allowed ✓
6. Subdir CSS file matching path + content → blocked ✓

All 30 static `scripts/validate.sh` checks still pass after the changes.

[0.3.1]: https://github.com/aldefy/spec-kit-compound/releases/tag/v0.3.1

---

## [0.3.0] — 2026-06-03

**Active corrections.** The compound store stops being passive — corrections become **tool-level enforcement**, not just background context. When the agent attempts a Write or Edit that matches a documented past mistake, the operation is blocked at the moment of the tool call, before any code is written.

This is the **two-layer enforcement** completion called out in `docs/hooks-research.md`:
- **L1 (since v0.2.2)**: spec-kit phase boundary gates — `/speckit-specify` refuses if no intent doc exists
- **L2 (NEW in v0.3)**: Claude Code `PreToolUse` tool-call gates — `Write`/`Edit` refuses if proposed change matches a documented correction

L2 catches everything L1 catches, plus everything L1 misses (the user who skips spec-kit entirely and just starts coding with the agent).

Designed via dogfooding: the v0.3 intent + expectations were captured by roleplaying `/speckit-compound-intent` and chain-handoff to `/speckit-compound-expectations` against the v0.3 outcome itself. See `docs/intents/active-corrections.intent.md` and `docs/expectations/active-corrections.expectations.md`.

### Added

- **`.claude/hooks/compound-correction-match.sh`** — the gate script. Reads tool input from stdin, parses every correction in `docs/compound/corrections/` for `paths:` + `match:` + `rule:` + `context:` frontmatter, runs the regex against the proposed content for any matching path, blocks the tool call (exit 2) with a structured stderr message citing each match. Honors the `// compound-allow: <slug>` per-file escape hatch and the `COMPOUND_BYPASS=1` session bypass.
- **`.claude/settings.template.json`** — Claude Code hook registration template. Single `PreToolUse` entry matching `Write|Edit`, invoking the gate script.
- **`scripts/bash/install-claude-hooks.sh`** — installer script. Anchors to spec-kit project root, copies the gate script into the user's `.claude/hooks/`, performs an idempotent jq-based merge of the registration into the user's `.claude/settings.json` (preserves all non-compound entries per intent's C6).
- **`commands/speckit.compound.install-hooks.md`** — the slash command (`/speckit-compound-install-hooks`). Thin wrapper that invokes the installer script via Bash. Shell-script-wrapper pattern, dispatches cleanly under spec-kit's hook executor.
- **`docs/compound/CORRECTIONS-SCHEMA.md`** — full reference for the v0.3+ correction-note schema, with field reference, mental model of how matching works, rules for writing good `match:` regexes and `rule:` text, both bypass mechanisms, and a worked example.
- **`docs/compound/corrections/2026-06-03-sample-no-css-img-filters.md`** — sample correction that doubles as a smoke test. After install, asking the agent to Write a CSS file matching the regex should produce a hook block citing this correction.
- **`scripts/validate.sh` Section 7** — checks the new files exist, settings template parses as JSON, sample correction has all four required frontmatter fields, gate script is executable.
- **`extension.yml`** registers `speckit.compound.install-hooks` as a new command. Version bumped to `0.3.0`. New `claude-hooks` tag.

### Notes

- **Backward compatibility**: pre-v0.3 corrections (markdown body only, no frontmatter) continue to load as agent context via `/speckit-compound-load`. They aren't enforced until upgraded to the v0.3 schema. Migration is deliberately out-of-scope for v0.3 per the intent doc — upgrade incrementally as you revisit each correction.
- **Multi-CLI**: only Claude Code is supported in v0.3 (`.claude/settings.json`). Codex CLI, Cursor, and Gemini CLI use the same shell-script contract but different settings file paths; ports planned for v0.4+ per the roadmap in README. See `docs/hooks-research.md` for the design.
- **Performance budget**: hook is designed for p95 < 250ms on a corrections directory of ~50 entries and a file write of ~50KB. No LLM calls in the hook path — purely shell + grep + jq. If the budget is exceeded in real use, the script can be ported to a small Go/Rust binary without changing the contract.
- **The hook is opt-in**: installing the extension does NOT auto-register the hook. The user runs `/speckit-compound-install-hooks` explicitly. This prevents surprise behavior in projects that install the extension for the spec-kit-phase gates only.

### Verification

Static validation (`./scripts/validate.sh` from repo root) covers all new files. Live install + hook fire pending — will record in v0.3.1 notes after first real run in `~/TravvIdea/backend-springboot/` or the jetpack-compose demo repo.

[0.3.0]: https://github.com/aldefy/spec-kit-compound/releases/tag/v0.3.0

---

## [0.2.2] — 2026-06-03

Two real bugs from the v0.2.1 retrofit run, plus the re-introduction of a hook that actually fires.

### Fixed

- **Working-directory drift bug (CRITICAL).** v0.2.1's retrofit run wrote `intent.md` and `expectations.md` to `~/TravvIdea/docs/intents/` instead of `~/TravvIdea/backend-springboot/docs/intents/` — the agent's bash cwd drifted to the parent directory during an inspection command and subsequent Write operations landed under the wrong root. The eval script reported all artifacts missing even though they existed (just one directory up). Added an explicit **Project root anchor** section at the top of `speckit.compound.intent.md` and `speckit.compound.expectations.md` instructing the agent to walk up from cwd to find `.specify/`, `cd` to it, and re-anchor after any subsequent `cd` in a Bash command.

### Added

- **`commands/speckit.compound.require-intent.md`** — a shell-script wrapper command that runs `.specify/extensions/compound/scripts/bash/require-intent.sh`. Refuses to allow `/speckit-specify` to proceed if `docs/intents/` is empty or missing.
- **`scripts/bash/require-intent.sh`** — the actual gate script. Walks up to find the spec-kit project root, checks `docs/intents/` for any `*.intent.md` file, exits 0 if at least one exists or 1 with a clear message otherwise.
- **`hooks:` block back in `extension.yml`** — but only **one** hook this time: `before_specify: speckit.compound.require-intent` (mandatory). This is the **script-runner pattern** that bundled `git`'s hooks use (and which DO dispatch under Claude Code, verified). The agent-prompt hook pattern that v0.2.0 tried (and v0.2.1 removed) silently no-ops; the script-runner gate fires reliably.
- **`scripts/validate.sh`** — static validation of the extension repo. Checks: `extension.yml` parses, `id: compound`, all referenced command files exist with frontmatter, no orphan dotted slash references in markdown, scripts executable, and **every hook-registered command points to a shell-script-running command file (not an interactive prompt)**. The last check would have caught v0.2.0's silent-noop bug before install.

### Changed

- **`extension.yml`** version bumped to `0.2.2`. New gate command added to `provides.commands`. New single-entry `hooks:` block.

### Notes

- **Why one hook came back:** discipline enforcement through *gating* (refuse to proceed until intent doc exists) is achievable with a shell-script hook because the hook's job is a deterministic check, not an interactive interview. Discipline enforcement through *chaining* (auto-run the intent interview before specify) still requires agent-prompt hook dispatch, which spec-kit's executor doesn't do. v0.2.2 gives us gating; the chain remains manual (or auto-dispatched in-prompt via Phase 8 handoffs from v0.2.1).
- **The cwd anchor is defensive.** Most of the time the agent's cwd matches the project root, and the anchor block is a no-op. The bug surfaced because the agent's bash inspection commands changed directory mid-session. Anchoring is cheap and prevents the recurrence.
- **The validate.sh static check is your pre-flight before pushing.** Run `./scripts/validate.sh` from the repo root; if it fails, don't push. It would have caught all three of v0.2.0's pivots (naming, hooks-as-list, namespace) before install.

[0.2.2]: https://github.com/aldefy/spec-kit-compound/releases/tag/v0.2.2

---

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
