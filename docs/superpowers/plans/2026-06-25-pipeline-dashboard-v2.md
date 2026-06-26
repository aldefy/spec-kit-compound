# Pipeline Dashboard v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a confidence layer to the read-only dashboard — inline intent/expectations content, an intentguard-driven drift panel, a live flowchart + static arch diagram, and Claude Code token usage from local transcripts.

**Architecture:** All additions are pure parsing helpers in `dashboard.py` plus extra panels in the existing inlined `PAGE_HTML`. The scanner gains body-section parsers, an intentguard-report parser, and a transcript token reader; the page gains expandable content, a drift panel, a per-feature flowchart, an About/arch panel, and a header token total. Read-only and dependency-free throughout — no Mermaid, no CDN, no chain-command changes.

**Tech Stack:** Python 3 stdlib (`re`, `os`, `glob`, `json`, `unittest`); vanilla HTML/CSS/SVG inlined in the server.

## Global Constraints

- **No third-party dependencies.** Python stdlib only; diagrams are hand-built SVG/CSS — no Mermaid, no CDN script, no external stylesheet beyond the existing Google Fonts `@import`.
- **Read-only.** No new writes; no changes to the 8 `/speckit-compound-*` command files.
- **Server binds `127.0.0.1` only.** (unchanged from v1)
- **All parsing is defensive.** Missing file/section → `""`/`[]`; malformed line → skipped, never raised. A broken panel shows "unavailable", never blanks the page or 500s `/api/state`.
- **Token math:** `billable = input + output + cache_creation`; `cache_read` reported separately, not summed into billable.
- **Token attribution is best-effort and labeled `~`.** The header total is exact; per-feature is a hint only.
- **All v1 tests must keep passing.** Run `python3 -m unittest discover tests` green at every commit.

---

## File Structure

