# Design: spec-kit-compound pipeline dashboard

- **Date**: 2026-06-25
- **Status**: approved for planning
- **Topic**: A local, read-only web dashboard that visualizes the spec-kit-compound chain — which features exist, what stage each has reached, task progress, intentguard verdict, and the accumulating compound store.

---

## 1. Problem

The spec-kit-compound chain produces a sequence of artifacts per feature (intent → expectations → spec → plan → tasks → gapfill → implement → intentguard → writeback), scattered across `docs/intents/`, `docs/expectations/`, `specs/<dir>/`, and `docs/compound/`. There is no single view of *what is done and what is not*. A developer running the chain has to read directories by hand to know where a feature stands. This dashboard gives an at-a-glance, live view on localhost.

## 2. Goals

- One row per feature showing how far it has advanced through the 9 chain stages.
- Real task progress (parsed `- [ ]` / `- [x]` counts from `tasks.md`), not just "tasks file exists."
- Surface the intentguard verdict (PASS / REVIEW NEEDED / BLOCKED) for instant triage.
- Show the compound store accumulating (ADRs / corrections / patterns counts + filenames).
- Live: updates as the developer runs chain commands, without a manual refresh.

## 3. Non-goals (YAGNI)

- No write actions. The dashboard never runs chain commands, never edits files. Pure read.
- No changes to the 8 existing `/speckit-compound-*` commands. (Confirmed: intentguard already writes a machine-readable verdict file, so no command change is needed to surface it.)
- No auth, no multi-project, no remote hosting. Localhost only.
- No database, no event log, no persisted state. Stateless re-scan on every request.
- No build step, no package manager, no third-party dependency.
- No websocket/SSE push. Polling is sufficient for a single-user local tool.

## 4. Architecture

A single Python-stdlib server plus a thin launcher. No `pip install`, no `node_modules`.

```
dashboard.py          ← stdlib http.server; two routes (below). Contains the scanner + the inlined HTML page.
scripts/dashboard.sh  ← launcher: python3 dashboard.py [--port N] [--open]
```

Two routes:

| Route | Returns |
|---|---|
| `GET /` | The dashboard HTML page (one inlined HTML/CSS/JS string). |
| `GET /api/state` | JSON snapshot of the current chain state, produced by a fresh filesystem scan. |

The page loads once, then polls `GET /api/state` every ~3s and re-renders. Because each poll re-scans from scratch, the view is always truthful — there is no cached state to drift.

The server resolves the repo root from its own location (so it works regardless of CWD) and refuses to serve anything outside it.

### Units (each independently understandable + testable)

1. **Scanner** (`scan_state(repo_root) -> dict`) — pure function: filesystem in, JSON-able dict out. No HTTP, no globals. This is the core and gets the most tests.
2. **Frontmatter parser** (`parse_frontmatter(text) -> dict`) — minimal YAML-ish reader for the `key: value` frontmatter the commands already write. Not a full YAML parser; handles the flat scalar fields the schemas use.
3. **Task parser** (`parse_tasks(text) -> {done, total}`) — counts GFM checkboxes `- [ ]` / `- [x]` (case-insensitive on the x).
4. **HTTP layer** (`Handler`) — routes `/` and `/api/state`, calls the scanner, serializes. Thin.
5. **Launcher** (`scripts/dashboard.sh`) — arg parsing, port selection, optional `--open`.

## 5. Data model

`scan_state` returns:

