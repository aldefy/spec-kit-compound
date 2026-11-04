"""Black-box tests for scripts/compound_refresh.py (v0.8 store refresh scanner).

Each test builds a throwaway git repo with a compound store, runs the scanner
with --json, and asserts on the finding kinds it reports.
"""
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCANNER = os.path.join(REPO, "scripts", "compound_refresh.py")


def write(root, rel, body):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(textwrap.dedent(body).lstrip("\n"))


def correction(slug, paths, match, rule="Do not do X.", extra=""):
    paths_yaml = "\n".join(f'  - "{p}"' for p in paths)
    return f"""---
slug: {slug}
paths:
{paths_yaml}
match: '{match}'
rule: "{rule}"
context: "Past mistake."
{extra}---

# Correction: {slug}
"""


class RefreshScanTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        subprocess.run(["git", "init", "-q", self.root], check=True)
        for sub in ("adr", "corrections", "patterns"):
            os.makedirs(os.path.join(self.root, "docs/compound", sub))

    def tearDown(self):
        self.tmp.cleanup()

    def scan(self):
        subprocess.run(["git", "-C", self.root, "add", "-A"], check=True)
        out = subprocess.run(
            [sys.executable, "-I", SCANNER, "--root", self.root, "--json"],
            capture_output=True, text=True,
        )
        self.assertEqual(out.returncode, 0, out.stderr)
        return json.loads(out.stdout)["findings"]

    def kinds(self, findings, file_suffix=None):
        return sorted(
            f["kind"] for f in findings
            if file_suffix is None or f["file"].endswith(file_suffix)
        )

    # ── clean store ─────────────────────────────────────────────
    def test_empty_store_has_no_findings(self):
        self.assertEqual(self.scan(), [])

    def test_missing_store_is_not_an_error(self):
        subprocess.run(["rm", "-rf", os.path.join(self.root, "docs")], check=True)
        self.assertEqual(self.scan(), [])

    def test_healthy_correction_has_no_findings(self):
        write(self.root, "src/app.css", "body { color: red; }\n")
        write(self.root, "docs/compound/corrections/2026-01-01-no-filter.md",
              correction("2026-01-01-no-filter", ["**/*.css"], "filter:[[:space:]]*brightness"))
        self.assertEqual(self.scan(), [])

    # ── R: no-guard ─────────────────────────────────────────────
    def test_correction_without_frontmatter_is_no_guard(self):
        write(self.root, "docs/compound/corrections/2026-01-01-old.md",
              "# Correction: old\n\n## Derived rule\nDo not.\n")
        self.assertEqual(self.kinds(self.scan()), ["no-guard"])

    def test_unenforceable_reason_suppresses_no_guard(self):
        write(self.root, "docs/compound/corrections/2026-01-01-judgement.md", """
            ---
            slug: 2026-01-01-judgement
            unenforceable_reason: "Naming judgement; no syntactic form to match."
            ---
            # Correction: judgement
        """)
        self.assertEqual(self.scan(), [])

    def test_guarded_by_test_only_is_a_guard(self):
        # rung 1 without a hook regex: seen in a real store (upsert clobbers)
        write(self.root, "tests/DbTest.kt", "x\n")
        write(self.root, "docs/compound/corrections/2026-01-01-upsert.md", """
            ---
            slug: 2026-01-01-upsert
            guarded_by: tests/DbTest.kt::upsertPreservesStatus
            ---
            # Correction: upsert
        """)
        self.assertEqual(self.scan(), [])

    def test_guarded_by_missing_file_is_stale_guard(self):
        write(self.root, "docs/compound/corrections/2026-01-01-upsert.md", """
            ---
            slug: 2026-01-01-upsert
            guarded_by: tests/GoneTest.kt::x
            ---
            # Correction: upsert
        """)
        found = self.scan()
        self.assertEqual(self.kinds(found), ["stale-guard"])
        self.assertIn("tests/GoneTest.kt", found[0]["detail"])

    # ── R: dup-rule ─────────────────────────────────────────────
    def test_duplicate_match_is_flagged_on_both(self):
        write(self.root, "src/a.css", "a{}\n")
        for slug in ("2026-01-01-a", "2026-02-01-b"):
            write(self.root, f"docs/compound/corrections/{slug}.md",
                  correction(slug, ["**/*.css"], "filter:[[:space:]]*invert", rule=f"rule {slug}"))
        self.assertEqual(self.kinds(self.scan()), ["dup-rule", "dup-rule"])

    # ── R: dead-paths ───────────────────────────────────────────
    def test_paths_matching_no_tracked_file_is_dead(self):
        write(self.root, "src/app.ts", "x\n")
        write(self.root, "docs/compound/corrections/2026-01-01-scss.md",
              correction("2026-01-01-scss", ["**/*.scss"], "@extend"))
        self.assertEqual(self.kinds(self.scan()), ["dead-paths"])

    # ── R: fires-on-tree ────────────────────────────────────────
    def test_match_on_current_tree_is_flagged(self):
        write(self.root, "src/app.css", "img { filter: brightness(0.8); }\n")
        write(self.root, "docs/compound/corrections/2026-01-01-no-filter.md",
              correction("2026-01-01-no-filter", ["**/*.css"], "filter:[[:space:]]*brightness"))
        found = self.scan()
        self.assertEqual(self.kinds(found), ["fires-on-tree"])
        self.assertIn("src/app.css:1", found[0]["detail"])

    def test_compound_allow_bypass_is_respected(self):
        write(self.root, "src/app.css",
              "/* compound-allow: 2026-01-01-no-filter */\nimg { filter: brightness(0.8); }\n")
        write(self.root, "docs/compound/corrections/2026-01-01-no-filter.md",
              correction("2026-01-01-no-filter", ["**/*.css"], "filter:[[:space:]]*brightness"))
        self.assertEqual(self.scan(), [])

    def test_store_docs_are_not_scanned_for_fires(self):
        # the correction file itself contains the bad snippet in prose
        write(self.root, "src/app.md", "fine\n")
        write(self.root, "docs/compound/corrections/2026-01-01-md.md",
              correction("2026-01-01-md", ["**/*.md"], "TODO-HACK")
              + "\nExample: TODO-HACK\n")
        self.assertEqual(self.scan(), [])

    # ── R: superseded ───────────────────────────────────────────
    def test_superseded_adr_is_flagged(self):
        write(self.root, "docs/compound/adr/001-old.md",
              "# ADR-001: old\n\n## Status\nSuperseded by ADR-002\n")
        write(self.root, "docs/compound/adr/002-new.md",
              "# ADR-002: new\n\n## Status\nAccepted\n")
        self.assertEqual(self.kinds(self.scan()), ["superseded"])

    # ── R: stale-guard (ledger) ─────────────────────────────────
    def test_ledger_guard_missing_on_disk_is_stale(self):
        write(self.root, "tests/test_ok.py", "pass\n")
        write(self.root, "docs/compound/ENFORCED.md", """
            # Enforced lessons

            | Lesson | Tier | Guard | Feature | Date |
            |---|---|---|---|---|
            | no eval | test | `tests/test_ok.py::test_no_eval` | foo | 2026-01-01 |
            | no sleep | lint | `.eslintrc.json` | bar | 2026-01-02 |
        """)
        found = self.scan()
        self.assertEqual(self.kinds(found), ["stale-guard"])
        self.assertIn(".eslintrc.json", found[0]["detail"])

    def test_standards_tier_guard_is_checked_too(self):
        write(self.root, "docs/compound/ENFORCED.md", """
            | Lesson | Tier | Guard | Feature | Date |
            |---|---|---|---|---|
            | use kebab | standards | `AGENTS.md` | foo | 2026-01-01 |
        """)
        self.assertEqual(self.kinds(self.scan()), ["stale-guard"])

    # ── R: dead-example (patterns) ──────────────────────────────
    def test_pattern_example_pointing_nowhere_is_flagged(self):
        write(self.root, "docs/intents/real.intent.md", "x\n")
        write(self.root, "docs/compound/patterns/p.md", """
            # Pattern: p

            ## Examples in this repo
            - `docs/intents/real.intent.md` (feature real)
            - `docs/intents/gone.intent.md` (feature gone)
        """)
        found = self.scan()
        self.assertEqual(self.kinds(found), ["dead-example"])
        self.assertIn("gone.intent.md", found[0]["detail"])

    def test_pattern_shorthand_paths_resolve_against_repo(self):
        # seen in a real store: examples cite partial paths and '...' elisions
        write(self.root, "app/src/main/java/in/x/ui/components/Card.kt", "x\n")
        write(self.root, "app/src/test/java/in/x/ui/components/CardTest.kt", "x\n")
        write(self.root, "docs/compound/patterns/p.md", """
            # Pattern: p

            ## Examples in this repo
            - `ui/components/Card.kt` — mapper
            - `app/src/test/.../ui/components/CardTest.kt` (cases)
            - `app/src/test/.../ui/components/GoneTest.kt` (cases)
        """)
        found = self.scan()
        self.assertEqual(self.kinds(found), ["dead-example"])
        self.assertIn("GoneTest.kt", found[0]["detail"])

    # ── corrections that target the store itself ────────────────
    def test_correction_scoped_to_store_is_not_dead(self):
        # seen in a real store: a correction guarding other corrections' frontmatter
        write(self.root, "src/a.kt", "x\n")
        write(self.root, "docs/compound/corrections/2026-01-01-escapes.md",
              correction("2026-01-01-escapes", ["docs/compound/corrections/*.md"],
                         "^match: .*BADESC", rule="No doubled escapes."))
        write(self.root, "docs/compound/corrections/2026-01-02-other.md",
              correction("2026-01-02-other", ["**/*.kt"], "GlobalScope", rule="No GlobalScope."))
        self.assertEqual(self.scan(), [])

    def test_store_scoped_correction_still_fires_on_other_corrections(self):
        write(self.root, "src/a.kt", "x\n")
        write(self.root, "docs/compound/corrections/2026-01-01-escapes.md",
              correction("2026-01-01-escapes", ["docs/compound/corrections/*.md"],
                         "^rule: .*FORBIDDEN"))
        write(self.root, "docs/compound/corrections/2026-01-02-other.md",
              correction("2026-01-02-other", ["**/*.kt"], "GlobalScope",
                         rule="FORBIDDEN word here"))
        found = self.scan()
        self.assertEqual(self.kinds(found), ["fires-on-tree"])
        self.assertIn("2026-01-02-other.md", found[0]["detail"])

    # ── archive is ignored ──────────────────────────────────────
    def test_archive_and_drafts_are_ignored(self):
        write(self.root, "docs/compound/_archive/corrections/old.md", "# no frontmatter\n")
        write(self.root, "docs/compound/_drafts/x.md", "# no frontmatter\n")
        self.assertEqual(self.scan(), [])

    # ── human output ────────────────────────────────────────────
    def test_text_output_reports_count(self):
        write(self.root, "docs/compound/corrections/2026-01-01-old.md", "# old\n")
        subprocess.run(["git", "-C", self.root, "add", "-A"], check=True)
        out = subprocess.run([sys.executable, "-I", SCANNER, "--root", self.root],
                             capture_output=True, text=True)
        self.assertEqual(out.returncode, 0)
        self.assertIn("1 finding", out.stdout)
        self.assertIn("no-guard", out.stdout)


if __name__ == "__main__":
    unittest.main()
