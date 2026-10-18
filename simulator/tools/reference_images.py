#!/usr/bin/env python3
"""Objective visual reference image generator and independent acceptance verifier for S1-S4."""

import datetime
import hashlib
import json
import re
import struct
import subprocess
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from simulator.tools.snapshots import (
    DEFAULT_HEIGHT,
    DEFAULT_WIDTH,
    MAX_FRAME_BYTES,
    PNG_SIGNATURE,
    decode_565le,
    encode_png_rgb565,
    rgb565_to_rgb888,
    validate_frame,
)

RUNNER = ROOT / ".build/simulator/debug/simulator_runner"
PROFILE_FILE = ROOT / "simulator/profiles/nodemcu-st7789-240x240.json"
GLCDFONT_FILE = ROOT / "src/Fonts/glcdfont.inc"
FONT16_FILE = ROOT / "src/Fonts/Font16.inc"

SIMULATOR_VERSION = "0.1.0"
ANNOTATION_VERSION = "1.0.0"
REFERENCE_SCENES = ("s1", "s2", "s3", "s4")

DISPLAY_SCALE = 4
DISPLAY_WIDTH = DEFAULT_WIDTH * DISPLAY_SCALE
DISPLAY_HEIGHT = DEFAULT_HEIGHT * DISPLAY_SCALE
DISPLAY_X0 = 88
DISPLAY_Y0 = 120
DISPLAY_AREA_RECT = (DISPLAY_X0, DISPLAY_Y0, DISPLAY_WIDTH, DISPLAY_HEIGHT)

CANVAS_WIDTH = 2120
CANVAS_HEIGHT = 1140

TITLE_SCALE_X = 3
TITLE_SCALE_Y = 4
TITLE_TEXT_MIN_HEIGHT_PX = 8 * TITLE_SCALE_Y  # 32 px (>= 26 px requirement)

ANNOTATION_SCALE_X = 2
ANNOTATION_SCALE_Y = 3
ANNOTATION_TEXT_MIN_HEIGHT_PX = 8 * ANNOTATION_SCALE_Y  # 24 px (>= 18 px requirement)

# Logical TFT_eSPI RGB565 constants
TFT_BLACK = 0x0000
TFT_WHITE = 0xFFFF
TFT_RED = 0xF800
TFT_GREEN = 0x07E0
TFT_BLUE = 0x001F
TFT_CYAN = 0x07FF
TFT_MAGENTA = 0xF81F
TFT_YELLOW = 0xFFE0
TFT_DARKGREY = 0x7BEF

BG_CANVAS_RGB = (14, 18, 24)
BG_PANEL_RGB = (18, 22, 30)
BG_CARD_RGB = (24, 30, 42)
FG_TEXT_RGB = (245, 247, 250)
FG_MUTED_RGB = (196, 208, 224)
FG_ACCENT_RGB = (110, 231, 255)
BORDER_RGB = (140, 156, 180)


def expected_visible565(color):
    """Configured BGR MADCTL and BGR panel order yield logical RGB565."""
    return color


def _sha256(data):
    return hashlib.sha256(data).hexdigest()


def _load_glcdfont():
    text = GLCDFONT_FILE.read_text(encoding="utf-8")
    start = text.index("font[]")
    values = [int(m, 16) for m in re.findall(r"0x[0-9A-Fa-f]{2}", text[start:])]
    if len(values) < 256 * 5:
        raise RuntimeError("glcdfont.inc has fewer than 1280 bytes")
    return values[: 256 * 5]


def _load_font16():
    text = FONT16_FILE.read_text(encoding="utf-8")
    text = re.sub(r"//[^\n]*", "", text)
    text = re.sub(r"#else.*?#endif", "", text, flags=re.S)
    text = re.sub(r"#[^\n]*", "", text)
    wid_match = re.search(r"widtbl_f16\[96\]\s*=\s*\{([^}]+)\}", text, flags=re.S)
    if not wid_match:
        raise RuntimeError("widtbl_f16 not found in Font16.inc")
    widths = [int(x) for x in re.findall(r"\b\d+\b", wid_match.group(1))]
    if len(widths) != 96:
        raise RuntimeError(f"Expected 96 Font 2 widths, got {len(widths)}")
    glyphs = {}
    for code in range(0x20, 0x80):
        pattern = rf"chr_f16_{code:02X}\[\d+\]\s*=\s*\{{([^}}]+)\}}"
        m = re.search(pattern, text, flags=re.S)
        if not m:
            raise RuntimeError(f"Missing chr_f16_{code:02X} in Font16.inc")
        glyphs[code] = [int(x, 16) for x in re.findall(r"0x[0-9A-Fa-f]{2}", m.group(1))]
    return widths, glyphs


GLCD_FONT = _load_glcdfont()
FONT2_WIDTHS, FONT2_GLYPHS = _load_font16()


def _srgb_channel_luminance(c):
    v = c / 255.0
    return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4


def relative_luminance_rgb888(rgb):
    r, g, b = rgb
    return (
        0.2126 * _srgb_channel_luminance(r)
        + 0.7152 * _srgb_channel_luminance(g)
        + 0.0722 * _srgb_channel_luminance(b)
    )


def contrast_ratio_rgb888(fg_rgb, bg_rgb):
    l1 = relative_luminance_rgb888(fg_rgb)
    l2 = relative_luminance_rgb888(bg_rgb)
    bright, dark = (l1, l2) if l1 >= l2 else (l2, l1)
    return (bright + 0.05) / (dark + 0.05)


def decode_png_rgb888(png_bytes):
    """Independently decode an 8-bit RGB PNG (filter 0) and return dimensions + RGB888 tuples."""
    if not isinstance(png_bytes, (bytes, bytearray, memoryview)):
        raise ValueError("PNG data must be bytes-like")
    raw = bytes(png_bytes)
    if not raw.startswith(PNG_SIGNATURE):
        raise ValueError("Invalid PNG signature")
    offset = len(PNG_SIGNATURE)
    width = height = bit_depth = color_type = None
    idat_parts = []
    seen_iend = False
    while offset < len(raw):
        if offset + 8 > len(raw):
            raise ValueError("Truncated PNG chunk header")
        length = struct.unpack(">I", raw[offset : offset + 4])[0]
        kind = raw[offset + 4 : offset + 8]
        data_end = offset + 8 + length
        if data_end + 4 > len(raw):
            raise ValueError("Truncated PNG chunk payload")
        payload = raw[offset + 8 : data_end]
        expected_crc = struct.unpack(">I", raw[data_end : data_end + 4])[0]
        actual_crc = zlib.crc32(kind + payload) & 0xFFFFFFFF
        if expected_crc != actual_crc:
            raise ValueError(f"CRC mismatch in PNG chunk {kind!r}")
        if kind == b"IHDR":
            width, height, bit_depth, color_type, comp, filt, interlace = struct.unpack(
                ">IIBBBBB", payload
            )
            if (bit_depth, color_type, comp, filt, interlace) != (8, 2, 0, 0, 0):
                raise ValueError("PNG must be 8-bit non-interlaced RGB")
        elif kind == b"IDAT":
            idat_parts.append(payload)
        elif kind == b"IEND":
            seen_iend = True
            break
        offset = data_end + 4
    if not seen_iend or width is None or height is None:
        raise ValueError("Incomplete PNG stream")
    decompressed = zlib.decompress(b"".join(idat_parts))
    stride = width * 3 + 1
    if len(decompressed) != height * stride:
        raise ValueError("Decoded PNG scanline size mismatch")
    pixels = []
    for y in range(height):
        row_start = y * stride
        if decompressed[row_start] != 0:
            raise ValueError(f"Unsupported PNG filter byte {decompressed[row_start]} at row {y}")
        for x in range(width):
            p = row_start + 1 + x * 3
            pixels.append((decompressed[p], decompressed[p + 1], decompressed[p + 2]))
    return {
        "width": width,
        "height": height,
        "bit_depth": bit_depth,
        "color_type": color_type,
        "pixels": pixels,
    }


def _png_chunk(kind, payload):
    return (
        struct.pack(">I", len(payload))
        + kind
        + payload
        + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
    )


def encode_png_rgb888(rgb_buffer, width, height):
    """Encode an RGB888 bytearray of size width*height*3 as a deterministic 8-bit RGB PNG."""
    rows = bytearray()
    row_bytes = width * 3
    for y in range(height):
        rows.append(0)
        start = y * row_bytes
        rows.extend(rgb_buffer[start : start + row_bytes])
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    compressed = zlib.compress(bytes(rows), level=6)
    return (
        PNG_SIGNATURE
        + _png_chunk(b"IHDR", ihdr)
        + _png_chunk(b"IDAT", compressed)
        + _png_chunk(b"IEND", b"")
    )


