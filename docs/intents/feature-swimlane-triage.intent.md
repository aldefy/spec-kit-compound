---
slug: feature-swimlane-triage
status: completed
created: 2026-07-23
completed: 2026-07-23
---

# Intent: Developers can triage every feature on a branch by its pipeline progress — grouped, searchable, and sortable — so a teammate can pick up work someone else started.

## Why now
The compound workflow is explicitly multi-developer: intent/expectation docs, the compound store, and the constitution are all git-shared so teammates and their agents read the same context. But the dashboard's master pane is still a flat, filesystem-sorted list. When one developer's intent/expectation docs land on the shared branch, another developer can't scan, group, or search them to pick the work up. The design notes reframe the master pane as a team review surface — "everyone participates via the spec and diagram diff at PR stage" — yet today it does not behave like one. This closes that gap.

## In scope
- A **lane** derived per feature purely from its pipeline stage state (⚠ Needs attention → WIP → Review → Backlog → Done).
- A **grouped, collapsible master list** that replaces the current flat feature list, with per-lane counts.
- **Controls** above the list: live search (matching slug, goal, and compound-store body text), sort-within-lane, and lane filter chips.
- **Per-card signals**: a blocked/drift badge (always visible, even when filtered into another lane) and a git "WIP dot" when the feature's intent or expectation doc has uncommitted git changes.
- **View state** (search text, sort mode, active chips, collapse) that survives both the 3s poll re-render and a dashboard restart (localStorage).

## Out of scope
- ComposeProof and its HTML verification dashboard — a separate MCP/project, not this repo.
- Drag-to-reorder or any manual lane assignment; lanes are derived only.
- Any new server route or endpoint; grouping/search/sort run client-side over the existing state poll.
- Editing intent `status:` frontmatter (or any doc) from the UI.
- Changes to the detail pane, stage rendering, or the document viewer.

## Constraints
- **C1**: Lane derivation is a pure function of a feature's stage state — identical stage state always yields the same lane, with zero manual input.
- **C2**: A full master-pane render (group + filter + sort of the entire feature set) completes in **< 50ms for up to 50 features**, so the 3s poll never janks.
- **C3**: Search is **live** — visible results update within **150ms of a keystroke**, with no submit action.
- **C4**: View state (search text, sort mode, active chips, collapse) **survives both the 3s poll and a dashboard restart** via localStorage.
- **C5**: **Zero new server routes** — grouping, search, and sort run entirely client-side over the existing state poll; git-dirty status and compound-store search text ship inside the existing state payload.
- **C6**: The controls and list are **keyboard- and screen-reader operable to WCAG 2.1 AA** — every control reachable by Tab, lane headers semantic, chips as toggle buttons exposing pressed state.

## Failure conditions
- **F1**: The `_derive_lane` unit tests fail (fixture per lane plus the blocked-override case).
- **F2**: `python -c "import dashboard"` fails, or the dashboard process errors on startup.
- **F3**: A new server route or endpoint is added to `dashboard.py` (violates C5), as detected by grep for added request-handler routes.
- **F4**: The planverify/intentguard hyphenation validator flags any slash-command reference in changed prose (repo's known validator rule).
- **F5**: The existing `tests/` suite regresses — any previously passing test fails.

## Test record
- Goal: G1 ✓  G2 ✓  G3 ✓  G4 ✓  G5 ✓
- Constraints: 6 total, all pass C1–C5
- Failure conditions: 5 total, all pass F1–F4

## Compound store refs
- ADRs respected: none (no ADR store present)
- Corrections applied: none (only sample CSS-filter correction present, not applicable to a Python/JS dashboard feature)
- Patterns reached for: none
