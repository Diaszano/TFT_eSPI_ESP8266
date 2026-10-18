"""Canonical RGB565 frame validation and deterministic PNG encoding."""

import json
import hashlib
import re
import struct
import zlib
from collections import namedtuple
from pathlib import Path


DEFAULT_WIDTH = 240
DEFAULT_HEIGHT = 240
MAX_FRAME_BYTES = DEFAULT_WIDTH * DEFAULT_HEIGHT * 2
MAX_GOLDEN_METADATA_BYTES = 64 * 1024
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
CompareResult = namedtuple(
    "CompareResult",
    "status total_pixels diff_pixels diff_percent first_xy expected_pixel actual_pixel bbox channels",
)


def _pixel_count(width, height):
    if (not isinstance(width, int) or isinstance(width, bool) or
            not isinstance(height, int) or isinstance(height, bool) or
            width <= 0 or height <= 0 or width > DEFAULT_WIDTH or height > DEFAULT_HEIGHT):
        raise ValueError("frame dimensions must be within 1..240")
    return width * height


def validate_frame(data, width=DEFAULT_WIDTH, height=DEFAULT_HEIGHT):
    """Validate a row-major little-endian RGB565 frame and return its pixels."""
    if not isinstance(data, (bytes, bytearray, memoryview)):
        raise ValueError("frame must be a bytes-like object")
    pixels = _pixel_count(width, height)
    expected = width * height * 2
    if expected > MAX_FRAME_BYTES or len(data) != expected:
        raise ValueError("RGB565 frame length does not match dimensions")
    return pixels


def decode_565le(data):
    """Decode little-endian RGB565 bytes to integer pixels."""
    if not isinstance(data, (bytes, bytearray, memoryview)):
        raise ValueError("frame must be a bytes-like object")
    if len(data) % 2 or len(data) > MAX_FRAME_BYTES:
        raise ValueError("RGB565 data must contain complete pixels within frame limits")
    return [data[i] | (data[i + 1] << 8) for i in range(0, len(data), 2)]


def rgb565_to_rgb888(pixel):
    """Expand RGB565 channels to 8-bit RGB using the versioned linear rule."""
    if not isinstance(pixel, int) or isinstance(pixel, bool) or not 0 <= pixel <= 0xFFFF:
        raise ValueError("pixel must be an unsigned 16-bit integer")
    red = (pixel >> 11) & 0x1F
    green = (pixel >> 5) & 0x3F
    blue = pixel & 0x1F
    return ((red * 255 + 15) // 31, (green * 255 + 31) // 63,
            (blue * 255 + 15) // 31)


def _chunk(kind, data):
    return (struct.pack(">I", len(data)) + kind + data +
            struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF))


def _zlib_stored(data):
    stream = bytearray(b"\x78\x01")
    for offset in range(0, len(data), 65535):
        block = data[offset:offset + 65535]
        stream.append(1 if offset + len(block) == len(data) else 0)
        stream.extend(struct.pack("<HH", len(block), len(block) ^ 0xFFFF))
        stream.extend(block)
    stream.extend(struct.pack(">I", zlib.adler32(data) & 0xFFFFFFFF))
    return bytes(stream)


def encode_png_rgb565(data, width=DEFAULT_WIDTH, height=DEFAULT_HEIGHT):
    """Encode canonical RGB565 bytes as deterministic RGB8 PNG (filter 0)."""
    validate_frame(data, width, height)
    rows = bytearray()
    stride = width * 2
    for y in range(height):
        rows.append(0)
        for offset in range(y * stride, (y + 1) * stride, 2):
            red, green, blue = rgb565_to_rgb888(data[offset] | (data[offset + 1] << 8))
            rows.extend((red, green, blue))
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (PNG_SIGNATURE + _chunk(b"IHDR", header) +
            _chunk(b"IDAT", _zlib_stored(rows)) + _chunk(b"IEND", b""))