```json
{
  "scanned_at": "2026-06-25T12:04:31",
  "repo": "spec-kit-compound",
  "stages": ["intent","expectations","specify","plan","tasks","gapfill","implement","intentguard","writeback"],
  "features": [
    {
      "slug": "active-corrections",
      "status": "active",
      "created": "2026-06-03",
      "spec_dir": "specs/003-active-corrections",   // or null if no match
      "stages": {
        "intent":       {"state": "done"},
        "expectations": {"state": "done"},
        "specify":      {"state": "done"},
        "plan":         {"state": "done"},
        "tasks":        {"state": "current", "done": 5, "total": 8},
        "gapfill":      {"state": "pending"},
        "implement":    {"state": "pending"},
        "intentguard":  {"state": "pending", "verdict": null},
        "writeback":    {"state": "pending"}
      },
      "files": ["docs/intents/active-corrections.intent.md", "..."]
    }
  ],
  "orphan_specs": [ {"dir": "specs/099-stray", "stages_present": ["specify","plan"]} ],
  "compound": {
    "adr":        ["001-hook-dispatch.md"],
    "corrections":["2026-06-03-sample-no-css-img-filters.md"],
    "patterns":   []
  }
}
```

`state` per stage is one of `done | current | pending | blocked`. The **current** stage is the last `done` stage's successor (the first non-done stage). `blocked` is set only on the `intentguard` stage when its verdict is `BLOCKED`.

## 6. Stage detection (done-signals)

The spine is `docs/intents/*.intent.md` — one feature row per intent. For each slug:

| # | Stage | Done-signal |
|---|---|---|
| 1 | intent | `docs/intents/<slug>.intent.md` exists |
| 2 | expectations | `docs/expectations/<slug>.expectations.md` exists |
| 3 | specify | matched `specs/<dir>/spec.md` exists |
| 4 | plan | matched `specs/<dir>/plan.md` exists |
| 5 | tasks | matched `specs/<dir>/tasks.md` exists; parse checkboxes for `done`/`total` |
| 6 | gapfill | `tasks.md` contains a gapfill source-comment marker (string match on the marker the gapfill command emits) |
| 7 | implement | `tasks.md` checkboxes 100% complete (`done == total > 0`) |
| 8 | intentguard | `docs/intents/<slug>.intentguard.md` exists; read its frontmatter `verdict:` → `PASS` / `REVIEW NEEDED` / `BLOCKED` |
| 9 | writeback | any file in `docs/compound/{adr,corrections,patterns}/` with mtime newer than the intent file's `created` date (best-effort attribution) |

Notes:
- Stage 7 (implement) is inferred from task completion; this is best-effort and labeled as such in the UI tooltip.
- Stage 9 (writeback) attribution is heuristic (mtime vs created); the compound panel shows the store as a whole regardless, so a wrong attribution never hides a file.

### Feature join (slug ↔ spec dir)

Best-effort, no schema change. Normalize both sides (strip a leading `NNN-` numeric prefix from the spec dir, lowercase, compare). On a unique match, link. On no match, stages 3–7 stay `pending` and a hint ("no spec dir matched") shows on hover. `specs/` dirs that match no intent become **orphan rows** in their own panel — honest about what can't be linked.

## 7. Visual design

Concept: **the chain as a lit conveyor rail.** Each feature is a horizontal row; the 9 stages are fixed lanes left→right. A stage is a node on a rail: done nodes filled and joined by a solid rail, the current node glowing, pending nodes hollow on a dashed rail. Numbering (`01 INTENT … 09 WRITEBACK`) is honest — the stages are a real ordered sequence, so the numbers carry information. The compound store sits at the bottom and visibly grows as features complete.

### Palette (instrument-panel, deep slate — deliberately not the AI-default near-black+acid-green)

| Token | Hex | Use |
|---|---|---|
| ground | `#0E1116` | page background |
| surface | `#161B22` | cards, rails, panels |
| text | `#E6EDF3` | primary text |
| muted | `#7D8590` | labels, captions |
| done | `#3FB950` | completed stage nodes + rail |
| progress | `#D29922` | in-progress / REVIEW NEEDED |
| blocked | `#F85149` | intentguard BLOCKED node only |
| accent | `#388BFD` | current-stage glow, links |

### Type

- **Display** (title, feature slugs): Space Grotesk — engineered feel, used with restraint.
- **Body / UI** (labels): Inter.
- **Data / mono** (stage numbers, `5/8` counts, file paths, verdict tokens): JetBrains Mono — the numeric spine aligns in monospace.
- Google Fonts via `@import` (page is server-inlined, not CSP-locked), with a system fallback stack so it degrades cleanly offline.