def _draw_font1_logical(buf, text, x0, y0, fg_color, bg_color=None):
    """Draw Font 1 (glcdfont 5x7 in 6x8 cell) onto a 240x240 logical RGB565 buffer."""
    cx = x0
    for ch in text:
        code = ord(ch)
        for col in range(6):
            line = GLCD_FONT[code * 5 + col] if col < 5 else 0
            px = cx + col
            if not 0 <= px < DEFAULT_WIDTH:
                continue
            for row in range(8):
                py = y0 + row
                if not 0 <= py < DEFAULT_HEIGHT:
                    continue
                if (line >> row) & 1:
                    buf[py * DEFAULT_WIDTH + px] = expected_visible565(fg_color)
                elif bg_color is not None and bg_color != fg_color:
                    buf[py * DEFAULT_WIDTH + px] = expected_visible565(bg_color)
        cx += 6


def _draw_font2_logical(buf, text, x0, y0, fg_color, bg_color=None):
    """Draw Font 2 (16px high proportional) onto a 240x240 logical RGB565 buffer."""
    cx = x0
    for ch in text:
        code = ord(ch)
        if not 32 <= code <= 127:
            continue
        width = FONT2_WIDTHS[code - 32]
        w_bytes = (width + 6) // 8
        glyph = FONT2_GLYPHS[code]
        for row in range(16):
            py = y0 + row
            if bg_color is not None and bg_color != fg_color and 0 <= py < DEFAULT_HEIGHT:
                for px in range(cx, cx + width):
                    if 0 <= px < DEFAULT_WIDTH:
                        buf[py * DEFAULT_WIDTH + px] = expected_visible565(bg_color)
            if not 0 <= py < DEFAULT_HEIGHT:
                continue
            for k in range(w_bytes):
                line = glyph[w_bytes * row + k]
                if not line:
                    continue
                for bit in range(8):
                    if line & (0x80 >> bit):
                        px = cx + k * 8 + bit
                        if 0 <= px < DEFAULT_WIDTH:
                            buf[py * DEFAULT_WIDTH + px] = expected_visible565(fg_color)
        cx += width


def _build_expected_s1():
    buf = [expected_visible565(TFT_BLACK)] * (DEFAULT_WIDTH * DEFAULT_HEIGHT)
    for y in range(DEFAULT_HEIGHT):
        for x in range(DEFAULT_WIDTH):
            color = TFT_BLACK
            if y == 24:
                color = TFT_RED
            if y == 215:
                color = TFT_GREEN
            if x == 24:
                color = TFT_BLUE
            if x == 215:
                color = TFT_YELLOW
            if x < 16 and y < 16:
                color = TFT_CYAN
            if x >= 224 and y >= 224:
                color = TFT_MAGENTA
            if y == ((x + 20) * 239 + 139) // 279:
                color = TFT_WHITE
            buf[y * DEFAULT_WIDTH + x] = expected_visible565(color)
    _draw_font1_logical(buf, "Review pixels; N next, Q stop", 2, 228, TFT_WHITE, TFT_BLACK)
    return buf


def _build_expected_s2():
    buf = [expected_visible565(TFT_BLACK)] * (DEFAULT_WIDTH * DEFAULT_HEIGHT)
    for y in range(40, 56):
        for x in range(0, 13):
            sx = x + 3
            sy = y - 40
            buf[y * DEFAULT_WIDTH + x] = expected_visible565(TFT_RED if ((sx + sy) & 1) else TFT_GREEN)
    for y in range(60, 76):
        for x in range(220, 236):
            sx = x - 220
            sy = y - 60
            buf[y * DEFAULT_WIDTH + x] = expected_visible565(TFT_RED if ((sx + sy) & 1) else TFT_GREEN)
    _draw_font1_logical(buf, "Review pixels; N next, Q stop", 2, 228, TFT_WHITE, TFT_BLACK)
    return buf


def _expected_s3_unrotated_sprite_pixel(sx, sy):
    color = TFT_MAGENTA
    if 3 <= sx < 28 and 3 <= sy < 28:
        color = TFT_RED
    if 36 <= sx < 61 and 3 <= sy < 28:
        color = TFT_GREEN
    if 3 <= sx < 28 and 36 <= sy < 61:
        color = TFT_BLUE
    if 36 <= sx < 61 and 36 <= sy < 61:
        color = TFT_YELLOW
    if (
        sx == 0
        or sx == 63
        or sy == 0
        or sy == 63
        or (sx == 32 and 8 <= sy <= 24)
        or (sx + sy == 40 and 24 <= sx <= 32)
        or (sx - sy == 24 and 32 <= sx <= 40)
        or (sy == 32 and 29 <= sx <= 35)
        or (sx == 32 and 29 <= sy <= 35)
    ):
        color = TFT_WHITE
    if 30 <= sx < 35 and 30 <= sy < 35:
        color = TFT_CYAN
    if color == TFT_MAGENTA:
        color = TFT_BLACK
    return expected_visible565(color)


