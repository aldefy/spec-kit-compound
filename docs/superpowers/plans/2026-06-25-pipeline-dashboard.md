# Pipeline Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A read-only localhost web dashboard that scans the filesystem and shows, per feature, how far it has advanced through the 9-stage spec-kit-compound chain, with live task progress and intentguard verdict.

**Architecture:** A single Python-stdlib server (`dashboard.py`) exposes `GET /` (an inlined HTML/CSS/JS page) and `GET /api/state` (a JSON snapshot from a fresh filesystem scan). The page polls the JSON endpoint every ~3s and re-renders. A thin bash launcher (`scripts/dashboard.sh`) starts it. No third-party dependencies; the 8 existing chain commands are untouched.

**Tech Stack:** Python 3 stdlib only (`http.server`, `glob`, `os`, `json`, `re`, `unittest`); bash launcher; vanilla HTML/CSS/JS inlined in the server.

## Global Constraints

- **No third-party dependencies.** Python stdlib only; no `pip install`, no `node_modules`, no build step. (Repo is dependency-free by design.)
- **Read-only.** The dashboard never writes files, never runs chain commands. `/api/state` takes no path input from the request.
- **No changes to the 8 `/speckit-compound-*` command files** or `extension.yml` command list.
- **Server binds `127.0.0.1` only.** Localhost tool, no external exposure.
- **Repo root resolved from the script's own location**, not CWD, so it runs from anywhere.
- **9 stages, fixed order, exact names:** `intent, expectations, specify, plan, tasks, gapfill, implement, intentguard, writeback`.
- **Stage states, exact strings:** `done | current | pending | blocked`.
- **`shellcheck` clean** on `scripts/dashboard.sh`. `scripts/validate.sh` exits 0 after updates.
- **Tests use stdlib `unittest`**, runnable via `python3 -m unittest discover tests`.

---

## File Structure

- Create: `dashboard.py` — server + scanner + parsers + inlined page. Single file (the whole tool is small enough to hold in context; splitting into a package would add ceremony for no benefit). Internally organized: parser fns → `scan_state` → `Handler` → `PAGE_HTML` constant → `main()`.
- Create: `scripts/dashboard.sh` — launcher (arg parse, port pick, optional `--open`).
- Create: `tests/test_dashboard.py` — unittest suite (parsers + scanner + HTTP smoke).
- Create: `tests/__init__.py` — empty, makes `tests` discoverable.
- Modify: `scripts/validate.sh` — add a section asserting the new files exist + `dashboard.sh` executable + `dashboard.py` is valid Python.
- Modify: `README.md` — one Roadmap/usage line (final task).

The scanner is the heart and gets the most tests. Parsers are split out as pure functions so they test in isolation. The HTTP layer stays thin.

---

### Task 1: Frontmatter and task-checkbox parsers

**Files:**
- Create: `dashboard.py`
- Test: `tests/test_dashboard.py`
- Create: `tests/__init__.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `parse_frontmatter(text: str) -> dict[str, str]` — returns the flat `key: value` scalars from a leading `---`-fenced YAML block; `{}` if no frontmatter. Values are stripped strings; quotes trimmed. Does not parse nested/list YAML.
  - `parse_tasks(text: str) -> dict` — returns `{"done": int, "total": int}` counting GFM checkbox lines. A line matches `^\s*[-*]\s+\[( |x|X)\]\s` ; `done` counts `x`/`X`.

- [ ] **Step 1: Create the tests package marker**

```bash
mkdir -p tests
: > tests/__init__.py
```

- [ ] **Step 2: Write the failing tests**

Create `tests/test_dashboard.py`:

```python
import unittest
import dashboard as d


class TestParseFrontmatter(unittest.TestCase):
    def test_reads_scalars(self):
        text = "---\nslug: active-corrections\nstatus: active\ncreated: 2026-06-03\n---\n# body\n"
        self.assertEqual(
            d.parse_frontmatter(text),
            {"slug": "active-corrections", "status": "active", "created": "2026-06-03"},
        )

    def test_trims_quotes(self):
        self.assertEqual(d.parse_frontmatter('---\nverdict: "PASS"\n---\n'), {"verdict": "PASS"})

    def test_no_frontmatter_returns_empty(self):
        self.assertEqual(d.parse_frontmatter("# just a heading\n"), {})

    def test_empty_string_returns_empty(self):
        self.assertEqual(d.parse_frontmatter(""), {})


