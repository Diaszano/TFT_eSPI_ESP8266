#!/usr/bin/env python3
"""Offline CLI for production-rendered ST7789 frames and exact RGB565 diffs."""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from simulator.tools.snapshots import (
    DEFAULT_HEIGHT,
    DEFAULT_WIDTH,
    MAX_FRAME_BYTES,
    encode_png_rgb565,
    validate_frame,
    write_comparison_artifacts,
)


RUNNER = ROOT / ".build/simulator/debug/simulator_runner"
PROFILE_FILE = ROOT / "simulator/profiles/nodemcu-st7789-240x240.json"
SIMULATOR_VERSION = "0.1.0"
MAX_MANIFEST_BYTES = 64 * 1024
SCENE_TIMEOUT_SECONDS = 5
EXIT_FAIL = 1
EXIT_UNSUPPORTED = 2
EXIT_SKIP = 3
EXIT_NO_BASELINE = 4
EXIT_INCONCLUSIVE = 5
VISUAL_REVIEW_SCENES = {"s1", "s2", "s3", "s4"}


def _canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _sha256(data):
    return hashlib.sha256(data).hexdigest()


def _git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, check=True, timeout=5).stdout


def _source_identity():
    source_sha = _git("rev-parse", "HEAD").decode("ascii").strip()
    dirty = bool(_git("status", "--porcelain", "--untracked-files=no"))
    return source_sha, dirty


def _profile():
    raw = PROFILE_FILE.read_bytes()
    if len(raw) > MAX_MANIFEST_BYTES:
        raise ValueError("profile file exceeds size limit")
    profile = json.loads(raw.decode("utf-8"))
    validate_profile(profile)
    return profile


def validate_profile(profile):
    if not isinstance(profile, dict) or profile.get("pixel_format") != "RGB565":
        raise ValueError("profile must describe RGB565")
    visible = profile.get("visible")
    if not isinstance(visible, dict):
        raise ValueError("profile is missing visible dimensions")
    width, height = visible.get("width"), visible.get("height")
    if (not isinstance(width, int) or isinstance(width, bool) or
            not isinstance(height, int) or isinstance(height, bool) or
            not 1 <= width <= DEFAULT_WIDTH or not 1 <= height <= DEFAULT_HEIGHT):
        raise ValueError("profile visible dimensions are invalid")
    gram = profile.get("gram")
    if (not isinstance(gram, dict) or
            any(not isinstance(gram.get(key), int) or isinstance(gram.get(key), bool) or
                gram[key] < visible[key] for key in ("width", "height"))):
        raise ValueError("profile GRAM dimensions are invalid")
    if profile.get("supported_rotations") != [0, 1, 2, 3]:
        raise ValueError("profile rotation set is unsupported")
    return width, height


def _prepare_output(path, names):
    requested = Path(path).expanduser().absolute()
    if any(part.is_symlink() for part in (requested, *requested.parents)):
        raise ValueError("output path cannot contain symlinks")
    output = requested.resolve()
    output.mkdir(parents=True, exist_ok=True)
    if not output.is_dir():
        raise ValueError("output path is not a directory")
    for name in names:
        target = output / name
        if target.is_symlink():
            raise ValueError("refusing output artifact symlink: {}".format(name))
        if target.resolve().parent != output:
            raise ValueError("output artifact escapes output directory")
        if target.exists() and not target.is_file():
            raise ValueError("output artifact is not a regular file: {}".format(name))
    return output


def _write_bytes(output, name, data):
    target = output / name
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    flags |= getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(str(target), flags, 0o644)
    with os.fdopen(descriptor, "wb") as destination:
        destination.write(data)


def _write_json(output, name, value):
    _write_bytes(output, name, (json.dumps(value, sort_keys=True, indent=2) + "\n").encode("utf-8"))


def _status_report(output, status, message, extra=None):
    report = {"schema_version": 1, "status": status, "diagnostic": message}
    if extra:
        report.update(extra)
    _write_json(output, "report.json", report)
    _write_bytes(output, "report.md", ("# Simulator report\n\nstatus: {}\ndiagnostic: {}\n".format(
        status, message)).encode("utf-8"))
    return report


