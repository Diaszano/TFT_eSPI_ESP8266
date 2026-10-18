import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from simulator.tools.reference_images import (
    DEFAULT_HEIGHT,
    DEFAULT_WIDTH,
    decode_png_rgb888,
)
from simulator.tools.generate_visual_guide import (
    EXPECTED_RAW_HASHES,
    FB_DISPLAY_H,
    FB_DISPLAY_W,
    FB_SCALE,
    FB_X0,
    FB_Y0,
    TIMELINE_SEGMENTS,
    VIDEO_FPS,
    VIDEO_HEIGHT,
    VIDEO_WIDTH,
    generate_visual_guide,
    verify_visual_guide,
)


ROOT = Path(__file__).resolve().parents[2]
RENDERS_DIR = ROOT / ".build/simulator/renders"


class VisualGuideVideoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out_dir = RENDERS_DIR
        cls.result = generate_visual_guide(out_dir=cls.out_dir)
        cls.verification = verify_visual_guide(cls.out_dir)

    def test_phase1_artifact_provenance_and_hashes(self):
        self.assertTrue(self.verification["overall_pass"], self.verification)
        for scene_id, expected_hash in EXPECTED_RAW_HASHES.items():
            scene_meta = self.result["scenes"][scene_id]
            self.assertEqual(scene_meta["raw_rgb565_sha256"], expected_hash)
            frame_png = self.out_dir / scene_id / "frame.png"
            self.assertTrue(frame_png.is_file())
            decoded = decode_png_rgb888(frame_png.read_bytes())
            self.assertEqual(decoded["width"], DEFAULT_WIDTH)
            self.assertEqual(decoded["height"], DEFAULT_HEIGHT)

    def test_phase2_mp4_container_and_encoding_specs(self):
        mp4_path = Path(self.result["video_path"])
        self.assertTrue(mp4_path.is_file())
        self.assertGreater(mp4_path.stat().st_size, 10_000)

        probe = self.verification["ffprobe"]
        self.assertEqual(probe["codec_name"], "h264")
        self.assertEqual(probe["width"], VIDEO_WIDTH)
        self.assertEqual(probe["height"], VIDEO_HEIGHT)
        self.assertEqual(probe["pix_fmt"], "yuv420p")
        self.assertEqual(probe["r_frame_rate"], f"{VIDEO_FPS}/1")
        self.assertEqual(probe["avg_frame_rate"], f"{VIDEO_FPS}/1")
        self.assertGreaterEqual(probe["duration_s"], 35.0)
        self.assertLessEqual(probe["duration_s"], 60.0)
        self.assertEqual(probe["nb_frames"], self.result["total_frames"])
        self.assertEqual(probe["audio_streams"], 0)
        self.assertTrue(self.verification["clean_decode_pass"])

    def test_phase3_and_4_timeline_and_slide_fidelity(self):
        segments = self.result["segments"]
        self.assertEqual(
            [s["id"] for s in segments],
            ["intro", "s1", "s2", "s3", "s4", "conclusion"],
        )
        for seg, spec in zip(segments, TIMELINE_SEGMENTS):
            self.assertEqual(seg["id"], spec["id"])
            self.assertEqual(seg["start_s"], spec["start_s"])
            self.assertEqual(seg["end_s"], spec["end_s"])
            self.assertEqual(seg["duration_s"], spec["duration_s"])
            if seg["id"] in ("s1", "s2", "s3", "s4"):
                self.assertGreaterEqual(seg["duration_s"], 6.0)

        # Verify pre-encoded slide images preserve 100% pixel-exact 4x nearest-neighbor framebuffer
        for scene_id in ("s1", "s2", "s3", "s4"):
            slide_info = self.verification["slides"][scene_id]
            self.assertTrue(slide_info["framebuffer_exact_4x_match"])
            self.assertEqual(slide_info["framebuffer_mismatch_pixels"], 0)
            self.assertTrue(slide_info["no_overlay_on_framebuffer"])
            self.assertTrue(slide_info["typography_pass"])

    def test_phase6_decoded_mp4_frames_match_slides(self):
        decoded_checks = self.verification["decoded_frames"]
        for seg_id in ("intro", "s1", "s2", "s3", "s4", "conclusion"):
            self.assertIn(seg_id, decoded_checks)
            check = decoded_checks[seg_id]
            self.assertTrue(check["pass"], f"Decoded frame check failed for {seg_id}: {check}")
            self.assertLess(check["full_frame_mae"], 4.0)
            extracted_path = ROOT / check["extracted_frame_path"]
            self.assertTrue(extracted_path.is_file())
            if seg_id in ("s1", "s2", "s3", "s4"):
                self.assertLess(check["framebuffer_mae"], 4.0)
                self.assertTrue(check["info_panel_non_empty"])

        # Verify that decoded scene frames are pairwise distinct
        mp4_path = Path(self.result["video_path"])
        scene_T = {"s1": 8.0, "s2": 17.0, "s3": 28.0, "s4": 41.0}
        scene_fb_pixels = {}
        stride = VIDEO_WIDTH * 3
        for sid, ts in scene_T.items():
            raw = subprocess.run(
                [
                    "ffmpeg",
                    "-v",
                    "error",
                    "-ss",
                    f"{ts:.2f}",
                    "-i",
                    str(mp4_path),
                    "-frames:v",
                    "1",
                    "-f",
                    "rawvideo",
                    "-pix_fmt",
                    "rgb24",
                    "-",
                ],
                check=True,
                capture_output=True,
            ).stdout
            self.assertEqual(len(raw), VIDEO_WIDTH * VIDEO_HEIGHT * 3)
            fb_crop = []
            for y in range(FB_Y0, FB_Y0 + FB_DISPLAY_H, FB_SCALE):
                row_start = y * stride
                for x in range(FB_X0, FB_X0 + FB_DISPLAY_W, FB_SCALE):
                    p = row_start + x * 3
                    fb_crop.append((raw[p], raw[p + 1], raw[p + 2]))
            scene_fb_pixels[sid] = fb_crop

        sids = list(scene_fb_pixels.keys())
        for i in range(len(sids)):
            for j in range(i + 1, len(sids)):
                p_a = scene_fb_pixels[sids[i]]
                p_b = scene_fb_pixels[sids[j]]
                diff_count = sum(1 for a, b in zip(p_a, p_b) if a != b)
                self.assertGreater(
                    diff_count,
                    500,
                    f"Decoded MP4 scenes {sids[i]} and {sids[j]} are not sufficiently distinct",
                )

    def test_video_manifest_and_report_written(self):
        manifest_path = self.out_dir / "video_manifest.json"
        report_path = self.out_dir / "VIDEO_GUIDE_REPORT.md"
        self.assertTrue(manifest_path.is_file())
        self.assertTrue(report_path.is_file())
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["video"]["codec"], "h264")
        self.assertEqual(manifest["video"]["width"], 1920)
        self.assertEqual(manifest["video"]["height"], 1080)
        self.assertEqual(manifest["video"]["fps"], 30)
        self.assertTrue(manifest["verification"]["overall_pass"])


if __name__ == "__main__":
    unittest.main()
