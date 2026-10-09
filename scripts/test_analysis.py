import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import analysis


class AnalysisTests(unittest.TestCase):
    def setUp(self):
        self.finding = {
            "path": "src/internal/Sprite.inc",
            "check": "unused-variable",
            "message": "unused variable value",
            "context_sha256": "a" * 64,
            "line": 10,
        }
        self.profile = {
            "platform": "4.2.1",
            "toolchain": "2.100300.220621",
            "setup_sha256": "b" * 64,
            "flags": ["-Wall", "-Wextra"],
        }
        self.baseline = {
            "schema": 1,
            "scope": "target",
            "profile": self.profile,
            "findings": [{**self.finding, "owner": "library", "rationale": "legacy"}],
        }

    def test_line_shift_does_not_change_identity(self):
        shifted = {**self.finding, "line": 100}
        self.assertEqual(analysis.diagnostic_key(self.finding), analysis.diagnostic_key(shifted))

    def test_check_message_and_context_are_part_of_identity(self):
        key = analysis.diagnostic_key(self.finding)
        for change in (
            {"check": "other-check"},
            {"message": "unused variable elsewhere"},
            {"context_sha256": "c" * 64},
        ):
            self.assertNotEqual(key, analysis.diagnostic_key({**self.finding, **change}))

    def test_comparison_reports_new_and_resolved_findings(self):
        unchanged = analysis.compare_findings([self.finding], self.baseline, self.profile)
        self.assertEqual(unchanged, {"new": [], "resolved": []})
        new = {**self.finding, "path": "src/new.cpp"}
        result = analysis.compare_findings([self.finding, new], self.baseline, self.profile)
        self.assertEqual(result["new"], [new])
        result = analysis.compare_findings([], self.baseline, self.profile)
        self.assertEqual(result["resolved"], self.baseline["findings"])

    def test_invalid_baseline_profile_and_duplicate_findings_fail(self):
        duplicate = {**self.baseline, "findings": [*self.baseline["findings"]] * 2}
        with self.assertRaises(ValueError):
            analysis.compare_findings([self.finding], duplicate, self.profile)
        with self.assertRaises(ValueError):
            analysis.compare_findings([self.finding], self.baseline, {"flags": []})
        with self.assertRaises(ValueError):
            analysis.compare_findings(
                [self.finding], self.baseline, {**self.profile, "toolchain": "other"}
            )

    def test_warning_parser_separates_owned_and_vendor_diagnostics(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            stage = root / ".build/pio-library"
            source = root / "src/internal/Sprite.inc"
            source.parent.mkdir(parents=True)
            source.write_text("one\n  warning_line();\nthree\n")
            staged_source = stage / "src/internal/Sprite.inc"
            staged_source.parent.mkdir(parents=True)
            staged_source.write_text(source.read_text())
            vendor = root / ".platformio/packages/framework/core.cpp"
            vendor.parent.mkdir(parents=True)
            vendor.write_text("int core;\n")
            log = (
                f"{staged_source}:2:3: warning: unused variable value [-Wunused-variable]\n"
                f"{vendor}:1:1: warning: vendor warning [-Wextra]\n"
            )
            owned, third_party = analysis.parse_warnings(log, root, stage, "Example")
            self.assertEqual(len(owned), 1)
            self.assertEqual(owned[0]["path"], "src/internal/Sprite.inc")
            self.assertEqual(owned[0]["check"], "-Wunused-variable")
            self.assertEqual(len(third_party), 1)

    def test_warning_builds_use_fresh_warning_profile_for_all_examples(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            examples = root / "examples"
            examples.mkdir()
            names = [f"Example{i}" for i in range(14)]
            for name in names:
                project = examples / name
                project.mkdir()
                (project / f"{name}.ino").write_text("void setup() {}\n")
            calls = []

            def fake_run(command, **kwargs):
                calls.append((command, kwargs))
                return subprocess.CompletedProcess(command, 0, stdout="ok\n", stderr="")

            logs = analysis.build_warning_profile(root, names, ["-Wall", "-Wextra"], fake_run)
            self.assertEqual(set(logs), set(names))
            self.assertEqual(len(calls), 14)
            for name, (command, kwargs) in zip(names, calls):
                self.assertEqual(command[0:2], ["pio", "ci"])
                self.assertIn("platform=espressif8266@4.2.1", command)
                self.assertIn("build_flags=-Wall -Wextra", command)
                build_dir = pathlib.Path(command[command.index("--build-dir") + 1])
                self.assertEqual(build_dir, root / ".build/warnings" / name)
                self.assertTrue(build_dir.is_relative_to(root / ".build/warnings"))
                self.assertTrue(kwargs["capture_output"])


if __name__ == "__main__":
    unittest.main()
