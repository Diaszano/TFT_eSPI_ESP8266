import json
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

    def test_compile_database_maps_one_verified_library_translation_unit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            project = root / ".build/TFT_Print_Test"
            stage = project / "lib/pio-library"
            source = root / "src/TFT_eSPI.cpp"
            staged_source = stage / "src/TFT_eSPI.cpp"
            source.parent.mkdir(parents=True)
            staged_source.parent.mkdir(parents=True)
            source.write_text("int library_source;\n")
            staged_source.write_text(source.read_text())
            command = [
                "xtensa-g++", "-std=gnu++17", "-DUSER_SETUP_LOADED",
                "-include", "setup file.h", "-Ilib/pio-library/src",
                "-o", ".pio/file.o", "-c", "lib/pio-library/src/TFT_eSPI.cpp",
            ]
            entry = {
                "directory": str(project),
                "file": "lib/pio-library/src/TFT_eSPI.cpp",
                "arguments": command,
            }
            mapped = analysis.map_compile_database([entry], stage, root)
            self.assertEqual(len(mapped), 1)
            self.assertEqual(mapped[0]["file"], str(source))
            self.assertEqual(mapped[0]["directory"], str(project))
            self.assertEqual(mapped[0]["arguments"], [
                "xtensa-g++", "-std=gnu++17", "-DUSER_SETUP_LOADED",
                "-include", "setup file.h", "-I" + str(root / "src"),
                "-o", ".pio/file.o", "-c", str(source),
            ])

    def test_compile_database_rejects_stale_missing_or_extra_library_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            stage = root / ".build/project/lib/pio-library"
            source = root / "src/TFT_eSPI.cpp"
            staged = stage / "src/TFT_eSPI.cpp"
            source.parent.mkdir(parents=True)
            staged.parent.mkdir(parents=True)
            source.write_text("int original;\n")
            staged.write_text("int changed;\n")
            entry = {
                "directory": str(root),
                "file": str(staged),
                "arguments": ["g++", "-c", str(staged)],
            }
            with self.assertRaises(ValueError):
                analysis.map_compile_database([entry], stage, root)
            staged.write_text(source.read_text())
            with self.assertRaises(ValueError):
                analysis.map_compile_database([], stage, root)
            with self.assertRaises(ValueError):
                extra = stage / "src/Sprite.cpp"
                extra.write_text("int other;\\n")
                extra_entry = {**entry, "file": str(extra)}
                analysis.map_compile_database([entry, extra_entry], stage, root)

    def test_native_database_requires_and_maps_the_real_color_probe(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            project = root / "test"
            source = project / "analysis/color_probe.cpp"
            source.parent.mkdir(parents=True)
            source.write_text("int main() {}\\n")
            entry = {
                "directory": str(project),
                "file": "analysis/color_probe.cpp",
                "arguments": ["g++", "-std=c++11", "-I../src", "-c", "analysis/color_probe.cpp"],
            }
            with self.assertRaises(ValueError):
                analysis.map_native_compile_database([], project, root)
            mapped = analysis.map_native_compile_database([entry], project, root)
            self.assertEqual(mapped[0]["file"], str(source))
            self.assertIn("-I" + str(root / "src"), mapped[0]["arguments"])
            self.assertEqual(mapped[0]["arguments"][-1], str(source))

    def test_native_baseline_cannot_be_used_for_target_scope(self):
        native = {**self.baseline, "scope": "native"}
        with self.assertRaises(ValueError):
            analysis.compare_findings([self.finding], native, self.profile, scope="target")

    def test_native_profile_fingerprints_host_compiler_and_tidy_config(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            (root / "test").mkdir()
            (root / "test/platformio.ini").write_text("[env:analysis-native]\\n")
            (root / ".clang-tidy").write_text("Checks: -*\\n")
            entry = {"arguments": ["g++", "-std=c++11", "-I" + str(root / "src")]}
            result = subprocess.CompletedProcess([], 0, "g++ (GCC) 13.3.0\n", "")
            with mock.patch("analysis.subprocess.run", return_value=result):
                profile = analysis.native_profile(root, entry, "LLVM version 22.1.8", "checks")
            self.assertEqual(profile["platform"], "native@1.2.1")
            self.assertEqual(profile["toolchain"], "g++ 13.3.0")
            self.assertEqual(profile["clang_tidy"], "22.1.8")
            self.assertNotIn("xtensa", profile["toolchain"].lower())

    def test_native_baseline_detects_seeded_pure_header_warning(self):
        native_baseline = {
            "schema": 1,
            "scope": "native",
            "profile": self.profile,
            "findings": [],
        }
        result = analysis.compare_findings(
            [self.finding], native_baseline, self.profile, scope="native"
        )
        self.assertEqual(result["new"], [self.finding])

    def test_native_analysis_reports_findings_from_shared_pure_header(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            source = root / "src/internal/color_conversion.h"
            source.parent.mkdir(parents=True)
            source.write_text("one\nsecond_line();\nthree\n")
            log = f"{source}:2:1: warning: seeded finding [bugprone-test]\n"
            owned, vendor = analysis.parse_warnings(log, root, root / ".build/stage", "")
            self.assertEqual(owned[0]["path"], "src/internal/color_conversion.h")
            self.assertEqual(owned[0]["check"], "bugprone-test")
            self.assertEqual(vendor, [])

    def test_tidy_parse_errors_fail_even_when_other_findings_are_empty(self):
        self.assertTrue(analysis.tidy_has_parse_error(
            "error: unsupported target flag [clang-diagnostic-error]"
        ))
        self.assertTrue(analysis.tidy_has_parse_error("Found compiler error(s)."))
        self.assertFalse(analysis.tidy_has_parse_error("0 warnings generated."))

    def test_cppcheck_pilot_scans_staged_library_with_explicit_cxx11_argv(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            project = root / ".build/TFT_Print_Test"
            staged = project / "lib/pio-library/src/TFT_eSPI.cpp"
            staged.parent.mkdir(parents=True)
            staged.write_text("int library_source;\\n")
            (project / "platformio.ini").write_text("[env:nodemcuv2]\\nboard = nodemcuv2\\n")
            calls = []

            def fake_run(command, **kwargs):
                calls.append((command, kwargs))
                return subprocess.CompletedProcess(command, 0, stdout="[]\\n", stderr="")

            self.assertEqual(analysis.run_cppcheck(project, root, fake_run), 0)
            command, kwargs = calls[0]
            self.assertIn("cppcheck", (project / ".pio-analysis.ini").read_text())
            self.assertIn("+<lib/pio-library/>", command)
            self.assertIn("cppcheck: --enable=warning,performance,portability --std=c++11", command)
            self.assertIn("--json-output", command)
            self.assertNotIn("--skip-packages", command)
            self.assertEqual(kwargs["capture_output"], True)
            self.assertEqual(json.loads((root / ".build/analysis/cppcheck.json").read_text()), [])

    def test_cppcheck_rejects_project_without_staged_library(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            project = root / "project"
            project.mkdir()
            with self.assertRaises(ValueError):
                analysis.run_cppcheck(project, root, mock.Mock())

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

    def test_warning_copy_relative_and_absolute_map_to_owned_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            source = root / "src/internal/Smooth_font.inc"
            source.parent.mkdir(parents=True)
            source.write_text("one\nfontFS = SPIFFS;\nthree\n")
            project = root / ".build/warnings/Example"
            for path in ("lib/pio-library/src/internal/Smooth_font.inc",
                         str(project / "lib/pio-library/src/internal/Smooth_font.inc")):
                with self.subTest(path=path):
                    log = f"{path}:2:1: warning: SPIFFS is deprecated [-Wdeprecated-declarations]\n"
                    owned, vendor = analysis.parse_warnings(log, root, root / ".build/pio-library", "Example")
                    self.assertEqual(len(owned), 1)
                    self.assertEqual(owned[0]["path"], "src/internal/Smooth_font.inc")
                    self.assertEqual(owned[0]["check"], "-Wdeprecated-declarations")
                    self.assertEqual(vendor, [])

    def test_warning_vendor_stays_vendor_and_new_owned_warning_fails_comparison(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            source = root / "src/TFT_eSPI.cpp"
            source.parent.mkdir(parents=True)
            source.write_text("int seeded;\n")
            log = ("lib/pio-library/src/TFT_eSPI.cpp:1:1: warning: seeded [-Wunused-variable]\n"
                   + f"{root}/.platformio/packages/framework/core.cpp:1:1: warning: vendor [-Wextra]\n")
            owned, vendor = analysis.parse_warnings(log, root, root / ".build/pio-library", "Example")
            self.assertEqual(len(owned), 1)
            self.assertEqual(len(vendor), 1)
            baseline = {"schema": 1, "scope": "target", "profile": self.profile, "findings": []}
            delta = analysis.compare_findings(owned, baseline, self.profile)
            self.assertEqual(delta["new"], owned)
            self.assertEqual(delta["resolved"], [])
            with mock.patch("analysis.build_warning_profile", return_value={"Example": log}), \
                 mock.patch("analysis._warning_profile", return_value=self.profile):
                (root / "examples/Example").mkdir(parents=True)
                (root / "examples/Example/Example.ino").write_text("void setup() {}\n")
                (root / ".build/warnings").mkdir(parents=True)
                baseline_path = root / "baseline.json"
                baseline_path.write_text(json.dumps(baseline))
                self.assertEqual(analysis.warnings(root, baseline_path, ["-Wall", "-Wextra"]), 1)

    def test_missing_owned_source_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            with self.assertRaisesRegex(ValueError, "cannot read owned warning source"):
                analysis.parse_warnings(
                    "lib/pio-library/src/missing.h:1:1: warning: seeded [-Wextra]",
                    root, root / ".build/pio-library", "Example")

    def test_generated_ino_and_setup_copy_keep_repository_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            (root / "examples/Example").mkdir(parents=True)
            (root / "examples/Example/Example.ino").write_text("int unused;\n")
            (root / "User_Setup.h").write_text("int setup_warning;\n")
            log = ("src/Example.ino.cpp:1:1: warning: sketch [-Wunused-variable]\n"
                   "lib/pio-library/User_Setup.h:1:1: warning: setup [-Wunused-variable]\n")
            owned, vendor = analysis.parse_warnings(log, root, root / ".build/pio-library", "Example")
            self.assertEqual({finding["path"] for finding in owned},
                             {"examples/Example/Example.ino", "User_Setup.h"})
            self.assertEqual(vendor, [])


if __name__ == "__main__":
    unittest.main()
