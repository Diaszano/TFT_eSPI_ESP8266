import tempfile
import unittest
from pathlib import Path

from tests.host.extremes_runner import run_case


class ExtremeRunnerTests(unittest.TestCase):
    def test_timeout_is_not_success(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory) / 'hang'
            fixture.write_text('#!/usr/bin/env python3\nimport sys,time\nif sys.argv[1]=="hang":\n while True: time.sleep(1)\n')
            fixture.chmod(0o755)
            result = run_case(str(fixture), 'hang', timeout_s=0.05)
            self.assertEqual(result['status'], 'TIMEOUT')
            self.assertNotEqual(result['status'], 'PASS')


if __name__ == '__main__':
    unittest.main()
