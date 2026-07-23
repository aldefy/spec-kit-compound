# Quickstart: Swimlane Triage

## Run the dashboard

```bash
python3 dashboard.py            # serves the master pane + detail on localhost
```

Open the printed URL. The left rail is the master pane this feature reworks.

## Exercise the feature

1. **Lanes** — features appear grouped under lane headers (NEEDS ATTENTION / WIP /
   REVIEW / BACKLOG / DONE) with counts. A feature with a BLOCKED guard or
   BLOCKED_DRIFT planverify floats to NEEDS ATTENTION and shows a badge.
2. **Search** — type in the search box; the list narrows live across lanes (matches
   slug, goal, and compound-store note text). Clear it to restore all.
3. **Sort** — change the sort control (Newest / A–Z / Progress); items reorder within
   each lane, lane order stays fixed.
4. **Filter** — toggle lane chips to hide/show lanes; NEEDS ATTENTION always stays.
5. **WIP dot** — a feature whose intent/expectation doc has uncommitted git changes
   shows an in-progress dot. Try: edit `docs/intents/<slug>.intent.md` without
   committing → the dot appears within one 3s poll.
6. **Persistence** — set a search + sort, then reload the page (and restart the
   dashboard): the same search, sort, and collapsed lanes are restored.

## Run the tests

```bash
python3 -m pytest tests/ -q          # or the repo's existing test runner
```

The lane logic is covered by `tests/` fixtures — one per lane plus the
blocked-override case (F1). Existing tests must stay green (F5).

## Verify the constraints

- **No new route**: `grep -n "do_GET\|self.path ==" dashboard.py` — the route set is
  unchanged from before the feature (F3 / C5).
- **Imports still stdlib-only**: no new top-level import added (F2 startup check:
  `python3 -c "import dashboard"`).
- **Keyboard/SR**: Tab through search → sort → chips → lane headers; each chip and lane
  header exposes pressed/expanded state (C6 / E12).
