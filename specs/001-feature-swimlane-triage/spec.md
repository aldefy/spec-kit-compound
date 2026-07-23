# Feature Specification: Swimlane Triage for the Dashboard Master Pane

**Feature Branch**: `main` (dogfooded; no dedicated branch)
**Created**: 2026-07-23
**Status**: Draft
**Intent**: `../../docs/intents/feature-swimlane-triage.intent.md`
**Expectations** (validator-only): `../../docs/expectations/feature-swimlane-triage.expectations.md`

## Summary

The dashboard's master pane currently lists every feature on a branch as a flat,
filesystem-ordered list. Because the compound workflow is multi-developer — intent
and expectation documents are git-shared so teammates can pick up each other's work —
that flat list makes it hard to tell what stage each feature is at, whose work is
still in progress, and what needs attention. This feature reorganizes the master pane
into progress-derived lanes with search, sort, and filtering, so any developer can
triage the whole branch at a glance and pick up work someone else started.

## User Scenarios & Testing

### Primary user story

A developer opens the dashboard on a shared branch where a teammate has already
created several intent and expectation documents. Instead of a flat list, they see
features grouped into lanes by pipeline progress. They filter to just the in-progress
work, search for a feature by name, and open it to read the teammate's intent before
writing any code — confident about which items are still being drafted and which are
blocked and need attention first.

### Acceptance scenarios

1. **Given** a branch with features at different pipeline stages, **When** a developer
   opens the dashboard, **Then** features appear grouped under lane headers
   (Needs attention, WIP, Review, Backlog, Done), each header showing a count.
2. **Given** the grouped list, **When** a developer types part of a feature's name,
   **Then** only matching features remain visible across lanes, updating live as they
   type, with no submit action.
3. **Given** a search term that appears only inside a compound-store decision note,
   **When** the developer searches it, **Then** the feature whose store text contains
   that term stays visible.
4. **Given** the grouped list, **When** a developer changes the sort control to
   alphabetical, **Then** features inside each lane reorder A–Z while lane order is
   unchanged.
5. **Given** the grouped list, **When** a developer disables all lanes except WIP,
   **Then** only in-progress features show, and any feature needing attention remains
   visible regardless of the toggle.
6. **Given** a search term and sort mode are set, **When** the developer closes and
   reopens the dashboard, **Then** the same search, sort, and collapsed lanes are
   still in effect.
7. **Given** a blocked feature and a feature whose docs a teammate is still drafting,
   **When** viewing any lane, **Then** the blocked feature carries an attention badge
   (visible even when filtered into another lane) and the in-progress feature carries
   a distinct in-progress marker.

### Edge cases

- **Empty branch**: no intent docs yet → a clear empty state, never an error or blank
  screen.
- **No matches**: a search matching nothing → every lane reads zero with a clear
  "no matches" indication; clearing the search restores all features.
- **No persistent storage** (private/incognito browsing): search/sort/filter work for
  the session and simply do not persist across restart, with no error.
- **Background refresh**: while a search is typed and a lane collapsed, the periodic
  refresh brings in a teammate's newly added feature into its correct lane without
  resetting the developer's search, sort, or collapse state.
- **Keyboard-only / screen reader**: all controls are reachable and operable by
  keyboard, and lane headers and filter toggles are announced with their state.

## Requirements

### Functional Requirements

- **FR-001**: The system MUST assign each feature to exactly one lane derived solely
  from its pipeline stage state, with no manual assignment. Lanes, in fixed display
  order: Needs attention, WIP, Review, Backlog, Done.
- **FR-002**: A feature that is blocked or has detected drift MUST be placed in the
  Needs-attention lane regardless of its other stage progress, and MUST still carry a
  visible attention marker if a filter would otherwise place it elsewhere.
- **FR-003**: The master pane MUST display features grouped under collapsible lane
  headers, each header showing the count of features in that lane.
- **FR-004**: The system MUST provide a live search that filters visible features by
  feature name, goal text, and compound-store body text, updating results as the user
  types without a submit action.
- **FR-005**: The system MUST provide a sort control that orders features within each
  lane (at minimum: newest-first and name A–Z), leaving lane order fixed.
- **FR-006**: The system MUST provide per-lane filter toggles that show or hide whole
  lanes; the Needs-attention lane MUST remain visible regardless of toggles.
- **FR-007**: Each feature card MUST show an in-progress marker when its intent or
  expectation document has uncommitted changes on the branch.
- **FR-008**: The system MUST preserve the user's search term, sort mode, active lane
  filters, and collapse state across the periodic background refresh.
- **FR-009**: The system MUST persist that same view state so it survives closing and
  reopening the dashboard; where persistent storage is unavailable, the feature MUST
  still function for the session without error.
- **FR-010**: On a branch with no features, the master pane MUST show a clear empty
  state rather than an error or blank screen.
- **FR-011**: All controls (search, sort, lane toggles) and lane headers MUST be
  operable by keyboard and expose their state to assistive technology (WCAG 2.1 AA).
- **FR-012**: The feature MUST NOT add any new server route or endpoint; all grouping,
  search, sorting, and filtering operate over data already delivered by the existing
  periodic state refresh.

### Key Entities

- **Feature**: a unit of work on the branch, identified by its slug, carrying a goal,
  a set of pipeline stage states, verdicts (blocked / drift), a derived lane, a
  progress measure, and an in-progress (uncommitted-doc) flag.
- **Lane**: a named bucket derived from a feature's stage state
  (Needs attention / WIP / Review / Backlog / Done), with a fixed display order and a
  live count.
- **View state**: the developer's current search term, sort mode, active lane filters,
  and per-lane collapse state — held across refreshes and across restarts.

## Success Criteria

- **SC-001**: A developer landing on a branch with mixed-stage features can identify
  which features are in progress, which are blocked, and which are done without
  opening any individual feature — from the grouped view alone.
- **SC-002**: Searching narrows the visible list within a fraction of a second of
  typing, fast enough that it feels instant and never stalls the periodic refresh.
- **SC-003**: A developer can restrict the view to a single lane and back in one action
  each, and the view returns to exactly its prior state.
- **SC-004**: The developer's search, sort, and filter selections are still in place
  after reopening the dashboard.
- **SC-005**: The grouped master pane redraws without visible jank for a branch of up
  to 50 features.
- **SC-006**: A keyboard-only user can reach and operate every control and understand,
  via a screen reader, which lane each feature is in and which filters are active.

## Assumptions

- "Blocked" and "drift" are determined by the existing gate verdicts already surfaced
  by the dashboard (intentguard BLOCKED, planverify BLOCKED_DRIFT).
- Compound-store search targets the decision/correction/pattern notes already present
  under the project's compound store.
- "Uncommitted doc" is judged against the current git working tree of the branch.
- 50 features is a reasonable upper bound for a single branch's active feature set.

## Out of Scope

- ComposeProof and its separate verification dashboard.
- Drag-to-reorder or any manual lane assignment.
- Editing a feature's intent status or any document from the dashboard UI.
- Any change to the detail pane, per-stage rendering, or the document viewer.
- Adding new server routes or endpoints.
