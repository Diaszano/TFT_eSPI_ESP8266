import hashlib
import struct
import json
import subprocess
import tempfile
import unittest
import zlib
from pathlib import Path

from simulator.tools import snapshots


def decode_png_fixture(png):
    if png[:8] != b"\x89PNG\r\n\x1a\n":
        raise AssertionError("invalid PNG signature")
    offset = 8
    chunks = []
    while offset < len(png):
        size = struct.unpack_from(">I", png, offset)[0]
        kind = png[offset + 4:offset + 8]
        data = png[offset + 8:offset + 8 + size]
        crc = struct.unpack_from(">I", png, offset + 8 + size)[0]
        if zlib.crc32(kind + data) & 0xFFFFFFFF != crc:
            raise AssertionError("invalid PNG chunk CRC")
        chunks.append((kind, data))
        offset += size + 12
    header = next(data for kind, data in chunks if kind == b"IHDR")
    width, height, depth, color_type, compression, filtering, interlace = struct.unpack(
        ">IIBBBBB", header
    )
    if (depth, color_type, compression, filtering, interlace) != (8, 2, 0, 0, 0):
        raise AssertionError("unexpected PNG format")
    raw = zlib.decompress(b"".join(data for kind, data in chunks if kind == b"IDAT"))
    rows = []
    stride = width * 3
    for y in range(height):
        row = raw[y * (stride + 1):(y + 1) * (stride + 1)]
        if row[0] != 0:
            raise AssertionError("fixture supports only PNG filter 0")
        rows.append([tuple(row[i:i + 3]) for i in range(1, len(row), 3)])
    return width, height, rows, [kind for kind, _ in chunks]


