# Contract: `/api/state` feature object (swimlane additions)

The dashboard exposes exactly one interface this feature depends on: the JSON returned
by the existing `GET /api/state` route. **No route is added or changed** (C5 / FR-012);
this feature only adds fields to objects already in that payload.

## Added feature fields

Each element of `state.features[]` gains:

```jsonc
{
  // ...all existing fields (slug, stages, content, stage_files, docs, ...)
  "lane": "attention",   // one of: attention | wip | review | backlog | done
  "progress": 0.42,       // float 0.0–1.0; tasks done ÷ total, 0 when no tasks
  "doc_dirty": true       // bool; intent/expectation doc has uncommitted git changes
}
```

**Guarantees**:
- `lane` is always present and always one of the five enum values (never null).
- `progress` is always a number in `[0.0, 1.0]`.
- `doc_dirty` is always a bool; `false` when the repo has no git / git is unavailable
  (never raises, never omitted).

## Added compound field

`state.compound` gains:

```jsonc
{
  "adr": [ "..." ], "corrections": [ "..." ], "patterns": [ "..." ],  // unchanged
  "search_text": "lowercased concatenated store-note bodies, per-file capped"
}
```

**Guarantees**:
- `search_text` is always a string (possibly empty when the store is empty).
- It is branch-wide (not per-feature); the client matches it globally for store-text search.

## Consumer expectations (frontend)

- `renderMaster()` must tolerate a feature with `doc_dirty` absent (treat as false) and
  an unknown `lane` value (fall back to `backlog`) so an older/newer payload never breaks
  the render.
- The client performs all grouping, filtering, and sorting; the server does not sort or
  filter `features[]` for the master pane.
