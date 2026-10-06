import json
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import check_version


class CheckVersionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.temp.name)
        (self.root / "library.json").write_text(json.dumps({"version": "1.0.0"}))
        (self.root / "library.properties").write_text("name=TFT_eSPI_ESP8266\nversion=1.0.0\n")

    def tearDown(self):
        self.temp.cleanup()

    def test_equal_versions_ok(self):
        self.assertEqual(
            check_version.versions(self.root),
            {"library.json": "1.0.0", "library.properties": "1.0.0"},
        )

    def test_properties_mismatch(self):
        (self.root / "library.properties").write_text("version=1.0.1\n")
        self.assertNotEqual(*check_version.versions(self.root).values())

    def test_manifest_included(self):
        (self.root / ".release-please-manifest.json").write_text(json.dumps({".": "1.0.0"}))
        self.assertEqual(len(check_version.versions(self.root)), 3)

    def test_properties_with_release_please_markers(self):
        (self.root / "library.properties").write_text(
            "# x-release-please-start-version\nversion=1.2.3\n# x-release-please-end\n"
        )
        self.assertEqual(check_version.versions(self.root)["library.properties"], "1.2.3")


if __name__ == "__main__":
    unittest.main()
