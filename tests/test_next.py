"""Black-box tests for scripts/compound_next.py (v0.9 /speckit-compound-help)."""
import json
import os
import subprocess
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NEXT = os.path.join(REPO, "scripts", "compound_next.py")


def write(root, rel, body):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(body)


def intent(root, slug, status="active", size="full"):
    write(root, f"docs/intents/{slug}.intent.md",
          f"---\nslug: {slug}\nstatus: {status}\nsize: {size}\n---\n# Intent: {slug}\n")


class NextTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        subprocess.run(["git", "init", "-q", self.root], check=True)
        os.makedirs(os.path.join(self.root, ".specify"))

    def tearDown(self):
        self.tmp.cleanup()

    def run_next(self):
        out = subprocess.run([sys.executable, "-I", NEXT, "--root", self.root, "--json"],
                             capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stderr)
        return json.loads(out.stdout)

    def commands(self):
        return [s["command"] for s in self.run_next()["next"]]

    def test_no_store_says_load(self):
        self.assertEqual(self.commands()[0], "/speckit-compound-load")

    def test_empty_store_says_intent(self):
        os.makedirs(os.path.join(self.root, "docs/compound/adr"))
        self.assertEqual(self.commands(), ["/speckit-compound-intent"])

    def test_fresh_full_intent_says_expectations(self):
        os.makedirs(os.path.join(self.root, "docs/compound/adr"))
        intent(self.root, "dark-mode")
        steps = self.run_next()["next"]
        self.assertEqual(steps[0]["command"], "/speckit-compound-expectations")
        self.assertEqual(steps[0]["feature"], "dark-mode")

    def test_spec_kit_stages_map_to_core_commands(self):
        os.makedirs(os.path.join(self.root, "docs/compound/adr"))
        intent(self.root, "dark-mode")
        write(self.root, "docs/expectations/dark-mode.expectations.md", "x\n")
        write(self.root, "specs/001-dark-mode/spec.md", "x\n")
        self.assertEqual(self.commands()[0], "/speckit-plan")

    def test_blocked_intentguard_comes_first(self):
        os.makedirs(os.path.join(self.root, "docs/compound/adr"))
        intent(self.root, "dark-mode")
        write(self.root, "docs/intents/dark-mode.intentguard.md", "---\nverdict: BLOCKED\n---\n")
        step = self.run_next()["next"][0]
        self.assertEqual(step["command"], "/speckit-compound-intentguard")
        self.assertIn("BLOCKED", step["why"])

    def test_planverify_drift_says_replan(self):
        os.makedirs(os.path.join(self.root, "docs/compound/adr"))
        intent(self.root, "dark-mode")
        write(self.root, "docs/intents/dark-mode.planverify.md", "---\nverdict: BLOCKED_DRIFT\n---\n")
        step = self.run_next()["next"][0]
        self.assertEqual(step["command"], "/speckit-compound-planverify")
        self.assertIn("BLOCKED_DRIFT", step["why"])

    def test_lite_intent_says_implement_then_guard(self):
        os.makedirs(os.path.join(self.root, "docs/compound/adr"))
        intent(self.root, "fix-typo", size="lite")
        step = self.run_next()["next"][0]
        self.assertEqual(step["command"], "/speckit-compound-intentguard")
        self.assertIn("lite", step["why"])

    def test_completed_features_are_ignored(self):
        os.makedirs(os.path.join(self.root, "docs/compound/adr"))
        intent(self.root, "old", status="completed")
        self.assertEqual(self.commands(), ["/speckit-compound-intent"])

    def test_store_findings_suggest_refresh(self):
        os.makedirs(os.path.join(self.root, "docs/compound/adr"))
        write(self.root, "docs/compound/corrections/2026-01-01-old.md", "# no guard\n")
        cmds = self.commands()
        self.assertIn("/speckit-compound-writeback refresh", cmds)

    def test_text_output_names_the_command(self):
        os.makedirs(os.path.join(self.root, "docs/compound/adr"))
        out = subprocess.run([sys.executable, "-I", NEXT, "--root", self.root],
                             capture_output=True, text=True)
        self.assertEqual(out.returncode, 0)
        self.assertIn("/speckit-compound-intent", out.stdout)


if __name__ == "__main__":
    unittest.main()