def _frame_pixels(frame, width, height):
    count = _pixel_count(width, height)
    if isinstance(frame, (bytes, bytearray, memoryview)):
        validate_frame(frame, width, height)
        return decode_565le(frame)
    if not isinstance(frame, (list, tuple)) or len(frame) != count:
        raise ValueError("RGB565 frame pixel count does not match dimensions")
    if any(not isinstance(pixel, int) or isinstance(pixel, bool) or
           pixel < 0 or pixel > 0xFFFF for pixel in frame):
        raise ValueError("RGB565 pixels must be unsigned 16-bit integers")
    return frame


def compare_frames(expected, actual, width, height, expected_profile_hash=None,
                   actual_profile_hash=None):
    """Compare canonical frames; incompatible profiles are never pixel-compared."""
    left = _frame_pixels(expected, width, height)
    right = _frame_pixels(actual, width, height)
    total = len(left)
    if ((expected_profile_hash is None) != (actual_profile_hash is None) or
            (expected_profile_hash is not None and expected_profile_hash != actual_profile_hash)):
        return CompareResult("INCONCLUSIVE", total, None, None, None, None, None, None, {})

    differences = []
    channels = {
        name: {"changed_pixels": 0, "absolute_difference": 0, "maximum_difference": 0}
        for name in ("red", "green", "blue")
    }
    for index, (expected_pixel, actual_pixel) in enumerate(zip(left, right)):
        if expected_pixel == actual_pixel:
            continue
        x, y = index % width, index // width
        differences.append((index, x, y, expected_pixel, actual_pixel))
        expected_rgb = rgb565_to_rgb888(expected_pixel)
        actual_rgb = rgb565_to_rgb888(actual_pixel)
        for index_channel, name in enumerate(("red", "green", "blue")):
            delta = abs(expected_rgb[index_channel] - actual_rgb[index_channel])
            channel = channels[name]
            if delta:
                channel["changed_pixels"] += 1
                channel["absolute_difference"] += delta
                channel["maximum_difference"] = max(channel["maximum_difference"], delta)

    if not differences:
        return CompareResult("PASS", total, 0, 0.0, None, None, None, None, channels)
    first = differences[0]
    xs = [item[1] for item in differences]
    ys = [item[2] for item in differences]
    return CompareResult(
        "FAIL", total, len(differences), len(differences) * 100.0 / total,
        (first[1], first[2]), first[3], first[4],
        (min(xs), min(ys), max(xs), max(ys)), channels,
    )


def compare_golden(actual, golden_path, profile_hash, width, height):
    """Compare only against a separately approved, checksum-verified golden."""
    total = _pixel_count(width, height)
    validate_frame(actual, width, height)
    golden = Path(golden_path)
    metadata_path = golden.with_suffix(".json")
    if not golden.exists() and not metadata_path.exists():
        return CompareResult("NO_BASELINE", total, None, None, None,
                            None, None, None, {})
    try:
        if golden.is_symlink() or metadata_path.is_symlink():
            raise ValueError("golden paths cannot be symlinks")
        if not golden.is_file() or not metadata_path.is_file():
            raise ValueError("golden frame or metadata is missing")
        if golden.stat().st_size > MAX_FRAME_BYTES or metadata_path.stat().st_size > MAX_GOLDEN_METADATA_BYTES:
            raise ValueError("golden exceeds size limit")
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        required = ("schema_version", "status", "scene_id", "width", "height", "profile_hash",
                    "source_revision", "baseline_sha256", "approved_by", "approval_reason")
        if not isinstance(metadata, dict) or any(key not in metadata for key in required):
            raise ValueError("golden metadata is incomplete")
        if (type(metadata["schema_version"]) is not int or metadata["schema_version"] != 1 or
                metadata["status"] != "APPROVED"):
            raise ValueError("golden is not explicitly approved")
        if (type(metadata["width"]) is not int or type(metadata["height"]) is not int or
                (metadata["width"], metadata["height"]) != (width, height)):
            raise ValueError("golden dimensions do not match requested profile")
        if (not isinstance(metadata["profile_hash"], str) or
                not re.fullmatch(r"[0-9a-f]{64}", metadata["profile_hash"]) or
                metadata["profile_hash"] != profile_hash):
            raise ValueError("golden profile hash does not match")
        if (not isinstance(metadata["source_revision"], str) or
                not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", metadata["source_revision"]) or
                not isinstance(metadata["scene_id"], str) or
                not re.fullmatch(r"[a-z0-9_]+", metadata["scene_id"]) or
                not isinstance(metadata["approved_by"], str) or not metadata["approved_by"].strip() or
                not isinstance(metadata["approval_reason"], str) or not metadata["approval_reason"].strip()):
            raise ValueError("golden approval provenance is invalid")
        baseline = golden.read_bytes()
        validate_frame(baseline, width, height)
        if (not isinstance(metadata["baseline_sha256"], str) or
                not re.fullmatch(r"[0-9a-f]{64}", metadata["baseline_sha256"]) or
                hashlib.sha256(baseline).hexdigest() != metadata["baseline_sha256"]):
            raise ValueError("golden checksum does not match metadata")
        validate_frame(actual, width, height)
        return compare_frames(baseline, actual, width, height, profile_hash, metadata["profile_hash"])
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return CompareResult("INCONCLUSIVE", total, None, None, None,
                            None, None, None, {})