class TestParseTasks(unittest.TestCase):
    def test_counts_done_and_total(self):
        text = "- [ ] one\n- [x] two\n- [X] three\nplain line\n"
        self.assertEqual(d.parse_tasks(text), {"done": 2, "total": 3})

    def test_no_tasks(self):
        self.assertEqual(d.parse_tasks("no checkboxes here\n"), {"done": 0, "total": 0})

    def test_indented_and_asterisk_bullets(self):
        text = "  - [ ] indented\n* [x] star\n"
        self.assertEqual(d.parse_tasks(text), {"done": 1, "total": 2})


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `python3 -m unittest tests.test_dashboard -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'dashboard'` (or AttributeError once the file exists but functions don't).

- [ ] **Step 4: Write minimal implementation**

Create `dashboard.py` with just the parsers (rest of the file added in later tasks):

```python
#!/usr/bin/env python3
"""spec-kit-compound pipeline dashboard — read-only localhost view of the chain."""

import re

_TASK_RE = re.compile(r"^\s*[-*]\s+\[( |x|X)\]\s")


def parse_frontmatter(text):
    """Return flat key:value scalars from a leading ---fenced YAML block, or {}."""
    if not text.startswith("---"):
        return {}
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    out = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key:
            out[key] = val
    return out


def parse_tasks(text):
    """Count GFM checkbox lines: {'done': n_checked, 'total': n_boxes}."""
    done = total = 0
    for line in text.splitlines():
        m = _TASK_RE.match(line)
        if m:
            total += 1
            if m.group(1) in ("x", "X"):
                done += 1
    return {"done": done, "total": total}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python3 -m unittest tests.test_dashboard -v`
Expected: PASS — all 7 tests.

- [ ] **Step 6: Commit**

```bash
git add dashboard.py tests/__init__.py tests/test_dashboard.py
git commit -m "feat(dashboard): frontmatter + task-checkbox parsers"
```

---

### Task 2: The filesystem scanner

**Files:**
- Modify: `dashboard.py` (add `scan_state` + helpers)
- Test: `tests/test_dashboard.py` (add scanner tests)

**Interfaces:**
- Consumes: `parse_frontmatter`, `parse_tasks` from Task 1.
- Produces:
  - `STAGES: list[str]` — the 9 stage names in order.
  - `scan_state(repo_root: str) -> dict` — pure function, filesystem in, dict out, matching the spec's data model. Top-level keys: `scanned_at` (str, ISO; injected by caller — see note), `repo` (str, basename of repo_root), `stages` (== STAGES), `features` (list), `orphan_specs` (list), `compound` (dict with `adr`/`corrections`/`patterns` filename lists).
  - Each feature: `{slug, status, created, spec_dir, stages: {<name>: {state, ...}}, files}`. The `tasks` stage dict carries `done`/`total`; the `intentguard` stage dict carries `verdict` (str or null).
  - Helper `_normalize(name: str) -> str` — lowercases and strips a leading `NNN-` numeric-prefix for the slug↔dir join.

Note on `scanned_at`: keep `scan_state` deterministic for testing by accepting an optional `now=None` arg; when `None`, it omits/0-fills the timestamp. The HTTP layer (Task 4) passes the real time. So signature is `scan_state(repo_root, now=None)`.

- [ ] **Step 1: Write the failing scanner tests**

Add to `tests/test_dashboard.py` (append before the `if __name__` block):

```python
import os
import tempfile
import shutil


def _write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(text)


class TestScanState(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_empty_repo(self):
        state = d.scan_state(self.root)
        self.assertEqual(state["features"], [])
        self.assertEqual(state["orphan_specs"], [])
        self.assertEqual(state["stages"], d.STAGES)
        self.assertEqual(state["compound"], {"adr": [], "corrections": [], "patterns": []})

    def test_intent_only_feature(self):
        _write(os.path.join(self.root, "docs/intents/foo.intent.md"),
               "---\nslug: foo\nstatus: active\ncreated: 2026-01-01\n---\n# Intent\n")
        state = d.scan_state(self.root)
        self.assertEqual(len(state["features"]), 1)
        feat = state["features"][0]
        self.assertEqual(feat["slug"], "foo")
        self.assertEqual(feat["status"], "active")
        self.assertEqual(feat["stages"]["intent"]["state"], "done")
        self.assertEqual(feat["stages"]["expectations"]["state"], "current")
        self.assertEqual(feat["stages"]["specify"]["state"], "pending")
        self.assertIsNone(feat["spec_dir"])

    def test_join_strips_numeric_prefix_and_counts_tasks(self):
        _write(os.path.join(self.root, "docs/intents/bar.intent.md"),
               "---\nslug: bar\ncreated: 2026-01-01\n---\n")
        _write(os.path.join(self.root, "docs/expectations/bar.expectations.md"), "x\n")
        _write(os.path.join(self.root, "specs/007-bar/spec.md"), "spec\n")
        _write(os.path.join(self.root, "specs/007-bar/plan.md"), "plan\n")
        _write(os.path.join(self.root, "specs/007-bar/tasks.md"), "- [x] a\n- [ ] b\n")
        feat = d.scan_state(self.root)["features"][0]
        self.assertEqual(feat["spec_dir"], "specs/007-bar")
        self.assertEqual(feat["stages"]["tasks"]["state"], "current")
        self.assertEqual(feat["stages"]["tasks"]["done"], 1)
        self.assertEqual(feat["stages"]["tasks"]["total"], 2)
        self.assertEqual(feat["stages"]["plan"]["state"], "done")

    def test_implement_done_when_tasks_complete(self):
        _write(os.path.join(self.root, "docs/intents/baz.intent.md"), "---\nslug: baz\n---\n")
        _write(os.path.join(self.root, "specs/baz/tasks.md"), "- [x] a\n- [x] b\n")
        feat = d.scan_state(self.root)["features"][0]
        self.assertEqual(feat["stages"]["implement"]["state"], "done")

    def test_intentguard_blocked_sets_blocked_state(self):
        _write(os.path.join(self.root, "docs/intents/q.intent.md"), "---\nslug: q\n---\n")
        _write(os.path.join(self.root, "docs/intents/q.intentguard.md"),
               "---\nverdict: BLOCKED\n---\n# report\n")
        feat = d.scan_state(self.root)["features"][0]
        self.assertEqual(feat["stages"]["intentguard"]["verdict"], "BLOCKED")
        self.assertEqual(feat["stages"]["intentguard"]["state"], "blocked")

    def test_orphan_spec_dir(self):
        _write(os.path.join(self.root, "specs/050-stray/spec.md"), "x\n")
        state = d.scan_state(self.root)
        self.assertEqual(state["features"], [])
        self.assertEqual(len(state["orphan_specs"]), 1)
        self.assertEqual(state["orphan_specs"][0]["dir"], "specs/050-stray")
        self.assertIn("specify", state["orphan_specs"][0]["stages_present"])

    def test_malformed_frontmatter_does_not_crash(self):
        _write(os.path.join(self.root, "docs/intents/bad.intent.md"), "no frontmatter at all\n")
        feat = d.scan_state(self.root)["features"][0]
        self.assertEqual(feat["slug"], "bad")  # slug falls back to filename
        self.assertEqual(feat["stages"]["intent"]["state"], "done")

    def test_compound_store_listed(self):
        _write(os.path.join(self.root, "docs/compound/adr/001-x.md"), "x\n")
        _write(os.path.join(self.root, "docs/compound/corrections/2026-01-01-y.md"), "y\n")
        state = d.scan_state(self.root)
        self.assertEqual(state["compound"]["adr"], ["001-x.md"])
        self.assertEqual(state["compound"]["corrections"], ["2026-01-01-y.md"])
        self.assertEqual(state["compound"]["patterns"], [])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m unittest tests.test_dashboard -v`
Expected: FAIL — `AttributeError: module 'dashboard' has no attribute 'scan_state'` (and `STAGES`).

- [ ] **Step 3: Write minimal implementation**

Add to `dashboard.py` (after the parsers, before any `main`):

```python
import os
import glob

STAGES = [
    "intent", "expectations", "specify", "plan",
    "tasks", "gapfill", "implement", "intentguard", "writeback",
]

# String the gapfill command stamps into tasks.md for appended tests.
_GAPFILL_MARKER = "speckit-compound-gapfill"


def _read(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""


def _normalize(name):
    """Lowercase, strip a leading NNN- numeric prefix (spec-dir convention)."""
    base = os.path.basename(name).lower()
    return re.sub(r"^\d+-", "", base)


def _stage_present(spec_dir_abs, filename):
    return os.path.isfile(os.path.join(spec_dir_abs, filename))


def _compute_states(stages):
    """Given a dict of stage->{'state': 'done'|'pending', ...} with done/pending only,
    mark the first pending stage as 'current'. Blocked is applied separately."""
    seen_pending = False
    for name in STAGES:
        st = stages[name]
        if st["state"] == "done":
            continue
        if not seen_pending:
            st["state"] = "current"
            seen_pending = True
    return stages


def scan_state(repo_root, now=None):
    repo_root = os.path.abspath(repo_root)
    intents = sorted(glob.glob(os.path.join(repo_root, "docs/intents/*.intent.md")))

    # Map normalized spec-dir name -> relative spec dir path.
    spec_dirs = {}
    specs_root = os.path.join(repo_root, "specs")
    if os.path.isdir(specs_root):
        for entry in sorted(os.listdir(specs_root)):
            full = os.path.join(specs_root, entry)
            if os.path.isdir(full):
                spec_dirs[_normalize(entry)] = os.path.relpath(full, repo_root)

    features = []
    matched_dirs = set()
    for intent_path in intents:
        fname = os.path.basename(intent_path)
        slug_from_file = fname[: -len(".intent.md")]
        fm = parse_frontmatter(_read(intent_path))
        slug = fm.get("slug") or slug_from_file

        rel_spec = spec_dirs.get(_normalize(slug))
        if rel_spec:
            matched_dirs.add(_normalize(slug))
        spec_abs = os.path.join(repo_root, rel_spec) if rel_spec else None

        exp_path = os.path.join(repo_root, "docs/expectations", slug + ".expectations.md")
        guard_path = os.path.join(repo_root, "docs/intents", slug + ".intentguard.md")

        tasks_text = _read(os.path.join(spec_abs, "tasks.md")) if spec_abs else ""
        task_counts = parse_tasks(tasks_text)

        guard_verdict = None
        if os.path.isfile(guard_path):
            guard_verdict = parse_frontmatter(_read(guard_path)).get("verdict")

        files = [os.path.relpath(intent_path, repo_root)]
        if os.path.isfile(exp_path):
            files.append(os.path.relpath(exp_path, repo_root))
        if os.path.isfile(guard_path):
            files.append(os.path.relpath(guard_path, repo_root))

        def done(flag):
            return {"state": "done"} if flag else {"state": "pending"}

        stages = {
            "intent": done(True),
            "expectations": done(os.path.isfile(exp_path)),
            "specify": done(bool(spec_abs) and _stage_present(spec_abs, "spec.md")),
            "plan": done(bool(spec_abs) and _stage_present(spec_abs, "plan.md")),
            "tasks": done(bool(spec_abs) and _stage_present(spec_abs, "tasks.md")),
            "gapfill": done(_GAPFILL_MARKER in tasks_text),
            "implement": done(task_counts["total"] > 0 and task_counts["done"] == task_counts["total"]),
            "intentguard": done(os.path.isfile(guard_path)),
            "writeback": done(False),  # set below
        }
        stages["tasks"].update(done=task_counts["done"], total=task_counts["total"])
        stages["intentguard"]["verdict"] = guard_verdict

        _compute_states(stages)
        if guard_verdict == "BLOCKED":
            stages["intentguard"]["state"] = "blocked"

        features.append({
            "slug": slug,
            "status": fm.get("status", ""),
            "created": fm.get("created", ""),
            "spec_dir": rel_spec,
            "stages": stages,
            "files": files,
        })

    orphan_specs = []
    for norm, rel in spec_dirs.items():
        if norm in matched_dirs:
            continue
        abs_dir = os.path.join(repo_root, rel)
        present = [
            stage for stage, fn in (("specify", "spec.md"), ("plan", "plan.md"), ("tasks", "tasks.md"))
            if os.path.isfile(os.path.join(abs_dir, fn))
        ]
        orphan_specs.append({"dir": rel, "stages_present": present})

    def _ls(sub):
        p = os.path.join(repo_root, "docs/compound", sub)
        return sorted(os.path.basename(x) for x in glob.glob(os.path.join(p, "*.md"))) if os.path.isdir(p) else []

    return {
        "scanned_at": now or "",
        "repo": os.path.basename(repo_root),
        "stages": STAGES,
        "features": features,
        "orphan_specs": orphan_specs,
        "compound": {"adr": _ls("adr"), "corrections": _ls("corrections"), "patterns": _ls("patterns")},
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m unittest tests.test_dashboard -v`
Expected: PASS — all parser + scanner tests.

- [ ] **Step 5: Commit**

```bash
git add dashboard.py tests/test_dashboard.py
git commit -m "feat(dashboard): filesystem scanner with slug<->spec-dir join"
```

---

### Task 3: The inlined HTML page

**Files:**
- Modify: `dashboard.py` (add `PAGE_HTML` constant)
- Test: `tests/test_dashboard.py` (assert the constant is well-formed and self-contained)

**Interfaces:**
- Consumes: nothing at runtime (served verbatim).
- Produces: `PAGE_HTML: str` — a complete HTML document. It fetches `/api/state` on load and every 3000ms, renders the header, the lane legend (`01 INTENT … 09 WRITEBACK`), one row per feature with a rail of 9 nodes colored by state (`done`=green, `current`=accent-pulse, `pending`=hollow, `blocked`=red), the `done/total` task count and verdict on the `tasks`/`intentguard` nodes, the orphan-specs panel, and the compound-store panel. Respects `prefers-reduced-motion`. Self-contained except Google Fonts `@import` (with a system fallback stack).

- [ ] **Step 1: Write the failing test**

Add to `tests/test_dashboard.py`:

```python
class TestPageHtml(unittest.TestCase):
    def test_is_self_contained_document(self):
        html = d.PAGE_HTML
        self.assertIn("<!doctype html", html.lower())
        self.assertIn("/api/state", html)            # polls the endpoint
        self.assertIn("01", html)                    # lane numbering present
        self.assertIn("prefers-reduced-motion", html)  # motion gate present
        # No external scripts/styles beyond the font import.
        self.assertNotIn("<script src=", html)
        self.assertNotIn('rel="stylesheet"', html)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_dashboard.TestPageHtml -v`
Expected: FAIL — `AttributeError: module 'dashboard' has no attribute 'PAGE_HTML'`.

- [ ] **Step 3: Write the implementation**

Add to `dashboard.py` (a module-level string). Use the spec's palette and type system. Build the full page:

```python
PAGE_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>spec-kit-compound · pipeline</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;700&family=Inter:wght@400;500&family=JetBrains+Mono:wght@400;500&display=swap');
:root{
  --ground:#0E1116; --surface:#161B22; --text:#E6EDF3; --muted:#7D8590;
  --done:#3FB950; --progress:#D29922; --blocked:#F85149; --accent:#388BFD;
  --display:'Space Grotesk',system-ui,sans-serif;
  --body:'Inter',system-ui,sans-serif;
  --mono:'JetBrains Mono',ui-monospace,Menlo,monospace;
}
*{box-sizing:border-box}
body{margin:0;background:var(--ground);color:var(--text);font-family:var(--body);
  font-size:14px;line-height:1.5;-webkit-font-smoothing:antialiased}
header{display:flex;justify-content:space-between;align-items:baseline;
  padding:20px 28px;border-bottom:1px solid #21262d}
h1{font-family:var(--display);font-weight:700;font-size:18px;margin:0;letter-spacing:-.01em}
h1 .sub{color:var(--muted);font-weight:500}
.live{font-family:var(--mono);font-size:12px;color:var(--muted)}
.live .dot{color:var(--done)}
.live.stale .dot{color:var(--muted)}
main{padding:20px 28px;max-width:1200px}
.legend,.row{display:grid;grid-template-columns:200px 1fr;gap:16px;align-items:center}
.legend{padding:0 0 12px;color:var(--muted);font-family:var(--mono);font-size:11px}
.lanes{display:flex;justify-content:space-between}
.lane{flex:1;text-align:center;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.rowscroll{overflow-x:auto}
.row{padding:14px 0;border-top:1px solid #21262d;cursor:pointer}
.slug{font-family:var(--display);font-weight:500}
.rail{display:flex;align-items:center;min-width:520px}
.node{width:14px;height:14px;border-radius:50%;border:2px solid var(--muted);
  background:transparent;flex:none}
.seg{flex:1;height:2px;background:#30363d;border-top:1px dashed #30363d}
.node.done{background:var(--done);border-color:var(--done)}
.seg.done{background:var(--done);border-top:2px solid var(--done)}
.node.current{border-color:var(--accent);box-shadow:0 0 0 3px rgba(56,139,253,.25);
  animation:pulse 1.8s ease-in-out infinite}
.node.blocked{background:var(--blocked);border-color:var(--blocked)}
.meta{font-family:var(--mono);font-size:12px;color:var(--muted);margin-top:6px}
.meta .blocked{color:var(--blocked)} .meta .review{color:var(--progress)} .meta .pass{color:var(--done)}
.panel{margin-top:28px;padding:16px;background:var(--surface);border:1px solid #21262d;border-radius:8px}
.panel h2{font-family:var(--display);font-size:13px;margin:0 0 10px;letter-spacing:.02em;color:var(--muted);text-transform:uppercase}
.files{font-family:var(--mono);font-size:12px;color:var(--muted);display:none;margin-top:10px}
.row.open .files{display:block}
.empty{color:var(--muted);text-align:center;padding:60px 0;font-family:var(--mono)}
@keyframes pulse{0%,100%{box-shadow:0 0 0 3px rgba(56,139,253,.25)}50%{box-shadow:0 0 0 6px rgba(56,139,253,.08)}}
@media (prefers-reduced-motion: reduce){.node.current{animation:none}}
</style>
</head>
<body>
<header>
  <h1>spec-kit-compound <span class="sub">· pipeline</span></h1>
  <div class="live" id="live"><span class="dot">●</span> connecting…</div>
</header>
<main id="main"><div class="empty">Loading…</div></main>
<script>
const STAGE_LABELS = ["INTENT","EXP","SPEC","PLAN","TASKS","GAP","IMPL","GUARD","WB"];
function esc(s){return String(s).replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));}

function railHtml(feat){
  let h = '<div class="rail">';
  feat.stages_order.forEach((name,i)=>{
    const st = feat.stages[name];
    const cls = st.state==="done"?"done":st.state==="current"?"current":st.state==="blocked"?"blocked":"";
    h += `<span class="node ${cls}" title="${esc(name)}: ${esc(st.state)}"></span>`;
    if(i < feat.stages_order.length-1){
      const segDone = st.state==="done" ? "done":"";
      h += `<span class="seg ${segDone}"></span>`;
    }
  });
  return h + '</div>';
}

function metaHtml(feat){
  const t = feat.stages.tasks;
  const g = feat.stages.intentguard;
  let bits = [];
  if(t.total>0) bits.push(`tasks ${t.done}/${t.total}`);
  if(g.verdict){
    const k = g.verdict==="PASS"?"pass":g.verdict==="BLOCKED"?"blocked":"review";
    bits.push(`<span class="${k}">GUARD ${esc(g.verdict)}</span>`);
  }
  if(!feat.spec_dir) bits.push("no spec dir matched");
  return bits.join(" · ");
}

function render(state){
  const main = document.getElementById("main");
  if(!state.features.length && !state.orphan_specs.length){
    main.innerHTML = '<div class="empty">No features yet. Run <b>/speckit-compound-intent</b> to start the chain.</div>';
    return;
  }
  let h = '<div class="legend"><div></div><div class="rowscroll"><div class="lanes" style="min-width:520px">';
  STAGE_LABELS.forEach((l,i)=>{ h += `<div class="lane">${String(i+1).padStart(2,"0")} ${l}</div>`; });
  h += '</div></div></div>';

  state.features.forEach(feat=>{
    feat.stages_order = state.stages;
    h += `<div class="row" tabindex="0">
      <div><div class="slug">${esc(feat.slug)}</div><div class="meta">${metaHtml(feat)}</div></div>
      <div class="rowscroll">${railHtml(feat)}</div>
      <div class="files">${feat.files.map(esc).join("<br>")}</div>
    </div>`;
  });

  if(state.orphan_specs.length){
    h += '<div class="panel"><h2>Orphan spec dirs (no intent)</h2>';
    state.orphan_specs.forEach(o=>{ h += `<div class="meta">${esc(o.dir)} — ${o.stages_present.map(esc).join(", ")||"empty"}</div>`; });
    h += '</div>';
  }

  const c = state.compound;
  h += `<div class="panel"><h2>Compound store</h2>
    <div class="meta">ADRs ${c.adr.length} · Corrections ${c.corrections.length} · Patterns ${c.patterns.length}</div>
    <div class="meta">${[...c.adr,...c.corrections,...c.patterns].map(esc).join("  ·  ")||"empty — grows from your first writeback"}</div>
  </div>`;

  main.innerHTML = h;
  main.querySelectorAll(".row").forEach(r=>{
    const toggle=()=>r.classList.toggle("open");
    r.addEventListener("click",toggle);
    r.addEventListener("keydown",e=>{if(e.key==="Enter"){e.preventDefault();toggle();}});
  });
}

async function poll(){
  const live = document.getElementById("live");
  try{
    const r = await fetch("/api/state",{cache:"no-store"});
    const state = await r.json();
    render(state);
    live.classList.remove("stale");
    live.innerHTML = `<span class="dot">●</span> live · scanned ${esc((state.scanned_at||"").slice(11,19)||"now")}`;
  }catch(e){
    live.classList.add("stale");
    live.innerHTML = '<span class="dot">●</span> disconnected — is dashboard.py running?';
  }
}
poll();
setInterval(poll, 3000);
</script>
</body>
</html>
"""
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_dashboard.TestPageHtml -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add dashboard.py tests/test_dashboard.py
git commit -m "feat(dashboard): inlined HTML page — rail visual, live poll"
```

---

### Task 4: HTTP server + main()

**Files:**
- Modify: `dashboard.py` (add `Handler`, `find_repo_root`, `main`, `__main__` guard)
- Test: `tests/test_dashboard.py` (HTTP smoke test against an ephemeral port)

**Interfaces:**
- Consumes: `scan_state`, `PAGE_HTML`.
- Produces:
  - `find_repo_root(start: str) -> str` — walk up from `start` until a dir containing `extension.yml` is found; fall back to `start`.
  - `make_handler(repo_root) -> type` — returns a `BaseHTTPRequestHandler` subclass bound to `repo_root`, serving `GET /` (the page) and `GET /api/state` (JSON via `scan_state(repo_root, now=<iso>)`); any other path → 404. Silences the default request logging.
  - `main(argv=None) -> int` — parses `--port` (default 8787) and `--open`; binds `127.0.0.1`; on `OSError` (port busy) tries the next 10 ports; prints the chosen URL; serves forever.

- [ ] **Step 1: Write the failing HTTP smoke test**

Add to `tests/test_dashboard.py`:

```python
import threading
import urllib.request
import json
from http.server import HTTPServer


class TestHttp(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        _write(os.path.join(self.root, "docs/intents/foo.intent.md"), "---\nslug: foo\n---\n")
        handler = d.make_handler(self.root)
        self.httpd = HTTPServer(("127.0.0.1", 0), handler)
        self.port = self.httpd.server_address[1]
        self.t = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.t.start()

    def tearDown(self):
        self.httpd.shutdown()
        shutil.rmtree(self.root, ignore_errors=True)

    def _get(self, path):
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}{path}") as r:
            return r.status, r.read().decode(), r.headers.get_content_type()

    def test_root_serves_html(self):
        status, body, ctype = self._get("/")
        self.assertEqual(status, 200)
        self.assertEqual(ctype, "text/html")
        self.assertIn("<!doctype html", body.lower())

    def test_api_state_serves_json(self):
        status, body, ctype = self._get("/api/state")
        self.assertEqual(status, 200)
        self.assertEqual(ctype, "application/json")
        state = json.loads(body)
        self.assertEqual(state["features"][0]["slug"], "foo")
        self.assertTrue(state["scanned_at"])  # real timestamp injected

    def test_unknown_path_404(self):
        with self.assertRaises(urllib.error.HTTPError) as cm:
            self._get("/nope")
        self.assertEqual(cm.exception.code, 404)
```

Also add `import urllib.error` near the top of the test file.

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_dashboard.TestHttp -v`
Expected: FAIL — `AttributeError: module 'dashboard' has no attribute 'make_handler'`.

- [ ] **Step 3: Write the implementation**

Add to `dashboard.py`:

```python
import json
import argparse
import datetime
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer


def find_repo_root(start):
    cur = os.path.abspath(start)
    while True:
        if os.path.isfile(os.path.join(cur, "extension.yml")):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            return os.path.abspath(start)
        cur = parent


def make_handler(repo_root):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):  # silence default stderr logging
            pass

        def _send(self, status, body, ctype):
            data = body.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if self.path == "/" or self.path == "/index.html":
                self._send(200, PAGE_HTML, "text/html")
            elif self.path == "/api/state":
                now = datetime.datetime.now().isoformat(timespec="seconds")
                self._send(200, json.dumps(scan_state(repo_root, now=now)), "application/json")
            else:
                self._send(404, "not found", "text/plain")

    return Handler


