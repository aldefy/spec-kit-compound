# Research: Swimlane Triage

No external technology unknowns (stdlib Python + vanilla JS, no deps). Three internal
design decisions resolved below.

## Decision 1 — Lane derivation rules

**Decision**: Derive the lane purely from the feature's already-computed `stages` dict,
first-match-wins in this order:

1. **attention** — `stages.intentguard.verdict == "BLOCKED"` OR
   `stages.planverify.verdict == "BLOCKED_DRIFT"`.
2. **done** — `stages.writeback.state == "done"`.
3. **review** — `stages.implement.state == "done"` OR either gate stage
   (`planverify` / `intentguard`) is present (has a doc / verdict) but not blocked/closed.
4. **wip** — any of `specify | plan | tasks | implement` has state `done` or `current`
   (work started, cycle not closed).
5. **backlog** — otherwise (only `intent`, optionally `expectations`, present).

**Rationale**: Zero manual upkeep (C1/FR-001); reuses existing verdicts the dashboard
already parses; the attention override matches the intent's "blocked work floats to top"
and is the repo's genuine differentiator vs compound-engineering (no equivalent guard).

**Alternatives considered**: (a) frontmatter `status:` — rejected, manual and drifts.
(b) git WIP-vs-committed as the lane axis — rejected, ties lanes to git rather than
pipeline progress; retained instead as a per-card dot (FR-007).

## Decision 2 — Compound-store text search

**Decision**: Ship a lowercased, per-file-capped concatenation of compound-store note
bodies as `compound.search_text` inside the existing `/api/state` payload; client search
matches slug + goal + this shared blob.

**Rationale**: Satisfies E3/FR-004 store-text search with **no new route** (C5/FR-012).
The store is branch-wide (not per-feature), so a single shared blob is correct and cheap;
capping per file bounds payload + keeps client search within C2/C3 latency.

**Alternatives considered**: a `/api/search` endpoint — rejected, violates C5. Per-feature
store attribution — rejected as out of scope (store notes aren't reliably feature-tagged
in v1).

## Decision 3 — Uncommitted-doc (WIP dot) detection

**Decision**: One `git status --porcelain -- <intent-path> <exp-path>` per feature scan
via the existing `_git()` wrapper; `doc_dirty = True` if either path shows as
modified/untracked. (Batched into as few git calls as practical.)

**Rationale**: `_git()` already degrades to `""` on any failure (not a repo, no git,
timeout), so `doc_dirty` is simply false there (FR-007 graceful, C-side never blocks).
Matches the intent's "uncommitted doc = teammate still drafting; don't build on it yet."

**Alternatives considered**: diffing mtimes — rejected, unreliable across checkouts.
Parsing `git diff` — rejected, `--porcelain` status is cheaper and sufficient (presence,
not content).
