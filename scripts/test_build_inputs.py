import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import build_inputs


class BuildInputsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.temp.name)
        for name in ("TFT_eSPI.cpp", "TFT_eSPI.h", "User_Setup.h", "library.json"):
            (self.root / name).write_text("fixture\n")
        (self.root / "Fonts/Custom").mkdir(parents=True)
        (self.root / "Fonts/Custom/Fixture.h").write_text("fixture\n")
        (self.root / "examples/Fixture").mkdir(parents=True)
        (self.root / "examples/Fixture/helper.h").write_text("fixture\n")
        (self.root / ".build").mkdir()
        (self.root / ".build/ignored.cpp").write_text("ignored\n")

    def tearDown(self):
        self.temp.cleanup()

    def test_src_layout_keeps_root_setup_and_selector_inputs(self):
        (self.root / "src").mkdir()
        (self.root / "src/TFT_eSPI.cpp").write_text("core\n")
        for name in ("User_Setup.h", "User_Setup_Select.h"):
            (self.root / name).write_text("setup\n")
        self.assertIn("User_Setup.h", build_inputs.library_files(self.root))
        self.assertIn("User_Setup_Select.h", build_inputs.library_files(self.root))

    def test_nested_inputs_and_deleted_header(self):
        self.assertIn("Fonts/Custom/Fixture.h", build_inputs.library_files(self.root))
        self.assertIn("examples/Fixture/helper.h", build_inputs.example_files(self.root))
        before = build_inputs.library_files(self.root)
        (self.root / "Fonts/Custom/Fixture.h").unlink()
        self.assertNotEqual(before, build_inputs.library_files(self.root))
        self.assertNotIn(".build/ignored.cpp", build_inputs.library_files(self.root))

    def test_src_internal_files_are_build_inputs(self):
        folder = self.root / "src/internal"
        folder.mkdir(parents=True)
        header = folder / "sprite_layout.h"
        header.write_text("layout\n")
        self.assertIn("src/internal/sprite_layout.h", build_inputs.library_files(self.root))

    @unittest.skipUnless(shutil.which("make"), "GNU Make is required")
    def test_inventory_changes_rebuild_once_and_stays_stable(self):
        inventory = self.root / ".build/source-inventory.txt"
        counter = self.root / ".build/build-count"
        makefile = self.root / "Makefile"
        makefile.write_text(
            "PYTHON := " + sys.executable + "\n"
            ".PHONY: FORCE\n"
            "FORCE:\n"
            ".build/source-inventory.txt: FORCE\n"
            "\t@$(PYTHON) scripts/build_inputs.py library > $@.tmp\n"
            "\t@$(PYTHON) scripts/build_inputs.py examples >> $@.tmp\n"
            "\t@cmp -s $@.tmp $@ || mv $@.tmp $@\n"
            "\t@rm -f $@.tmp\n"
            ".build/stamp: .build/source-inventory.txt\n"
            "\t@echo build >> .build/build-count\n"
            "\t@touch $@\n"
            "build: .build/stamp\n"
        )
        (self.root / "scripts").mkdir()
        shutil.copy(pathlib.Path(__file__).with_name("build_inputs.py"), self.root / "scripts/build_inputs.py")

        def build():
            subprocess.run(["make", "-C", str(self.root), "build"], check=True, capture_output=True)

        build()
        first_mtime = inventory.stat().st_mtime_ns
        build()
        self.assertEqual(counter.read_text().splitlines(), ["build"])
        self.assertEqual(inventory.stat().st_mtime_ns, first_mtime)
        (self.root / "Fonts/Custom/Fixture.h").write_text("changed\n")
        build()
        self.assertEqual(counter.read_text().splitlines(), ["build", "build"])
        (self.root / "Fonts/Custom/Fixture.h").unlink()
        build()
        self.assertEqual(counter.read_text().splitlines(), ["build", "build", "build"])
        (self.root / "examples/Fixture/helper.h").write_text("changed\n")
        build()
        (self.root / "examples/Fixture/helper.h").unlink()
        build()
        self.assertEqual(counter.read_text().splitlines(), ["build"] * 5)


if __name__ == "__main__":
    unittest.main()
