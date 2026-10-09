import pathlib
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import arduino_build


class ArduinoBuildTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="tft path ")
        self.addCleanup(self.temp.cleanup)
        self.root = pathlib.Path(self.temp.name)
        for index in range(14):
            name = f"Example{index}"
            folder = self.root / "examples" / name
            folder.mkdir(parents=True)
            (folder / f"{name}.ino").write_text("void setup() {}\nvoid loop() {}\n")
        for name in ("sprite_ownership", "minimal_setup", "firmware_memory"):
            folder = self.root / "tests/compile" / name
            folder.mkdir(parents=True)
            (folder / f"{name}.cpp").write_text("void setup() {}\nvoid loop() {}\n")
        self.calls = []

    def fake_run(self, command, **kwargs):
        self.calls.append(command)
        if command[1:] == ["version"]:
            return subprocess.CompletedProcess(command, 0, "arduino-cli Version: 1.3.1 Commit: test\n")
        if command[1:] == ["core", "list"]:
            return subprocess.CompletedProcess(command, 0, "ID Installed Latest Name\nesp8266:esp8266 3.1.2 3.1.2 ESP8266\n")
        kwargs["stdout"].write("compiled fixture\n")
        return subprocess.CompletedProcess(command, 0)

    def test_all_examples_and_three_compile_regressions_use_real_checkout(self):
        arduino_build.compile_examples(self.root, run=self.fake_run)
        builds = [call for call in self.calls if call[1] == "compile"]
        self.assertEqual(len(builds), 17)
        names = {pathlib.Path(call[-1]).name for call in builds}
        self.assertEqual(names, {f"Example{i}" for i in range(14)} | {"sprite_ownership", "minimal_setup", "firmware_memory"})
        for call in builds:
            self.assertEqual(call[call.index("--library") + 1], str(self.root))
            self.assertEqual(call[call.index("--fqbn") + 1], arduino_build.FQBN)
            self.assertIn("--clean", call)
        minimal = next(call for call in builds if pathlib.Path(call[-1]).name == "minimal_setup")
        self.assertIn(f"compiler.cpp.extra_flags={arduino_build.MINIMAL_FLAGS}", minimal)
        self.assertTrue((self.root / ".build/arduino/sketches/minimal_setup/minimal_setup.cpp").is_file())

    def test_compiler_failure_stops_matrix_and_keeps_log(self):
        def fail(command, **kwargs):
            result = self.fake_run(command, **kwargs)
            if command[1] == "compile":
                return subprocess.CompletedProcess(command, 9)
            return result
        with self.assertRaisesRegex(RuntimeError, "Arduino compile failed"):
            arduino_build.compile_examples(self.root, run=fail)
        self.assertEqual(sum(call[1] == "compile" for call in self.calls), 1)
        self.assertEqual(len(list((self.root / ".build/arduino").glob("*.log"))), 1)

    def test_wrong_core_is_rejected_before_compile(self):
        def wrong_core(command, **kwargs):
            result = self.fake_run(command, **kwargs)
            if command[1:] == ["core", "list"]:
                return subprocess.CompletedProcess(command, 0, "esp8266:esp8266 3.1.1 3.1.2 ESP8266\n")
            return result
        with self.assertRaisesRegex(ValueError, "core 3.1.2"):
            arduino_build.compile_examples(self.root, run=wrong_core)
        self.assertFalse(any(call[1] == "compile" for call in self.calls))

    def test_wrong_cli_is_rejected_before_compile(self):
        for version in ("1.3.2", "1.3.1-rc1"):
            with self.subTest(version=version), self.assertRaisesRegex(ValueError, "CLI 1.3.1"):
                arduino_build.compile_examples(self.root, run=lambda command, **kwargs:
                    subprocess.CompletedProcess(command, 0, f"arduino-cli Version: {version}\n"))

    def test_empty_or_incomplete_example_set_is_rejected(self):
        (self.root / "examples/Example0/Example0.ino").unlink()
        with self.assertRaisesRegex(ValueError, "found 13"):
            arduino_build.compile_examples(self.root, run=self.fake_run)
        self.assertFalse(any(call[1] == "compile" for call in self.calls))


if __name__ == "__main__":
    unittest.main()
