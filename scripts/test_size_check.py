import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import size_check


class SizeCheckTests(unittest.TestCase):
    def test_parses_section_table_and_totals(self):
        output = """.build/firmware.elf  :
section           size     addr
.irom0.text       300000       0
.text              10000  100000
.text1               1000  110000
.data                1000  120000
.rodata               500  121000
.bss                25000  122000
"""
        sections = size_check.parse_sections(output)
        self.assertEqual(sections[".irom0.text"], 300000)
        self.assertEqual(size_check.resource_totals(sections), {"flash": 312500, "ram": 26500})

    def test_optional_text1_but_required_sections(self):
        sections = {".irom0.text": 1, ".text": 2, ".data": 0, ".rodata": 0, ".bss": 0}
        self.assertEqual(size_check.resource_totals(sections), {"flash": 3, "ram": 0})
        with self.assertRaises(ValueError):
            size_check.resource_totals({".text": 1})

    def test_rejects_bad_or_duplicate_section_rows(self):
        with self.assertRaises(ValueError):
            size_check.parse_sections(".text nope 0\n")
        with self.assertRaises(ValueError):
            size_check.parse_sections(".text 1 0\n.text 2 1\n")

    def test_profile_records_platform_version(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            project = root / "project"
            project.mkdir()
            (project / "platformio.ini").write_text("[env:nodemcuv2]\nboard = nodemcuv2\nplatform = espressif8266@4.2.1\nframework = arduino\n")
            (root / "User_Setup.h").write_text("setup\n")
            log = "PLATFORM: Espressif 8266 (4.2.1) > NodeMCU 1.0 (ESP-12E Module)\nPACKAGES:\n - framework-arduinoespressif8266 @ 3.30102.0 (3.1.2)\n - toolchain-xtensa @ 2.100300.220621 (10.3.0)\n"
            self.assertEqual(size_check._profile(root, log, project)["platform"], "4.2.1")

    def test_resource_increase_and_profile_mismatch_fail(self):
        profile = {"setup_sha256": "abc", "toolchain": "10.3.0"}
        baseline = {"flash": 312500, "ram": 26500}
        self.assertEqual(size_check.compare_resources(baseline, baseline, profile, profile), {"flash": 0, "ram": 0})
        for actual in ({"flash": 312501, "ram": 26500}, {"flash": 312500, "ram": 26501}):
            with self.assertRaises(ValueError):
                size_check.compare_resources(actual, baseline, profile, profile)
        with self.assertRaises(ValueError):
            size_check.compare_resources(baseline, baseline, {**profile, "setup_sha256": "other"}, profile)
        with self.assertRaises(ValueError):
            size_check.compare_resources({"flash": -1, "ram": 0}, baseline, profile, profile)

    def test_empty_requested_size_report_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            for name in ("firmware.elf", "size.log", "build.log", "baseline.json"):
                (root / name).write_text("\n")
            with self.assertRaises(SystemExit):
                size_check.main(["--elf", str(root / "firmware.elf"), "--log", str(root / "size.log"), "--build-log", str(root / "build.log"), "--profile", "default", "--baseline", str(root / "baseline.json"), "--label", "test"])

    def test_missing_size_report_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            missing = pathlib.Path(directory) / "missing.log"
            with self.assertRaises(SystemExit):
                size_check.main(["--elf", "firmware.elf", "--log", str(missing), "--build-log", str(missing), "--profile", "default", "--baseline", str(missing), "--label", "test"])


if __name__ == "__main__":
    unittest.main()