def main(argv=None):
    ap = argparse.ArgumentParser(description="spec-kit-compound pipeline dashboard")
    ap.add_argument("--port", type=int, default=8787)
    ap.add_argument("--open", action="store_true", help="open the dashboard in a browser")
    args = ap.parse_args(argv)

    repo_root = find_repo_root(os.path.dirname(os.path.abspath(__file__)))
    handler = make_handler(repo_root)

    httpd = None
    for port in range(args.port, args.port + 11):
        try:
            httpd = HTTPServer(("127.0.0.1", port), handler)
            break
        except OSError:
            continue
    if httpd is None:
        print("error: no free port in range", flush=True)
        return 1

    url = f"http://127.0.0.1:{httpd.server_address[1]}/"
    print(f"spec-kit-compound dashboard → {url}  (scanning {repo_root})", flush=True)
    if args.open:
        webbrowser.open(url)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nbye", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run the full suite to verify it passes**

Run: `python3 -m unittest discover tests -v`
Expected: PASS — all parser, scanner, page, and HTTP tests.

- [ ] **Step 5: Commit**

```bash
git add dashboard.py tests/test_dashboard.py
git commit -m "feat(dashboard): http server + main entrypoint"
```

---

### Task 5: Bash launcher

**Files:**
- Create: `scripts/dashboard.sh`

