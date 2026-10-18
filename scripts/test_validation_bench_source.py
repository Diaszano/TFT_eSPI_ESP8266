import re
import unittest
from pathlib import Path


def extract_timed_blocks(source):
    return re.findall(r'// BENCH_BEGIN(.*?)// BENCH_END', source, re.S)


class BenchmarkSourceTests(unittest.TestCase):
    def test_pushpixels_window_matches_image_dimensions(self):
        source = Path('extras/hardware/Audit_Validation/ValidationBench.cpp').read_text()
        self.assertRegex(source, r'setAddrWindow\(24,\s*80,\s*16,\s*16\)')

    def test_run_reports_esp_reset_reason(self):
        source = Path('extras/hardware/Audit_Validation/ValidationTelemetry.cpp').read_text()
        self.assertIn('ESP.getResetReason()', source)

    def test_bench_has_three_rounds_and_io_free_timed_blocks(self):
        source = Path('extras/hardware/Audit_Validation/ValidationBench.cpp').read_text()
        self.assertIn('fillrect_160x100', source)
        self.assertIn('BENCH,', source)
        self.assertIn('constexpr uint8_t kRounds = 3', source)
        self.assertIn('constexpr uint8_t kSamplesPerRound = 10', source)
        blocks = extract_timed_blocks(source)
        self.assertTrue(blocks)
        for block in blocks:
            self.assertNotRegex(block, r'Serial\.|\.print\(|createSprite|deleteSprite|setTextPadding')


if __name__ == '__main__':
    unittest.main()