def verify_scene_geometry_independent(scene_id, pixels_565):
    """Independently verify scene geometry against mathematical expectations."""
    if len(pixels_565) != DEFAULT_WIDTH * DEFAULT_HEIGHT:
        return {"status": "FAIL", "reason": "invalid pixel count"}

    if scene_id == "s1":
        expected = _build_expected_s1()
        mismatches = [
            i for i, (act, exp) in enumerate(zip(pixels_565, expected)) if act != exp
        ]
        return {
            "status": "PASS" if not mismatches else "FAIL",
            "scene_id": "s1",
            "verified_pixels": len(expected) - len(mismatches),
            "mismatched_pixels": len(mismatches),
            "first_mismatch_xy": (
                (mismatches[0] % DEFAULT_WIDTH, mismatches[0] // DEFAULT_WIDTH)
                if mismatches
                else None
            ),
        }

    if scene_id == "s2":
        expected = _build_expected_s2()
        mismatches = [
            i for i, (act, exp) in enumerate(zip(pixels_565, expected)) if act != exp
        ]
        return {
            "status": "PASS" if not mismatches else "FAIL",
            "scene_id": "s2",
            "verified_pixels": len(expected) - len(mismatches),
            "mismatched_pixels": len(mismatches),
            "clipped_left_visible_size": [13, 16],
            "unclipped_right_visible_size": [16, 16],
            "first_mismatch_xy": (
                (mismatches[0] % DEFAULT_WIDTH, mismatches[0] // DEFAULT_WIDTH)
                if mismatches
                else None
            ),
        }

    if scene_id == "s3":
        failures = []
        # 1. All 4,096 pixels of 0 deg 64x64 sprite at (3..66, 39..102)
        for sy in range(64):
            for sx in range(64):
                act = pixels_565[(sy + 39) * DEFAULT_WIDTH + (sx + 3)]
                exp = _expected_s3_unrotated_sprite_pixel(sx, sy)
                if act != exp:
                    failures.append(f"0deg sprite mismatch at ({sx + 3},{sy + 39})")
                    break
        # 2. All 130 pixels of clipped 13x13 checkerboard at (0..9, 146..158), source cols 3..12
        checker_ok = 0
        for row in range(13):
            for col in range(10):
                sx = col + 3
                exp_logical = (
                    TFT_CYAN
                    if (row == 0 or row == 12 or sx == 12)
                    else (TFT_WHITE if ((sx + row) & 1) else TFT_BLACK)
                )
                act = pixels_565[(row + 146) * DEFAULT_WIDTH + col]
                if act == expected_visible565(exp_logical):
                    checker_ok += 1
                else:
                    failures.append(f"checkerboard mismatch at ({col},{row + 146})")
        # 3. 45 deg and 90 deg rotation probes (pivots, arrow tips, quadrants, transparent bg)
        probes = [
            (35, 71, TFT_CYAN),
            (120, 71, TFT_CYAN),
            (205, 71, TFT_CYAN),
            (137, 54, TFT_WHITE),
            (229, 71, TFT_WHITE),
            (120, 51, TFT_RED),
            (140, 71, TFT_GREEN),
            (120, 91, TFT_YELLOW),
            (100, 71, TFT_BLUE),
            (225, 51, TFT_RED),
            (225, 91, TFT_GREEN),
            (185, 51, TFT_BLUE),
            (185, 91, TFT_YELLOW),
            (133, 53, TFT_BLACK),
            (227, 67, TFT_BLACK),
            (74, 71, TFT_BLACK),
            (166, 71, TFT_BLACK),
            (120, 25, TFT_BLACK),
            (120, 117, TFT_BLACK),
            (172, 71, TFT_BLACK),
            (238, 71, TFT_BLACK),
            (205, 38, TFT_BLACK),
            (205, 104, TFT_BLACK),
            (10, 147, TFT_BLACK),
        ]
        for px, py, col in probes:
            if pixels_565[py * DEFAULT_WIDTH + px] != expected_visible565(col):
                failures.append(f"probe ({px},{py}) expected 0x{expected_visible565(col):04X}")
        # 4. Verify Font 1 labels and footer exactly
        label_buf = [expected_visible565(TFT_BLACK)] * (DEFAULT_WIDTH * DEFAULT_HEIGHT)
        _draw_font1_logical(label_buf, "0 deg", 23, 120, TFT_WHITE, TFT_BLACK)
        _draw_font1_logical(label_buf, "45 deg", 105, 120, TFT_WHITE, TFT_BLACK)
        _draw_font1_logical(label_buf, "90 deg", 193, 120, TFT_WHITE, TFT_BLACK)
        _draw_font1_logical(label_buf, "13x13 checker clipped left", 18, 149, TFT_WHITE, TFT_BLACK)
        _draw_font1_logical(label_buf, "Review pixels; N next, Q stop", 2, 228, TFT_WHITE, TFT_BLACK)
        for bx0, by0, bx1, by1 in (
            (23, 120, 52, 127),
            (105, 120, 140, 127),
            (193, 120, 228, 127),
            (18, 149, 173, 156),
            (2, 228, 175, 235),
        ):
            for py in range(by0, by1 + 1):
                for px in range(bx0, bx1 + 1):
                    idx = py * DEFAULT_WIDTH + px
                    if pixels_565[idx] != label_buf[idx]:
                        failures.append(f"label mismatch at ({px},{py})")
                        break
        return {
            "status": "PASS" if not failures and checker_ok == 130 else "FAIL",
            "scene_id": "s3",
            "unrotated_sprite_verified_pixels": 4096,
            "checkerboard_verified_pixels": checker_ok,
            "rotation_probes_verified": len(probes),
            "failures": failures[:5],
        }

    if scene_id == "s4":
        expected = [expected_visible565(TFT_BLACK)] * (DEFAULT_WIDTH * DEFAULT_HEIGHT)
        _draw_font1_logical(expected, "FONT 1 OPAQUE", 8, 14, TFT_WHITE, TFT_BLUE)
        _draw_font1_logical(expected, "Aa 123", 8, 26, TFT_YELLOW, TFT_BLACK)
        for band_x in range(8, 152, 8):
            band_col = TFT_BLUE if (((band_x - 8) // 8) & 1) else TFT_RED
            for py in range(48, 68):
                for px in range(band_x, band_x + 8):
                    expected[py * DEFAULT_WIDTH + px] = expected_visible565(band_col)
        _draw_font1_logical(expected, "FONT 2 TRANSPARENT", 8, 38, TFT_WHITE, TFT_BLACK)
        _draw_font2_logical(expected, "TRANSPARENT", 12, 50, TFT_YELLOW, None)
        _draw_font1_logical(expected, "FONT 4 OPAQUE", 8, 74, TFT_WHITE, TFT_BLACK)
        for px in range(8, 232):
            expected[122 * DEFAULT_WIDTH + px] = expected_visible565(TFT_DARKGREY)
        _draw_font1_logical(expected, "LEFT EDGE", 4, 130, TFT_CYAN, TFT_BLACK)
        _draw_font1_logical(expected, "RIGHT EDGE", 154, 130, TFT_CYAN, TFT_BLACK)
        _draw_font1_logical(expected, "LEFT", -4, 142, TFT_YELLOW, TFT_BLACK)
        _draw_font1_logical(expected, "RIGHT", 222, 142, TFT_YELLOW, TFT_BLACK)
        _draw_font1_logical(expected, "BOTTOM", 190, 233, TFT_GREEN, TFT_BLACK)
        _draw_font1_logical(expected, "Review pixels; N next, Q stop", 2, 228, TFT_WHITE, TFT_BLACK)

        # Font 4 RLE region: x in 8..92 (85px wide), y in 86..111 (26px high) lacks independent golden
        font4_bbox = (8, 86, 92, 111)
        mismatches = []
        font4_fg_count = 0
        font4_bg_count = 0
        font4_unexpected = 0
        for y in range(DEFAULT_HEIGHT):
            for x in range(DEFAULT_WIDTH):
                act = pixels_565[y * DEFAULT_WIDTH + x]
                if font4_bbox[0] <= x <= font4_bbox[2] and font4_bbox[1] <= y <= font4_bbox[3]:
                    if act == expected_visible565(TFT_WHITE):
                        font4_fg_count += 1
                    elif act == expected_visible565(TFT_BLUE):
                        font4_bg_count += 1
                    else:
                        font4_unexpected += 1
                else:
                    if act != expected[y * DEFAULT_WIDTH + x]:
                        mismatches.append((x, y))
        ok = (
            not mismatches
            and font4_unexpected == 0
            and font4_fg_count > 100
            and font4_bg_count > 100
        )
        return {
            "status": "PASS" if ok else "FAIL",
            "scene_id": "s4",
            "mismatched_pixels_outside_font4": len(mismatches),
            "first_mismatch_xy": mismatches[0] if mismatches else None,
            "font4_rle_bbox": list(font4_bbox),
            "font4_rle_fg_pixels": font4_fg_count,
            "font4_rle_bg_pixels": font4_bg_count,
            "font4_rle_unexpected_pixels": font4_unexpected,
            "font4_rle_golden_status": "NO_BASELINE",
        }

    raise ValueError(f"Unsupported reference scene: {scene_id}")


SCENE_SPECIFICATIONS = {
    "s1": {
        "title": "S1: EDGE CLIPPING (ST7789 240x240)",
        "subtitle": "Fast H/V lines, corner fillRects, Bresenham diagonal, Font 1 footer",
        "annotations": [
            {
                "scene_id": "s1",
                "feature_id": "cyan_corner_tl",
                "bbox": [0, 0, 15, 15],
                "visibility": "intentionally_clipped",
                "swatch_565": expected_visible565(TFT_CYAN),
                "expected_color_or_behavior": "fillRect(-8,-8,24,24,TFT_CYAN) clipped to 16x16 at (0..15,0..15)",
            },
            {
                "scene_id": "s1",
                "feature_id": "red_hline_y24",
                "bbox": [0, 24, 239, 24],
                "visibility": "intentionally_clipped",
                "swatch_565": expected_visible565(TFT_RED),
                "expected_color_or_behavior": "drawFastHLine(-16,24,272,TFT_RED) clipped to x=0..239 at y=24",
            },
            {
                "scene_id": "s1",
                "feature_id": "blue_vline_x24",
                "bbox": [24, 0, 24, 239],
                "visibility": "intentionally_clipped",
                "swatch_565": expected_visible565(TFT_BLUE),
                "expected_color_or_behavior": "drawFastVLine(24,-16,272,TFT_BLUE) clipped to y=0..239 at x=24",
            },
            {
                "scene_id": "s1",
                "feature_id": "white_diag_line",
                "bbox": [0, 17, 239, 222],
                "visibility": "intentionally_clipped",
                "swatch_565": expected_visible565(TFT_WHITE),
                "expected_color_or_behavior": "drawLine(-20,0,259,239,TFT_WHITE) clipped to (0,17)..(239,222)",
            },
            {
                "scene_id": "s1",
                "feature_id": "black_bg_interior",
                "bbox": [40, 60, 180, 110],
                "visibility": "fully_visible",
                "swatch_565": expected_visible565(TFT_BLACK),
                "expected_color_or_behavior": "Unwritten interior background remains TFT_BLACK (0x0000)",
            },
            {
                "scene_id": "s1",
                "feature_id": "yellow_vline_x215",
                "bbox": [215, 0, 215, 239],
                "visibility": "intentionally_clipped",
                "swatch_565": expected_visible565(TFT_YELLOW),
                "expected_color_or_behavior": "drawFastVLine(215,-16,272,TFT_YELLOW) clipped to y=0..239 at x=215",
            },
            {
                "scene_id": "s1",
                "feature_id": "green_hline_y215",
                "bbox": [0, 215, 239, 215],
                "visibility": "intentionally_clipped",
                "swatch_565": expected_visible565(TFT_GREEN),
                "expected_color_or_behavior": "drawFastHLine(-16,215,272,TFT_GREEN) clipped to x=0..239 at y=215",
            },
            {
                "scene_id": "s1",
                "feature_id": "magenta_corner_br",
                "bbox": [224, 224, 239, 239],
                "visibility": "intentionally_clipped",
                "swatch_565": expected_visible565(TFT_MAGENTA),
                "expected_color_or_behavior": "fillRect(224,224,24,24,TFT_MAGENTA) clipped to 16x16 at (224..239)",
            },
            {
                "scene_id": "s1",
                "feature_id": "instruction_footer",
                "bbox": [2, 228, 175, 235],
                "visibility": "fully_visible",
                "swatch_565": expected_visible565(TFT_WHITE),
                "expected_color_or_behavior": "Font 1 opaque footer 'Review pixels; N next, Q stop' at (2,228)",
            },
        ],
    },
    "s2": {
        "title": "S2: IMAGE SOURCE CLIPPING (ST7789 240x240)",
        "subtitle": "16x16 RGB565 red/green checkerboards at (-3,40) clipped and (220,60) full",
        "annotations": [
            {
                "scene_id": "s2",
                "feature_id": "clipped_checkerboard_left",
                "bbox": [0, 40, 12, 55],
                "visibility": "intentionally_clipped",
                "swatch_565": expected_visible565(TFT_RED),
                "expected_color_or_behavior": "16x16 at (-3,40): visible 13x16 [0..12,40..55] maps src cols 3..15",
            },
            {
                "scene_id": "s2",
                "feature_id": "clipped_col0_mapping",
                "bbox": [0, 40, 0, 55],
                "visibility": "intentionally_clipped",
                "swatch_565": expected_visible565(TFT_RED),
                "expected_color_or_behavior": "Dest col x=0 receives source col sx=3 (top pixel (0,40) is TFT_RED)",
            },
            {
                "scene_id": "s2",
                "feature_id": "unclipped_checkerboard_right",
                "bbox": [220, 60, 235, 75],
                "visibility": "fully_visible",
                "swatch_565": expected_visible565(TFT_GREEN),
                "expected_color_or_behavior": "16x16 at (220,60): fully visible 16x16 [220..235,60..75] cols 0..15",
            },
            {
                "scene_id": "s2",
                "feature_id": "black_bg_separation",
                "bbox": [13, 40, 219, 75],
                "visibility": "fully_visible",
                "swatch_565": expected_visible565(TFT_BLACK),
                "expected_color_or_behavior": "Area outside destination rects remains TFT_BLACK with zero bleed",
            },
            {
                "scene_id": "s2",
                "feature_id": "instruction_footer",
                "bbox": [2, 228, 175, 235],
                "visibility": "fully_visible",
                "swatch_565": expected_visible565(TFT_WHITE),
                "expected_color_or_behavior": "Font 1 opaque footer 'Review pixels; N next, Q stop' at (2,228)",
            },
        ],
    },
    "s3": {
        "title": "S3: SPRITE CROPPING AND ROTATION (ST7789 240x240)",
        "subtitle": "64x64 asymmetric sprite at 0/45/90 deg + left-clipped 13x13 checker at (-3,146)",
        "annotations": [
            {
                "scene_id": "s3",
                "feature_id": "sprite_0deg_unrotated",
                "bbox": [3, 39, 66, 102],
                "visibility": "fully_visible",
                "swatch_565": expected_visible565(TFT_RED),
                "expected_color_or_behavior": "64x64 sprite at 0 deg [3..66,39..102]: R/G/B/Y quadrants + up arrow",
            },
            {
                "scene_id": "s3",
                "feature_id": "pivot_marker_0deg",
                "bbox": [33, 69, 37, 73],
                "visibility": "fully_visible",
                "swatch_565": expected_visible565(TFT_CYAN),
                "expected_color_or_behavior": "Cyan 5x5 pivot marker centered at screen (35,71) for 0 deg sprite",
            },
            {
                "scene_id": "s3",
                "feature_id": "sprite_45deg_rotated",
                "bbox": [75, 26, 164, 115],
                "visibility": "fully_visible",
                "swatch_565": expected_visible565(TFT_GREEN),
                "expected_color_or_behavior": "64x64 sprite rotated 45 deg around pivot (120,71), key TFT_MAGENTA",
            },
            {
                "scene_id": "s3",
                "feature_id": "sprite_90deg_rotated",
                "bbox": [173, 39, 236, 102],
                "visibility": "fully_visible",
                "swatch_565": expected_visible565(TFT_YELLOW),
                "expected_color_or_behavior": "64x64 sprite rotated 90 deg around pivot (205,71), arrow points right",
            },
            {
                "scene_id": "s3",
                "feature_id": "transparent_bg_preserved",
                "bbox": [67, 39, 74, 102],
                "visibility": "fully_visible",
                "swatch_565": expected_visible565(TFT_BLACK),
                "expected_color_or_behavior": "TFT_MAGENTA key preserves TFT_BLACK background outside rotated sprites",
            },
            {
                "scene_id": "s3",
                "feature_id": "rotation_angle_labels",
                "bbox": [23, 120, 228, 127],
                "visibility": "fully_visible",
                "swatch_565": expected_visible565(TFT_WHITE),
                "expected_color_or_behavior": "Font 1 labels '0 deg' (23,120), '45 deg' (105,120), '90 deg' (193,120)",
            },
            {
                "scene_id": "s3",
                "feature_id": "clipped_checkerboard_13x13",
                "bbox": [0, 146, 9, 158],
                "visibility": "intentionally_clipped",
                "swatch_565": expected_visible565(TFT_CYAN),
                "expected_color_or_behavior": "13x13 checker at (-3,146): 10x13=130 visible pixels (src cols 3..12)",
            },
            {
                "scene_id": "s3",
                "feature_id": "checker_caption_label",
                "bbox": [18, 149, 173, 156],
                "visibility": "fully_visible",
                "swatch_565": expected_visible565(TFT_WHITE),
                "expected_color_or_behavior": "Font 1 label '13x13 checker clipped left' at (18,149)",
            },
            {
                "scene_id": "s3",
                "feature_id": "instruction_footer",
                "bbox": [2, 228, 175, 235],
                "visibility": "fully_visible",
                "swatch_565": expected_visible565(TFT_WHITE),
                "expected_color_or_behavior": "Font 1 opaque footer 'Review pixels; N next, Q stop' at (2,228)",
            },
        ],
    },
    "s4": {
        "title": "S4: TEXT RENDERING AND TRANSPARENCY (ST7789 240x240)",
        "subtitle": "Fonts 1/2/4 opaque & transparent over bands, gray line y=122, edge clipping",
        "annotations": [
            {
                "scene_id": "s4",
                "feature_id": "font1_opaque_samples",
                "bbox": [8, 14, 85, 33],
                "visibility": "fully_visible",
                "swatch_565": expected_visible565(TFT_BLUE),
                "expected_color_or_behavior": "Font 1 opaque 'FONT 1 OPAQUE' (white/blue) & 'Aa 123' (yellow/black)",
            },
            {
                "scene_id": "s4",
                "feature_id": "font2_transparent_bands",
                "bbox": [8, 48, 151, 67],
                "visibility": "fully_visible",
                "swatch_565": expected_visible565(TFT_YELLOW),
                "expected_color_or_behavior": "Font 2 'TRANSPARENT' (yellow) over 18 red/blue bands preserving bg",
            },
            {
                "scene_id": "s4",
                "feature_id": "font4_rle_opaque_no_baseline",
                "bbox": [8, 86, 92, 111],
                "visibility": "fully_visible",
                "swatch_565": expected_visible565(TFT_WHITE),
                "expected_color_or_behavior": "Font 4 RLE 'FONT 4' (white on blue) at [8,86,92,111] [NO_BASELINE]",
            },
            {
                "scene_id": "s4",
                "feature_id": "gray_reference_hline_y122",
                "bbox": [8, 122, 231, 122],
                "visibility": "fully_visible",
                "swatch_565": expected_visible565(TFT_DARKGREY),
                "expected_color_or_behavior": "Horizontal reference line drawFastHLine(8,122,224,TFT_DARKGREY)",
            },
            {
                "scene_id": "s4",
                "feature_id": "font1_visible_edge_labels",
                "bbox": [4, 130, 213, 137],
                "visibility": "fully_visible",
                "swatch_565": expected_visible565(TFT_CYAN),
                "expected_color_or_behavior": "Unclipped Font 1 'LEFT EDGE' (4,130) and 'RIGHT EDGE' (154,130)",
            },
            {
                "scene_id": "s4",
                "feature_id": "font1_clipped_left",
                "bbox": [0, 142, 19, 149],
                "visibility": "intentionally_clipped",
                "swatch_565": expected_visible565(TFT_YELLOW),
                "expected_color_or_behavior": "Font 1 'LEFT' at (-4,142): cols -4..-1 clipped, visible [0..19,142..149]",
            },
            {
                "scene_id": "s4",
                "feature_id": "font1_clipped_right",
                "bbox": [222, 142, 239, 149],
                "visibility": "intentionally_clipped",
                "swatch_565": expected_visible565(TFT_YELLOW),
                "expected_color_or_behavior": "Font 1 'RIGHT' at (222,142): cols 240..251 clipped, visible [222..239]",
            },
            {
                "scene_id": "s4",
                "feature_id": "font1_clipped_bottom",
                "bbox": [190, 233, 225, 239],
                "visibility": "intentionally_clipped",
                "swatch_565": expected_visible565(TFT_GREEN),
                "expected_color_or_behavior": "Font 1 'BOTTOM' at (190,233): row 240 clipped, visible [190..225,233..239]",
            },
            {
                "scene_id": "s4",
                "feature_id": "instruction_footer",
                "bbox": [2, 228, 175, 235],
                "visibility": "fully_visible",
                "swatch_565": expected_visible565(TFT_WHITE),
                "expected_color_or_behavior": "Font 1 opaque footer 'Review pixels; N next, Q stop' at (2,228)",
            },
        ],
    },
}


def _fill_rect_rgb(canvas, width, height, x0, y0, w, h, rgb):
    r, g, b = rgb
    x_start = max(0, x0)
    y_start = max(0, y0)
    x_end = min(width, x0 + w)
    y_end = min(height, y0 + h)
    if x_start >= x_end or y_start >= y_end:
        return
    row_bytes = bytes((r, g, b)) * (x_end - x_start)
    stride = width * 3
    for y in range(y_start, y_end):
        start = y * stride + x_start * 3
        canvas[start : start + len(row_bytes)] = row_bytes


def _draw_line_rgb(canvas, width, height, x0, y0, x1, y1, rgb, thickness=2):
    dx = abs(x1 - x0)
    dy = abs(y1 - y0)
    steps = max(dx, dy, 1)
    half = thickness // 2
    for step in range(steps + 1):
        x = x0 + (x1 - x0) * step // steps
        y = y0 + (y1 - y0) * step // steps
        _fill_rect_rgb(canvas, width, height, x - half, y - half, thickness, thickness, rgb)


def _draw_text_rgb(canvas, width, height, text, x0, y0, scale_x, scale_y, fg_rgb, bg_rgb, labels_log):
    glyph_w = 5 * scale_x
    glyph_h = 8 * scale_y
    pitch_x = 6 * scale_x
    total_w = max(0, len(text) * pitch_x - scale_x)
    labels_log.append(
        {
            "text": text,
            "rect": [x0, y0, x0 + total_w - 1, y0 + glyph_h - 1],
            "height_px": glyph_h,
            "contrast_ratio": round(contrast_ratio_rgb888(fg_rgb, bg_rgb), 2),
        }
    )
    cx = x0
    for ch in text:
        code = ord(ch) if ord(ch) < 256 else ord("?")
        for col in range(5):
            line = GLCD_FONT[code * 5 + col]
            for row in range(8):
                if (line >> row) & 1:
                    _fill_rect_rgb(
                        canvas,
                        width,
                        height,
                        cx + col * scale_x,
                        y0 + row * scale_y,
                        scale_x,
                        scale_y,
                        fg_rgb,
                    )
        cx += pitch_x


def render_annotated_png(scene_id, frame_bytes):
    """Render annotated.png with 4x nearest-neighbor 960x960 display and side callout panel."""
    validate_frame(frame_bytes, DEFAULT_WIDTH, DEFAULT_HEIGHT)
    spec = SCENE_SPECIFICATIONS[scene_id]
    pixels_565 = decode_565le(frame_bytes)

    canvas = bytearray(CANVAS_WIDTH * CANVAS_HEIGHT * 3)
    _fill_rect_rgb(canvas, CANVAS_WIDTH, CANVAS_HEIGHT, 0, 0, CANVAS_WIDTH, CANVAS_HEIGHT, BG_CANVAS_RGB)

    labels_log = []
    # Top banner panel
    _fill_rect_rgb(canvas, CANVAS_WIDTH, CANVAS_HEIGHT, 16, 12, CANVAS_WIDTH - 32, 82, BG_PANEL_RGB)
    _draw_text_rgb(
        canvas,
        CANVAS_WIDTH,
        CANVAS_HEIGHT,
        spec["title"],
        32,
        18,
        TITLE_SCALE_X,
        TITLE_SCALE_Y,
        FG_TEXT_RGB,
        BG_PANEL_RGB,
        labels_log,
    )
    _draw_text_rgb(
        canvas,
        CANVAS_WIDTH,
        CANVAS_HEIGHT,
        spec["subtitle"],
        32,
        58,
        ANNOTATION_SCALE_X,
        ANNOTATION_SCALE_Y,
        FG_MUTED_RGB,
        BG_PANEL_RGB,
        labels_log,
    )

    # Outer border around 960x960 display area (strictly outside [88..1047, 120..1079])
    _fill_rect_rgb(
        canvas,
        CANVAS_WIDTH,
        CANVAS_HEIGHT,
        DISPLAY_X0 - 4,
        DISPLAY_Y0 - 4,
        DISPLAY_WIDTH + 8,
        4,
        BORDER_RGB,
    )
    _fill_rect_rgb(
        canvas,
        CANVAS_WIDTH,
        CANVAS_HEIGHT,
        DISPLAY_X0 - 4,
        DISPLAY_Y0 + DISPLAY_HEIGHT,
        DISPLAY_WIDTH + 8,
        4,
        BORDER_RGB,
    )
    _fill_rect_rgb(
        canvas,
        CANVAS_WIDTH,
        CANVAS_HEIGHT,
        DISPLAY_X0 - 4,
        DISPLAY_Y0 - 4,
        4,
        DISPLAY_HEIGHT + 8,
        BORDER_RGB,
    )
    _fill_rect_rgb(
        canvas,
        CANVAS_WIDTH,
        CANVAS_HEIGHT,
        DISPLAY_X0 + DISPLAY_WIDTH,
        DISPLAY_Y0 - 4,
        4,
        DISPLAY_HEIGHT + 8,
        BORDER_RGB,
    )

    # Coordinate ruler labels outside the 960x960 display area
    for coord in (0, 60, 120, 180, 239):
        px = DISPLAY_X0 + coord * DISPLAY_SCALE
        py = DISPLAY_Y0 + coord * DISPLAY_SCALE
        _fill_rect_rgb(canvas, CANVAS_WIDTH, CANVAS_HEIGHT, px, DISPLAY_Y0 - 10, 2, 6, FG_ACCENT_RGB)
        _fill_rect_rgb(
            canvas,
            CANVAS_WIDTH,
            CANVAS_HEIGHT,
            DISPLAY_X0 - 10,
            py,
            6,
            2,
            FG_ACCENT_RGB,
        )
    _draw_text_rgb(
        canvas,
        CANVAS_WIDTH,
        CANVAS_HEIGHT,
        "X:0..239 (4x NN = 960x960 UNALTERED)",
        DISPLAY_X0,
        DISPLAY_Y0 + DISPLAY_HEIGHT + 12,
        ANNOTATION_SCALE_X,
        ANNOTATION_SCALE_Y,
        FG_ACCENT_RGB,
        BG_CANVAS_RGB,
        labels_log,
    )

    # Right-hand annotation panel (strictly outside 960x960 framebuffer display area)
    panel_x = 1120
    panel_w = CANVAS_WIDTH - panel_x - 16
    _fill_rect_rgb(
        canvas,
        CANVAS_WIDTH,
        CANVAS_HEIGHT,
        panel_x,
        DISPLAY_Y0 - 4,
        panel_w,
        DISPLAY_HEIGHT + 8,
        BG_PANEL_RGB,
    )

    annotations = spec["annotations"]
    slot_h = DISPLAY_HEIGHT // len(annotations)
    for idx, item in enumerate(annotations, start=1):
        card_y = DISPLAY_Y0 + (idx - 1) * slot_h + 4
        card_h = slot_h - 8
        _fill_rect_rgb(
            canvas,
            CANVAS_WIDTH,
            CANVAS_HEIGHT,
            panel_x + 10,
            card_y,
            panel_w - 20,
            card_h,
            BG_CARD_RGB,
        )
        swatch_rgb = rgb565_to_rgb888(item["swatch_565"])
        _fill_rect_rgb(canvas, CANVAS_WIDTH, CANVAS_HEIGHT, panel_x + 18, card_y + 10, 16, 16, BORDER_RGB)
        _fill_rect_rgb(canvas, CANVAS_WIDTH, CANVAS_HEIGHT, panel_x + 20, card_y + 12, 12, 12, swatch_rgb)

        bx0, by0, bx1, by1 = item["bbox"]
        vis_tag = "CLIPPED" if item["visibility"] == "intentionally_clipped" else "VISIBLE"
        header_line = f"[{idx}] {item['feature_id']} ({vis_tag}) [{bx0},{by0}..{bx1},{by1}]"
        detail_line = item["expected_color_or_behavior"]

        _draw_text_rgb(
            canvas,
            CANVAS_WIDTH,
            CANVAS_HEIGHT,
            header_line,
            panel_x + 42,
            card_y + 8,
            ANNOTATION_SCALE_X,
            ANNOTATION_SCALE_Y,
            FG_ACCENT_RGB,
            BG_CARD_RGB,
            labels_log,
        )
        _draw_text_rgb(
            canvas,
            CANVAS_WIDTH,
            CANVAS_HEIGHT,
            detail_line,
            panel_x + 42,
            card_y + 38,
            ANNOTATION_SCALE_X,
            ANNOTATION_SCALE_Y,
            FG_TEXT_RGB,
            BG_CARD_RGB,
            labels_log,
        )

        # Leader line + arrowhead in gutter [1052..1120] pointing to exact feature center Y
        target_cy = DISPLAY_Y0 + ((by0 + by1) * DISPLAY_SCALE) // 2 + 2
        card_cy = card_y + card_h // 2
        gutter_edge_x = DISPLAY_X0 + DISPLAY_WIDTH + 6
        _draw_line_rgb(
            canvas,
            CANVAS_WIDTH,
            CANVAS_HEIGHT,
            panel_x + 8,
            card_cy,
            gutter_edge_x,
            target_cy,
            FG_ACCENT_RGB,
            thickness=2,
        )
        # Arrowhead at right border of framebuffer (outside 960x960)
        for step in range(8):
            _fill_rect_rgb(
                canvas,
                CANVAS_WIDTH,
                CANVAS_HEIGHT,
                gutter_edge_x + step,
                target_cy - step // 2,
                2,
                step + 1,
                FG_ACCENT_RGB,
            )

    # Finally, write the 4x nearest-neighbor 960x960 framebuffer into [DISPLAY_X0..DISPLAY_X0+959, DISPLAY_Y0..DISPLAY_Y0+959]
    stride = CANVAS_WIDTH * 3
    for ly in range(DEFAULT_HEIGHT):
        row_offset = ly * DEFAULT_WIDTH
        scaled_row = b"".join(
            bytes(rgb565_to_rgb888(pixels_565[row_offset + lx])) * DISPLAY_SCALE
            for lx in range(DEFAULT_WIDTH)
        )
        base_y = DISPLAY_Y0 + ly * DISPLAY_SCALE
        for dy in range(DISPLAY_SCALE):
            start = (base_y + dy) * stride + DISPLAY_X0 * 3
            canvas[start : start + len(scaled_row)] = scaled_row

    png_bytes = encode_png_rgb888(canvas, CANVAS_WIDTH, CANVAS_HEIGHT)
    return png_bytes, labels_log


def verify_annotated_image(scene_id, frame_bytes, annotated_png_bytes, labels_log=None):
    """Independently verify 4x nearest-neighbor enlargement, 0 obscured pixels, and label metrics."""
    validate_frame(frame_bytes, DEFAULT_WIDTH, DEFAULT_HEIGHT)
    pixels_565 = decode_565le(frame_bytes)
    decoded = decode_png_rgb888(annotated_png_bytes)
    width = decoded["width"]
    height = decoded["height"]
    ann_pixels = decoded["pixels"]

    x0, y0, disp_w, disp_h = DISPLAY_AREA_RECT
    if (disp_w, disp_h) != (960, 960) or x0 + disp_w > width or y0 + disp_h > height:
        return {"status": "FAIL", "reason": "invalid 960x960 display area bounds"}

    altered_blocks = 0
    first_altered = None
    for ly in range(DEFAULT_HEIGHT):
        for lx in range(DEFAULT_WIDTH):
            expected_rgb = rgb565_to_rgb888(pixels_565[ly * DEFAULT_WIDTH + lx])
            base_x = x0 + lx * DISPLAY_SCALE
            base_y = y0 + ly * DISPLAY_SCALE
            block_ok = True
            for dy in range(DISPLAY_SCALE):
                row_offset = (base_y + dy) * width + base_x
                for dx in range(DISPLAY_SCALE):
                    if ann_pixels[row_offset + dx] != expected_rgb:
                        block_ok = False
                        break
                if not block_ok:
                    break
            if not block_ok:
                altered_blocks += 1
                if first_altered is None:
                    first_altered = (lx, ly)

    if labels_log is None:
        _, labels_log = render_annotated_png(scene_id, frame_bytes)

    overlapping = 0
    out_of_bounds = 0
    obscuring_labels = 0
    for i, label in enumerate(labels_log):
        lx0, ly0, lx1, ly1 = label["rect"]
        if lx0 < 0 or ly0 < 0 or lx1 >= width or ly1 >= height:
            out_of_bounds += 1
        # Check intersection with 960x960 display area
        if not (lx1 < x0 or lx0 >= x0 + disp_w or ly1 < y0 or ly0 >= y0 + disp_h):
            obscuring_labels += 1
        for other in labels_log[i + 1 :]:
            ox0, oy0, ox1, oy1 = other["rect"]
            if not (lx1 < ox0 or lx0 > ox1 or ly1 < oy0 or ly0 > oy1):
                overlapping += 1

    title_h = labels_log[0]["height_px"] if labels_log else 0
    min_text_h = min((item["height_px"] for item in labels_log[1:]), default=0)
    min_contrast = min((item["contrast_ratio"] for item in labels_log), default=0.0)

    spec_annotations = SCENE_SPECIFICATIONS[scene_id]["annotations"]
    invalid_callouts = 0
    for callout in spec_annotations:
        bx0, by0, bx1, by1 = callout["bbox"]
        if (
            callout["scene_id"] != scene_id
            or not (0 <= bx0 <= bx1 < DEFAULT_WIDTH and 0 <= by0 <= by1 < DEFAULT_HEIGHT)
            or callout["visibility"] not in ("fully_visible", "intentionally_clipped")
        ):
            invalid_callouts += 1

    ok = (
        altered_blocks == 0
        and overlapping == 0
        and out_of_bounds == 0
        and obscuring_labels == 0
        and invalid_callouts == 0
        and title_h >= 26
        and min_text_h >= 18
        and min_contrast >= 4.5
    )
    return {
        "status": "PASS" if ok else "FAIL",
        "annotated_dimensions": [width, height],
        "display_area_rect": list(DISPLAY_AREA_RECT),
        "display_area_width": disp_w,
        "display_area_height": disp_h,
        "enlargement_scale": DISPLAY_SCALE,
        "interpolation": "nearest_neighbor",
        "altered_or_obscured_pixels": altered_blocks,
        "first_altered_logical_xy": first_altered,
        "title_height_px": title_h,
        "min_text_height_px": min_text_h,
        "min_contrast_ratio": min_contrast,
        "overlapping_labels": overlapping,
        "out_of_bounds_labels": out_of_bounds,
        "obscuring_labels": obscuring_labels,
        "invalid_callouts": invalid_callouts,
    }


def _render_notes_md(scene_id, entry):
    spec = SCENE_SPECIFICATIONS[scene_id]
    lines = [
        f"# {spec['title']}",
        "",
        f"- **Scene ID:** `{scene_id}` (`{entry['scene_name']}`)",
        f"- **Git Commit:** `{entry['git_commit']}` (`dirty={entry['source_dirty']}`)",
        f"- **Display Profile:** `{entry['display_profile']['name']}` (`240x240`, `rotation={entry['rotation']}`, `seed={entry['seed']}`)",
        f"- **Raw Framebuffer (`frame.rgb565`) SHA-256:** `{entry['raw_frame_sha256']}`",
        f"- **Original PNG (`frame.png`) SHA-256:** `{entry['png_sha256']}`",
        f"- **Annotated PNG (`annotated.png`) SHA-256:** `{entry['annotated_png_sha256']}`",
        "- **ST7789 Color Order Note:** the 240x240 profile selects MADCTL BGR (`0x08`) and assumes BGR panel filters. The virtual visible pixel and exported frame are canonical RGB565. Confirm filter order on the real panel with the red/blue diagnostic.",
        "",
        "## Objective Verification Statuses",
        "",
        "| Criterion | Status |",
        "| --- | --- |",
    ]
    for key, val in entry["verification_results"].items():
        lines.append(f"| `{key}` | `{val}` |")
    lines.extend(
        [
            f"| `baseline_approval_status` | `{entry['baseline_approval_status']}` |",
            "",
            "## Verified Feature Callouts (240x240 Logical Coordinates)",
            "",
            "| # | Feature ID | Logical BBox `[x0, y0, x1, y1]` | Visibility | Expected Color / Behavior |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for idx, callout in enumerate(entry["annotations"], start=1):
        lines.append(
            f"| {idx} | `{callout['feature_id']}` | `{callout['bbox']}` | `{callout['visibility']}` | {callout['expected_color_or_behavior']} |"
        )
    if scene_id == "s4":
        lines.extend(
            [
                "",
                "## Font 4 RLE Golden Notice",
                "",
                "- Font 4 RLE glyphs (`\"FONT 4\"` at `[8, 86, 89, 111]`) remain marked `NO_BASELINE` because no independently approved Font 4 pixel golden exists yet.",
            ]
        )
    return "\n".join(lines) + "\n"


def _git_identity():
    sha = (
        subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
            timeout=5,
        )
        .stdout.decode("ascii")
        .strip()
    )
    dirty = bool(
        subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=no"],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
            timeout=5,
        ).stdout
    )
    return sha, dirty


def _run_simulator_raw(scene_id, seed=0, rotation=0):
    if not RUNNER.is_file():
        raise RuntimeError(f"simulator_runner is missing at {RUNNER}; run sim-build first")
    res = subprocess.run(
        [
            str(RUNNER),
            "--scene",
            scene_id,
            "--seed",
            str(seed),
            "--rotation",
            str(rotation),
            "--rgb565-stdout",
        ],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=5,
    )
    if res.returncode != 0:
        raise RuntimeError(
            f"simulator_runner failed for {scene_id}: {res.stderr.decode('utf-8', 'replace').strip()}"
        )
    return res.stdout


def populate_scene_reference_artifacts(
    scene_dir,
    scene_id,
    frame_bytes,
    png_bytes,
    profile,
    profile_hash,
    source_sha,
    dirty,
    seed=0,
    rotation=0,
    run2_frame_bytes=None,
    run2_png_bytes=None,
    timestamp=None,
):
    """Write annotated.png, notes.md, and enrich manifest_data for an S1-S4 scene."""
    scene_dir = Path(scene_dir)
    if timestamp is None:
        timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if run2_frame_bytes is None:
        run2_frame_bytes = _run_simulator_raw(scene_id, seed=seed, rotation=rotation)
    if run2_png_bytes is None:
        run2_png_bytes = encode_png_rgb565(run2_frame_bytes, DEFAULT_WIDTH, DEFAULT_HEIGHT)

    raw_sha1 = _sha256(frame_bytes)
    raw_sha2 = _sha256(run2_frame_bytes)
    png_sha1 = _sha256(png_bytes)
    png_sha2 = _sha256(run2_png_bytes)
    decoded_png1 = decode_png_rgb888(png_bytes)
    decoded_png2 = decode_png_rgb888(run2_png_bytes)
    expected_rgb = [rgb565_to_rgb888(p) for p in decode_565le(frame_bytes)]

    file_valid = (
        len(frame_bytes) == MAX_FRAME_BYTES
        and decoded_png1["width"] == DEFAULT_WIDTH
        and decoded_png1["height"] == DEFAULT_HEIGHT
        and decoded_png1["bit_depth"] == 8
        and decoded_png1["color_type"] == 2
        and len(decoded_png1["pixels"]) == DEFAULT_WIDTH * DEFAULT_HEIGHT
    )
    pixel_conv_ok = decoded_png1["pixels"] == expected_rgb
    determinism_ok = (
        frame_bytes == run2_frame_bytes
        and png_bytes == run2_png_bytes
        and raw_sha1 == raw_sha2
        and png_sha1 == png_sha2
        and decoded_png1["pixels"] == decoded_png2["pixels"]
    )

    annotated_bytes, labels_log = render_annotated_png(scene_id, frame_bytes)
    annotated_sha = _sha256(annotated_bytes)
    ann_validation = verify_annotated_image(scene_id, frame_bytes, annotated_bytes, labels_log)
    geom_validation = verify_scene_geometry_independent(scene_id, decode_565le(frame_bytes))

    scene_names = {
        "s1": "edge_clipping",
        "s2": "image_source_clipping",
        "s3": "sprite_crop_and_rotation",
        "s4": "text_opaque_transparent_edges",
    }
    annotations_clean = [
        {
            "scene_id": item["scene_id"],
            "feature_id": item["feature_id"],
            "bbox": list(item["bbox"]),
            "expected_color_or_behavior": item["expected_color_or_behavior"],
            "visibility": item["visibility"],
        }
        for item in SCENE_SPECIFICATIONS[scene_id]["annotations"]
    ]
    verification_results = {
        "file_validity": "PASS" if file_valid else "FAIL",
        "pixel_conversion": "PASS" if pixel_conv_ok else "FAIL",
        "determinism": "PASS" if determinism_ok else "FAIL",
        "geometry_validation": geom_validation["status"],
        "annotation_accuracy": ann_validation["status"],
        "independent_golden_availability": "NO_BASELINE",
        "physical_visual_approval": "VISUAL_REVIEW_REQUIRED",
    }
    runner_sha = _sha256(RUNNER.read_bytes()) if RUNNER.is_file() else "unknown"
    entry = {
        "schema_version": 1,
        "scene_id": scene_id,
        "scene_name": scene_names[scene_id],
        "seed": seed,
        "rotation": rotation,
        "source_sha": source_sha,
        "git_commit": source_sha,
        "source_dirty": dirty,
        "simulator_version": SIMULATOR_VERSION,
        "build_identity": f"simulator_runner:{SIMULATOR_VERSION}:{runner_sha[:16]}",
        "profile": profile,
        "display_profile": profile,
        "profile_hash": profile_hash,
        "pixel_dimensions": {
            "width": DEFAULT_WIDTH,
            "height": DEFAULT_HEIGHT,
            "total_pixels": DEFAULT_WIDTH * DEFAULT_HEIGHT,
            "raw_bytes": MAX_FRAME_BYTES,
        },
        "frame_sha256": raw_sha1,
        "raw_frame_sha256": raw_sha1,
        "png_sha256": png_sha1,
        "annotated_png_sha256": annotated_sha,
        "annotation_version": ANNOTATION_VERSION,
        "generation_timestamp": timestamp,
        "hardware": False,
        "simulated_timing": False,
        "simulated_memory": False,
        "review_status": "VISUAL_REVIEW_REQUIRED",
        "baseline_approval_status": "NO_BASELINE",
        "verification_results": verification_results,
        "reproducibility": {
            "status": "PASS" if determinism_ok else "FAIL",
            "runs": 2,
            "seed": seed,
            "rotation": rotation,
            "run1_raw_sha256": raw_sha1,
            "run2_raw_sha256": raw_sha2,
            "run1_png_sha256": png_sha1,
            "run2_png_sha256": png_sha2,
        },
        "geometry_validation": geom_validation,
        "annotation_validation": ann_validation,
        "annotations": annotations_clean,
    }
    notes_md = _render_notes_md(scene_id, entry)
    (scene_dir / "annotated.png").write_bytes(annotated_bytes)
    (scene_dir / "notes.md").write_text(notes_md, encoding="utf-8")
    return entry


def render_inspection_report_md(out_dir, shared_manifest):
    """Render the Final Visual Inspection Report (Section 12) with per-scene details and checklist."""
    out_dir = Path(out_dir)
    lines = [
        "# Final Visual Inspection Report — S1–S4 Reference Images",
        "",
        f"- **Git Commit:** `{shared_manifest['git_commit']}` (`dirty={shared_manifest['source_dirty']}`)",
        f"- **Simulator Build Identity:** `{shared_manifest['build_identity']}`",
        f"- **Display Profile:** `{shared_manifest['display_profile']['name']}` (`240x240`, little-endian RGB565, `rotation=0`, `seed=0`)",
        f"- **Annotation Version:** `{shared_manifest['annotation_version']}`",
        f"- **Generation Timestamp:** `{shared_manifest['generation_timestamp']}`",
        "",
    ]
    for scene_id in REFERENCE_SCENES:
        entry = shared_manifest["scenes"][scene_id]
        vr = entry["verification_results"]
        geom = entry["geometry_validation"]
        ann = entry["annotation_validation"]
        scene_dir = out_dir / scene_id
        lines.extend(
            [
                f"## {scene_id.upper()} — `{entry['scene_name']}`",
                "",
                f"- **Original Screenshot Path:** `{scene_dir / 'frame.png'}`",
                f"- **Annotated Screenshot Path:** `{scene_dir / 'annotated.png'}`",
                f"- **Raw Framebuffer Path:** `{scene_dir / 'frame.rgb565'}`",
                f"- **Notes Path:** `{scene_dir / 'notes.md'}`",
                f"- **Exact RGB565 SHA-256 (Run 1 & Run 2):** `{entry['raw_frame_sha256']}`",
                f"- **Exact PNG SHA-256 (Run 1 & Run 2):** `{entry['png_sha256']}`",
                f"- **Annotated PNG SHA-256:** `{entry['annotated_png_sha256']}`",
                f"- **Image Dimensions:** Original `{entry['pixel_dimensions']['width']}x{entry['pixel_dimensions']['height']}` (`57,600` pixels, `115,200` bytes); Annotated `{ann['annotated_dimensions'][0]}x{ann['annotated_dimensions'][1]}` with exact `960x960` (`4x` nearest-neighbor) unaltered framebuffer display area at `{ann['display_area_rect']}`",
                "",
                "### Objective Verification Statuses",
                "",
                "| Category | Status | Details |",
                "| --- | --- | --- |",
                f"| `file_validity` | `{vr['file_validity']}` | `240x240` 8-bit RGB PNG, `115,200`-byte RGB565 |",
                f"| `pixel_conversion` | `{vr['pixel_conversion']}` | 100% match with `rgb565_to_rgb888(decode_565le(frame.rgb565))` |",
                f"| `determinism` | `{vr['determinism']}` | 2 identical runs (`run1 == run2` raw & PNG hashes) |",
                f"| `geometry_validation` | `{vr['geometry_validation']}` | `{json.dumps(geom, sort_keys=True)}` |",
                f"| `annotation_accuracy` | `{vr['annotation_accuracy']}` | `0` obscured pixels, title `{ann['title_height_px']}px`, text `{ann['min_text_height_px']}px`, min contrast `{ann['min_contrast_ratio']}:1` |",
                f"| `independent_golden_availability` | `{vr['independent_golden_availability']}` | No externally approved baseline golden on disk |",
                f"| `physical_visual_approval` | `{vr['physical_visual_approval']}` | Requires human operator comparison on physical ST7789 panel |",
                f"| `baseline_approval_status` | `{entry['baseline_approval_status']}` | Unapproved until physical hardware inspection completes |",
                "",
                "### Verified Geometry & Clipping Callouts",
                "",
                "| # | Feature ID | Logical BBox `[x0, y0, x1, y1]` | Visibility | Expected Color / Behavior |",
                "| --- | --- | --- | --- | --- |",
            ]
        )
        for idx, c in enumerate(entry["annotations"], start=1):
            lines.append(
                f"| {idx} | `{c['feature_id']}` | `{c['bbox']}` | `{c['visibility']}` | {c['expected_color_or_behavior']} |"
            )
        lines.append("")

    lines.extend(
        [
            "## Remaining Items Requiring Human Visual Inspection & Operator Physical Comparison Checklist",
            "",
            "Automated simulator checks verify deterministic rendering and mathematical clipping/sprite/font geometry, but **do not replace physical ST7789 hardware inspection** or provide an approved Font 4 RLE golden.",
            "",
            "- [ ] **S1 (`edge_clipping`):** Confirm on physical 240x240 ST7789 panel that the top-left cyan (`16x16`) and bottom-right magenta (`16x16`) corner blocks, red (`y=24`) and green (`y=215`) horizontal lines, blue (`x=24`) and yellow (`x=215`) vertical lines, and white diagonal line (`(0,17)..(239,222)`) reach the exact bezel edges without wrap-around.",
            "- [ ] **S2 (`image_source_clipping`):** Confirm on physical panel that the left checkerboard at `(-3,40)` displays `13x16` columns with red at `(0,40)` and green at `(0,41)`, and the right checkerboard at `(220,60)` displays all `16x16` columns cleanly.",
            "- [ ] **S3 (`sprite_crop_and_rotation`):** Confirm on physical panel that the `64x64` sprite at `0 deg`, `45 deg`, and `90 deg` shows crisp white arrows pointing up, up-right, and right around cyan pivots `(35,71)`, `(120,71)`, `(205,71)` with black transparent background, and that the `13x13` clipped checkerboard at `(-3,146)` shows `10x13` pixels with top/bottom/right cyan border.",
            "- [ ] **S4 (`text_opaque_transparent_edges`):** Confirm on physical panel that `'FONT 1 OPAQUE'`, `'Aa 123'`, transparent Font 2 `'TRANSPARENT'` over 18 red/blue bands, opaque Font 4 `'FONT 4'` (currently `NO_BASELINE`), gray line at `y=122`, `'LEFT EDGE'`, `'RIGHT EDGE'`, clipped `'LEFT'`/`'RIGHT'`/`'BOTTOM'`, and the bottom footer are legible and properly clipped.",
        ]
    )
    return "\n".join(lines) + "\n"


def generate_reference_suite(out_dir, seed=0, rotation=0):
    """Generate and validate all S1-S4 reference image artifacts twice for reproducibility."""
    out_dir = Path(out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    profile = json.loads(PROFILE_FILE.read_text(encoding="utf-8"))
    profile_hash = _sha256(
        json.dumps(profile, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    )
    source_sha, dirty = _git_identity()
    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    runner_sha = _sha256(RUNNER.read_bytes()) if RUNNER.is_file() else "unknown"

    scenes_manifest = {}
    for scene_id in REFERENCE_SCENES:
        scene_dir = out_dir / scene_id
        scene_dir.mkdir(parents=True, exist_ok=True)
        raw1 = _run_simulator_raw(scene_id, seed=seed, rotation=rotation)
        png1 = encode_png_rgb565(raw1, DEFAULT_WIDTH, DEFAULT_HEIGHT)
        raw2 = _run_simulator_raw(scene_id, seed=seed, rotation=rotation)
        png2 = encode_png_rgb565(raw2, DEFAULT_WIDTH, DEFAULT_HEIGHT)

        (scene_dir / "frame.rgb565").write_bytes(raw1)
        (scene_dir / "frame.png").write_bytes(png1)
        entry = populate_scene_reference_artifacts(
            scene_dir=scene_dir,
            scene_id=scene_id,
            frame_bytes=raw1,
            png_bytes=png1,
            profile=profile,
            profile_hash=profile_hash,
            source_sha=source_sha,
            dirty=dirty,
            seed=seed,
            rotation=rotation,
            run2_frame_bytes=raw2,
            run2_png_bytes=png2,
            timestamp=timestamp,
        )
        (scene_dir / "manifest.json").write_text(
            json.dumps(entry, sort_keys=True, indent=2) + "\n", encoding="utf-8"
        )
        (scene_dir / "result.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "status": "RENDERED",
                    "scene_id": scene_id,
                    "seed": seed,
                    "rotation": rotation,
                    "frame_sha256": entry["raw_frame_sha256"],
                    "review_status": "VISUAL_REVIEW_REQUIRED",
                    "baseline_approval_status": "NO_BASELINE",
                    "verification_results": entry["verification_results"],
                },
                sort_keys=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        scenes_manifest[scene_id] = entry

    shared_manifest = {
        "schema_version": 1,
        "suite": "s1_s4_visual_reference",
        "scene_ids": list(REFERENCE_SCENES),
        "git_commit": source_sha,
        "source_sha": source_sha,
        "source_dirty": dirty,
        "simulator_version": SIMULATOR_VERSION,
        "build_identity": f"simulator_runner:{SIMULATOR_VERSION}:{runner_sha[:16]}",
        "display_profile": profile,
        "profile_hash": profile_hash,
        "rotation": rotation,
        "seed": seed,
        "pixel_dimensions": {
            "width": DEFAULT_WIDTH,
            "height": DEFAULT_HEIGHT,
            "total_pixels": DEFAULT_WIDTH * DEFAULT_HEIGHT,
            "raw_bytes": MAX_FRAME_BYTES,
        },
        "annotation_version": ANNOTATION_VERSION,
        "generation_timestamp": timestamp,
        "baseline_approval_status": "NO_BASELINE",
        "scenes": scenes_manifest,
    }
    (out_dir / "manifest.json").write_text(
        json.dumps(shared_manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    report_md = render_inspection_report_md(out_dir, shared_manifest)
    (out_dir / "VISUAL_INSPECTION_REPORT.md").write_text(report_md, encoding="utf-8")
    return shared_manifest


def verify_suite_artifacts(out_dir):
    """Independently verify that all mandatory S1-S4 artifacts and manifests exist and pass."""
    out_dir = Path(out_dir)
    manifest_path = out_dir / "manifest.json"
    if not manifest_path.is_file():
        return {"status": "FAIL", "reason": "missing shared manifest.json"}
    shared = json.loads(manifest_path.read_text(encoding="utf-8"))
    required_shared = (
        "scene_ids",
        "git_commit",
        "source_dirty",
        "simulator_version",
        "build_identity",
        "display_profile",
        "rotation",
        "pixel_dimensions",
        "annotation_version",
        "generation_timestamp",
        "baseline_approval_status",
        "scenes",
    )
    if any(k not in shared for k in required_shared):
        return {"status": "FAIL", "reason": "shared manifest missing required keys"}

    for scene_id in REFERENCE_SCENES:
        scene_dir = out_dir / scene_id
        for name in ("frame.rgb565", "frame.png", "annotated.png", "notes.md", "manifest.json"):
            if not (scene_dir / name).is_file():
                return {"status": "FAIL", "reason": f"missing {scene_id}/{name}"}
        entry = shared["scenes"].get(scene_id)
        if not entry:
            return {"status": "FAIL", "reason": f"missing {scene_id} in shared manifest"}
        raw = (scene_dir / "frame.rgb565").read_bytes()
        png = (scene_dir / "frame.png").read_bytes()
        ann = (scene_dir / "annotated.png").read_bytes()
        if _sha256(raw) != entry["raw_frame_sha256"] or _sha256(png) != entry["png_sha256"]:
            return {"status": "FAIL", "reason": f"hash mismatch for {scene_id}"}
        if _sha256(ann) != entry["annotated_png_sha256"]:
            return {"status": "FAIL", "reason": f"annotated hash mismatch for {scene_id}"}
        vr = entry["verification_results"]
        for key in (
            "file_validity",
            "pixel_conversion",
            "determinism",
            "geometry_validation",
            "annotation_accuracy",
        ):
            if vr.get(key) != "PASS":
                return {"status": "FAIL", "reason": f"{scene_id} {key}={vr.get(key)}"}
        if vr.get("independent_golden_availability") != "NO_BASELINE":
            return {"status": "FAIL", "reason": f"{scene_id} golden status invalid"}
        if vr.get("physical_visual_approval") != "VISUAL_REVIEW_REQUIRED":
            return {"status": "FAIL", "reason": f"{scene_id} physical review status invalid"}
    return {"status": "PASS", "scenes_verified": list(REFERENCE_SCENES)}


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / ".build/simulator/renders"
    generate_reference_suite(target)
    audit = verify_suite_artifacts(target)
    if audit["status"] != "PASS":
        raise SystemExit(1)
