import base64
import struct
import unittest
import zlib

from scripts.hw_perf_analysis import (
    analyze_run, summarize_samples, elapsed_u32, summarize_frame_run,
    compare_frame_profiles, baseline_content_hash)
from scripts.hw_perf_analysis import summarize_heap


def line(sequence, kind, *fields, run_id="run42"):
    body = f"PERF,1,{run_id},{sequence},{kind}," + ",".join(map(str, fields))
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

    def test_frame_summary_uses_wall_time_and_keeps_cold_separate(self):
        run = {"samples": [1000] * 1000, "elapsed_us": 2_000_000,
               "cold_us": 5000, "pixels_per_frame": 57600,
               "timer_overhead_us": 4}
        summary = summarize_frame_run(run)
        self.assertEqual(summary["fps_effective"], 500)
        self.assertEqual(summary["cold_us"], 5000)
        self.assertEqual(summary["pixel_throughput"], 28_800_000)
        self.assertEqual(summary["p95_minus_p50_us"], 0)

    def test_comparison_requires_five_distinct_attested_boots(self):
        profile = {"board": "node", "display": "st7789", "rotation": 0,
                   "cpu_hz": 80_000_000, "spi_hz": 40_000_000, "wifi": "off",
                   "scene": "fp1_scanline", "seed": 0, "supply": "5V"}

        def sessions(prefix, sha):
            return [{"boot_id": f"{prefix}{i}", "firmware_sha": sha,
                     "source_type": "physical", "boot_witness": f"witness{i}",
                     "transport_integrity": "COMPLETE",
                     "profile_compatibility": "COMPATIBLE",
                     "physical_review": "APPROVED_BY_OPERATOR",
                     "profile": profile, "samples": [1000] * 1000,
                     "elapsed_us": 2_000_000} for i in range(5)]

        baseline = sessions("base", "sha1")
        candidate = sessions("cand", "sha2")
        approval = {"operator": "tester", "approved_utc": "2026-10-18T00:00:00Z",
                    "baseline_sha256": baseline_content_hash(baseline)}
        self.assertEqual(compare_frame_profiles(baseline, candidate, approval)["status"],
                         "INFORMATIONAL")
        self.assertEqual(compare_frame_profiles(baseline * 5, candidate, approval)["status"],
                         "INCOMPARABLE")
        self.assertEqual(compare_frame_profiles(baseline, candidate, {})["status"],
                         "NO_BASELINE")
        candidate[0] = {**candidate[0], "source_type": "synthetic"}
        self.assertEqual(compare_frame_profiles(baseline, candidate, approval)["status"],
                         "INCOMPARABLE")

    def test_analysis_keeps_cold_and_warm_runs_separate(self):
        one = base64.b64encode(struct.pack("<I", 1000)).decode()
        raw = (line(0, "BEGIN", "FP1", 0, 1, "fp1_cold")
               + line(1, "SAMPLES", "FP1", 0, 0, 1, one)
               + line(2, "END", "FP1", 1, 1000, "PASS")
               + line(0, "BEGIN", "FP1", 0, 1, "fp1_warm", run_id="run43")
               + line(1, "SAMPLES", "FP1", 0, 0, 1, one, run_id="run43")
               + line(2, "END", "FP1", 1, 1000, "PASS", run_id="run43"))
        result = analyze_run(raw, {"source_type": "synthetic"})
        self.assertEqual(len(result["runs"]), 2)
        self.assertEqual(result["runs"][1]["run"]["profile_id"], "fp1_warm")

    def test_heap_warning_is_not_leak_verdict(self):
        run = {"memory": [
            {"checkpoint": 0, "free_heap": 20000, "largest_block": 15000,
             "min_heap": 20000, "failures": 0},
            {"checkpoint": 1, "free_heap": 18976, "largest_block": 14000,
             "min_heap": 18000, "failures": 0}],
            "samples": [1, 2], "elapsed_us": 100,
            "transport_integrity": "COMPLETE"}
        summary = summarize_heap(run)
        self.assertNotIn("WARNING_HEAP_DROP", summary["warnings"])
        run["memory"][-1]["free_heap"] = 18975
        summary = summarize_heap(run)
        self.assertIn("WARNING_HEAP_DROP", summary["warnings"])
        self.assertNotEqual(summary["leak_status"], "PROVEN")
        run["memory"][-1]["free_heap"] = 20000
        summary = summarize_heap(run)
        self.assertEqual(summary["post_minus_pre_bytes"], 0)
        self.assertEqual(summary["recovered_bytes"], 2000)
        self.assertLess(summary["largest_block_delta"], 0)
        run["memory"][0]["largest_block"] = 20001
        with self.assertRaises(ValueError):
            summarize_heap(run)
        run["memory"][0]["free_heap"] = 0
        with self.assertRaises(ValueError):
            summarize_heap(run)


if __name__ == "__main__":
    unittest.main()
