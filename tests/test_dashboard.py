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