**Interfaces:**
- Consumes: `dashboard.py`.
- Produces: an executable launcher that finds `dashboard.py` relative to itself and runs it with `python3`, forwarding all args.

- [ ] **Step 1: Write the launcher**

Create `scripts/dashboard.sh`:

```bash
#!/bin/bash
# scripts/dashboard.sh
#
# Launch the spec-kit-compound pipeline dashboard (read-only localhost view).
#
#   ./scripts/dashboard.sh              # serve on the default port
#   ./scripts/dashboard.sh --open       # ...and open a browser
#   ./scripts/dashboard.sh --port 9000  # pick a port
#
set -eu

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

if ! command -v python3 >/dev/null 2>&1; then
  echo "error: python3 not found on PATH" >&2
  exit 1
fi

exec python3 "$REPO_ROOT/dashboard.py" "$@"
```

- [ ] **Step 2: Make it executable**

```bash
chmod +x scripts/dashboard.sh
```

- [ ] **Step 3: Verify shellcheck is clean**

Run: `shellcheck scripts/dashboard.sh`
Expected: no output, exit 0. (If `shellcheck` is not installed, skip — `scripts/validate.sh` does not run it; CI does.)

- [ ] **Step 4: Smoke-test the launcher boots and serves**

Run:
```bash
./scripts/dashboard.sh --port 8799 &
SERVER_PID=$!
sleep 1
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8799/api/state
kill "$SERVER_PID"
```
Expected: prints `200`.