def _runner_call(arguments, timeout=SCENE_TIMEOUT_SECONDS):
    if not RUNNER.is_file():
        raise RuntimeError("simulator runner is missing; build simulator_runner first")
    return subprocess.run([str(RUNNER), *arguments], cwd=ROOT, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, timeout=timeout, check=False)


def _scene_ids():
    result = _runner_call(["--list-scenes"])
    if result.returncode != 0:
        raise RuntimeError("scene registry failed: {}".format(result.stderr.decode("utf-8", "replace")))
    return {line for line in result.stdout.decode("ascii").splitlines() if line}


def _render(args):
    try:
        output = _prepare_output(args.out, ("frame.rgb565", "frame.png", "manifest.json", "result.json"))
        profile = _profile()
        width, height = validate_profile(profile)
        if args.scene not in _scene_ids():
            _write_json(output, "result.json", {"schema_version": 1, "status": "UNSUPPORTED",
                                                "scene_id": args.scene, "reason": "unknown scene id"})
            print("UNSUPPORTED scene={} reason=unknown scene id".format(args.scene), file=sys.stderr)
            return EXIT_UNSUPPORTED
        command = ["--scene", args.scene, "--seed", str(args.seed), "--rotation", str(args.rotation),
                   "--rgb565-stdout"]
        result = _runner_call(command)
        if result.returncode == EXIT_SKIP:
            message = result.stderr.decode("utf-8", "replace").strip()
            _write_json(output, "result.json", {"schema_version": 1, "status": "SKIP",
                                                "scene_id": args.scene, "seed": args.seed,
                                                "rotation": args.rotation, "reason": message})
            print(message, file=sys.stderr)
            return EXIT_SKIP
        if result.returncode == EXIT_UNSUPPORTED:
            message = result.stderr.decode("utf-8", "replace").strip()
            _write_json(output, "result.json", {"schema_version": 1, "status": "UNSUPPORTED",
                                                "scene_id": args.scene, "reason": message})
            print(message, file=sys.stderr)
            return EXIT_UNSUPPORTED
        if result.returncode == EXIT_FAIL:
            message = result.stderr.decode("utf-8", "replace").strip()
            _write_json(output, "result.json", {"schema_version": 1, "status": "FAIL",
                                                "scene_id": args.scene, "seed": args.seed,
                                                "rotation": args.rotation, "reason": message})
            print(message, file=sys.stderr)
            return EXIT_FAIL
        if result.returncode != 0:
            raise RuntimeError("production renderer failed: {}".format(
                result.stderr.decode("utf-8", "replace").strip()))
        frame = result.stdout
        validate_frame(frame, width, height)
        source_sha, dirty = _source_identity()
        profile_hash = _sha256(_canonical_json(profile))
        manifest = {
            "schema_version": 1, "scene_id": args.scene, "seed": args.seed,
            "rotation": args.rotation, "source_sha": source_sha,
            "source_dirty": dirty,
            "simulator_version": SIMULATOR_VERSION, "profile": profile,
            "profile_hash": profile_hash, "frame_sha256": _sha256(frame),
            "hardware": False, "simulated_timing": False, "simulated_memory": False,
        }
        if args.scene in VISUAL_REVIEW_SCENES:
            manifest["review_status"] = "VISUAL_REVIEW_REQUIRED"
        _write_bytes(output, "frame.rgb565", frame)
        _write_bytes(output, "frame.png", encode_png_rgb565(frame, width, height))
        _write_json(output, "manifest.json", manifest)
        result_report = {"schema_version": 1, "status": "RENDERED",
                         "scene_id": args.scene, "seed": args.seed,
                         "rotation": args.rotation,
                         "frame_sha256": manifest["frame_sha256"]}
        if args.scene in VISUAL_REVIEW_SCENES:
            result_report["review_status"] = "VISUAL_REVIEW_REQUIRED"
        _write_json(output, "result.json", result_report)
        print("RENDERED scene={} seed={} rotation={} frame_sha256={}".format(
            args.scene, args.seed, args.rotation, manifest["frame_sha256"]))
        return 0
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
        print("FAILED render: {}".format(error), file=sys.stderr)
        return EXIT_FAIL


