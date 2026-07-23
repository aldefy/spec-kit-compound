# Tasks: Swimlane Triage for the Dashboard Master Pane

**Feature dir**: `specs/001-feature-swimlane-triage/`
**Plan**: [plan.md](./plan.md) | **Spec**: [spec.md](./spec.md)
**Single edit target**: `dashboard.py` (backend scan + embedded HTML/CSS/JS) and `tests/test_dashboard.py`.

Tests ARE requested — the intent's F1 failure condition mandates `_derive_lane` unit
tests, so test tasks are included and written before the code they cover (TDD for the
pure backend helpers).

Story mapping to spec requirements:
- **US1 — Grouped lanes** (FR-001, FR-002, FR-003): stage-derived lanes, attention override, collapsible grouped render.
- **US2 — Search** (FR-004, FR-010): live search over slug + goal + store text; empty/no-match states.
- **US3 — Sort & filter** (FR-005, FR-006): within-lane sort; lane chips with attention exempt.
- **US4 — Card signals** (FR-002 badge, FR-007 WIP dot): blocked/drift badge + uncommitted-doc dot.
- **US5 — Persistence & a11y** (FR-008, FR-009, FR-011): view-state survives poll + restart; keyboard/SR.

Every story keeps FR-012 (no new route) intact.

---

## Phase 1 — Setup

- [x] T001 Confirm baseline is green: run `python3 -c "import dashboard"` and `python3 -m unittest tests.test_dashboard` and record they pass before any change (F2/F5 baseline).

## Phase 2 — Foundational (blocking prerequisites)

- [x] T002 Add module-level lane constants to `dashboard.py`: an ordered `LANES` list `["attention","wip","review","backlog","done"]` and a `LANE_LABELS` map, placed near the existing `STAGES`/`LABELS` definitions so both backend and the embedded JS label set stay consistent.

---

## Phase 3 — US1: Grouped lanes (P1, MVP)

**Goal**: features appear grouped under stage-derived, collapsible lane headers with counts; blocked/drift features float to the attention lane.
**Independent test**: on this repo, `active-corrections` and `feature-swimlane-triage` each resolve to a defined lane; a fixture with a BLOCKED guard lands in `attention`.

- [x] T003 [US1] Write failing unit tests in `tests/test_dashboard.py`: a `TestDeriveLane` class with one case per lane (backlog=intent-only, wip=spec/plan/tasks started, review=implement done or gate present, done=writeback done) plus the blocked-override case (intentguard BLOCKED and planverify BLOCKED_DRIFT both → attention). Build the `stages` dicts the way `scan_state` does (state + verdict keys).
- [x] T004 [US1] Implement `_derive_lane(stages)` in `dashboard.py` as a pure first-match-wins function per data-model.md; run `TestDeriveLane` to green (F1).
- [x] T005 [P] [US1] Write failing unit tests for `_feature_progress(stages)` in `tests/test_dashboard.py` (0 when no tasks, done÷total otherwise, clamped 0.0–1.0).
- [x] T006 [US1] Implement `_feature_progress(stages)` in `dashboard.py`; add `"lane": _derive_lane(stages)` and `"progress": _feature_progress(stages)` to each feature dict in `scan_state` (per contracts/state-feature.md).
- [x] T007 [US1] Add a pure JS `groupFeatures(features, opts)` in the embedded script of `dashboard.py` returning ordered `[{lane,label,items}]` in fixed lane order (opts stubbed for now: no filter/sort — those land in US2/US3). Unknown `lane` falls back to `backlog`.
- [x] T008 [US1] Rewrite `renderMaster()` in `dashboard.py` to render collapsible lane sections (`<button aria-expanded>` header + count) iterating `groupFeatures(...)`; keep the existing per-card minibar and guard chip; preserve the click-to-select behavior and the zero-features "RUN /SPECKIT-COMPOUND-INTENT" card (FR-003, FR-010 empty state).
- [x] T009 [P] [US1] Add lane-section + collapse CSS to the embedded `<style>` in `dashboard.py`, following the existing `.grouphd`/`.feat`/`.lbl` visual language.

**Checkpoint**: US1 alone is a usable, shippable improvement (grouped view). MVP ends here.

---

## Phase 4 — US2: Search (P2)

**Goal**: live search narrows visible features across lanes by slug, goal, and compound-store text; clear no-match state.
**Independent test**: typing a slug substring narrows the list live; a word only in a compound note keeps that feature; a nonsense term shows NO MATCHES and clearing restores all.

