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


import os
import tempfile
import shutil
import threading
import urllib.request
import urllib.error
import json
from http.server import HTTPServer


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
        # tasks.md exists -> tasks stage done; current advances to the next gap (gapfill)
        self.assertEqual(feat["stages"]["tasks"]["state"], "done")
        self.assertEqual(feat["stages"]["gapfill"]["state"], "current")
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


class TestPageHtml(unittest.TestCase):
    def test_is_self_contained_document(self):
        html = d.PAGE_HTML
        self.assertIn("<!doctype html", html.lower())
        self.assertIn("/api/state", html)              # polls the endpoint
        self.assertIn("01", html)                      # lane numbering present
        self.assertIn("prefers-reduced-motion", html)  # motion gate present
        self.assertNotIn("<script src=", html)
        self.assertNotIn('rel="stylesheet"', html)


if __name__ == "__main__":
    unittest.main()
