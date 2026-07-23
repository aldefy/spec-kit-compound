# ADR-001: Dashboard derived views are computed client-side over the existing state poll

## Status
Accepted

## Context
The dashboard (`dashboard.py`) is a single-file server that ships an embedded
HTML/CSS/JS app and exposes a small fixed route set, chiefly `GET /api/state`, which
the browser polls every 3 seconds. The swimlane-triage feature needed a new way to
*view* the same features — grouped into lanes, searchable, sortable, filterable — plus
two derived signals (a stage-derived lane, a git-dirty flag). The forces: keep the
route surface minimal and auditable; keep the poll fast; avoid a second data path that
could drift from `/api/state`.

## Decision
New *views* are derived on the client over data already delivered by the existing
`/api/state` poll. The backend's only job is to add **data fields** to the existing
payload (e.g. per-feature `lane`/`progress`/`doc_dirty`, and a `compound.search_text`
blob). Grouping, filtering, and sorting run entirely in the embedded JS. No new HTTP
route or endpoint is added for a view.

## Consequences
- **Positive**: one data path (the poll) — no drift between a view endpoint and the
  main state; the route set stays small and easy to audit (a grep for handlers is a
  real regression check); views cost nothing server-side.
- **Positive**: makes "zero new server routes" a cheap, enforceable constraint
  (planverify/intentguard both check it via a route-diff).
- **Negative**: everything a view needs must fit in the state payload, so derived
  fields and any search corpus must be bounded (per-file caps) to keep the poll light.
- **Negative**: heavy client-side work over a very large feature set would move cost to
  the browser; acceptable at the ~50-feature scale this dashboard targets.

## Rule for AI
When adding a dashboard view, extend the `/api/state` payload with the data it needs
and render it client-side; do NOT add an HTTP route or endpoint for a view.