class SnapshotEncodingTests(unittest.TestCase):
    def test_approved_golden_checks_independent_metadata_profile_and_hash(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "fixture.rgb565"
            raw = (Path(__file__).parent / "fixtures/expected/tiny.rgb565").read_bytes()
            path.write_bytes(raw)
            metadata = {
                "schema_version": 1, "status": "APPROVED", "scene_id": "fixture",
                "width": 2, "height": 2, "profile_hash": "a" * 64,
                "source_revision": "b" * 40, "baseline_sha256": hashlib.sha256(raw).hexdigest(),
                "approved_by": "independent reviewer", "approval_reason": "oracle verified",
            }
            sidecar = path.with_suffix(".json")
            sidecar.write_text(json.dumps(metadata))
            result = snapshots.compare_golden(raw, path, "a" * 64, 2, 2)
            self.assertEqual(result.status, "PASS")
            mutated = bytearray(raw)
            mutated[6] ^= 1
            result = snapshots.compare_golden(mutated, path, "a" * 64, 2, 2)
            self.assertEqual((result.status, result.diff_pixels, result.first_xy), ("FAIL", 1, (1, 1)))
            self.assertEqual(snapshots.compare_golden(raw, path, "c" * 64, 2, 2).status,
                             "INCONCLUSIVE")
            metadata["width"] = 1
            sidecar.write_text(json.dumps(metadata))
            self.assertEqual(snapshots.compare_golden(raw, path, "a" * 64, 2, 2).status,
                             "INCONCLUSIVE")
            metadata["baseline_sha256"] = "0" * 64
            sidecar.write_text(json.dumps(metadata))
            self.assertEqual(snapshots.compare_golden(raw, path, "a" * 64, 2, 2).status,
                             "INCONCLUSIVE")

    def test_missing_or_unapproved_golden_never_passes(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "missing.rgb565"
            result = snapshots.compare_golden(bytes(8), path, "a" * 64, 2, 2)
            self.assertEqual(result.status, "NO_BASELINE")
            path.write_bytes(bytes(8))
            path.with_suffix(".json").write_text("{}")
            self.assertEqual(snapshots.compare_golden(bytes(8), path, "a" * 64, 2, 2).status,
                             "INCONCLUSIVE")

    def test_production_runner_exports_canonical_frame_bytes(self):
        root = Path(__file__).resolve().parents[2]
        runner = root / ".build/simulator/debug/simulator_runner"
        result = subprocess.run(
            [str(runner), "--scene", "solid_rgb565", "--seed", "7", "--rotation", "0",
             "--rgb565-stdout"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", "replace"))
        self.assertEqual(len(result.stdout), 240 * 240 * 2)
        self.assertEqual(result.stdout[:2], bytes.fromhex("00 f8"))

    def test_rgb565_bytes_decode_as_little_endian_primaries(self):
        raw = bytes.fromhex("00 f8 e0 07 1f 00 00 00 ff ff")
        self.assertEqual(snapshots.decode_565le(raw), [0xF800, 0x07E0, 0x001F, 0x0000, 0xFFFF])

    def test_png_encodes_rgb565_as_rgb888_and_filter_zero(self):
        raw = bytes.fromhex("00 f8 e0 07 1f 00 ff ff")
        png = snapshots.encode_png_rgb565(raw, width=2, height=2)
        width, height, rows, chunks = decode_png_fixture(png)
        self.assertEqual((width, height), (2, 2))
        self.assertEqual(rows, [[(255, 0, 0), (0, 255, 0)], [(0, 0, 255), (255, 255, 255)]])
        self.assertEqual(chunks, [b"IHDR", b"IDAT", b"IEND"])

    def test_png_output_is_byte_deterministic(self):
        raw = bytes.fromhex("00 f8 e0 07 1f 00 ff ff")
        self.assertEqual(snapshots.encode_png_rgb565(raw, 2, 2), snapshots.encode_png_rgb565(raw, 2, 2))

    def test_frame_validation_checks_dimensions_and_exact_length(self):
        self.assertEqual(snapshots.validate_frame(bytes(240 * 240 * 2)), 240 * 240)
        with self.assertRaises(ValueError):
            snapshots.validate_frame(bytes(8), 240, 240)
        with self.assertRaises(ValueError):
            snapshots.validate_frame(bytes(10), 2, 2)

    def test_default_profile_frame_encodes_at_240_by_240(self):
        png = snapshots.encode_png_rgb565(bytes.fromhex("00 f8") * (240 * 240))
        width, height, rows, _ = decode_png_fixture(png)
        self.assertEqual((width, height), (240, 240))
        self.assertEqual(rows[0][0], (255, 0, 0))

    def test_decoder_rejects_incomplete_pixel(self):
        with self.assertRaises(ValueError):
            snapshots.decode_565le(b"\x00")

    def test_encoder_rejects_malformed_frame_size(self):
        with self.assertRaises(ValueError):
            snapshots.encode_png_rgb565(bytes(7), 2, 2)

    def test_one_pixel_difference_reports_exact_coordinate_and_values(self):
        expected = [0xF800, 0x0000, 0xFFFF, 0x07E0]
        actual = [0xF800, 0x0000, 0x001F, 0x07E0]
        result = snapshots.compare_frames(expected, actual, 2, 2)
        self.assertEqual(result.status, "FAIL")
        self.assertEqual(result.total_pixels, 4)
        self.assertEqual(result.diff_pixels, 1)
        self.assertEqual(result.diff_percent, 25.0)
        self.assertEqual(result.first_xy, (0, 1))
        self.assertEqual((result.expected_pixel, result.actual_pixel), (0xFFFF, 0x001F))
        self.assertEqual(result.bbox, (0, 1, 0, 1))
        self.assertEqual(result.channels["red"], {
            "changed_pixels": 1, "absolute_difference": 255, "maximum_difference": 255
        })
        self.assertEqual(result.channels["green"]["maximum_difference"], 255)
        self.assertEqual(result.channels["blue"]["changed_pixels"], 0)

    def test_multiple_edge_mutations_have_exact_inclusive_bounding_box(self):
        expected = [0] * 9
        actual = [0] * 9
        for index in (0, 2, 4, 6, 8):
            actual[index] = 0xFFFF
        result = snapshots.compare_frames(expected, actual, 3, 3)
        self.assertEqual(result.diff_pixels, 5)
        self.assertEqual(result.first_xy, (0, 0))
        self.assertEqual(result.bbox, (0, 0, 2, 2))

    def test_incompatible_profile_hashes_are_not_compared(self):
        result = snapshots.compare_frames(
            [0], [0], 1, 1, expected_profile_hash="profile-a", actual_profile_hash="profile-b"
        )
        self.assertEqual(result.status, "INCONCLUSIVE")
        self.assertIsNone(result.diff_pixels)
        partial = snapshots.compare_frames([0], [0], 1, 1, expected_profile_hash="profile-a")
        self.assertEqual(partial.status, "INCONCLUSIVE")

    def test_invalid_frame_sizes_raise_instead_of_becoming_equal(self):
        with self.assertRaises(ValueError):
            snapshots.compare_frames(bytes(2), bytes(4), 2, 1)
        with self.assertRaises(ValueError):
            snapshots.compare_frames([0], [0], 2, 1)

    def test_comparison_writes_separate_diff_and_reports(self):
        expected = [0xF800, 0, 0, 0]
        actual = [0xF800, 0, 0x001F, 0]
        with tempfile.TemporaryDirectory() as output:
            result = snapshots.write_comparison_artifacts(expected, actual, 2, 2, output)
            self.assertEqual(result.status, "FAIL")
            self.assertTrue((Path(output) / "diff.png").is_file())
            report = json.loads((Path(output) / "report.json").read_text())
            self.assertEqual(report["status"], "FAIL")
            expected_bytes = bytes((0x00, 0xF8, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00))
            actual_bytes = bytes((0x00, 0xF8, 0x00, 0x00, 0x1F, 0x00, 0x00, 0x00))
            self.assertEqual(report["expected_frame_sha256"], hashlib.sha256(expected_bytes).hexdigest())
            self.assertEqual(report["actual_frame_sha256"], hashlib.sha256(actual_bytes).hexdigest())
            self.assertEqual(report["first_difference"], {
                "x": 0, "y": 1, "expected_rgb565": "0x0000", "actual_rgb565": "0x001F"
            })
            self.assertIn("different_pixels: 1", (Path(output) / "report.md").read_text())


if __name__ == "__main__":
    unittest.main()
