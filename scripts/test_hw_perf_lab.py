import unittest
from scripts.hw_perf_lab import validate_lab_session


class LabCharacterizationTests(unittest.TestCase):
    def setUp(self):
        self.profile = {
            "board": "nodemcuv2", "display": "st7789", "rotation": 0,
            "cpu_hz": 80_000_000, "spi_hz": 40_000_000, "wifi": "off",
            "scene": "fp3_mixed", "seed": 0x13579bdf, "supply": "5V"
        }
        self.perf_summary = {
            "source_type": "physical",
            "transport_integrity": "COMPLETE",
            "firmware_result": "PASS",
            "profile": self.profile,
            "capture_utc_start": "2026-10-18T10:00:00Z",
            "capture_utc_end": "2026-10-18T10:05:00Z"
        }
        self.manifest = {
            "instrument_id": "RIGOL_DS1054Z_SN12345",
            "operator": "diaszano",
            "capture_utc_start": "2026-10-18T10:00:00Z",
            "capture_utc_end": "2026-10-18T10:05:00Z",
            "profile": self.profile,
            "calibration": {"voltage_factor": 1.0, "current_factor": 1.0}
        }

    def test_complete_capture_without_external_trace_reports_unavailable(self):
        result = validate_lab_session(self.perf_summary, self.manifest, [])
        self.assertEqual(result["status"], "COMPLETE")
        self.assertEqual(result["optical"], "UNAVAILABLE")
        self.assertEqual(result["power"], "UNAVAILABLE")

        result_none = validate_lab_session(self.perf_summary, self.manifest, None)
        self.assertEqual(result_none["status"], "COMPLETE")
        self.assertEqual(result_none["optical"], "UNAVAILABLE")
        self.assertEqual(result_none["power"], "UNAVAILABLE")

    def test_synthetic_source_cannot_be_physical_lab_evidence(self):
        synthetic_perf = {**self.perf_summary, "source_type": "synthetic"}
        readings = [{"timestamp_utc": "2026-10-18T10:01:00Z", "channel": "voltage", "value": 5.0, "unit": "V"}]
        result = validate_lab_session(synthetic_perf, self.manifest, readings)
        self.assertEqual(result["status"], "INCOMPARABLE")
        self.assertEqual(result["optical"], "INCOMPARABLE")
        self.assertEqual(result["power"], "INCOMPARABLE")

    def test_reading_outside_capture_interval_is_incomparable(self):
        readings = [
            {"timestamp_utc": "2026-10-18T09:59:59Z", "channel": "optical", "value": 1.2, "unit": "V"}
        ]
        result = validate_lab_session(self.perf_summary, self.manifest, readings)
        self.assertEqual(result["status"], "INCOMPARABLE")
        self.assertEqual(result["optical"], "INCOMPARABLE")

    def test_current_trace_without_calibration_does_not_produce_watts(self):
        uncalibrated_manifest = {**self.manifest, "calibration": {}}
        readings = [
            {"timestamp_utc": "2026-10-18T10:01:00Z", "channel": "voltage", "value": 5.0, "unit": "V"},
            {"timestamp_utc": "2026-10-18T10:01:00Z", "channel": "current", "value": 0.08, "unit": "A"}
        ]
        result = validate_lab_session(self.perf_summary, uncalibrated_manifest, readings)
        self.assertEqual(result["power"]["status"], "INCOMPARABLE")
        self.assertEqual(result["power"]["watts"], "UNAVAILABLE")

    def test_current_trace_with_bad_units_does_not_produce_watts(self):
        readings = [
            {"timestamp_utc": "2026-10-18T10:01:00Z", "channel": "voltage", "value": 5.0, "unit": "raw_adc"},
            {"timestamp_utc": "2026-10-18T10:01:00Z", "channel": "current", "value": 0.08, "unit": "A"}
        ]
        result = validate_lab_session(self.perf_summary, self.manifest, readings)
        self.assertEqual(result["power"]["status"], "INCOMPARABLE")
        self.assertEqual(result["power"]["watts"], "UNAVAILABLE")

    def test_calibrated_paired_voltage_and_current_computes_watts(self):
        readings = [
            {"timestamp_utc": "2026-10-18T10:01:00Z", "channel": "voltage", "value": 5.0, "unit": "V"},
            {"timestamp_utc": "2026-10-18T10:01:00Z", "channel": "current", "value": 0.10, "unit": "A"},
            {"timestamp_utc": "2026-10-18T10:02:00Z", "channel": "voltage", "value": 5.0, "unit": "V"},
            {"timestamp_utc": "2026-10-18T10:02:00Z", "channel": "current", "value": 0.12, "unit": "A"}
        ]
        result = validate_lab_session(self.perf_summary, self.manifest, readings)
        self.assertEqual(result["status"], "COMPLETE")
        self.assertEqual(result["power"]["status"], "COMPLETE")
        self.assertAlmostEqual(result["power"]["mean_watts"], 0.55)
        self.assertAlmostEqual(result["power"]["max_watts"], 0.60)

    def test_profile_mismatch_is_incomparable(self):
        mismatched_manifest = {
            **self.manifest,
            "profile": {**self.profile, "spi_hz": 27_000_000}
        }
        readings = [
            {"timestamp_utc": "2026-10-18T10:01:00Z", "channel": "optical", "value": 1.2, "unit": "V"}
        ]
        result = validate_lab_session(self.perf_summary, mismatched_manifest, readings)
        self.assertEqual(result["status"], "INCOMPARABLE")

    def test_nonmonotonic_timestamps_rejected(self):
        readings = [
            {"timestamp_utc": "2026-10-18T10:02:00Z", "channel": "optical", "value": 1.2, "unit": "V"},
            {"timestamp_utc": "2026-10-18T10:01:00Z", "channel": "optical", "value": 1.3, "unit": "V"}
        ]
        result = validate_lab_session(self.perf_summary, self.manifest, readings)
        self.assertEqual(result["status"], "INCOMPARABLE")
        self.assertEqual(result["reason"], "nonmonotonic timestamps")


if __name__ == "__main__":
    unittest.main()
