---
slug: active-corrections
status: active
created: 2026-06-03
intent: ../intents/active-corrections.intent.md
---

# Expectations: An agent cannot make a mistake the team already documented.

> **Compartmentation note.** This file is consumed by `/speckit-compound-intentguard`. It is NOT consumed by `/speckit-implement`. Do not paste scenarios from this file into builder prompts.

## Positive scenarios

- **E1**: A developer with at least one matchable correction in `docs/compound/corrections/` runs an agent that attempts to Write a file whose path matches the correction's `paths:` glob and whose content matches the `match:` regex; the Write is blocked, and the agent reads the correction file path + matched rule + one-line context from stderr.

- **E2**: A developer runs `/speckit-compound-install-hooks` in a project that has no existing `.claude/settings.json`; the file is created with valid JSON containing only the compound hook entries; the script is marked executable.

- **E3**: A developer runs `/speckit-compound-install-hooks` in a project that already has `.claude/settings.json` with hook entries from other extensions or the user's own hand-edits; the existing entries are preserved byte-for-byte, compound entries are added alongside; re-running the installer a second time produces the same result.

- **E4**: A developer commits a new correction note with valid `paths:` and `match:` frontmatter; the next agent Write to a matching path picks it up without restarting Claude or re-installing the extension.

- **E5**: An agent attempts a Write whose content matches a correction, but the file content also contains `// compound-allow: <correction-slug>` referencing the matched correction; the Write is allowed through and the diff shows the override comment as audit trail.

- **E6**: A developer with `COMPOUND_BYPASS=1` set in their shell starts an agent session; compound hooks do not fire for any Write or Edit during that session; agent writes proceed without any compound-store check.

## Edge / negative scenarios

- **E7**: An agent attempts a Write in a project where `docs/compound/corrections/` does not exist or is empty; the hook runs to completion with no error and no block; the Write proceeds normally.

- **E8**: A developer commits a correction note with malformed frontmatter (missing `paths:` field, or invalid YAML); the next agent Write triggers a warning to stderr naming the broken file, but the agent continues; other valid corrections still match.

- **E9**: An agent attempts a Write whose content matches `match:` regexes from two or more different corrections at once; both correction file paths and both matched rules appear in stderr; the Write is blocked once with combined context.

- **E10**: An agent attempts a Write of a ~50KB file against a `docs/compound/corrections/` directory containing 50 correction notes; the hook completes within the 250ms p95 budget; the Write either proceeds (no match) or is blocked (match) within budget.

## Test record

- Total scenarios: 6 positive + 4 edge = 10 total
- All pass E1–E4 (specific, observable, user-recognizable, doesn't reveal implementation)

## Compound store refs

- Patterns reached for: none (compound store empty at expectations-capture time)
- Corrections applied: none

## Source notes

Drafted by `/speckit-compound-expectations` invoked as Phase 8 chain handoff from `/speckit-compound-intent` for the `active-corrections` intent. The roleplayed interview happened in a Claude Code session where the agent acted as the spec-kit-compound extension's prompts and the user (the extension's author) answered inline. The scenarios were auto-derived from the intent doc's in-scope items (positives 1–6) and failure conditions + out-of-scope items (edges 7–10), then locked via `accept all`.