- Modify: `dashboard.py` — add `extract_goal`, `extract_section`, `parse_intentguard`, `scan_tokens`; extend `scan_state` (new `home` param, merge `content`/`drift`/`tokens`/`stage_descriptions`); extend `PAGE_HTML` (content blocks, drift panel, flowchart, About/arch SVG, header token total). Single file stays cohesive — the whole tool is still small enough to hold in context.
- Modify: `tests/test_dashboard.py` — new test classes for each helper + integration + page anchors.
- No README change needed (v1's Dashboard section already covers usage; the new panels are self-describing).

Order: pure parsers first (Tasks 1–3, each independently testable), then token reader (Task 4), then scanner integration (Task 5), then the page (Task 6). Parsers land before the scanner that calls them.

---

### Task 1: Body-section content parsers

**Files:**
- Modify: `dashboard.py` (add `extract_goal`, `extract_section`)
- Test: `tests/test_dashboard.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `extract_goal(text: str) -> str` — text after the first `# Intent:` marker on its line, stripped; `""` if absent.
  - `extract_section(text: str, header: str) -> list[str]` — the non-empty list/`-`/`*` lines under a `## <header>` heading, until the next `## ` heading or EOF. Each returned line has its leading bullet (`- ` / `* `) stripped and is `.strip()`ed. Non-bullet prose lines under the heading are skipped. `[]` if the header is absent.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_dashboard.py` (before the final `if __name__`):

```python
class TestContentParsers(unittest.TestCase):
    INTENT = (
        "---\nslug: x\n---\n"
        "# Intent: An agent cannot repeat a documented mistake.\n\n"
        "## Constraints\n\n"
        "- **C1**: p95 < 250ms\n"
        "- **C2**: false-positive < 5%\n\n"
        "## Failure conditions\n\n"
        "- **F1**: Build fails\n\n"
        "## Out of scope\n\n"
        "- Multi-CLI support\n"
    )

    def test_extract_goal(self):
        self.assertEqual(
            d.extract_goal(self.INTENT),
            "An agent cannot repeat a documented mistake.",
        )

    def test_extract_goal_absent(self):
        self.assertEqual(d.extract_goal("# Heading only\n"), "")

    def test_extract_section_constraints(self):
        self.assertEqual(
            d.extract_section(self.INTENT, "Constraints"),
            ["**C1**: p95 < 250ms", "**C2**: false-positive < 5%"],
        )

    def test_extract_section_stops_at_next_heading(self):
        self.assertEqual(d.extract_section(self.INTENT, "Failure conditions"),
                         ["**F1**: Build fails"])

    def test_extract_section_absent(self):
        self.assertEqual(d.extract_section(self.INTENT, "Nonexistent"), [])

    def test_extract_section_star_bullets(self):
        self.assertEqual(d.extract_section("## Positive scenarios\n* E1 thing\n", "Positive scenarios"),
                         ["E1 thing"])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m unittest tests.test_dashboard.TestContentParsers -v`
Expected: FAIL — `AttributeError: module 'dashboard' has no attribute 'extract_goal'`.

- [ ] **Step 3: Write minimal implementation**

Add to `dashboard.py` (after `parse_tasks`, before `STAGES`):

```python
_GOAL_RE = re.compile(r"^#\s*Intent:\s*(.+?)\s*$", re.MULTILINE)
_BULLET_RE = re.compile(r"^\s*[-*]\s+(.*\S)\s*$")


def extract_goal(text):
    """Return the text after the first '# Intent:' marker, or ''."""
    m = _GOAL_RE.search(text)
    return m.group(1).strip() if m else ""


def extract_section(text, header):
    """Return stripped bullet lines under '## <header>' until the next '## ', or []."""
    out = []
    in_section = False
    for line in text.splitlines():
        if line.startswith("## "):
            if in_section:
                break
            in_section = line[3:].strip() == header
            continue
        if in_section:
            m = _BULLET_RE.match(line)
            if m:
                out.append(m.group(1).strip())
    return out
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m unittest tests.test_dashboard.TestContentParsers -v`
Expected: PASS — all 6.

- [ ] **Step 5: Commit**

```bash
git add dashboard.py tests/test_dashboard.py
git commit -m "feat(dashboard): intent/expectations body-section parsers"
```

---

### Task 2: Intentguard drift parser

**Files:**
- Modify: `dashboard.py` (add `parse_intentguard`)
- Test: `tests/test_dashboard.py`

**Interfaces:**
- Consumes: `parse_frontmatter` (v1).
- Produces:
  - `parse_intentguard(text: str) -> dict` → `{"verdict": str|None, "drift": list[dict]}`. `verdict` from frontmatter `verdict:` (or `None`). `drift` = one entry per body bullet line under a `## L3a …` / `## L3b …` / `## L3d …` heading whose text contains `BLOCKED` or `REVIEW` (case-insensitive). Each entry: `{"level": "L3a"|"L3b"|"L3d", "kind": "out-of-scope"|"constraint"|"expectation", "text": <stripped line>, "severity": "blocked"|"review"}`. PASS-only lines are omitted. Empty text or no L3 sections → `{"verdict": None or fm value, "drift": []}`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_dashboard.py`:

```python
class TestParseIntentguard(unittest.TestCase):
    REPORT = (
        "---\nverdict: BLOCKED\n---\n"
        "# Intent Guard Report\n\n"
        "## Verdict: **BLOCKED**\n\n"
        "## L3a — Out-of-scope check\n"
        "- Multi-CLI support: matched at `foo.sh:3` -> BLOCKED\n"
        "- Server-side enforcement: PASS\n\n"
        "## L3b — Constraint check\n"
        "- **C1**: REVIEW NEEDED -- can't tell from diff\n\n"
        "## L3d — Expectations satisfaction\n"
        "- **E1**: PASS -- demonstrated\n"
        "- **E2**: BLOCKED -- scenario regressed\n"
    )

    def test_verdict_and_drift(self):
        r = d.parse_intentguard(self.REPORT)
        self.assertEqual(r["verdict"], "BLOCKED")
        texts = [(x["level"], x["kind"], x["severity"]) for x in r["drift"]]
        self.assertIn(("L3a", "out-of-scope", "blocked"), texts)
        self.assertIn(("L3b", "constraint", "review"), texts)
        self.assertIn(("L3d", "expectation", "blocked"), texts)
        self.assertEqual(len(r["drift"]), 3)  # PASS lines excluded

    def test_pass_report_has_no_drift(self):
        report = ("---\nverdict: PASS\n---\n## L3a — Out-of-scope check\n- item: PASS\n")
        r = d.parse_intentguard(report)
        self.assertEqual(r["verdict"], "PASS")
        self.assertEqual(r["drift"], [])

    def test_empty(self):
        self.assertEqual(d.parse_intentguard(""), {"verdict": None, "drift": []})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m unittest tests.test_dashboard.TestParseIntentguard -v`
Expected: FAIL — `AttributeError: ... 'parse_intentguard'`.

- [ ] **Step 3: Write minimal implementation**

Add to `dashboard.py` (after `extract_section`):

```python
_L3_KINDS = {"L3a": "out-of-scope", "L3b": "constraint", "L3d": "expectation"}


def parse_intentguard(text):
    """Return {'verdict': str|None, 'drift': [...]} from an intentguard report."""
    verdict = parse_frontmatter(text).get("verdict")
    drift = []
    current = None  # active L3 level, or None
    for line in text.splitlines():
        if line.startswith("## "):
            head = line[3:].strip()
            current = None
            for level in _L3_KINDS:
                if head.startswith(level):
                    current = level
                    break
            continue
        if not current:
            continue
        m = _BULLET_RE.match(line)
        if not m:
            continue
        body = m.group(1).strip()
        upper = body.upper()
        if "BLOCKED" in upper:
            sev = "blocked"
        elif "REVIEW" in upper:
            sev = "review"
        else:
            continue  # PASS / clean line — not drift
        drift.append({"level": current, "kind": _L3_KINDS[current], "text": body, "severity": sev})
    return {"verdict": verdict, "drift": drift}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m unittest tests.test_dashboard.TestParseIntentguard -v`
Expected: PASS — all 3.

- [ ] **Step 5: Commit**

```bash
git add dashboard.py tests/test_dashboard.py
git commit -m "feat(dashboard): intentguard drift parser"
```

---

### Task 3: Token transcript reader

**Files:**
- Modify: `dashboard.py` (add `scan_tokens`)
- Test: `tests/test_dashboard.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `scan_tokens(home: str, repo_root: str) -> dict` → the shape in spec §6. `available: bool`; `total` and per-session `tokens` with keys `input/output/cache_creation/cache_read/billable`. Reads `<home>/.claude/projects/<slug>/*.jsonl` where `<slug>` is `repo_root` abspath with every `os.sep` and `.` replaced by `-` (matches Claude Code's dir naming: leading `/` → leading `-`). A usage block is found at `line["message"]["usage"]` or `line["usage"]`. Per-line failures are skipped. Missing dir → `{"available": False, "total": {...zeros...}, "sessions": []}`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_dashboard.py`:

```python
def _slug_for(root):
    # mirror Claude Code's project-dir slugging used by scan_tokens
    return d._project_slug(root)


class TestScanTokens(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp()
        self.repo = "/Users/x/StudioProjects/demo"
        self.proj = os.path.join(self.home, ".claude", "projects", _slug_for(self.repo))
        os.makedirs(self.proj, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.home, ignore_errors=True)

    def _line(self, sid, inp, out, cc=0, cr=0, ts="2026-06-25T10:00:00Z"):
        return json.dumps({
            "sessionId": sid, "timestamp": ts,
            "message": {"usage": {
                "input_tokens": inp, "output_tokens": out,
                "cache_creation_input_tokens": cc, "cache_read_input_tokens": cr,
            }},
        }) + "\n"

    def test_sums_sessions_and_total(self):
        with open(os.path.join(self.proj, "s.jsonl"), "w") as f:
            f.write(self._line("A", 100, 10, cc=5, cr=50))
            f.write(self._line("A", 200, 20, cc=0, cr=0))
            f.write("garbage not json\n")            # skipped
            f.write(json.dumps({"type": "nousage"}) + "\n")  # skipped
        tok = d.scan_tokens(self.home, self.repo)
        self.assertTrue(tok["available"])
        self.assertEqual(tok["total"]["input"], 300)
        self.assertEqual(tok["total"]["output"], 30)
        self.assertEqual(tok["total"]["cache_creation"], 5)
        self.assertEqual(tok["total"]["cache_read"], 50)
        self.assertEqual(tok["total"]["billable"], 335)  # 300+30+5
        self.assertEqual(len(tok["sessions"]), 1)
        self.assertEqual(tok["sessions"][0]["session"], "A")

    def test_missing_dir_unavailable(self):
        tok = d.scan_tokens(self.home, "/no/such/repo")
        self.assertFalse(tok["available"])
        self.assertEqual(tok["total"]["billable"], 0)
        self.assertEqual(tok["sessions"], [])

    def test_top_level_usage_also_read(self):
        with open(os.path.join(self.proj, "t.jsonl"), "w") as f:
            f.write(json.dumps({"sessionId": "B", "timestamp": "2026-06-25T11:00:00Z",
                                "usage": {"input_tokens": 7, "output_tokens": 3}}) + "\n")
        tok = d.scan_tokens(self.home, self.repo)
        self.assertEqual(tok["total"]["billable"], 10)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m unittest tests.test_dashboard.TestScanTokens -v`
Expected: FAIL — `AttributeError: ... '_project_slug'` / `'scan_tokens'`.

- [ ] **Step 3: Write minimal implementation**

Add to `dashboard.py` (after `scan_tokens`'s dependencies; place near the other scanners, the `import json` from v1's server section must be available — move `import json` to the top of the file if it is currently only imported in the server block):

First ensure `import json` is at module top (with the other imports). Then add:

```python
def _project_slug(repo_root):
    """Claude Code project-dir slug: abspath with os.sep and '.' replaced by '-'."""
    abspath = os.path.abspath(repo_root)
    return abspath.replace(os.sep, "-").replace(".", "-")


def _empty_tokens():
    z = {"input": 0, "output": 0, "cache_creation": 0, "cache_read": 0, "billable": 0}
    return {"available": False, "total": dict(z), "sessions": []}


def _add_usage(acc, u):
    inp = u.get("input_tokens", 0) or 0
    out = u.get("output_tokens", 0) or 0
    cc = u.get("cache_creation_input_tokens", 0) or 0
    cr = u.get("cache_read_input_tokens", 0) or 0
    acc["input"] += inp
    acc["output"] += out
    acc["cache_creation"] += cc
    acc["cache_read"] += cr
    acc["billable"] += inp + out + cc


def scan_tokens(home, repo_root):
    proj = os.path.join(home, ".claude", "projects", _project_slug(repo_root))
    if not os.path.isdir(proj):
        return _empty_tokens()

    total = {"input": 0, "output": 0, "cache_creation": 0, "cache_read": 0, "billable": 0}
    sessions = {}  # sid -> {"session","first","last","tokens"}
    for path in sorted(glob.glob(os.path.join(proj, "*.jsonl"))):
        try:
            with open(path, encoding="utf-8") as f:
                for line in f:
                    try:
                        o = json.loads(line)
                    except (ValueError, TypeError):
                        continue
                    u = (o.get("message") or {}).get("usage") or o.get("usage")
                    if not isinstance(u, dict):
                        continue
                    sid = o.get("sessionId", "unknown")
                    ts = o.get("timestamp", "")
                    s = sessions.setdefault(sid, {
                        "session": sid, "first": ts, "last": ts,
                        "tokens": {"input": 0, "output": 0, "cache_creation": 0, "cache_read": 0, "billable": 0},
                    })
                    if ts and (not s["first"] or ts < s["first"]):
                        s["first"] = ts
                    if ts and ts > s["last"]:
                        s["last"] = ts
                    _add_usage(s["tokens"], u)
                    _add_usage(total, u)
        except OSError:
            continue

    return {
        "available": True,
        "total": total,
        "sessions": sorted(sessions.values(), key=lambda x: x["first"]),
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m unittest tests.test_dashboard.TestScanTokens -v`
Expected: PASS — all 3.

- [ ] **Step 5: Commit**

```bash
git add dashboard.py tests/test_dashboard.py
git commit -m "feat(dashboard): token usage reader from Claude Code transcripts"
```

---

### Task 4: Scanner integration (content + drift + tokens + descriptions)

**Files:**
- Modify: `dashboard.py` (`scan_state` signature + merges; add `STAGE_DESCRIPTIONS`)
- Test: `tests/test_dashboard.py`

**Interfaces:**
- Consumes: `extract_goal`, `extract_section`, `parse_intentguard`, `scan_tokens` (Tasks 1–3).
- Produces: `scan_state(repo_root, now=None, home=None)` — new optional `home` (defaults to `os.path.expanduser("~")`). Each feature gains `content` (keys: `goal`, `constraints`, `failures`, `out_of_scope`, `expectations_positive`, `expectations_edge`) and `stages.intentguard.drift` (list). Top-level gains `tokens` (== `scan_tokens(home, repo_root)`) and `stage_descriptions` (== `STAGE_DESCRIPTIONS`). All v1 keys unchanged.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_dashboard.py` (inside the existing `TestScanState` class or a new one; here a new class to keep home-injection isolated):

```python
class TestScanStateV2(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.home = tempfile.mkdtemp()  # empty -> tokens unavailable, fine

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)
        shutil.rmtree(self.home, ignore_errors=True)

    def test_content_and_drift_merged(self):
        _write(os.path.join(self.root, "docs/intents/k.intent.md"),
               "---\nslug: k\n---\n# Intent: Do the thing.\n\n## Constraints\n- **C1**: be fast\n")
        _write(os.path.join(self.root, "docs/expectations/k.expectations.md"),
               "## Positive scenarios\n- **E1**: it works\n")
        _write(os.path.join(self.root, "docs/intents/k.intentguard.md"),
               "---\nverdict: REVIEW NEEDED\n---\n## L3b — Constraint check\n- **C1**: REVIEW -- unclear\n")
        feat = d.scan_state(self.root, home=self.home)["features"][0]
        self.assertEqual(feat["content"]["goal"], "Do the thing.")
        self.assertEqual(feat["content"]["constraints"], ["**C1**: be fast"])
        self.assertEqual(feat["content"]["expectations_positive"], ["**E1**: it works"])
        self.assertEqual(feat["stages"]["intentguard"]["drift"][0]["severity"], "review")

    def test_tokens_and_descriptions_present(self):
        state = d.scan_state(self.root, home=self.home)
        self.assertIn("tokens", state)
        self.assertFalse(state["tokens"]["available"])  # empty home
        self.assertEqual(state["stage_descriptions"]["intent"],
                         "goal + constraints + failure conditions")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m unittest tests.test_dashboard.TestScanStateV2 -v`
Expected: FAIL — `KeyError: 'content'` (and `'tokens'`).

- [ ] **Step 3: Write the implementation**

In `dashboard.py`, add the descriptions constant after `STAGES`:

```python
STAGE_DESCRIPTIONS = {
    "intent": "goal + constraints + failure conditions",
    "expectations": "success + edge scenarios (validator-only)",
    "specify": "spec.md from intent",
    "plan": "design + architecture",
    "tasks": "dependency-ordered task list",
    "gapfill": "add missing constraint/failure/OOS tests",
    "implement": "build (tasks checked off)",
    "intentguard": "L3 validation -> PASS / REVIEW / BLOCKED",
    "writeback": "persist ADRs / corrections / patterns",
}
```

Change the `scan_state` signature:

```python
def scan_state(repo_root, now=None, home=None):
    repo_root = os.path.abspath(repo_root)
    if home is None:
        home = os.path.expanduser("~")
```

Inside the per-feature loop, after `guard_verdict` is computed and `exp_path` is known, build content and drift. Replace the block that sets `stages["intentguard"]["verdict"] = guard_verdict` with content+drift wiring:

```python
        intent_text = _read(intent_path)
        exp_text = _read(exp_path) if os.path.isfile(exp_path) else ""
        guard_text = _read(guard_path) if os.path.isfile(guard_path) else ""
        guard_parsed = parse_intentguard(guard_text) if guard_text else {"verdict": None, "drift": []}

        content = {
            "goal": extract_goal(intent_text),
            "constraints": extract_section(intent_text, "Constraints"),
            "failures": extract_section(intent_text, "Failure conditions"),
            "out_of_scope": extract_section(intent_text, "Out of scope"),
            "expectations_positive": extract_section(exp_text, "Positive scenarios"),
            "expectations_edge": extract_section(exp_text, "Edge / negative scenarios"),
        }
```

Then where the feature stages dict is finalized, set:

```python
        stages["intentguard"]["verdict"] = guard_parsed["verdict"] or guard_verdict
        stages["intentguard"]["drift"] = guard_parsed["drift"]
```

(Note: `guard_verdict` from v1 already reads the frontmatter; `guard_parsed["verdict"]` is the same value — keep `guard_parsed` authoritative, fall back to `guard_verdict`.)

Add `content` to the appended feature dict:

```python
        features.append({
            "slug": slug,
            "status": fm.get("status", ""),
            "created": fm.get("created", ""),
            "spec_dir": rel_spec,
            "stages": stages,
            "content": content,
            "files": files,
        })
```

Finally, add `tokens` and `stage_descriptions` to the returned top-level dict:

```python
    return {
        "scanned_at": now or "",
        "repo": os.path.basename(repo_root),
        "stages": STAGES,
        "stage_descriptions": STAGE_DESCRIPTIONS,
        "features": features,
        "orphan_specs": orphan_specs,
        "compound": {"adr": _ls("adr"), "corrections": _ls("corrections"), "patterns": _ls("patterns")},
        "tokens": scan_tokens(home, repo_root),
    }
```

- [ ] **Step 4: Run the full suite to verify it passes**

Run: `python3 -m unittest discover tests -v`
Expected: PASS — all v1 + v2 tests. (The blocked-verdict v1 test still passes because `guard_parsed["verdict"]` returns the same frontmatter value.)

- [ ] **Step 5: Commit**

```bash
git add dashboard.py tests/test_dashboard.py
git commit -m "feat(dashboard): merge content, drift, tokens, descriptions into scan_state"
```

---

### Task 5: Page — content blocks, drift panel, flowchart, About/arch, token total

**Files:**
- Modify: `dashboard.py` (`PAGE_HTML`)
- Test: `tests/test_dashboard.py` (anchor + self-contained assertions)

**Interfaces:**
- Consumes: the v2 `/api/state` shape (Task 4).
- Produces: an updated `PAGE_HTML` that renders, in each expanded row: the goal, collapsible constraints/failures/expectations, a per-feature flowchart (9 labeled stage boxes lit by state), and a drift panel (verdict badge + itemized findings). Adds a header token total and an About panel (toggle) holding the static arch SVG. Stays self-contained (no `<script src=`, no external stylesheet beyond the font import).

- [ ] **Step 1: Write the failing test**

Add to `tests/test_dashboard.py` (extend `TestPageHtml`):

```python
class TestPageHtmlV2(unittest.TestCase):
    def test_new_panels_present_and_self_contained(self):
        html = d.PAGE_HTML
        for anchor in ["flowchart", "drift", "About", "tokens", "renderContent"]:
            self.assertIn(anchor, html)
        self.assertNotIn("<script src=", html)
        self.assertNotIn('rel="stylesheet"', html)
        self.assertNotIn("mermaid", html.lower())  # no CDN diagram lib
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_dashboard.TestPageHtmlV2 -v`
Expected: FAIL — anchors like `flowchart` / `drift` not yet in `PAGE_HTML`.

- [ ] **Step 3: Write the implementation**

Edit `PAGE_HTML` in `dashboard.py`. Three edits:

**(3a) Add CSS** — inside the `<style>` block, before its closing `</style>`, add:

```css
.content{display:none;margin-top:12px}
.row.open .content{display:block}
.content h3{font-family:var(--display);font-size:11px;text-transform:uppercase;letter-spacing:.04em;color:var(--muted);margin:14px 0 6px}
.content ul{margin:0;padding-left:18px} .content li{font-family:var(--mono);font-size:12px;color:#c9d1d9;margin:2px 0}
.goal{font-family:var(--display);font-size:15px;color:var(--text);margin-top:4px}
.flow{display:flex;gap:0;align-items:stretch;min-width:760px;margin:8px 0}
.fstep{flex:1;text-align:center;padding:8px 6px;border-radius:6px;border:1px solid #30363d;background:#0d1117;position:relative}
.fstep .n{font-family:var(--mono);font-size:11px;color:var(--muted)}
.fstep .lbl{font-family:var(--display);font-size:11px;margin:2px 0}
.fstep .desc{font-size:10px;color:var(--muted);line-height:1.3}
.fstep.done{border-color:var(--done)} .fstep.done .lbl{color:var(--done)}
.fstep.current{border-color:var(--accent);box-shadow:0 0 0 2px rgba(56,139,253,.2)} .fstep.current .lbl{color:var(--accent)}
.fstep.blocked{border-color:var(--blocked)} .fstep.blocked .lbl{color:var(--blocked)}
.farrow{align-self:center;color:#30363d;padding:0 4px;font-family:var(--mono)}
.drift{margin-top:14px;padding:12px;border:1px solid #30363d;border-radius:6px;background:#0d1117}
.drift .badge{font-family:var(--mono);font-size:11px;padding:2px 8px;border-radius:10px}
.badge.blocked{background:rgba(248,81,73,.15);color:var(--blocked)}
.badge.review{background:rgba(210,153,34,.15);color:var(--progress)}
.badge.pass{background:rgba(63,185,80,.15);color:var(--done)}
.drift li.blocked{color:var(--blocked)} .drift li.review{color:var(--progress)}
.about{display:none;padding:16px 28px;border-bottom:1px solid #21262d;color:var(--muted)}
.about.open{display:block}
.about svg{max-width:100%}
.toktotal{cursor:pointer}
```

**(3b) Add the About panel + token total in the header.** Replace the existing `<header>...</header>` block with:

```html
<header>
  <h1>spec-kit-compound <span class="sub">· pipeline</span></h1>
  <div style="display:flex;gap:18px;align-items:baseline">
    <div class="live toktotal" id="tokens" title="Click for About / architecture">⌁ —</div>
    <div class="live" id="live"><span class="dot">●</span> connecting…</div>
  </div>
</header>
<section class="about" id="about" aria-label="About">
  <svg viewBox="0 0 760 90" role="img" aria-label="architecture">
    <defs><marker id="ah" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
      <path d="M0,0 L6,3 L0,6 Z" fill="#7D8590"/></marker></defs>
    <g font-family="JetBrains Mono, monospace" font-size="11" fill="#E6EDF3">
      <rect x="4" y="28" width="170" height="34" rx="5" fill="#161B22" stroke="#30363d"/>
      <text x="14" y="42">filesystem</text><text x="14" y="56" fill="#7D8590">docs/ · specs/ · ~/.claude</text>
      <line x1="178" y1="45" x2="244" y2="45" stroke="#7D8590" marker-end="url(#ah)"/>
      <rect x="248" y="28" width="150" height="34" rx="5" fill="#161B22" stroke="#30363d"/>
      <text x="258" y="49">scan_state()</text>
      <line x1="402" y1="45" x2="468" y2="45" stroke="#7D8590" marker-end="url(#ah)"/>
      <rect x="472" y="28" width="130" height="34" rx="5" fill="#161B22" stroke="#30363d"/>
      <text x="482" y="49">/api/state</text>
      <line x1="606" y1="45" x2="672" y2="45" stroke="#7D8590" marker-end="url(#ah)"/>
      <rect x="676" y="28" width="80" height="34" rx="5" fill="#161B22" stroke="#388BFD"/>
      <text x="686" y="42" fill="#388BFD">page</text><text x="686" y="56" fill="#7D8590">3s poll</text>
    </g>
  </svg>
  <div style="margin-top:8px;font-family:var(--mono);font-size:12px">Read-only · no dependencies · 127.0.0.1 · never runs chain commands.</div>
</section>
```

**(3c) Add the JS renderers and wire them.** In the `<script>`, add these functions before `render(state)`:

```javascript
function flowHtml(feat, state){
  let h = '<div class="rowscroll"><div class="flow">';
  state.stages.forEach((name,i)=>{
    const st = feat.stages[name];
    const cls = st.state==="done"?"done":st.state==="current"?"current":st.state==="blocked"?"blocked":"";
    const desc = (state.stage_descriptions||{})[name] || "";
    h += `<div class="fstep ${cls}"><div class="n">${String(i+1).padStart(2,"0")}</div>
      <div class="lbl">${esc(name)}</div><div class="desc">${esc(desc)}</div></div>`;
    if(i<state.stages.length-1) h += '<div class="farrow">→</div>';
  });
  return h + '</div></div>';
}

function listBlock(title, items){
  if(!items || !items.length) return "";
  return `<h3>${esc(title)}</h3><ul>${items.map(x=>`<li>${esc(x)}</li>`).join("")}</ul>`;
}

function driftHtml(feat){
  const g = feat.stages.intentguard;
  if(!g.verdict && (!g.drift || !g.drift.length)) return "";
  const vk = g.verdict==="PASS"?"pass":g.verdict==="BLOCKED"?"blocked":"review";
  let h = `<div class="drift"><span class="badge ${vk}">${esc(g.verdict||"not validated")}</span>`;
  if(g.drift && g.drift.length){
    h += `<ul style="margin-top:8px;padding-left:18px">` +
      g.drift.map(x=>`<li class="${esc(x.severity)}"><b>${esc(x.level)}</b> ${esc(x.text)}</li>`).join("") + `</ul>`;
  }
  return h + '</div>';
}

function renderContent(feat, state){
  const c = feat.content || {};
  let h = '<div class="content">';
  if(c.goal) h += `<div class="goal">${esc(c.goal)}</div>`;
  h += flowHtml(feat, state);
  h += listBlock("Constraints", c.constraints);
  h += listBlock("Failure conditions", c.failures);
  h += listBlock("Out of scope", c.out_of_scope);
  h += listBlock("Expectations — positive", c.expectations_positive);
  h += listBlock("Expectations — edge", c.expectations_edge);
  h += driftHtml(feat);
  h += `<h3>Files</h3><ul>${(feat.files||[]).map(f=>`<li>${esc(f)}</li>`).join("")}</ul>`;
  return h + '</div>';
}
```

Then, in `render(state)`, change the feature-row template to call `renderContent` instead of the bare `.files` div. Replace the `state.features.forEach` body's row string with:

```javascript
    h += `<div class="row" tabindex="0">
      <div><div class="slug">${esc(feat.slug)}</div><div class="meta">${metaHtml(feat)}</div></div>
      <div class="rowscroll">${railHtml(feat)}</div>
      ${renderContent(feat, state)}
    </div>`;
```

(Remove the old `<div class="files">…</div>` line from that template — files now render inside `renderContent`.)

In `poll()`, after `render(state)`, update the token total:

```javascript
    const t = state.tokens || {};
    const tokEl = document.getElementById("tokens");
    if(t.available){
      const b = t.total.billable;
      const human = b>=1e6 ? (b/1e6).toFixed(1)+"M" : b>=1e3 ? (b/1e3).toFixed(0)+"k" : String(b);
      tokEl.textContent = `⌁ ${human} tokens · ${t.sessions.length} sessions`;
    } else {
      tokEl.textContent = "⌁ no local transcripts";
    }
```

Finally, wire the About toggle — add once after `poll(); setInterval(...)`:

```javascript
document.getElementById("tokens").addEventListener("click",()=>{
  document.getElementById("about").classList.toggle("open");
});
```

- [ ] **Step 4: Run the full suite to verify it passes**

Run: `python3 -m unittest discover tests -v`
Expected: PASS — all tests, including `TestPageHtmlV2`.

- [ ] **Step 5: Live smoke test against the real repo**

Run:
```bash
./scripts/dashboard.sh --port 8802 &
PID=$!
sleep 1
curl -s http://127.0.0.1:8802/api/state | python3 -c "import sys,json; s=json.load(sys.stdin); f=s['features'][0]; print('goal:', f['content']['goal']); print('constraints:', len(f['content']['constraints'])); print('tokens available:', s['tokens']['available'], '· billable:', s['tokens']['total']['billable'])"
kill $PID 2>/dev/null; wait $PID 2>/dev/null
```
Expected: prints the real `active-corrections` goal, a non-zero constraints count, and `tokens available: True` with a non-zero billable total (this repo has transcripts).

- [ ] **Step 6: Commit**

```bash
git add dashboard.py tests/test_dashboard.py
git commit -m "feat(dashboard): content blocks, flowchart, drift panel, arch + token total"
```

---

### Task 6: Validate + final verification

**Files:**
- Modify: none (validate.sh already runs the test suite via the v1 dashboard section)

**Interfaces:**
- Consumes: all prior tasks.
- Produces: a green validation run.

- [ ] **Step 1: Run the validation script**

Run: `./scripts/validate.sh`
Expected: the Dashboard section shows `✓ dashboard.py is valid Python`, `✓ scripts/dashboard.sh is executable`, `✓ dashboard test suite passes`. (The pre-existing dotted-slash-ref failure in README roadmap is unrelated to this work and out of scope.)

- [ ] **Step 2: Run the full test suite once more**

Run: `python3 -m unittest discover tests -v`
Expected: all tests PASS.

- [ ] **Step 3: Confirm no accidental command-file edits (read-only invariant)**

Run: `git diff --name-only main...HEAD -- commands/ extension.yml`
Expected: empty output (no chain-command or manifest changes).

---

## Self-Review

**Spec coverage** — each v2 spec section maps to a task:
- §3 Content parsing (`extract_goal`, `extract_section`) → Task 1.
- §4 Drift (`parse_intentguard`) → Task 2.
- §6 Tokens (`scan_tokens`, `_project_slug`, billable math) → Task 3.
- §5 Diagrams (live flowchart + static arch SVG) → Task 5 (3a/3c flowchart, 3b arch).
- §7 Data model delta (`home` param, `content`, `drift`, `tokens`, `stage_descriptions`) → Task 4.
- §8 Error handling (defensive parses, token dir-missing, per-line skip) → Tasks 1–3 implementations + their missing/garbled tests.
- §9 Testing → every task's test steps; §the read-only invariant → Task 6 Step 3.

**Placeholder scan** — every code step shows complete code; no TODO/TBD; no "handle edge cases" hand-waves (each defensive path has a concrete test: missing section, empty report, garbled jsonl line, missing token dir).

**Type consistency** — names align across tasks: `extract_goal`, `extract_section`, `parse_intentguard`, `_project_slug`, `scan_tokens`, `STAGE_DESCRIPTIONS`, `scan_state(repo_root, now=None, home=None)`. Feature dict keys used in `PAGE_HTML` JS (`content.goal`, `content.constraints`, `content.failures`, `content.out_of_scope`, `content.expectations_positive`, `content.expectations_edge`, `stages.intentguard.drift[].{level,text,severity}`, top-level `stage_descriptions`, `tokens.available`, `tokens.total.billable`, `tokens.sessions`) all match the scanner output defined in Tasks 3–4. `_BULLET_RE` is defined in Task 1 and reused in Task 2 — Task 2 depends on Task 1 landing first (noted in its Consumes).

One consistency fix during review: Task 2 reuses `_BULLET_RE` from Task 1, so Task 1 must precede Task 2 — the task order already enforces this, and Task 2's Consumes line now names the dependency.