def _load_manifest(path, frame):
    if path.is_symlink() or not path.is_file():
        raise ValueError("manifest is missing or is a symlink")
    if path.stat().st_size > MAX_MANIFEST_BYTES:
        raise ValueError("manifest exceeds size limit")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    required = ("schema_version", "scene_id", "seed", "source_sha", "simulator_version",
                "profile", "profile_hash", "frame_sha256", "hardware",
                "simulated_timing", "simulated_memory")
    if not isinstance(manifest, dict) or any(key not in manifest for key in required):
        raise ValueError("manifest is missing required fields")
    if manifest["schema_version"] != 1 or manifest["hardware"] is not False:
        raise ValueError("manifest schema or hardware flag is invalid")
    if manifest["simulated_timing"] is not False or manifest["simulated_memory"] is not False:
        raise ValueError("manifest simulation flags are invalid")
    if not isinstance(manifest["scene_id"], str) or not manifest["scene_id"]:
        raise ValueError("manifest scene id is invalid")
    if not isinstance(manifest["seed"], int) or isinstance(manifest["seed"], bool) or not 0 <= manifest["seed"] <= 0xFFFFFFFF:
        raise ValueError("manifest seed is invalid")
    if not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", str(manifest["source_sha"])):
        raise ValueError("manifest source SHA is invalid")
    if not isinstance(manifest["simulator_version"], str) or not manifest["simulator_version"]:
        raise ValueError("manifest simulator version is invalid")
    width, height = validate_profile(manifest["profile"])
    profile_hash = _sha256(_canonical_json(manifest["profile"]))
    if manifest["profile_hash"] != profile_hash:
        raise ValueError("manifest profile hash is invalid")
    if not re.fullmatch(r"[0-9a-f]{64}", str(manifest["frame_sha256"])):
        raise ValueError("manifest frame SHA is invalid")
    validate_frame(frame, width, height)
    if _sha256(frame) != manifest["frame_sha256"]:
        raise ValueError("frame checksum does not match manifest")
    return manifest, width, height


def _read_frame(path):
    if path.is_symlink() or not path.is_file():
        raise FileNotFoundError(str(path))
    if path.stat().st_size > MAX_FRAME_BYTES:
        raise ValueError("frame exceeds size limit")
    return path.read_bytes()


def _approved_baseline(manifest):
    approval = manifest.get("golden_approval")
    return (isinstance(approval, dict) and approval.get("status") == "APPROVED" and
            isinstance(approval.get("approved_by"), str) and approval["approved_by"].strip() and
            isinstance(approval.get("approval_reason"), str) and approval["approval_reason"].strip())


