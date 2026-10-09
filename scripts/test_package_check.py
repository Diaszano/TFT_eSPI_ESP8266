import json
import pathlib
import sys
import tarfile
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import package_check


REQUIRED = {
    "TFT_eSPI.cpp", "TFT_eSPI.h", "User_Setup.h", "library.json", "library.properties",
    "license.txt", "Fonts/GFXFF/license.txt", "examples/TFT_Print_Test/TFT_Print_Test.ino",
    "examples/Font_Demo_1/data/NotoSansBold15.vlw", "examples/Font_Demo_1/data/NotoSansBold36.vlw",
    "examples/TFT_SPIFFS_BMP/data/parrot.bmp",
}


class PackageCheckTests(unittest.TestCase):
    def test_validates_required_legacy_package_contents(self):
        package_check.validate_members(REQUIRED, src_layout=False)

    def test_src_layout_requires_source_entry_points_and_root_setup(self):
        members = REQUIRED - {"TFT_eSPI.cpp", "TFT_eSPI.h"} | {"src/TFT_eSPI.cpp", "src/TFT_eSPI.h"}
        package_check.validate_members(members, src_layout=True)

    def test_missing_setup_notice_or_data_fails(self):
        for missing in ("User_Setup.h", "Fonts/GFXFF/license.txt", "examples/TFT_SPIFFS_BMP/data/parrot.bmp"):
            with self.subTest(missing=missing), self.assertRaises(ValueError):
                package_check.validate_members(REQUIRED - {missing}, src_layout=False)

    def test_rejects_unsafe_and_tooling_members(self):
        for bad in ("/etc/passwd", "../outside", "folder/../../outside", ".git/config", ".venv/bin/python", ".superpowers/sdd/progress.md"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                package_check.validate_members(REQUIRED | {bad}, src_layout=False)

    def test_fork_metadata_and_keywords(self):
        root = pathlib.Path(__file__).resolve().parent.parent
        manifest = json.loads((root / "library.json").read_text())
        properties = (root / "library.properties").read_text()
        self.assertIn("author=Bodmer, Lucas Dias (Diaszano)", properties)
        self.assertIn("maintainer=Lucas Dias (Diaszano) <61257292+Diaszano@users.noreply.github.com>", properties)
        self.assertIn("version=1.0.0", properties)
        authors = {author["name"]: author for author in manifest["authors"]}
        self.assertFalse(authors["Bodmer"]["maintainer"])
        self.assertEqual(authors["Lucas Dias (Diaszano)"]["email"], "61257292+Diaszano@users.noreply.github.com")
        self.assertTrue(authors["Lucas Dias (Diaszano)"]["maintainer"])
        keywords = [line.split("\t", 1)[0] for line in (root / "keywords.txt").read_text().splitlines() if line and not line.startswith("#")]
        self.assertEqual(keywords.count("TFT_eSPI"), 1)
        self.assertEqual(keywords.count("TFT_eSprite"), 1)
        self.assertEqual(keywords.count("resetViewport"), 1)
        for obsolete in ("begin_SDA_Read", "end_SDA_Read", "writeRegister"):
            self.assertNotIn(obsolete, keywords)

    def test_cli_reads_archive_without_extracting(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = pathlib.Path(directory) / "fixture.tar"
            with tarfile.open(archive, "w") as stream:
                for name in REQUIRED:
                    info = tarfile.TarInfo(name)
                    info.size = 0
                    stream.addfile(info)
            package_check.validate_archive(archive, src_layout=False)


if __name__ == "__main__":
    unittest.main()