- [x] T010 [US2] Extend the `compound` payload in `scan_state` (`dashboard.py`) with `search_text`: lowercased, per-file-capped concatenation of adr/corrections/patterns note bodies (per research.md Decision 2); always a string (FR-004, E3).
- [x] T011 [US2] Add search filtering to `groupFeatures(...)` in `dashboard.py`: match the query (case-insensitive) against slug + `content.goal` + the shared `compound.search_text`; store-text match keeps the feature visible.
- [x] T012 [US2] Add the search `<input>` with a visible `<label>` to the controls bar in `renderMaster()` (`dashboard.py`); wire `oninput` to re-render live with no submit (FR-004); render a "NO MATCHES" row when a non-empty query yields zero visible features and a clear control that restores all (FR-010, E9).

**Checkpoint**: US1 + US2 = grouped + searchable.

---

## Phase 5 — US3: Sort & lane filter (P2)

**Goal**: sort within each lane; toggle lanes on/off with attention always visible.
**Independent test**: switching sort to A–Z reorders items inside lanes only; disabling all chips except WIP hides other lanes but attention still shows.

- [x] T013 [US3] Add within-lane sorting to `groupFeatures(...)` in `dashboard.py`: modes `newest` (by `created` desc, default), `az` (slug), `progress` (desc); lane order stays fixed (FR-005).
- [x] T014 [US3] Add the sort `<select>` (labeled) to the controls bar in `renderMaster()` (`dashboard.py`); wire change → re-render.
- [x] T015 [US3] Add lane filter chips as `<button aria-pressed>` to the controls bar in `renderMaster()` (`dashboard.py`); hidden lanes are excluded by `groupFeatures`, but the `attention` lane is always rendered regardless of chip state (FR-006, E5).

**Checkpoint**: US1–US3 = grouped + searchable + sortable + filterable.

---

## Phase 6 — US4: Card signals (P2)

**Goal**: blocked/drift badge visible on the card in any lane; WIP dot for uncommitted docs.
**Independent test**: a blocked feature shows a badge even when filtered into a non-attention view; editing an intent doc without committing makes its dot appear within one poll.

- [x] T016 [US4] Add `doc_dirty` to each feature in `scan_state` (`dashboard.py`): a `git status --porcelain -- <intent> <exp>` check via the existing `_git()` helper (per research.md Decision 3); always a bool, `false` when git is unavailable (FR-007, never raises).
- [x] T017 [P] [US4] Write a unit test in `tests/test_dashboard.py` asserting `scan_state` on this repo returns `doc_dirty` as a bool for every feature and never raises when `_git` yields "" (simulate by monkeypatching `_git` to return "").
- [x] T018 [US4] In `renderMaster()` (`dashboard.py`), render a blocked/drift **badge** on any card whose `intentguard.verdict==="BLOCKED"` or `planverify.verdict==="BLOCKED_DRIFT"`, shown regardless of which lane the card is displayed in (FR-002, E7); render a **WIP dot** when `feat.doc_dirty` (FR-007, E7). Both carry `aria-label`/visually-hidden text.
- [x] T019 [P] [US4] Add badge + dot CSS to the embedded `<style>` in `dashboard.py`.

**Checkpoint**: US1–US4 = full triage surface with at-a-glance signals.

---

## Phase 7 — US5: Persistence & accessibility (P3)

**Goal**: search/sort/chips/collapse survive the 3s poll and a dashboard restart; everything keyboard- and screen-reader-operable.
**Independent test**: set search+sort, wait through a poll and reload → state restored; in incognito, no error and state simply resets on restart; Tab reaches every control and a screen reader announces lane headers + chip states.

- [x] T020 [US5] Add view-state module vars (`MQ, MSORT, MCHIPS, MCOLLAPSE`) in the embedded script of `dashboard.py`, hydrated from localStorage on load and persisted on every change via a best-effort try/catch (mirroring the existing `skc-docfs` pattern); keys per data-model.md (FR-008, FR-009, E10 incognito no-op).
- [x] T021 [US5] Ensure `poll()` in `dashboard.py` re-renders the master pane from the persisted view-state vars (not from `STATE`) so a background refresh that adds a teammate's feature does not reset search/sort/collapse (FR-008, E11).
- [x] T022 [US5] Accessibility pass in `renderMaster()` (`dashboard.py`): search input `<label for>`, sort `<select>` labeled, chips `<button aria-pressed>`, lane headers `<button aria-expanded>` controlling their section, logical Tab order across the controls bar and lanes (FR-011, C6, E12).

