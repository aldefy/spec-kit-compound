# Implementation Plan: Swimlane Triage for the Dashboard Master Pane

**Branch**: `main` (dogfooded) | **Date**: 2026-07-23 | **Spec**: [spec.md](./spec.md)
**Intent**: `../../docs/intents/feature-swimlane-triage.intent.md`

## Summary

Reorganize `dashboard.py`'s master pane from a flat feature list into
progress-derived, collapsible lanes with live search, within-lane sort, and lane
filter chips. Add two per-card signals — an always-visible blocked/drift badge and a
git "WIP dot" for uncommitted intent/expectation docs. All grouping/search/sort runs
client-side over the existing `/api/state` poll; the only backend additions are three
derived fields per feature plus a searchable compound-store text blob, all carried
inside the existing state payload. No new server routes.

## Technical Context

- **Language / runtime**: Python 3 (stdlib only — `http.server`, `subprocess`, `glob`);
  vanilla JS + CSS embedded as a string in `dashboard.py`. No build step, no deps.
- **Single file**: `dashboard.py` (1352 lines) holds backend scan + the entire
  embedded HTML/CSS/JS. This feature edits that one file, plus tests under `tests/`.
- **State transport**: browser polls `GET /api/state` every 3s → replaces global
  `STATE` → calls `renderMaster()` + `renderDetail()`. This is the only channel the
  feature uses (C5 / FR-012).
- **Existing primitives reused**:
  - `_git(repo_root, *args)` — read-only, never-raises git wrapper (for dirty-doc flag).
  - localStorage pattern already used for `skc-docfs` (doc font size) — reused for view state.
  - `guardChip(feat)`, `stageCls(st)`, `doneCount(feat)` — existing JS card helpers.
  - `_compute_states`, per-feature `stages` dict with `state` + `verdict` — the lane source.
- **Unknowns**: none. No NEEDS CLARIFICATION.

## Constitution Check

No `.specify/memory/constitution.md` in this repo. Repo conventions observed instead:
- stdlib-only, single-file dashboard — **honored** (no new imports, no deps).
- Validator rule (from memory): slash-command references in prose must be hyphenated,
  not dotted — **honored** in all docs (F4).
- Graceful git degradation (`_git` returns "" on any failure) — **honored**: dirty-doc
  detection must never raise or block render on a non-git repo.

## Phase 0 — Research

No external unknowns. One internal decision resolved, see `research.md`:
lane-derivation rules, store-text search shape, and dirty-doc detection approach.

## Phase 1 — Design & Contracts

### Backend changes (`scan_state` and helpers)

1. **`_derive_lane(stages)`** — new pure function. Input: a feature's `stages` dict
   (already computed). Output: one of `"attention" | "wip" | "review" | "backlog" | "done"`.
   Rules, first match wins (see data-model.md). Pure, deterministic (C1 / FR-001).

2. **`_feature_progress(stages)`** — new pure helper. Returns a float 0.0–1.0 from
   `stages.tasks.done / stages.tasks.total` (0 when no tasks). Sort key (FR-005).

3. **`doc_dirty` per feature** — in `scan_state`, one `git status --porcelain -- <intent> <exp>`
   call via `_git`; true when either doc path appears dirty/untracked. Never raises;
   false when not a git repo (FR-007, graceful degradation).

4. **Compound search text** — extend the existing `compound` payload with a
   `search_text` string: lowercased concatenation of compound-store note bodies
   (adr/corrections/patterns), truncated per file to a sane cap. Enables FR-004 / E3
   store-text search client-side without a new route. Feature cards match against it
   globally (store is branch-wide, not per-feature).

5. Each feature dict gains `lane` and `progress`; keep all existing fields.

### Frontend changes (embedded JS + CSS)

6. **`groupFeatures(features, {q, sort, chips})`** — new pure JS function. Returns an
   ordered array of `{lane, label, items}`. Filters by search (`q` over slug + goal +
   the shared store `search_text`), applies chip visibility (attention lane always
   shown), sorts items within each lane. Testable in isolation from render.

7. **Rewrite `renderMaster()`** to: render a controls bar (search input, sort `<select>`,
   lane chip toggle-buttons) + grouped collapsible lane sections with counts, iterating
   `groupFeatures(...)` output. Cards keep the existing minibar + guard chip, and gain:
   - blocked/drift **badge** when `stages.intentguard.verdict==="BLOCKED"` or
     `stages.planverify.verdict==="BLOCKED_DRIFT"` — rendered on the card in *any* lane (FR-002, E7).
   - **WIP dot** when `feat.doc_dirty` (FR-007, E7).

8. **View-state module vars** (`MQ, MSORT, MCHIPS, MCOLLAPSE`) hydrated from
   localStorage on load, persisted on change (FR-008 poll-survival + FR-009 restart;
   incognito → try/catch no-op, E10). Mirrors the `skc-docfs` pattern exactly.

9. **Empty / no-match states** (FR-010, E8/E9): zero features → existing "RUN /SPECKIT-…"
   card kept; search-with-zero-visible → a "NO MATCHES" row + clear affordance.

10. **Accessibility** (FR-011, C6, E12): search input `<label>`; sort a labeled
    `<select>`; chips are `<button aria-pressed>`; lane headers are `<button aria-expanded>`
    controlling their section; badge/dot carry `aria-label` / visually-hidden text.

### Interface contract

The only contract is the shape of each feature object in `/api/state` — documented in
`contracts/state-feature.md`. No route added/changed (C5).

### Agent context update

No `<!-- SPECKIT START -->` markers exist in this repo's CLAUDE.md; skip that step.

## Constitution Check (post-design)

Still clean: no new imports, no new routes, git degradation preserved, hyphenation rule
respected. Client render stays O(features) with a text-length-bounded search string (C2).

## Complexity Tracking

No deviations. One new git call per scan (batched, single invocation), bounded store
text, all-else client-side over existing poll.

## Artifacts generated

- `research.md` — lane rules, store-text search, dirty-doc detection decisions
- `data-model.md` — Feature / Lane / ViewState entities + lane derivation table
- `contracts/state-feature.md` — the `/api/state` feature-object contract
- `quickstart.md` — how to run the dashboard and exercise the feature