- [ ] **Step 5: Commit**

```bash
git add scripts/dashboard.sh
git commit -m "feat(dashboard): bash launcher"
```

---

### Task 6: Wire into validate.sh + README

**Files:**
- Modify: `scripts/validate.sh` (add a dashboard section before the Summary)
- Modify: `README.md` (one usage/roadmap line)

**Interfaces:**
- Consumes: all prior tasks' files.
- Produces: validation coverage + user-facing docs. No new code interface.

- [ ] **Step 1: Add a dashboard section to validate.sh**

In `scripts/validate.sh`, insert this block immediately before the `# Summary` separator comment (the `# ────…` line above `echo ""; echo "─────…"`):

```bash
# ─────────────────────────────────────────────────────────────────
# Section 8: dashboard (v0.4)
# ─────────────────────────────────────────────────────────────────
echo ""
echo "Dashboard"

if [ -f dashboard.py ]; then
  if python3 -c "import ast,sys; ast.parse(open('dashboard.py').read())" 2>/dev/null; then
    pass "dashboard.py is valid Python"
  else
    fail "dashboard.py does not parse as valid Python"
  fi
else
  fail "dashboard.py missing"
fi

if [ -x scripts/dashboard.sh ]; then
  pass "scripts/dashboard.sh is executable"
else
  fail "scripts/dashboard.sh missing or not executable"
fi

if [ -f tests/test_dashboard.py ]; then
  if python3 -m unittest discover -s tests >/dev/null 2>&1; then
    pass "dashboard test suite passes"
  else
    fail "dashboard test suite fails (python3 -m unittest discover -s tests)"
  fi
else
  fail "tests/test_dashboard.py missing"
fi
```

