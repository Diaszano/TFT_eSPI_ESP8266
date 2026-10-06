import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from docs_check import check


class DocsCheckTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.write("README.md", "# English\n")
        self.write("README.pt-BR.md", "# Português\n")
        self.write("docs/en/a.md", "# Guide\n")
        self.write("docs/pt-BR/a.md", "# Guia\n")

    def tearDown(self):
        self.temp.cleanup()

    def write(self, rel, text):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return path

    def test_clean_tree_has_no_errors(self):
        self.assertEqual(check(self.root), [])

    def test_missing_pt_br_pair(self):
        (self.root / "docs/pt-BR/a.md").unlink()
        errors = check(self.root)
        self.assertEqual(len(errors), 1)
        self.assertIn("docs/en/a.md", errors[0])

    def test_missing_en_pair(self):
        self.write("docs/pt-BR/b.md", "# B\n")
        errors = check(self.root)
        self.assertEqual(len(errors), 1)
        self.assertIn("docs/pt-BR/b.md", errors[0])

    def test_missing_readme_pt_br(self):
        (self.root / "README.pt-BR.md").unlink()
        errors = check(self.root)
        self.assertEqual(len(errors), 1)
        self.assertIn("README.pt-BR.md", errors[0])

    def test_broken_relative_link(self):
        self.write("docs/en/a.md", "[x](nope.md)\n")
        errors = check(self.root)
        self.assertEqual(len(errors), 1)
        self.assertIn("docs/en/a.md", errors[0])
        self.assertIn("nope.md", errors[0])

    def test_link_with_anchor_to_existing_file_ok(self):
        self.write("docs/en/a.md", "[x](a.md#sec)\n")
        self.assertEqual(check(self.root), [])

    def test_external_and_anchor_links_ignored(self):
        self.write("docs/en/a.md", "[x](https://example.com/x.md) [y](#top) [z](mailto:a@b.c)\n")
        self.assertEqual(check(self.root), [])

    def test_removed_api_flagged(self):
        self.write("docs/en/a.md", "`getTouch()`\n")
        errors = check(self.root)
        self.assertEqual(len(errors), 1)
        self.assertIn("getTouch", errors[0])

    def test_removed_api_allowed_in_limitations(self):
        self.write("docs/en/limitations.md", "getTouch\n")
        self.write("docs/pt-BR/limitations.md", "getTouch\n")
        self.assertEqual(check(self.root), [])

    def test_cross_language_link_ok(self):
        self.write("docs/en/a.md", "[pt](../pt-BR/a.md)\n")
        self.assertEqual(check(self.root), [])


if __name__ == "__main__":
    unittest.main()
