import io
import json
import tempfile
import unittest
from pathlib import Path

from scripts.hw_perf_capture import capture_stream


class CaptureTest(unittest.TestCase):
    def test_preserves_exact_bytes_and_marks_unattested_synthetic(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp) / "run"
            raw = b"\xffROM\r\nPERF,1,\x00\n"
            result = capture_stream(io.BytesIO(raw), directory, 100, 10, {"source": "stdin"})
            self.assertEqual((directory / "serial.raw").read_bytes(), raw)
            self.assertEqual(result["byte_count"], len(raw))
            self.assertEqual(json.loads((directory / "session.json").read_text())["source_type"],
                             "synthetic")
            with self.assertRaises(FileExistsError):
                capture_stream(io.BytesIO(b"x"), directory, 100, 10, {})

    def test_byte_limit_keeps_prefix(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp) / "run"
            result = capture_stream(io.BytesIO(b"abcdef"), directory, 3, 10, {})
            self.assertEqual((directory / "serial.raw").read_bytes(), b"abc")
            self.assertEqual(result["truncation_reason"], "byte_limit")

    def test_time_limit(self):
        ticks = iter([0, 0, 2, 2])
        with tempfile.TemporaryDirectory() as temp:
            result = capture_stream(io.BytesIO(b"abc"), Path(temp) / "run", 100, 1, {},
                                    clock=lambda: next(ticks))
            self.assertEqual(result["truncation_reason"], "time_limit")


if __name__ == "__main__":
    unittest.main()
