import base64
import struct
import unittest
import zlib

from scripts.hw_perf_analysis import analyze_run, summarize_samples, elapsed_u32


def line(sequence, kind, *fields):
    body = f"PERF,1,run42,{sequence},{kind}," + ",".join(map(str, fields))
    return f"{body},{zlib.crc32(body.encode()):08x}\n".encode()


class AnalysisTest(unittest.TestCase):
    def test_exact_quantiles_and_deadlines(self):
        values = list(range(1, 1000)) + [33334]
        summary = summarize_samples(values, 10_000_000)
        self.assertEqual((summary["p50_us"], summary["p95_us"], summary["p99_us"]),
                         (500, 950, 990))
        self.assertEqual(summary["max_us"], 33334)
        self.assertEqual(summary["deadline_miss_30"], 1)
        self.assertEqual(summary["deadline_miss_60"], 1)
        self.assertEqual(summary["fps_effective"], 100.0)
        self.assertEqual(summary["status"], "COMPLETE")

    def test_short_set_and_impossible_values(self):
        self.assertEqual(summarize_samples([1], 10)["status"], "INCOMPLETE")
        for samples, elapsed in (([], 10), ([0], 10), ([2**32], 10), ([1], 0),
                                 ([11], 10), ([1], 2**64)):
            with self.subTest(samples=samples, elapsed=elapsed):
                with self.assertRaises(ValueError):
                    summarize_samples(samples, elapsed)
        self.assertEqual(elapsed_u32(0x00000010, 0xfffffff0), 32)

    def test_synthetic_completion_cannot_be_physical_pass(self):
        payload = base64.b64encode(struct.pack("<I", 1)).decode()
        raw = (line(0, "BEGIN", "FP1", 0, 1, "full")
               + line(1, "SAMPLES", "FP1", 0, 0, 1, payload)
               + line(2, "END", "FP1", 1, 100, "PASS"))
        result = analyze_run(raw, {"source_type": "synthetic"})
        self.assertEqual(result["firmware_result"], "PASS")
        self.assertEqual(result["transport_integrity"], "COMPLETE")
        self.assertNotEqual(result["physical_review"], "APPROVED_BY_OPERATOR")
        self.assertNotEqual(result["overall_status"], "PASS")


if __name__ == "__main__":
    unittest.main()