def _diff(args):
    try:
        output = _prepare_output(args.out, ("diff.png", "report.json", "report.md"))
    except (OSError, ValueError) as error:
        print("FAILED diff output: {}".format(error), file=sys.stderr)
        return EXIT_FAIL
    expected_path, actual_path = Path(args.expected).expanduser(), Path(args.actual).expanduser()
    if not expected_path.is_file():
        _status_report(output, "NO_BASELINE", "expected frame is missing")
        print("NO_BASELINE expected frame is missing", file=sys.stderr)
        return EXIT_NO_BASELINE
    if not actual_path.is_file():
        _status_report(output, "INCONCLUSIVE", "actual frame is missing")
        print("INCONCLUSIVE actual frame is missing", file=sys.stderr)
        return EXIT_INCONCLUSIVE
    try:
        expected = _read_frame(expected_path)
        actual = _read_frame(actual_path)
        expected_manifest_path = Path(args.expected_manifest).expanduser() if args.expected_manifest else expected_path.parent / "manifest.json"
        actual_manifest_path = Path(args.actual_manifest).expanduser() if args.actual_manifest else actual_path.parent / "manifest.json"
        expected_manifest, ew, eh = _load_manifest(expected_manifest_path, expected)
        actual_manifest, aw, ah = _load_manifest(actual_manifest_path, actual)
        if (ew, eh) != (aw, ah) or expected_manifest["profile_hash"] != actual_manifest["profile_hash"]:
            _status_report(output, "INCONCLUSIVE", "frame profiles or dimensions do not match", {
                "expected_profile_hash": expected_manifest["profile_hash"],
                "actual_profile_hash": actual_manifest["profile_hash"],
            })
            print("INCONCLUSIVE frame profiles or dimensions do not match", file=sys.stderr)
            return EXIT_INCONCLUSIVE
        if expected_manifest["scene_id"] != actual_manifest["scene_id"]:
            _status_report(output, "INCONCLUSIVE", "frame scene identifiers do not match", {
                "expected_scene_id": expected_manifest["scene_id"],
                "actual_scene_id": actual_manifest["scene_id"],
            })
            print("INCONCLUSIVE frame scene identifiers do not match", file=sys.stderr)
            return EXIT_INCONCLUSIVE
        if not _approved_baseline(expected_manifest):
            _status_report(output, "NO_BASELINE", "expected frame has no explicit golden approval")
            print("NO_BASELINE expected frame has no explicit golden approval", file=sys.stderr)
            return EXIT_NO_BASELINE
        result = write_comparison_artifacts(expected, actual, ew, eh, output,
                                            expected_manifest["profile_hash"],
                                            actual_manifest["profile_hash"])
        print("{} different_pixels={} bbox={}".format(result.status, result.diff_pixels, result.bbox))
        return 0 if result.status == "PASS" else EXIT_FAIL
    except (OSError, ValueError, json.JSONDecodeError) as error:
        _status_report(output, "INCONCLUSIVE", str(error))
        print("INCONCLUSIVE {}".format(error), file=sys.stderr)
        return EXIT_INCONCLUSIVE


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("list-scenes", help="list production scene identifiers")
    render = commands.add_parser("render", help="render a production scene to RGB565/PNG")
    render.add_argument("--scene", required=True)
    render.add_argument("--seed", type=int, default=0)
    render.add_argument("--rotation", type=int, choices=range(4), default=0)
    render.add_argument("--profile", default="nodemcu-st7789-240x240",
                        choices=("nodemcu-st7789-240x240",))
    render.add_argument("--out", required=True)
    diff = commands.add_parser("diff", help="compare two canonical RGB565 frames")
    diff.add_argument("--expected", required=True)
    diff.add_argument("--actual", required=True)
    diff.add_argument("--expected-manifest")
    diff.add_argument("--actual-manifest")
    diff.add_argument("--out", required=True)
    refs = commands.add_parser("render-references", help="generate and verify S1-S4 reference image suite")
    refs.add_argument("--seed", type=int, default=0)
    refs.add_argument("--rotation", type=int, choices=range(4), default=0)
    refs.add_argument("--out", required=True)
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "list-scenes":
        try:
            result = _runner_call(["--list-scenes"])
            if result.returncode != 0:
                raise RuntimeError(result.stderr.decode("utf-8", "replace"))
            sys.stdout.buffer.write(result.stdout)
            return 0
        except (OSError, RuntimeError, subprocess.TimeoutExpired) as error:
            print("FAILED list-scenes: {}".format(error), file=sys.stderr)
            return EXIT_FAIL
    if args.command == "render":
        if not 0 <= args.seed <= 0xFFFFFFFF:
            parser.error("seed must be in 0..4294967295")
        return _render(args)
    if args.command == "render-references":
        if not 0 <= args.seed <= 0xFFFFFFFF:
            parser.error("seed must be in 0..4294967295")
        from simulator.tools.reference_images import generate_reference_suite, verify_suite_artifacts
        generate_reference_suite(args.out, seed=args.seed, rotation=args.rotation)
        audit = verify_suite_artifacts(args.out)
        return 0 if audit["status"] == "PASS" else EXIT_FAIL
    return _diff(args)


if __name__ == "__main__":
    raise SystemExit(main())
