import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CLI = ROOT / "simulator/tools/sim.py"


def write_test_frame(directory, frame, approved=False):
    directory.mkdir()
    profile = json.loads((ROOT / "simulator/profiles/nodemcu-st7789-240x240.json").read_text())
    profile_hash = hashlib.sha256(json.dumps(
        profile, sort_keys=True, separators=(",", ":")
    ).encode()).hexdigest()
    (directory / "frame.rgb565").write_bytes(frame)
    manifest = {
        "schema_version": 1, "scene_id": "test_fixture", "seed": 0,
        "source_sha": "0" * 40, "simulator_version": "test",
        "profile": profile, "profile_hash": profile_hash,
        "frame_sha256": hashlib.sha256(frame).hexdigest(),
        "hardware": False, "simulated_timing": False, "simulated_memory": False,
    }
    if approved:
        manifest["golden_approval"] = {
            "status": "APPROVED", "approved_by": "test fixture reviewer",
            "approval_reason": "independently constructed RGB565 fixture",
        }
    (directory / "manifest.json").write_text(json.dumps(manifest))


def invoke(*args):
    return subprocess.run(
        [sys.executable, str(CLI), *map(str, args)], cwd=ROOT,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=15,
    )


class SimulatorCliTests(unittest.TestCase):
    def test_list_scenes_uses_production_registry(self):
        result = invoke("list-scenes")
        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", "replace"))
        self.assertIn(b"edge_rect", result.stdout)
        self.assertIn(b"sprite_depths", result.stdout)

    def test_render_writes_reproducible_frame_png_and_manifest_only_in_output(self):
        with tempfile.TemporaryDirectory() as root:
            first = Path(root) / "first"
            second = Path(root) / "second"
            for output in (first, second):
                result = invoke("render", "--scene", "edge_rect", "--seed", "123",
                                "--out", output)
                self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", "replace"))
            frame = (first / "frame.rgb565").read_bytes()
            manifest = json.loads((first / "manifest.json").read_text())
            self.assertEqual(len(frame), 115200)
            self.assertEqual((first / "frame.png").read_bytes(), (second / "frame.png").read_bytes())
            self.assertEqual((first / "frame.rgb565").read_bytes(), (second / "frame.rgb565").read_bytes())
            self.assertEqual(manifest["schema_version"], 1)
            self.assertEqual(manifest["scene_id"], "edge_rect")
            self.assertEqual(manifest["seed"], 123)
            self.assertFalse(manifest["hardware"])
            self.assertFalse(manifest["simulated_timing"])
            self.assertFalse(manifest["simulated_memory"])
            self.assertEqual(manifest["frame_sha256"], hashlib.sha256(frame).hexdigest())
            self.assertEqual(manifest["profile_hash"], hashlib.sha256(json.dumps(
                manifest["profile"], sort_keys=True, separators=(",", ":")
            ).encode()).hexdigest())
            self.assertEqual(json.loads((first / "result.json").read_text())["status"], "RENDERED")
            self.assertEqual({p.name for p in first.iterdir()},
                             {"frame.rgb565", "frame.png", "manifest.json", "result.json"})
            self.assertEqual((first / "manifest.json").read_bytes(), (second / "manifest.json").read_bytes())

    def test_manifest_is_reproducible_for_output_directories_inside_repository(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as root:
            first, second = Path(root) / "first", Path(root) / "second"
            for output in (first, second):
                result = invoke("render", "--scene", "edge_rect", "--seed", "123", "--out", output)
                self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", "replace"))
            self.assertEqual((first / "manifest.json").read_bytes(),
                             (second / "manifest.json").read_bytes())

    def test_render_distinguishes_unsupported_and_skipped_scenes(self):
        with tempfile.TemporaryDirectory() as root:
            unsupported = invoke("render", "--scene", "no_such_scene", "--out", Path(root) / "u")
            skipped = invoke("render", "--scene", "text_edges", "--out", Path(root) / "s")
            self.assertEqual(unsupported.returncode, 2)
            self.assertEqual(json.loads((Path(root) / "u/result.json").read_text())["status"], "UNSUPPORTED")
            self.assertEqual(skipped.returncode, 3)
            self.assertEqual(json.loads((Path(root) / "s/result.json").read_text())["status"], "SKIP")
            self.assertFalse((Path(root) / "s/frame.rgb565").exists())

    def test_shared_s3_s4_export_reviewable_deterministic_frames(self):
        with tempfile.TemporaryDirectory() as root:
            for scene in ("s1", "s2", "s3", "s4"):
                outputs = [Path(root) / scene / str(index) for index in range(2)]
                for output in outputs:
                    result = invoke("render", "--scene", scene, "--seed", "0", "--out", output)
                    self.assertEqual(result.returncode, 0,
                                     result.stderr.decode("utf-8", "replace"))
                    self.assertEqual(len((output / "frame.rgb565").read_bytes()), 115200)
                    self.assertTrue((output / "frame.png").is_file())
                    manifest = json.loads((output / "manifest.json").read_text())
                    self.assertEqual(manifest["review_status"], "VISUAL_REVIEW_REQUIRED")
                    report = json.loads((output / "result.json").read_text())
                    self.assertEqual(report["status"], "RENDERED")
                    self.assertEqual(report["review_status"], "VISUAL_REVIEW_REQUIRED")
                self.assertEqual((outputs[0] / "frame.rgb565").read_bytes(),
                                 (outputs[1] / "frame.rgb565").read_bytes())

    def test_invalid_seed_is_usage_error_without_output(self):
        with tempfile.TemporaryDirectory() as root:
            output = Path(root) / "render"
            result = invoke("render", "--scene", "edge_rect", "--seed", "-1", "--out", output)
            self.assertEqual(result.returncode, 2)
            self.assertIn(b"seed", result.stderr.lower())
            self.assertFalse(output.exists())

    def test_diff_reports_one_pixel_mutation_and_preserves_inputs(self):
        with tempfile.TemporaryDirectory() as root:
            expected_dir, actual_dir, report_dir = (Path(root) / name for name in ("e", "a", "d"))
            baseline = bytes(240 * 240 * 2)
            write_test_frame(expected_dir, baseline, approved=True)
            write_test_frame(actual_dir, baseline)
            actual_frame = actual_dir / "frame.rgb565"
            same = invoke("diff", "--expected", expected_dir / "frame.rgb565",
                          "--actual", actual_frame, "--out", report_dir)
            self.assertEqual(same.returncode, 0, same.stderr.decode("utf-8", "replace"))
            self.assertEqual(json.loads((report_dir / "report.json").read_text())["status"], "PASS")
            frame = bytearray(actual_frame.read_bytes())
            frame[4] ^= 1
            actual_frame.write_bytes(frame)
            manifest_path = actual_dir / "manifest.json"
            manifest = json.loads(manifest_path.read_text())
            manifest["frame_sha256"] = hashlib.sha256(frame).hexdigest()
            manifest_path.write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n")
            expected_before = (expected_dir / "frame.rgb565").read_bytes()
            result = invoke("diff", "--expected", expected_dir / "frame.rgb565",
                            "--actual", actual_frame, "--out", report_dir)
            self.assertEqual(result.returncode, 1)
            report = json.loads((report_dir / "report.json").read_text())
            self.assertEqual(report["status"], "FAIL")
            self.assertEqual(report["different_pixels"], 1)
            self.assertEqual((report["first_difference"]["x"], report["first_difference"]["y"]), (2, 0))
            self.assertEqual((expected_dir / "frame.rgb565").read_bytes(), expected_before)
            self.assertTrue((report_dir / "diff.png").is_file())

    def test_generated_frame_cannot_approve_itself_as_a_baseline(self):
        with tempfile.TemporaryDirectory() as root:
            expected, actual = Path(root) / "e", Path(root) / "a"
            for output in (expected, actual):
                self.assertEqual(invoke("render", "--scene", "solid_rgb565", "--out", output).returncode, 0)
            result = invoke("diff", "--expected", expected / "frame.rgb565",
                            "--actual", actual / "frame.rgb565", "--out", Path(root) / "d")
            self.assertEqual(result.returncode, 4)
            self.assertEqual(json.loads((Path(root) / "d/report.json").read_text())["status"],
                             "NO_BASELINE")

    def test_missing_baseline_is_not_pass(self):
        with tempfile.TemporaryDirectory() as root:
            actual_dir = Path(root) / "a"
            self.assertEqual(invoke("render", "--scene", "solid_rgb565", "--out", actual_dir).returncode, 0)
            result = invoke("diff", "--expected", Path(root) / "missing.rgb565",
                            "--actual", actual_dir / "frame.rgb565", "--out", Path(root) / "d")
            self.assertEqual(result.returncode, 4)
            self.assertEqual(json.loads((Path(root) / "d/report.json").read_text())["status"], "NO_BASELINE")

    def test_profile_mismatch_and_frame_checksum_mismatch_are_inconclusive(self):
        with tempfile.TemporaryDirectory() as root:
            expected, actual, report_dir = (Path(root) / name for name in ("e", "a", "d"))
            for output in (expected, actual):
                self.assertEqual(invoke("render", "--scene", "solid_rgb565", "--out", output).returncode, 0)
            actual_manifest_path = actual / "manifest.json"
            actual_manifest = json.loads(actual_manifest_path.read_text())
            actual_manifest["profile"]["name"] = "different-profile"
            actual_manifest["profile_hash"] = hashlib.sha256(json.dumps(
                actual_manifest["profile"], sort_keys=True, separators=(",", ":")
            ).encode()).hexdigest()
            actual_manifest_path.write_text(json.dumps(actual_manifest))
            result = invoke("diff", "--expected", expected / "frame.rgb565",
                            "--actual", actual / "frame.rgb565", "--out", report_dir)
            self.assertEqual(result.returncode, 5)
            self.assertEqual(json.loads((report_dir / "report.json").read_text())["status"],
                             "INCONCLUSIVE")
            actual_manifest["profile"] = json.loads((expected / "manifest.json").read_text())["profile"]
            actual_manifest["profile_hash"] = json.loads((expected / "manifest.json").read_text())["profile_hash"]
            actual_manifest["frame_sha256"] = "0" * 64
            actual_manifest_path.write_text(json.dumps(actual_manifest))
            result = invoke("diff", "--expected", expected / "frame.rgb565",
                            "--actual", actual / "frame.rgb565", "--out", report_dir)
            self.assertEqual(result.returncode, 5)
            self.assertIn(b"checksum", result.stderr.lower())

    def test_different_scene_ids_cannot_produce_a_pass(self):
        with tempfile.TemporaryDirectory() as root:
            expected, actual, report_dir = (Path(root) / name for name in ("e", "a", "d"))
            frame = bytes(240 * 240 * 2)
            write_test_frame(expected, frame, approved=True)
            write_test_frame(actual, frame)
            manifest_path = actual / "manifest.json"
            manifest = json.loads(manifest_path.read_text())
            manifest["scene_id"] = "other_scene"
            manifest_path.write_text(json.dumps(manifest))
            result = invoke("diff", "--expected", expected / "frame.rgb565",
                            "--actual", actual / "frame.rgb565", "--out", report_dir)
            self.assertEqual(result.returncode, 5)
            self.assertEqual(json.loads((report_dir / "report.json").read_text())["status"],
                             "INCONCLUSIVE")

    def test_output_artifact_symlink_cannot_escape_output_directory(self):
        with tempfile.TemporaryDirectory() as root:
            output = Path(root) / "out"
            output.mkdir()
            outside = Path(root) / "outside.bin"
            outside.write_bytes(b"preserve")
            (output / "frame.rgb565").symlink_to(outside)
            result = invoke("render", "--scene", "solid_rgb565", "--out", output)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(b"symlink", result.stderr.lower())
            self.assertEqual(outside.read_bytes(), b"preserve")

    def test_output_directory_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            outside = Path(root) / "outside"
            outside.mkdir()
            link = Path(root) / "output"
            link.symlink_to(outside, target_is_directory=True)
            result = invoke("render", "--scene", "solid_rgb565", "--out", link)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(b"symlink", result.stderr.lower())
            self.assertEqual(list(outside.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
