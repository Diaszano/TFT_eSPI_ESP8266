import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from simulator.tools.snapshots import (
    DEFAULT_HEIGHT,
    DEFAULT_WIDTH,
    MAX_FRAME_BYTES,
    decode_565le,
    rgb565_to_rgb888,
)
from simulator.tools.reference_images import (
    ANNOTATION_TEXT_MIN_HEIGHT_PX,
    DISPLAY_AREA_RECT,
    DISPLAY_SCALE,
    REFERENCE_SCENES,
    TITLE_TEXT_MIN_HEIGHT_PX,
    contrast_ratio_rgb888,
    decode_png_rgb888,
    generate_reference_suite,
    verify_annotated_image,
    verify_scene_geometry_independent,
    verify_suite_artifacts,
)


class ReferenceImageAcceptanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.TemporaryDirectory()
        cls.out_dir = Path(cls._tmpdir.name) / "renders"
        cls.suite = generate_reference_suite(cls.out_dir)

    @classmethod
    def tearDownClass(cls):
        cls._tmpdir.cleanup()

    def test_01_png_dimensions_and_color_format(self):
        for scene_id in REFERENCE_SCENES:
            png_path = self.out_dir / scene_id / "frame.png"
            info = decode_png_rgb888(png_path.read_bytes())
            self.assertEqual(info["width"], DEFAULT_WIDTH)
            self.assertEqual(info["height"], DEFAULT_HEIGHT)
            self.assertEqual(info["bit_depth"], 8)
            self.assertEqual(info["color_type"], 2)
            self.assertEqual(len(info["pixels"]), 57600)

    def test_02_raw_framebuffer_size(self):
        for scene_id in REFERENCE_SCENES:
            raw_path = self.out_dir / scene_id / "frame.rgb565"
            data = raw_path.read_bytes()
            self.assertEqual(len(data), MAX_FRAME_BYTES)
            self.assertEqual(len(data), 115200)

    def test_03_rgb565_little_endian_decoding(self):
        sample = bytes([0x34, 0x12, 0xEF, 0xCD])
        self.assertEqual(decode_565le(sample), [0x1234, 0xCDEF])
        for scene_id in REFERENCE_SCENES:
            raw = (self.out_dir / scene_id / "frame.rgb565").read_bytes()
            pixels = decode_565le(raw)
            self.assertEqual(len(pixels), 57600)
            self.assertTrue(all(0 <= p <= 0xFFFF for p in pixels))

    def test_04_pixel_perfect_png_conversion(self):
        for scene_id in REFERENCE_SCENES:
            raw = (self.out_dir / scene_id / "frame.rgb565").read_bytes()
            png_info = decode_png_rgb888((self.out_dir / scene_id / "frame.png").read_bytes())
            expected_rgb = [rgb565_to_rgb888(p) for p in decode_565le(raw)]
            self.assertEqual(png_info["pixels"], expected_rgb)

    def test_05_deterministic_repeated_rendering(self):
        for scene_id in REFERENCE_SCENES:
            entry = self.suite["scenes"][scene_id]
            rep = entry["reproducibility"]
            self.assertEqual(rep["status"], "PASS")
            self.assertEqual(rep["runs"], 2)
            self.assertEqual(rep["run1_raw_sha256"], rep["run2_raw_sha256"])
            self.assertEqual(rep["run1_png_sha256"], rep["run2_png_sha256"])
            self.assertEqual(rep["run1_raw_sha256"], entry["raw_frame_sha256"])
            self.assertEqual(rep["run1_png_sha256"], entry["png_sha256"])

    def test_06_nearest_neighbor_4x_enlargement_and_07_framebuffer_preservation(self):
        x0, y0, w, h = DISPLAY_AREA_RECT
        self.assertEqual(DISPLAY_SCALE, 4)
        self.assertEqual((w, h), (960, 960))
        for scene_id in REFERENCE_SCENES:
            raw = (self.out_dir / scene_id / "frame.rgb565").read_bytes()
            annotated_bytes = (self.out_dir / scene_id / "annotated.png").read_bytes()
            check = verify_annotated_image(scene_id, raw, annotated_bytes)
            self.assertEqual(check["status"], "PASS", check)
            self.assertEqual(check["display_area_width"], 960)
            self.assertEqual(check["display_area_height"], 960)
            self.assertEqual(check["altered_or_obscured_pixels"], 0)

    def test_08_scene_specific_independent_geometry_assertions(self):
        for scene_id in REFERENCE_SCENES:
            raw = (self.out_dir / scene_id / "frame.rgb565").read_bytes()
            geom = verify_scene_geometry_independent(scene_id, decode_565le(raw))
            self.assertEqual(geom["status"], "PASS", geom)
        s3_geom = verify_scene_geometry_independent(
            "s3", decode_565le((self.out_dir / "s3/frame.rgb565").read_bytes())
        )
        self.assertEqual(s3_geom["checkerboard_verified_pixels"], 130)
        s4_geom = verify_scene_geometry_independent(
            "s4", decode_565le((self.out_dir / "s4/frame.rgb565").read_bytes())
        )
        self.assertEqual(s4_geom["font4_rle_golden_status"], "NO_BASELINE")

    def test_09_annotation_coordinates_and_readability(self):
        self.assertGreaterEqual(ANNOTATION_TEXT_MIN_HEIGHT_PX, 18)
        self.assertGreaterEqual(TITLE_TEXT_MIN_HEIGHT_PX, 26)
        self.assertGreaterEqual(contrast_ratio_rgb888((245, 247, 250), (18, 22, 30)), 4.5)
        for scene_id in REFERENCE_SCENES:
            entry = self.suite["scenes"][scene_id]
            ann_check = entry["annotation_validation"]
            self.assertEqual(ann_check["status"], "PASS", ann_check)
            self.assertGreaterEqual(ann_check["title_height_px"], 26)
            self.assertGreaterEqual(ann_check["min_text_height_px"], 18)
            self.assertGreaterEqual(ann_check["min_contrast_ratio"], 4.5)
            self.assertEqual(ann_check["overlapping_labels"], 0)
            self.assertEqual(ann_check["out_of_bounds_labels"], 0)
            for callout in entry["annotations"]:
                self.assertEqual(callout["scene_id"], scene_id)
                bx0, by0, bx1, by1 = callout["bbox"]
                self.assertTrue(0 <= bx0 <= bx1 < 240)
                self.assertTrue(0 <= by0 <= by1 < 240)
                self.assertIn(callout["visibility"], ("fully_visible", "intentionally_clipped"))
                self.assertTrue(callout["expected_color_or_behavior"])

    def test_10_manifest_and_artifact_completeness_and_objective_statuses(self):
        audit = verify_suite_artifacts(self.out_dir)
        self.assertEqual(audit["status"], "PASS", audit)
        shared_manifest = json.loads((self.out_dir / "manifest.json").read_text(encoding="utf-8"))
        self.assertTrue((self.out_dir / "VISUAL_INSPECTION_REPORT.md").is_file())
        for scene_id in REFERENCE_SCENES:
            scene_dir = self.out_dir / scene_id
            for name in ("frame.rgb565", "frame.png", "annotated.png", "notes.md", "manifest.json"):
                self.assertTrue((scene_dir / name).is_file(), f"missing {scene_id}/{name}")
            entry = shared_manifest["scenes"][scene_id]
            raw_bytes = (scene_dir / "frame.rgb565").read_bytes()
            png_bytes = (scene_dir / "frame.png").read_bytes()
            self.assertEqual(entry["raw_frame_sha256"], hashlib.sha256(raw_bytes).hexdigest())
            self.assertEqual(entry["png_sha256"], hashlib.sha256(png_bytes).hexdigest())
            self.assertEqual(entry["pixel_dimensions"], {"width": 240, "height": 240, "total_pixels": 57600, "raw_bytes": 115200})
            statuses = entry["verification_results"]
            self.assertEqual(statuses["file_validity"], "PASS")
            self.assertEqual(statuses["pixel_conversion"], "PASS")
            self.assertEqual(statuses["determinism"], "PASS")
            self.assertEqual(statuses["geometry_validation"], "PASS")
            self.assertEqual(statuses["annotation_accuracy"], "PASS")
            self.assertEqual(statuses["independent_golden_availability"], "NO_BASELINE")
            self.assertEqual(statuses["physical_visual_approval"], "VISUAL_REVIEW_REQUIRED")
            self.assertEqual(entry["baseline_approval_status"], "NO_BASELINE")

    def test_11_tamper_detection_fails_altered_pixels(self):
        raw = bytearray((self.out_dir / "s1/frame.rgb565").read_bytes())
        annotated = (self.out_dir / "s1/annotated.png").read_bytes()
        raw[0] ^= 0xFF
        geom = verify_scene_geometry_independent("s1", decode_565le(raw))
        self.assertEqual(geom["status"], "FAIL")
        ann_check = verify_annotated_image("s1", bytes(raw), annotated, [])
        self.assertEqual(ann_check["status"], "FAIL")
        self.assertGreater(ann_check["altered_or_obscured_pixels"], 0)

    def test_12_color_values_and_red_blue_mutation(self):
        probes = {
            "s1": [(5, 5, 0x07FF, (0, 255, 255)),
                   (50, 24, 0xF800, (255, 0, 0)),
                   (24, 50, 0x001F, (0, 0, 255)),
                   (50, 215, 0x07E0, (0, 255, 0)),
                   (215, 50, 0xFFE0, (255, 255, 0)),
                   (230, 230, 0xF81F, (255, 0, 255)),
                   (100, 50, 0x0000, (0, 0, 0))],
            "s2": [(0, 40, 0xF800, (255, 0, 0)),
                   (1, 40, 0x07E0, (0, 255, 0))],
            "s3": [(35, 71, 0x07FF, (0, 255, 255)),
                   (8, 44, 0xF800, (255, 0, 0)),
                   (8, 84, 0x001F, (0, 0, 255)),
                   (48, 84, 0xFFE0, (255, 255, 0))],
            "s4": [(8, 48, 0xF800, (255, 0, 0)),
                   (16, 48, 0x001F, (0, 0, 255)),
                   (12, 53, 0xFFE0, (255, 255, 0))],
        }
        for scene, scene_probes in probes.items():
            raw = (self.out_dir / scene / "frame.rgb565").read_bytes()
            rgb = decode_png_rgb888((self.out_dir / scene / "frame.png").read_bytes())["pixels"]
            for x, y, expected_565, expected_rgb in scene_probes:
                offset = 2 * (y * 240 + x)
                self.assertEqual(int.from_bytes(raw[offset:offset + 2], "little"), expected_565)
                self.assertEqual(rgb[y * 240 + x], expected_rgb)
        raw = bytearray((self.out_dir / "s1/frame.rgb565").read_bytes())
        for offset in range(0, len(raw), 2):
            value = int.from_bytes(raw[offset:offset + 2], "little")
            swapped = ((value & 31) << 11) | (value & 0x07E0) | (value >> 11)
            raw[offset:offset + 2] = swapped.to_bytes(2, "little")
        self.assertEqual(verify_scene_geometry_independent("s1", decode_565le(raw))["status"], "FAIL")


if __name__ == "__main__":
    unittest.main()
