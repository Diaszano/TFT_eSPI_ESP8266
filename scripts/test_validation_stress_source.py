import unittest
from pathlib import Path


class StressSourceTests(unittest.TestCase):
    def test_endurance_skips_when_sprite_is_unavailable(self):
        source = Path('extras/hardware/Audit_Validation/ValidationStress.cpp').read_text()
        endurance = source.split('void run_endurance_30m(', 1)[1]
        self.assertRegex(endurance, r'if \(!sprite\.created\(\)\)\s*\{')
        self.assertRegex(endurance, r'validation_emit_case_return\(log, "endurance_30m", 0, "SKIP"\)')


if __name__ == '__main__':
    unittest.main()