- [ ] **Step 2: Run validate.sh to confirm it passes**

Run: `./scripts/validate.sh`
Expected: ends with `All N checks passed ✓`, exit 0.

- [ ] **Step 3: Add a usage line to README**

In `README.md`, under the Roadmap section (or add a short "## Dashboard" subsection near the end), add:

```markdown
## Dashboard (read-only)

A local web view of the chain — which features exist and how far each has advanced through the 9 stages, live task counts, and intentguard verdicts. Pure read-only filesystem scan; no chain commands run.

    ./scripts/dashboard.sh --open

Serves on `http://127.0.0.1:8787` and re-scans every few seconds, so it updates as you run the chain.
```

- [ ] **Step 4: Commit**

```bash
git add scripts/validate.sh README.md
git commit -m "chore(dashboard): wire into validate.sh + document usage"
```

---

## Self-Review

**Spec coverage** — checked each spec section against a task:
- §4 Architecture (dashboard.py + dashboard.sh, two routes) → Tasks 1–5.
- §5 Data model (exact JSON shape) → Task 2 scanner + tests asserting each field.
- §6 Stage detection (all 9 done-signals + join + orphans) → Task 2, one test per signal class.
- §7 Visual (palette, type, rail signature, numbering, motion gate, empty/disconnected states) → Task 3 `PAGE_HTML` + test.
- §8 Error handling (per-file defensive read `_read`, 127.0.0.1 bind, port retry, no path from request) → Task 2 `_read` + malformed-frontmatter test; Task 4 `main` port retry + fixed routes.
- §9 Testing (scanner/parser units + HTTP smoke + validate.sh + shellcheck) → Tasks 1–6.

**Placeholder scan** — every code step shows complete code; no TODO/TBD; no "add error handling" hand-waves (the defensive `_read` and per-file fallback are concrete).

**Type consistency** — names match across tasks: `parse_frontmatter`, `parse_tasks`, `STAGES`, `scan_state(repo_root, now=None)`, `make_handler(repo_root)`, `find_repo_root`, `PAGE_HTML`, `main`. The feature dict keys used in `PAGE_HTML` JS (`slug`, `spec_dir`, `files`, `stages`, `stages.tasks.done/total`, `stages.intentguard.verdict`) match the scanner's output, and `stages_order` is assigned client-side from `state.stages` (Task 3 JS) — consistent with the scanner emitting `stages` as the ordered name list.

One gap found and fixed during review: the scanner's per-stage dicts initially had no ordering for the client rail; resolved by emitting the top-level `stages` list (the ordered names) and having the JS read it as `stages_order`. Consistent now.
```