def _comparison_dict(result, expected_profile_hash=None, actual_profile_hash=None):
    first = None
    if result.first_xy is not None:
        first = {
            "x": result.first_xy[0], "y": result.first_xy[1],
            "expected_rgb565": "0x{:04X}".format(result.expected_pixel),
            "actual_rgb565": "0x{:04X}".format(result.actual_pixel),
        }
    bbox = None
    if result.bbox is not None:
        bbox = dict(zip(("left", "top", "right", "bottom"), result.bbox))
    return {
        "schema_version": 1, "status": result.status,
        "total_pixels": result.total_pixels, "different_pixels": result.diff_pixels,
        "difference_percent": result.diff_percent, "first_difference": first,
        "bounding_box": bbox, "channel_differences": result.channels,
        "expected_profile_hash": expected_profile_hash,
        "actual_profile_hash": actual_profile_hash,
    }


def _canonical_frame_bytes(frame, width, height):
    pixels = _frame_pixels(frame, width, height)
    packed = bytearray(len(pixels) * 2)
    for index, pixel in enumerate(pixels):
        packed[index * 2] = pixel & 0xFF
        packed[index * 2 + 1] = pixel >> 8
    return bytes(packed)


def write_comparison_artifacts(expected, actual, width, height, output_dir,
                               expected_profile_hash=None, actual_profile_hash=None):
    """Write reports and a red/black heatmap separately from both input frames."""
    result = compare_frames(expected, actual, width, height,
                           expected_profile_hash, actual_profile_hash)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    report = _comparison_dict(result, expected_profile_hash, actual_profile_hash)
    report["expected_frame_sha256"] = hashlib.sha256(_canonical_frame_bytes(expected, width, height)).hexdigest()
    report["actual_frame_sha256"] = hashlib.sha256(_canonical_frame_bytes(actual, width, height)).hexdigest()
    if result.status != "INCONCLUSIVE":
        pixels = _frame_pixels(expected, width, height)
        other = _frame_pixels(actual, width, height)
        diff = bytearray()
        for a, b in zip(pixels, other):
            color = 0xF800 if a != b else 0
            diff.extend((color & 0xFF, color >> 8))
        (output / "diff.png").write_bytes(encode_png_rgb565(diff, width, height))
    (output / "report.json").write_text(
        json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    first = report["first_difference"]
    lines = ["# RGB565 comparison", "", "status: {}".format(result.status),
             "total_pixels: {}".format(result.total_pixels),
             "different_pixels: {}".format(result.diff_pixels),
             "difference_percent: {}".format(result.diff_percent),
             "bounding_box: {}".format(result.bbox)]
    if first:
        lines.extend(("first_difference: ({x}, {y})".format(**first),
                      "expected_rgb565: {}".format(first["expected_rgb565"]),
                      "actual_rgb565: {}".format(first["actual_rgb565"])))
    (output / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return result
