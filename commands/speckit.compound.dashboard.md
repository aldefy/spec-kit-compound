---
description: "Launch the read-only pipeline dashboard for the current spec-kit project (intent → spec → plan → tasks → expectations → intentguard, plus content, drift, tokens, architecture). Serves on localhost; background process."
---

# Pipeline Dashboard

This command launches the spec-kit-compound **pipeline dashboard** — a read-only,
self-contained localhost view of the SDD chain for the project you are currently
working in: intents, specs, plans, tasks, expectations, the L3 intentguard drift
panel, token usage, and the architecture diagram.

It is a **thin shell-script wrapper** that starts `dashboard.py` as a background
HTTP server, so it dispatches cleanly and returns immediately instead of tying up
the session.

---

## What you must do

1. Determine the spec-kit project root — the directory containing `.specify/`.
   When invoked from a spec-kit project this is the current working directory.

2. Launch the dashboard **in the background**, scanning that project root, via Bash:

   ```bash
   .specify/extensions/compound/scripts/dashboard.sh --repo "$(pwd)" >/tmp/compound-dashboard.log 2>&1 &
   ```

   (In this dev repo, where the extension is not installed under `.specify/`, run
   `./scripts/dashboard.sh --repo "$(pwd)"` instead.)

3. Read the first line of `/tmp/compound-dashboard.log` to get the chosen URL
   (the server probes ports starting at `8787` and prints
   `… dashboard → http://127.0.0.1:<port>/  (scanning <root>)`).

4. Tell the user the URL and confirm which project root is being scanned, e.g.:

   > *"Dashboard is live at http://127.0.0.1:8787/ — scanning `<project root>`. It polls `/api/state` and updates as your pipeline docs change. Stop it with `kill %1` or by closing the session."*

---

## Flags you may pass through

- `--repo PATH` — scan a different spec-kit project than the cwd
- `--port N` — start probing from port `N` (default `8787`; falls forward 10 ports if busy)
- `--open` — open the URL in a browser (skip when running headless)

---

## Tool choices

- **Bash** to launch the background server and read the log line for the URL.
- No Read/Write/Edit needed — the dashboard is read-only and ships as a single
  dependency-free Python file (stdlib `http.server` only).

---

## What you do NOT do

- **Do not run it in the foreground** — `serve_forever()` blocks until killed and
  would freeze the session. Always background it (`&`) and report the URL.
- **Do not point `--repo` at the extension's own directory**
  (`.specify/extensions/compound/`). That dir has no `docs/` or `specs/` and the
  dashboard would render an empty chain. Use the spec-kit **project** root.
- **Do not treat this as part of the enforced pipeline.** It is a visualization
  aid only — it never writes, gates, or validates anything.
