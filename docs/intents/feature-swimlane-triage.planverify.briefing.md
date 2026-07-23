# Sealed Briefing — Plan Verification

You are an **independent plan checker**. You did not write this plan. Judge the
proposed plan + tasks against the locked criteria and surface facts below. You have no
other context and must not assume any. Perform P3a–P3d and return exactly the JSON
verdict contract at the end.

---

## Goal
Developers can triage every feature on a branch by its pipeline progress — grouped,
searchable, and sortable — so a teammate can pick up work someone else started.

---

## Locked intent

### Out of scope (verbatim)
- ComposeProof and its HTML verification dashboard — a separate MCP/project, not this repo.
- Drag-to-reorder or any manual lane assignment; lanes are derived only.
- Any new server route or endpoint; grouping/search/sort run client-side over the existing state poll.
- Editing intent `status:` frontmatter (or any doc) from the UI.
- Changes to the detail pane, stage rendering, or the document viewer.

### Constraints (verbatim)
- **C1**: Lane derivation is a pure function of a feature's stage state — identical stage state always yields the same lane, with zero manual input.
- **C2**: A full master-pane render (group + filter + sort of the entire feature set) completes in < 50ms for up to 50 features, so the 3s poll never janks.
- **C3**: Search is live — visible results update within 150ms of a keystroke, with no submit action.
- **C4**: View state (search text, sort mode, active chips, collapse) survives both the 3s poll and a dashboard restart via localStorage.
- **C5**: Zero new server routes — grouping, search, and sort run entirely client-side over the existing state poll; git-dirty status and compound-store search text ship inside the existing state payload.
- **C6**: The controls and list are keyboard- and screen-reader operable to WCAG 2.1 AA — every control reachable by Tab, lane headers semantic, chips as toggle buttons exposing pressed state.

### Failure conditions (verbatim)
- **F1**: The `_derive_lane` unit tests fail (fixture per lane plus the blocked-override case).
- **F2**: `python -c "import dashboard"` fails, or the dashboard process errors on startup.
- **F3**: A new server route or endpoint is added to `dashboard.py` (violates C5).
- **F4**: The planverify/intentguard hyphenation validator flags any slash-command reference in changed prose.
- **F5**: The existing `tests/` suite regresses — any previously passing test fails.

---

## Locked expectations

### Positive scenarios
- **E1**: Feature list appears grouped under lane headers (Needs attention, WIP, Review, Backlog, Done), each header showing a count.
- **E2**: Typing part of a feature's name narrows the visible list live across lanes, no submit.
- **E3**: Searching a word that appears only inside a compound-store note keeps that feature visible.
- **E4**: Alphabetical sort reorders features within each lane; lane order unchanged.
- **E5**: Disabling all lanes except WIP shows only in-progress features; needs-attention still shows.
- **E6**: Search term, sort mode, and collapsed lanes persist across closing and reopening the dashboard.
- **E7**: A blocked feature carries an attention badge (visible even when filtered into another lane); an in-progress feature (teammate still drafting) carries a distinct in-progress marker.

### Edge / negative scenarios
- **E8**: A branch with no intent docs shows a clear empty state, never an error or blank screen.
- **E9**: A search matching nothing shows zero in every lane with a clear "no matches" indication; clearing restores all.
- **E10**: In private/incognito browsing, search/sort/filter work for the session, do not persist across restart, no error.
- **E11**: The 3-second refresh bringing in a new feature does not reset the developer's search, sort, or collapse state.
- **E12**: A keyboard-only user can operate the search box, sort control, and lane chips in order; a screen reader announces lane headers and each chip's on/off state.

---

## The plan (specs/001-feature-swimlane-triage/plan.md)

Summary: Reorganize `dashboard.py`'s master pane from a flat list into progress-derived,
collapsible lanes with live search, within-lane sort, and lane filter chips. Add an
always-visible blocked/drift badge and a git "WIP dot" for uncommitted intent/expectation
docs. All grouping/search/sort runs client-side over the existing `/api/state` poll. The
only backend additions are three derived per-feature fields (`lane`, `progress`,
`doc_dirty`) plus a compound-store `search_text` blob, all carried inside the existing
state payload. No new server routes.

Backend changes to `dashboard.py`:
1. `_derive_lane(stages)` — pure function, first-match-wins: attention (intentguard
   BLOCKED or planverify BLOCKED_DRIFT) → done (writeback done) → review (implement done
   or a gate present, not blocked) → wip (specify/plan/tasks/implement started) → backlog.
2. `_feature_progress(stages)` — tasks done ÷ total (0 if none).
3. `doc_dirty` per feature — one `git status --porcelain -- <intent> <exp>` via the
   existing never-raising `_git()` helper; false when git unavailable.
4. `compound.search_text` — lowercased, per-file-capped concatenation of store note bodies.
5. Each feature gains `lane` + `progress`; existing fields preserved.

