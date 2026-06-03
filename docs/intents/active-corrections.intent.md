---
slug: active-corrections
status: active
created: 2026-06-03
---

# Intent: An agent cannot make a mistake the team already documented.

## Why now

Important now, no point building post 100 days. The compound store is passive today — corrections get written by `/speckit-compound-writeback` but only loaded as context, where the agent can ignore them. Hooks research (committed to `docs/hooks-research.md`) just landed showing PreToolUse hooks dispatch reliably under Claude Code. The "compound" promise needs teeth before more features land, while session momentum and the hooks research are both fresh.

## In scope

- `.claude/hooks/compound-correction-match.sh` script
- `.claude/settings.template.json` (Claude Code hook registration template)
- `/speckit-compound-install-hooks` command (one-shot installer)
- Matching strategy — how a correction note's derived rule becomes a pattern the hook script checks
- Block message format — what the agent reads from stderr on a blocked Write
- Correction-note schema update — machine-readable frontmatter (`paths:`, `match:`) added to the existing markdown body
- Documentation for how a user writes a matchable correction

## Out of scope

- Multi-CLI support (Codex CLI, Cursor, Gemini CLI equivalents of this same hook). Defer to v0.4+ once Claude Code path is proven.
- Other 3 hook designs from `docs/hooks-research.md` (OOS write-gate, intent-existence check at tool level, complexity gate). Sibling intents, ship separately.
- Modifying any existing `/speckit-compound-*` command. This is a new capability layered on top, not a rewrite of intent / expectations / gapfill / intentguard.
- Changing how corrections are *captured* in `/speckit-compound-writeback`. Only how they are *matched* at write time changes.
- Server-side enforcement (`.git/hooks/pre-commit`, CI checks). Belt-and-braces work, separate scope.
- Migration of pre-v0.3 corrections to the new schema. The new schema applies to corrections written after v0.3; pre-v0.3 corrections continue to be loaded as context but are not matched at write time until upgraded by hand.
- Friends listing / catalog submission. Release-level concern, not feature scope.

## Constraints

- **C1**: p95 hook execution time < 250ms, measured on a benchmark write against a fully-populated `docs/compound/corrections/` directory.
- **C2**: False-positive rate < 5% across a curated test corpus of writes designed to exercise the matcher against known-good and known-bad cases.
- **C3**: Stderr block message must include three fields: the correction file path, the specific matched rule text, and a one-line context describing why this Write triggered the match.
- **C4**: Two bypass mechanisms — per-file `// compound-allow: <correction-slug>` comment for surgical override (audit trail in code); `COMPOUND_BYPASS=1` env var for session-wide bypass (no audit trail; intentional sledgehammer).
- **C5**: Correction-note schema uses `paths:` glob and `match:` regex frontmatter fields. The hook only runs the regex on writes whose target path matches the glob — bounded scope.
- **C6**: Installer (`/speckit-compound-install-hooks`) is a pragmatic merge — re-runs upgrade compound hook entries in `.claude/settings.json`, but preserve all non-compound entries (the user's own hooks, other extensions' entries) byte-for-byte.

## Failure conditions

- **F1**: Build fails
- **F2**: `shellcheck` reports any warning on `scripts/bash/*.sh` or `.claude/hooks/*.sh`
- **F3**: `scripts/validate.sh` fails (after updates to cover the new files)
- **F4**: Hook execution time exceeds 250ms on a benchmark write *(validates C1)*
- **F5**: False-positive count exceeds 5% on the curated corpus *(validates C2)*
- **F6**: stderr block message in any test missing one of {correction file path, matched rule text, one-line context} *(validates C3)*
- **F7**: `// compound-allow: <slug>` in a test file fails to bypass the matched correction *(validates C4)*
- **F8**: Re-running the installer modifies a non-compound entry in `.claude/settings.json` *(validates C6)*
- **F9**: `.claude/settings.template.json` does not parse as valid JSON
- **F10**: A correction file with valid `paths:` + `match:` frontmatter fails to load at hook runtime
- **F11**: Hook crashes on empty `docs/compound/corrections/` directory (must be graceful no-op)
- **F12**: Hook silently skips a correction with malformed frontmatter (must warn to stderr instead)

## Test record

- Goal: G1 ✓ G2 ✓ G3 ✓ G4 ✓ G5 ✓
- Constraints: 6 total, all pass C1–C5
- Failure conditions: 12 total, all pass F1–F4 (5 over the 3-7 soft cap; sanity-check confirmed all are independent post-output checks with no constraints in disguise)

## Compound store refs

- ADRs respected: none (compound store empty at intent capture time)
- Corrections applied: none
- Patterns reached for: none

## Follow-ups for `/speckit-compound-writeback`

- **Pattern candidate**: *"Out-of-scope items in intent docs that represent declared future work should be cross-referenced in a `## Roadmap` section in README.md."* — surfaced during Phase 4; the user's directive was that the seven out-of-scope items above (especially multi-CLI support) belong in the README roadmap as forward direction.
- **Self-host candidate**: this is the first intent doc written for spec-kit-compound itself (the extension dogfooding on itself). If the v0.3 chain ships cleanly, that's a strong demo signal worth capturing as a pattern.

## Source notes

This intent was captured via roleplayed `/speckit-compound-intent` interview during a Claude Code session where the agent (Claude) acted as the spec-kit-compound extension's interview prompt. The user (the extension's author) answered the rubric questions directly in chat. Slug `active-corrections` was chosen over `correction-enforcement` to capture the conceptual shift from passive to active compound-store behavior.
