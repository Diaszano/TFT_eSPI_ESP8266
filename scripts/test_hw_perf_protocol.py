import base64
import struct
import unittest
import zlib

from scripts.hw_perf_protocol import parse_perf


def line(run_id, sequence, kind, *fields):
    body = f"PERF,1,{run_id},{sequence},{kind}," + ",".join(map(str, fields))
    return f"{body},{zlib.crc32(body.encode('ascii')):08x}\n".encode("ascii")


class PerfProtocolTest(unittest.TestCase):
    def test_complete_sentinel(self):
        values = base64.b64encode(struct.pack("<2I", 1, 0x12345678)).decode()
        raw = (line("run42", 0, "BEGIN", "TI", 0, 2, "sentinel")
               + line("run42", 1, "SAMPLES", "TI", 0, 0, 2, values)
               + line("run42", 2, "END", "TI", 2, 1000, "PASS"))
        run = parse_perf(raw)["runs"][0]
        self.assertEqual(run["samples"], [1, 0x12345678])
        self.assertEqual(run["firmware_result"], "PASS")
        self.assertEqual(run["transport_integrity"], "COMPLETE")

    def test_gap_preserves_firmware_completion(self):
        raw = (line("run42", 0, "BEGIN", "TI", 0, 1, "sentinel")
               + line("run42", 2, "END", "TI", 1, 1000, "PASS"))
        run = parse_perf(raw)["runs"][0]
        self.assertEqual(run["firmware_result"], "PASS")
        self.assertEqual(run["transport_integrity"], "INCOMPLETE")

    def test_crc_correct_wrong_base64_count_is_corrupt(self):
        raw = (line("run42", 0, "BEGIN", "TI", 0, 1, "sentinel")
               + line("run42", 1, "SAMPLES", "TI", 0, 0, 2, "AQAAAA==")
               + line("run42", 2, "END", "TI", 2, 1000, "PASS"))
        self.assertEqual(parse_perf(raw)["runs"][0]["transport_integrity"], "CORRUPT")

    def test_bad_bytes_are_not_rewritten(self):
        raw = line("run42", 0, "BEGIN", "TI", 0, 0, "sentinel") + b"\xff\n"
        parsed = parse_perf(raw)
        self.assertTrue(parsed["errors"])
        self.assertEqual(parsed["runs"][0]["transport_integrity"], "CORRUPT")

    def test_fault_matrix(self):
        begin = line("run42", 0, "BEGIN", "TI", 0, 1, "sentinel")
        sample = line("run42", 1, "SAMPLES", "TI", 0, 0, 1, "AQAAAA==")
        end = line("run42", 2, "END", "TI", 1, 100, "PASS")
        faults = [
            (begin + sample[:-10] + b"00000000\n" + end, "CORRUPT"),
            (begin + sample + end + end, "CORRUPT"),
            (begin + begin + sample + end, "CORRUPT"),
            (begin + sample, "INCOMPLETE"),
            (begin + sample + line("run42", 2, "END", "TI", 2, 100, "PASS"),
             "CORRUPT"),
            (begin + b"PERF,2,run42,1,END,TI,1,100,PASS,00000000\n",
             "INCOMPLETE"),
        ]
        for raw, expected in faults:
            with self.subTest(raw=raw):
                self.assertEqual(parse_perf(raw)["runs"][0]["transport_integrity"],
                                 expected)

    def test_duration_run_and_second_boot(self):
        raw = (b"HWTEST,2\n"
               + line("run42", 0, "BEGIN", "FM", 0, 0, "long30")
               + line("run42", 1, "SAMPLES", "FM", 0, 0, 1, "AQAAAA==")
               + line("run42", 2, "END", "FM", 1, 2**32 + 1, "PASS")
               + b"HWTEST,2\n"
               + line("run42", 0, "BEGIN", "TI", 0, 0, "sentinel")
               + line("run42", 1, "END", "TI", 0, 1, "PASS"))
        parsed = parse_perf(raw)
        self.assertEqual(len(parsed["runs"]), 2)
        self.assertEqual([run["transport_integrity"] for run in parsed["runs"]],
                         ["COMPLETE", "COMPLETE"])

    def test_skip_has_complete_transport_without_samples(self):
        raw = (line("run42", 0, "BEGIN", "FP3", 0, 1000, "fp3_mixed")
               + line("run42", 1, "END", "FP3", 0, 0, "SKIP"))
        run = parse_perf(raw)["runs"][0]
        self.assertEqual(run["firmware_result"], "SKIP")
        self.assertEqual(run["transport_integrity"], "COMPLETE")


if __name__ == "__main__":
    unittest.main()
