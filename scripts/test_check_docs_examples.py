import os
import pathlib
import tempfile
import unittest

import check_docs_examples


class CheckDocsExamplesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.temp.name)
        (self.root / ".build/pio-library").mkdir(parents=True)
        for name in check_docs_examples.DOCS:
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("```cpp\nvoid setup() {}\nvoid loop() {}\n```\n", encoding="utf-8")
        self.log = self.root / "pio-argv.log"
        self.pio = self.root / "fake-pio"
        self.pio.write_text(
            "#!/usr/bin/env python3\n"
            "import os,sys\n"
            "open(os.environ['PIO_LOG'],'a').write(' '.join(sys.argv[1:])+'\\n')\n"
            "raise SystemExit(int(os.environ.get('FAKE_PIO_EXIT','0')))\n",
            encoding="utf-8",
        )
        self.pio.chmod(0o755)

    def tearDown(self):
        self.temp.cleanup()

    def test_missing_block_fails(self):
        (self.root / "README.md").write_text("No code sample\n", encoding="utf-8")
        with self.assertRaises(ValueError):
            check_docs_examples.check(self.root, str(self.pio))

    def test_compiles_every_selected_block(self):
        os.environ["PIO_LOG"] = str(self.log)
        try:
            check_docs_examples.check(self.root, str(self.pio))
        finally:
            os.environ.pop("PIO_LOG", None)
        calls = self.log.read_text().splitlines()
        self.assertEqual(len(calls), 4)
        self.assertTrue(all("nodemcuv2" in call for call in calls))

    def test_compiler_failure_propagates(self):
        os.environ["PIO_LOG"] = str(self.log)
        os.environ["FAKE_PIO_EXIT"] = "9"
        try:
            with self.assertRaises(Exception):
                check_docs_examples.check(self.root, str(self.pio))
        finally:
            os.environ.pop("PIO_LOG", None)
            os.environ.pop("FAKE_PIO_EXIT", None)


if __name__ == "__main__":
    unittest.main()