Frontend changes (embedded JS/CSS in `dashboard.py`):
6. `groupFeatures(features, opts)` — pure JS: filter (slug+goal+store text), chip
   visibility (attention always shown), within-lane sort. Ordered lane output.
7. Rewrite `renderMaster()` — controls bar (labeled search input, sort select, chip
   toggle-buttons) + collapsible lane sections with counts. Cards keep minibar + guard
   chip; gain blocked/drift badge (shown in any lane) + WIP dot.
8. View-state module vars (MQ/MSORT/MCHIPS/MCOLLAPSE) hydrated from + persisted to
   localStorage (mirrors existing skc-docfs pattern); best-effort try/catch for incognito.
9. Empty / no-match states preserved / added.
10. Accessibility: labeled search, labeled sort select, chips as button[aria-pressed],
    lane headers as button[aria-expanded], logical Tab order.

Explicitly declared out of scope in the plan: no new route; no change to renderDetail /
renderViewer / per-stage rendering; no drag/manual lane assignment; no UI writes to docs.
The agent-context update step is skipped (no SPECKIT markers in this repo).

No `requested_surface:` blocks are present in the plan.

## The tasks (specs/001-feature-swimlane-triage/tasks.md)

32 tasks. T001 baseline green; T002 lane constants; T003–T009 US1 grouped lanes (lane
tests + impl, progress helper, groupFeatures, renderMaster rewrite, CSS); T010–T012 US2
search (store search_text, filter, input + no-match); T013–T015 US3 sort + chips;
T016–T019 US4 card signals (doc_dirty + test, badge + dot render, CSS); T020–T022 US5
persistence + a11y; T023–T026 polish (no-new-route grep, import/startup, full suite +
quickstart, hyphenation check). Gapfill: T027 C2 perf, T028 C3 synchronous-search,
T029 ComposeProof regression, T030 drag/manual regression, T031 read-only-UI regression,
T032 detail-pane-unchanged regression. Every task names its file: only `dashboard.py`
and `tests/test_dashboard.py` are touched.

---

## Surface analysis (orchestrator — plain facts, not judgments)
- Proposed surface: 2 files — `dashboard.py`, `tests/test_dashboard.py`.
- `dashboard.py`: in-scope — the feature explicitly reworks this file's master pane.
- `tests/test_dashboard.py`: in-scope — F1/F5 mandate tests here.
- Drift candidates: none. No out-of-scope or undeclared paths proposed.
- Fact for your consideration: `dashboard.py` also contains out-of-scope code (the
  detail pane / viewer / per-stage rendering). The plan edits the same file but declares
  those regions unchanged; task T032 is a regression check asserting that. Editing a
  shared file is not itself a new path — judge whether the plan's approach risks the
  out-of-scope regions.
- No `requested_surface:` blocks exist (nothing to evaluate under P3b).

---

## Relevant compound-store notes
- One correction note exists: `2026-06-03-sample-no-css-img-filters` — forbids CSS
  `filter: brightness/invert/grayscale` on `img` selectors. This plan adds CSS for lane
  sections, badges, and a WIP dot. Flag BLOCKED_DRIFT under P3d only if the plan's CSS
  would plausibly require such an image filter (it should not — no image styling is planned).
- No ADRs present.

---

## Verdict contract — return EXACTLY this JSON as the LAST ```json block

```json
{
  "checked_by": "e.g. Codex (gpt-5.x)",
  "p3a_surface_drift": [
    {"path": "...", "classification": "out-of-scope|undeclared", "requested": false, "verdict": "PASS|BLOCKED_DRIFT"}
  ],
  "p3b_drift_requests": [],
  "p3c_obligation_coverage": [
    {"id": "C1", "planned_by": "task ref | null", "verdict": "PASS|REPLAN_ALLOWED"}
  ],
  "p3d_constraint_precheck": [
    {"id": "C2", "verdict": "PASS|BLOCKED_DRIFT", "rationale": "..."}
  ],
  "summary": "one short paragraph",
  "verdict": "PASS|REPLAN_ALLOWED|BLOCKED_DRIFT"
}
```

Judge:
- **P3a** surface drift (blocking): any true out-of-scope path → BLOCKED_DRIFT. (Empty candidate list is a valid PASS.)
- **P3b** drift requests: none present → empty array.
- **P3c** obligation coverage: does plan+tasks plan to satisfy every constraint (C1–C6),
  failure condition (F1–F5), and expectation (E1–E12)? Missing → REPLAN_ALLOWED.
- **P3d** constraint pre-check: does the planned approach already contradict any constraint? → BLOCKED_DRIFT.
- Final verdict: BLOCKED_DRIFT if any P3a/P3b/P3d block; else REPLAN_ALLOWED if any coverage gap; else PASS.