### Signature element

The **rail**: a horizontal line threading each feature row — solid+green up to the reached stage, dashed+grey after, current node pulsing accent blue. A BLOCKED feature's rail turns red at the intentguard node, making triage scannable across the whole list. This is the one bold element; everything else stays quiet.

### Layout (wireframe)

```
┌──────────────────────────────────────────────────────────────────┐
│  spec-kit-compound · pipeline            ● live  ·  scanned 12:04  │
├──────────────────────────────────────────────────────────────────┤
│  01 INTENT 02 EXP 03 SPEC 04 PLAN 05 TASKS 06 GAP 07 IMPL 08 GUARD 09 WB │
├──────────────────────────────────────────────────────────────────┤
│ active-corrections   ●━━●━━●━━●━━◉  ·  ·  ·  ·    tasks 5/8 · GUARD —  │
│ some-other-feature   ●━━●━━●━━●━━●━━●━━●━━✗·······  BLOCKED            │
│ orphan-spec-dir      ○··○··●━━●━━●  ·  ·  ·  ·    (no intent)         │
├──────────────────────────────────────────────────────────────────┤
│  COMPOUND STORE          ADRs 2 · Corrections 4 · Patterns 1         │
│   ▸ 001-hook-dispatch.md   ▸ 2026-06-03-no-css-filters.md  …         │
└──────────────────────────────────────────────────────────────────┘
```

Clicking a feature row expands it to show the actual filenames, the parsed task checklist (done/remaining), and the intentguard verdict + rationale snippet.

### Motion

Restrained, and gated behind `prefers-reduced-motion: reduce`. Current node has a slow ambient pulse; when a poll detects a stage changed state, that node plays a one-shot fill animation so progress is visible as it lands. Nothing else moves.

### Quality floor

Responsive down to a narrow window (rail becomes horizontally scrollable inside its row container; the page body never scrolls sideways). Visible keyboard focus on the expandable rows. Reduced motion respected.

### Empty / error states

- No `docs/intents/` or zero intents: a centered invitation — "No features yet. Run `/speckit-compound-intent` to start the chain." (direction, not mood).
- Scan error on a single file (e.g. malformed frontmatter): that feature still renders; the bad field shows as `—` and a small warning dot with the parse error on hover. One bad file never blanks the page.
- `/api/state` fetch fails (server stopped): the live indicator goes grey and reads "disconnected — is dashboard.py running?".

## 8. Error handling

- Scanner is defensive per-file: a `try/except` around each file read; a failure degrades that one field, never the whole scan.
- Server binds `127.0.0.1` only. If the port is taken, the launcher tries the next few ports and prints the chosen URL.
- Path traversal: `/` serves only the inlined page; `/api/state` takes no path input. No filesystem path is ever taken from the request.

## 9. Testing

- **Scanner unit tests** (the bulk): build small fixture trees (a `tmp` repo with assorted `docs/`/`specs/` states) and assert the returned dict — covering: no intents (empty), intent-only, full chain, BLOCKED verdict, malformed frontmatter (degrades, doesn't crash), orphan spec dir, slug↔dir join with `NNN-` prefix, task checkbox counting (0/0, partial, complete).
- **Parser unit tests**: frontmatter scalars, task checkbox variants (`[ ]`, `[x]`, `[X]`, non-task lines).
- **HTTP smoke test**: boot the server on an ephemeral port, `GET /` returns 200 HTML, `GET /api/state` returns valid JSON matching the schema.
- `scripts/validate.sh` updated to cover the new files; `shellcheck` clean on `scripts/dashboard.sh`.

## 10. Open questions

None outstanding. (The earlier question about intentguard's verdict resolved itself: `docs/intents/{slug}.intentguard.md` already carries `verdict:` in frontmatter, so the dashboard reads it directly with zero command changes.)
