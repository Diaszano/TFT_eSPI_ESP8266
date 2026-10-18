import pathlib
import subprocess
import sys
import unittest

from simulator.tools.snapshots import compare_frames

ROOT = pathlib.Path(__file__).resolve().parents[1]


class SimulatorIntegrationTests(unittest.TestCase):
    def test_simulator_docs_state_scope_and_limitations(self):
        readme = (ROOT / "simulator/README.md").read_text()
        for phrase in ("não emula CPU", "RGB565", "sem hardware", "limitações", "NO_BASELINE"):
            self.assertIn(phrase, readme)
        self.assertTrue(verify_mutated_pixel_fails())

    def test_makefile_exposes_explicit_simulator_targets(self):
        makefile = (ROOT / "Makefile").read_text()
        for target in ("sim-build", "sim-test", "sim-render", "sim-diff", "sim-preview", "sim-visual-video"):
            self.assertRegex(makefile, rf"(?m)^{target}:")
        self.assertIn("python3 simulator/tools/viewer_server.py", makefile)
        self.assertIn("python3 simulator/tools/generate_visual_guide.py", makefile)

    def test_workflow_is_headless_safe_and_runs_regressions(self):
        workflow = (ROOT / ".github/workflows/simulator.yml").read_text()
        for forbidden in ("pio upload", "esptool", "pio device", "sim-preview", "usb", "/dev/tty"):
            self.assertNotIn(forbidden, workflow)
        for required in ("ctest", "test_viewer", "test_simulator_integration", "test_cli", "test_snapshots", "sim-render"):
            self.assertIn(required, workflow)
        self.assertRegex(workflow, r"if: failure\(\)")
        self.assertIn("retention-days:", workflow)

    def test_workflow_mutation_test_selector_is_runnable(self):
        workflow = (ROOT / ".github/workflows/simulator.yml").read_text()
        line = next(line.strip() for line in workflow.splitlines()
                    if "test_one_pixel_difference_reports_exact_coordinate_and_values" in line)
        selector = line.split("python3 -m unittest ", 1)[1].removesuffix(" -v")
        result = subprocess.run([sys.executable, "-m", "unittest", selector], cwd=ROOT,
                                text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_make_diff_propagates_failure_without_approving_baselines(self):
        makefile = (ROOT / "Makefile").read_text()
        self.assertIn("--expected", makefile)
        self.assertIn("--actual", makefile)
        self.assertNotIn("golden-update", makefile)
        self.assertIn("sim-preview", makefile)


if __name__ == "__main__":
    unittest.main()


def verify_mutated_pixel_fails():
    result = compare_frames(bytes((0, 0)), bytes((1, 0)), 1, 1)
    return result.status == "FAIL" and result.first_xy == (0, 0)
