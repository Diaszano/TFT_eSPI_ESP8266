import subprocess
import unittest
from pathlib import Path


class HardwareMakeTargetsTests(unittest.TestCase):
    def test_offline_targets_exist_without_flash_dependencies(self):
        makefile = Path('Makefile').read_text()
        for target in ('test-hw-build', 'test-hw-preflight', 'test-hw-parse', 'test-hw-compare', 'test-host-extremes'):
            self.assertIn(target + ':', makefile)
        for target in ('test-hw-build', 'test-hw-preflight', 'test-hw-parse', 'test-hw-compare', 'test-host-extremes'):
            self.assertNotIn(target + ': upload', makefile)
        self.assertIn('test-hw-preflight: test-hw-build', makefile)
        self.assertIn('scripts/hw_validation_preflight.py', makefile)
        self.assertIn('LOG', makefile)
        self.assertIn('BASELINE', makefile)
        self.assertIn('CANDIDATE', makefile)

    def test_missing_log_or_baseline_fails_without_running_a_device_command(self):
        for target in ('test-hw-parse', 'test-hw-compare'):
            result = subprocess.run(['make', target], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('Usage:', result.stderr)

    def test_preflight_dry_run_is_build_only(self):
        result = subprocess.run(['make', '-n', 'test-hw-preflight'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('pio ci', result.stdout)
        self.assertIn('scripts/hw_validation_preflight.py', result.stdout)
        for forbidden in ('upload', 'esptool', 'device monitor', 'reset', 'dtr', 'rts'):
            self.assertNotIn(forbidden, result.stdout.lower())


if __name__ == '__main__':
    unittest.main()
