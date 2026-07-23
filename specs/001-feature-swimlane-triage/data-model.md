# Data Model: Swimlane Triage

All entities are in-memory / transport shapes — no database.

## Feature (extends the existing `/api/state` feature object)

Existing fields (unchanged): `slug`, `status`, `created`, `spec_dir`, `stages`,
`stage_files`, `content` (incl. `goal`), `files`, `docs`, `doc_stage`.

New fields added by `scan_state`:

| Field | Type | Meaning | Source |
|---|---|---|---|
| `lane` | string enum | `attention \| wip \| review \| backlog \| done` | `_derive_lane(stages)` |
| `progress` | float 0.0–1.0 | tasks done ÷ total (0 if none) | `_feature_progress(stages)` |
| `doc_dirty` | bool | intent/expectation doc has uncommitted git changes | `git status --porcelain` via `_git` |

## Lane derivation (first match wins)

| Order | Lane | Condition |
|---|---|---|
| 1 | `attention` | `intentguard.verdict == "BLOCKED"` or `planverify.verdict == "BLOCKED_DRIFT"` |
| 2 | `done` | `writeback.state == "done"` |
| 3 | `review` | `implement.state == "done"` or a gate stage present (doc/verdict) and not blocked |
| 4 | `wip` | any of specify/plan/tasks/implement is `done` or `current` |
| 5 | `backlog` | otherwise (intent-only / +expectations) |

**Display order (fixed, top→bottom)**: attention → wip → review → backlog → done.
Each lane header shows its live count. The `attention` lane is exempt from chip hiding.

## Lane (frontend-only, produced by `groupFeatures`)

| Field | Type | Meaning |
|---|---|---|
| `lane` | string enum | the lane key |
| `label` | string | display label (e.g. "NEEDS ATTENTION", "WIP") |
| `items` | Feature[] | features in this lane, sorted per the active sort mode |

## ViewState (frontend-only, persisted to localStorage)

| Field | localStorage key | Type | Default |
|---|---|---|---|
| search query | `skc-mq` | string | `""` |
| sort mode | `skc-msort` | `"newest" \| "az" \| "progress"` | `"newest"` |
| active lane chips | `skc-mchips` | string[] (lane keys shown) | all lanes |
| collapsed lanes | `skc-mcollapse` | string[] (lane keys collapsed) | `[]` |

Persistence is best-effort (try/catch) so private/incognito mode degrades to
session-only with no error (FR-009, E10). All four survive the 3s poll because they
live in module vars, not in `STATE` (FR-008).

## Compound (extends existing payload)

| Field | Type | Meaning |
|---|---|---|
| `search_text` | string | lowercased, per-file-capped concatenation of adr/corrections/patterns note bodies — the store-text search corpus (FR-004, E3) |

Existing `adr` / `corrections` / `patterns` filename lists are unchanged.