---

## Phase 8 — Polish & cross-cutting

- [x] T023 Verify FR-012 / F3: `grep -nE "do_GET|self\.path *==" dashboard.py` shows the route set unchanged from baseline; no new endpoint added.
- [x] T024 Verify F2: `python3 -c "import dashboard"` succeeds and the server starts without error; confirm no new top-level import was added.
- [x] T025 Run the full `python3 -m unittest tests.test_dashboard` suite green (F1 + F5) and manually walk quickstart.md against this repo (lanes, search incl. store text, sort, chips, badge, WIP dot, restart persistence).
- [x] T026 Prose validator check (F4): confirm no dotted slash-command references were introduced in any changed doc/comment (hyphenate, e.g. `/speckit-compound-intent`).

---

## Dependencies & order

- Setup (T001) → Foundational (T002) → then stories.
- **US1 is the foundation** for the master render; US2/US3/US4 all extend `groupFeatures`/`renderMaster` from US1, so US1 must land first.
- US2, US3, US4 are otherwise independent extensions (each adds to the controls bar / cards) and can be built in any order after US1; they touch the same two functions, so serialize their edits even though they're conceptually parallel.
- US5 (persistence/a11y) depends on the controls existing (US2/US3) and cards (US4).
- Polish (T023–T026) last.

## Parallel opportunities

- Within US1: T005/T006 (progress) can proceed alongside T003/T004 (lane) — different helpers; T009 CSS is `[P]` vs the JS tasks.
- T017 (dirty-doc test) `[P]` with T016 implementation once the field name is fixed.
- T019 (badge/dot CSS) `[P]` with T018 JS.
- Cross-story JS edits to `renderMaster`/`groupFeatures` are NOT parallel (same functions).

## MVP scope

**US1 (Phase 3)** alone — grouped, collapsible, stage-derived lanes with the attention
override — is the shippable MVP. Search, sort/filter, signals, and persistence layer on
top incrementally.

## Gap-filling tasks (from /speckit-compound-gapfill)
<!-- Generated: 2026-07-23. Sources: docs/intents/feature-swimlane-triage.intent.md, docs/expectations/feature-swimlane-triage.expectations.md -->

### Constraint-violation tests

- [x] T027 [P] Add a perf test in `tests/test_dashboard.py` that builds 50 synthetic features and asserts `scan_state`-shaped grouping stays cheap; and a lightweight JS-side note/manual check that a 50-feature master render stays under the jank budget per quickstart.md (C2). <!-- gapfill: derived from C2 -->
- [x] T028 [P] Add a test asserting the `groupFeatures(...)` filter over 50 features is a single synchronous pass with no async/network work (guards the <150ms live-search budget) in `tests/test_dashboard.py` (C3). <!-- gapfill: derived from C3 -->

### Out-of-scope regression checks

- [x] T029 Confirm the feature diff introduces no ComposeProof / `cp_*` references anywhere: `grep -niE "composeproof|\bcp_[a-z]" dashboard.py` returns nothing new (OOS: ComposeProof). <!-- gapfill: derived from OOS:composeproof -->
- [x] T030 Confirm no drag-to-reorder or manual lane-assignment logic was added (lanes remain purely `_derive_lane`-computed): review the diff for drag handlers / draggable attributes / any writable lane field (OOS: drag/manual assignment). <!-- gapfill: derived from OOS:drag-manual -->
- [x] T031 Confirm the dashboard remains read-only from the UI: the diff adds no write to intent `status:` or any doc, and no new mutating request handler (OOS: edit status/doc from UI). <!-- gapfill: derived from OOS:status-edit -->
- [x] T032 Confirm `renderDetail`, `renderViewer`, and per-stage rendering are behaviorally unchanged — the diff touches only the master pane render, `groupFeatures`, controls, `scan_state` fields, and CSS (OOS: detail pane / stage render / doc viewer). <!-- gapfill: derived from OOS:detail-pane -->

## Format validation

All tasks use `- [ ] Txxx [P?] [USn?] description + file path`; setup/foundational/polish
carry no story label; story-phase tasks carry `[US1]`–`[US5]`; every task names its file.
