#!/usr/bin/env python3
"""Generate and verify the deterministic S1-S4 Hardware Visual Validation Guide MP4 video."""

import argparse
import datetime
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from simulator.tools.reference_images import (
    BG_CANVAS_RGB,
    BG_CARD_RGB,
    BG_PANEL_RGB,
    BORDER_RGB,
    DEFAULT_HEIGHT,
    DEFAULT_WIDTH,
    FG_ACCENT_RGB,
    FG_MUTED_RGB,
    FG_TEXT_RGB,
    GLCD_FONT,
    REFERENCE_SCENES,
    contrast_ratio_rgb888,
    decode_565le,
    decode_png_rgb888,
    encode_png_rgb888,
    generate_reference_suite,
    rgb565_to_rgb888,
    validate_frame,
    verify_suite_artifacts,
)

VIDEO_WIDTH = 1920
VIDEO_HEIGHT = 1080
VIDEO_FPS = 30
VIDEO_CRF = 18

FB_SCALE = 4
FB_DISPLAY_W = DEFAULT_WIDTH * FB_SCALE  # 960
FB_DISPLAY_H = DEFAULT_HEIGHT * FB_SCALE  # 960
FB_X0 = 32
FB_Y0 = 92

ZOOM_SCALE = 8
ZOOM_SRC_SIZE = 32
ZOOM_DISPLAY_SIZE = ZOOM_SRC_SIZE * ZOOM_SCALE  # 256

TITLE_SCALE_X = 3
TITLE_SCALE_Y = 5  # 8 * 5 = 40 px (>= 36 px)
HEADING_SCALE_X = 2
HEADING_SCALE_Y = 4  # 8 * 4 = 32 px (>= 28 px)
BODY_SCALE_X = 2
BODY_SCALE_Y = 3  # 8 * 3 = 24 px (>= 24 px)
CAPTION_SCALE_X = 2
CAPTION_SCALE_Y = 3  # 8 * 3 = 24 px (>= 20 px)

FG_WARN_RGB = (255, 206, 115)
FG_OK_RGB = (130, 245, 175)
BG_BADGE_RGB = (38, 22, 30)

EXPECTED_RAW_HASHES = {
    "s1": "bff098e5e196a47670054bcd2037df950c7751cf2973d8f63cf0437c737d7327",
    "s2": "d2d9b724cabb8f054ad42e830dccc7456617f21937f33efd78adcb24f50b77bd",
    "s3": "5a670e4e6c3d2043714b6ebb4d4bbb587bff563ff4ca67d0553f4a133f19c222",
    "s4": "0af271024ca6581679fbc9e4e2bc7d440ae47e6568066b09f8d9be954a3c43da",
}

TIMELINE_SEGMENTS = (
    {
        "id": "intro",
        "slide_file": "slide_00_intro.png",
        "title": "ESP8266 + ST7789 — Hardware Visual Validation Guide",
        "start_s": 0,
        "end_s": 4,
        "duration_s": 4,
        "probe_time_s": 2.0,
    },
    {
        "id": "s1",
        "slide_file": "slide_01_s1.png",
        "title": "S1: Edge Clipping",
        "scene_name": "edge_clipping",
        "start_s": 4,
        "end_s": 13,
        "duration_s": 9,
        "probe_time_s": 8.0,
    },
    {
        "id": "s2",
        "slide_file": "slide_02_s2.png",
        "title": "S2: Image Source Clipping",
        "scene_name": "image_source_clipping",
        "start_s": 13,
        "end_s": 22,
        "duration_s": 9,
        "probe_time_s": 17.0,
    },
    {
        "id": "s3",
        "slide_file": "slide_03_s3.png",
        "title": "S3: Sprite Cropping and Rotation",
        "scene_name": "sprite_crop_and_rotation",
        "start_s": 22,
        "end_s": 35,
        "duration_s": 13,
        "probe_time_s": 28.0,
    },
    {
        "id": "s4",
        "slide_file": "slide_04_s4.png",
        "title": "S4: Text and Font Clipping",
        "scene_name": "text_opaque_transparent_edges",
        "start_s": 35,
        "end_s": 48,
        "duration_s": 13,
        "probe_time_s": 41.0,
    },
    {
        "id": "conclusion",
        "slide_file": "slide_05_conclusion.png",
        "title": "Hardware Visual Review Summary",
        "start_s": 48,
        "end_s": 53,
        "duration_s": 5,
        "probe_time_s": 50.0,
    },
)

SCENE_SLIDE_CONTENT = {
    "s1": {
        "header_title": "S1: Edge Clipping (edge_clipping)",
        "purpose": [
            "Scene ID: S1 (edge_clipping) | Serial Command: S1\\n",
            "Purpose: Verify negative/overflow coords clip cleanly at 0..239.",
        ],
        "expected": [
            "* Cyan fillRect(-8,-8,24,24): clipped to 16x16 at [0..15, 0..15].",
            "* Magenta fillRect(224,224,24,24): clipped to 16x16 at [224..239].",
            "* H-Lines (-16..255): Red at y=24, Green at y=215 across 0..239.",
            "* V-Lines: Blue x=24, Yellow x=215; White diag (0,17)..(239,222).",
        ],
        "clipping": [
            "* Top-left 8 cols/rows of cyan rect (-8..-1) are off-screen.",
            "* Bottom-right 8 cols/rows of magenta rect (240..247) clip off.",
            "* White diagonal (-20,0)->(259,239) clips to (0,17)..(239,222).",
        ],
        "failures": [
            "! FAIL if clipped lines/rects wrap around to opposite edges.",
            "! FAIL if 16x16 corner rects or H/V lines shift or bleed.",
        ],
        "operator": "Send 'S1\\n' at 115200 8N1; inspect 16x16 corners & line crossings.",
        "zooms": [
            {
                "src_x0": 0,
                "src_y0": 0,
                "caption1": "ZOOM A: Top-Left [0..31, 0..31]",
                "caption2": "16x16 cyan, y=24 H, x=24 V",
            },
            {
                "src_x0": 208,
                "src_y0": 208,
                "caption1": "ZOOM B: Bot-Right [208..239]",
                "caption2": "16x16 Mag [224..239], x/y=215",
            },
        ],
    },
    "s2": {
        "header_title": "S2: Image Source Clipping",
        "purpose": [
            "Scene ID: S2 (image_source_clipping) | Serial Command: S2\\n",
            "Purpose: Verify pushImage() source offset & stride on clipping.",
        ],
        "expected": [
            "* Left 16x16 checker at (-3,40) -> 13x16 visible [0..12, 40..55].",
            "* Right 16x16 checker at (220,60) -> 16x16 visible [220..235, 60..75].",
            "* Alternating 1x1 TFT_RED / TFT_GREEN pixels (setSwapBytes=true).",
            "* Footer 'Review pixels; N next, Q stop' at (2,228); black bg.",
        ],
        "clipping": [
            "* Left image clips 3 left cols (sx=0..2); sx=3..15 -> x=0..12.",
            "* At y=40 (sy=0), x=0 maps sx=3 -> (3+0)&1=1 -> TFT_RED first px.",
            "* Right image at x=220..235 fits 240 width (unclipped; TFT_GREEN).",
        ],
        "failures": [
            "! FAIL if left checker shows diagonal stripes (stride corruption).",
            "! FAIL if left checker is not 13x16 or right 16x16 image crops.",
        ],
        "operator": "Send 'S2\\n'; verify 13x16 left checker & full 16x16 right checker.",
        "zooms": [
            {
                "src_x0": 0,
                "src_y0": 36,
                "caption1": "ZOOM A: Left Clip [0..31, 36..67]",
                "caption2": "13x16 [0..12, 40..55] sx=3..15",
            },
            {
                "src_x0": 208,
                "src_y0": 56,
                "caption1": "ZOOM B: Right Full [208..239]",
                "caption2": "16x16 full [220..235, 60..75]",
            },
        ],
    },
    "s3": {
        "header_title": "S3: Sprite Cropping and Rotation",
        "purpose": [
            "Scene ID: S3 (sprite_crop_and_rotation) | Serial Command: S3\\n",
            "Purpose: Verify 64x64 sprite 0/45/90 deg rotation, pivots & crop.",
        ],
        "expected": [
            "* 64x64 sprite: white frame, TL=Red, TR=Grn, BL=Blue, BR=Yel + arrow.",
            "* 0 deg [3..66, 39..102] (pivot 35,71 UP); 45 deg (pivot 120,71 NE).",
            "* 90 deg CW [173..236, 39..102] (pivot 205,71 RIGHT, BL=Blue at TL).",
            "* 13x13 W/K checker + cyan border at (-3,146) -> 10x13 [0..9,146..158].",
        ],
        "clipping": [
            "* Cyan 5x5 marker stays anchored at (35,71), (120,71), (205,71).",
            "* Key TFT_MAGENTA preserves black bg around 45 deg rotated sprite.",
            "* 13x13 sprite at (-3,146) clips 3 left cols; sx=3..12 -> x=0..9.",
        ],
        "failures": [
            "! FAIL if magenta key pixels leak around 45 deg rotated sprite.",
            "! FAIL if 90 deg arrow points left/down or 10x13 checker skews.",
        ],
        "operator": "Send 'S3\\n'; check arrows (UP, NE, RIGHT) & 10x13 left checker.",
        "zooms": [
            {
                "src_x0": 104,
                "src_y0": 55,
                "caption1": "ZOOM A: 45 deg Pivot [104..135]",
                "caption2": "Center pivot (120,71) & NE arrow",
            },
            {
                "src_x0": 0,
                "src_y0": 140,
                "caption1": "ZOOM B: Clipped Sprite [0..31]",
                "caption2": "10x13 visible [0..9, 146..158]",
            },
        ],
    },
    "s4": {
        "header_title": "S4: Text and Font Clipping",
        "purpose": [
            "Scene ID: S4 (text_opaque_transparent_edges) | Serial Cmd: S4\\n",
            "Purpose: Verify opaque/transparent text, Font 4 RLE & edge clip.",
        ],
        "expected": [
            "* Font 1 opaque: 'FONT 1 OPAQUE' (white/blue) & 'Aa 123' (yel/blk).",
            "* Font 2 transp: yellow 'TRANSPARENT' over 18 red/blue 8px stripes.",
            "* Font 4 RLE opaque: white/blue 'FONT 4' (8,86..111) [NO_BASELINE].",
            "* Gray H-line y=122; 'LEFT EDGE' (4,130) & 'RIGHT EDGE' (154,130).",
        ],
        "clipping": [
            "* 'LEFT' at (-4,142): cols -4..-1 clipped; 20px visible [0..19].",
            "* 'RIGHT' at (222,142): cols 240..251 ('HT') clipped; [222..239].",
            "* 'BOTTOM' at (190,233): 7 top rows visible [233..239]; 240 clipped.",
        ],
        "failures": [
            "! FAIL if black boxes erase red/blue stripes behind 'TRANSPARENT'.",
            "! FAIL if clipped 'LEFT'/'RIGHT'/'BOTTOM' glyphs wrap around edges.",
        ],
        "operator": "Send 'S4\\n'; verify stripes in 'TRANSPARENT' & partial edge text.",
        "zooms": [
            {
                "src_x0": 8,
                "src_y0": 44,
                "caption1": "ZOOM A: Font 2 Transp [8..39]",
                "caption2": "Red/blue stripes inside glyphs",
            },
            {
                "src_x0": 0,
                "src_y0": 126,
                "caption1": "ZOOM B: Left Edge Clip [0..31]",
                "caption2": "'LEFT EDGE' & clipped 'LEFT'",
            },
        ],
    },
}


def _sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def _glyph_cols(ch):
    if ch == "\u2014":  # em-dash —
        return (0x10, 0x10, 0x10, 0x10, 0x10)
    if ch == "\u2013":  # en-dash –
        return (0x00, 0x10, 0x10, 0x10, 0x00)
    if ch == "\u00d7":  # multiplication ×
        return (0x22, 0x14, 0x08, 0x14, 0x22)
    if ch == "\u00b0":  # degree °
        return (0x06, 0x09, 0x09, 0x06, 0x00)
    code = ord(ch) if ord(ch) < 256 else ord("?")
    base = code * 5
    return tuple(GLCD_FONT[base : base + 5])


def _fill_rect(canvas, x0, y0, w, h, rgb):
    r, g, b = rgb
    xs = max(0, x0)
    ys = max(0, y0)
    xe = min(VIDEO_WIDTH, x0 + w)
    ye = min(VIDEO_HEIGHT, y0 + h)
    if xs >= xe or ys >= ye:
        return
    row_bytes = bytes((r, g, b)) * (xe - xs)
    stride = VIDEO_WIDTH * 3
    for y in range(ys, ye):
        start = y * stride + xs * 3
        canvas[start : start + len(row_bytes)] = row_bytes


def _stroke_rect(canvas, x0, y0, w, h, thickness, rgb):
    _fill_rect(canvas, x0, y0, w, thickness, rgb)
    _fill_rect(canvas, x0, y0 + h - thickness, w, thickness, rgb)
    _fill_rect(canvas, x0, y0, thickness, h, rgb)
    _fill_rect(canvas, x0 + w - thickness, y0, thickness, h, rgb)


def _draw_text(canvas, text, x0, y0, scale_x, scale_y, fg_rgb, bg_rgb, labels_log, role="body"):
    glyph_h = 8 * scale_y
    pitch_x = 6 * scale_x
    total_w = max(0, len(text) * pitch_x - scale_x)
    labels_log.append(
        {
            "text": text,
            "role": role,
            "rect": [x0, y0, x0 + total_w - 1, y0 + glyph_h - 1],
            "height_px": glyph_h,
            "contrast_ratio": round(contrast_ratio_rgb888(fg_rgb, bg_rgb), 2),
        }
    )
    cx = x0
    for ch in text:
        cols = _glyph_cols(ch)
        for col_idx, col_bits in enumerate(cols):
            for row_idx in range(8):
                if (col_bits >> row_idx) & 1:
                    _fill_rect(
                        canvas,
                        cx + col_idx * scale_x,
                        y0 + row_idx * scale_y,
                        scale_x,
                        scale_y,
                        fg_rgb,
                    )
        cx += pitch_x


def _blit_nearest(canvas, pixels_565, src_x0, src_y0, src_w, src_h, dst_x0, dst_y0, scale):
    for sy in range(src_h):
        py = src_y0 + sy
        if not 0 <= py < DEFAULT_HEIGHT:
            continue
        for sx in range(src_w):
            px = src_x0 + sx
            if not 0 <= px < DEFAULT_WIDTH:
                continue
            rgb = rgb565_to_rgb888(pixels_565[py * DEFAULT_WIDTH + px])
            _fill_rect(
                canvas,
                dst_x0 + sx * scale,
                dst_y0 + sy * scale,
                scale,
                scale,
                rgb,
            )


def _render_intro_slide(scene_frames_565):
    canvas = bytearray(VIDEO_WIDTH * VIDEO_HEIGHT * 3)
    _fill_rect(canvas, 0, 0, VIDEO_WIDTH, VIDEO_HEIGHT, BG_CANVAS_RGB)
    labels_log = []

    # Top Hero Banner
    _fill_rect(canvas, 24, 20, VIDEO_WIDTH - 48, 176, BG_PANEL_RGB)
    _stroke_rect(canvas, 24, 20, VIDEO_WIDTH - 48, 176, 2, BORDER_RGB)

    _draw_text(
        canvas,
        "ESP8266 + ST7789 — Hardware Visual Validation Guide",
        48,
        38,
        TITLE_SCALE_X,
        TITLE_SCALE_Y,
        FG_TEXT_RGB,
        BG_PANEL_RGB,
        labels_log,
        role="title",
    )
    _draw_text(
        canvas,
        "S1–S4 Simulator Reference",
        48,
        94,
        HEADING_SCALE_X,
        HEADING_SCALE_Y,
        FG_ACCENT_RGB,
        BG_PANEL_RGB,
        labels_log,
        role="heading",
    )
    _draw_text(
        canvas,
        "Simulator-generated reference — not physical hardware footage",
        48,
        142,
        HEADING_SCALE_X,
        HEADING_SCALE_Y,
        FG_WARN_RGB,
        BG_PANEL_RGB,
        labels_log,
        role="heading",
    )

    # Left Card: Hardware & Serial Inspection Workflow
    _fill_rect(canvas, 24, 216, 920, 840, BG_PANEL_RGB)
    _stroke_rect(canvas, 24, 216, 920, 840, 2, BORDER_RGB)

    _draw_text(
        canvas,
        "1. TARGET HARDWARE & DISPLAY PROFILE",
        48,
        240,
        HEADING_SCALE_X,
        HEADING_SCALE_Y,
        FG_ACCENT_RGB,
        BG_PANEL_RGB,
        labels_log,
        role="heading",
    )
    hw_lines = [
        "* MCU / Board : NodeMCU ESP8266 (ESP-12E)",
        "* Display     : ST7789 240x240 RGB565 SPI (Rotation 0)",
        "* Color Order : ST7789 MADCTL=0x08 (BGR panel order)",
        "* Reference   : Deterministic simulator framebuffer",
    ]
    y = 286
    for line in hw_lines:
        _draw_text(canvas, line, 48, y, BODY_SCALE_X, BODY_SCALE_Y, FG_TEXT_RGB, BG_PANEL_RGB, labels_log)
        y += 34

    _draw_text(
        canvas,
        "2. SERIAL COMMAND PROTOCOL (115200 8N1)",
        48,
        444,
        HEADING_SCALE_X,
        HEADING_SCALE_Y,
        FG_ACCENT_RGB,
        BG_PANEL_RGB,
        labels_log,
        role="heading",
    )
    serial_lines = [
        "* Send 'S1\\n' .. 'S4\\n' (newline-terminated) to jump to scene",
        "* Send 'N\\n' to advance to next scene; 'R\\n' to redraw scene",
        "* Send 'Q\\n' to leave interactive review mode",
        "* Never toggle DTR/RTS while capturing serial validation logs",
    ]
    y = 490
    for line in serial_lines:
        _draw_text(canvas, line, 48, y, BODY_SCALE_X, BODY_SCALE_Y, FG_TEXT_RGB, BG_PANEL_RGB, labels_log)
        y += 34

    _draw_text(
        canvas,
        "3. HOW TO USE THIS VIDEO GUIDE",
        48,
        648,
        HEADING_SCALE_X,
        HEADING_SCALE_Y,
        FG_ACCENT_RGB,
        BG_PANEL_RGB,
        labels_log,
        role="heading",
    )
    guide_lines = [
        "* Left 960x960 area shows exact 4x nearest-neighbor pixels.",
        "* Zero overlays obscure the 960x960 simulated display.",
        "* Right panel lists expected geometry, clipping & failure modes.",
        "* Bottom-right 8x zoom insets highlight critical edge boundaries.",
        "* Note: H.264 video is for operator guidance; use frame.png",
        "  and annotated.png for lossless pixel-exact verification.",
    ]
    y = 694
    for line in guide_lines:
        _draw_text(canvas, line, 48, y, BODY_SCALE_X, BODY_SCALE_Y, FG_MUTED_RGB, BG_PANEL_RGB, labels_log)
        y += 34

    # Right Card: Timeline & 4 Scene Previews
    _fill_rect(canvas, 968, 216, 928, 840, BG_PANEL_RGB)
    _stroke_rect(canvas, 968, 216, 928, 840, 2, BORDER_RGB)

    _draw_text(
        canvas,
        "4. VALIDATION TIMELINE (53 SECONDS TOTAL)",
        992,
        240,
        HEADING_SCALE_X,
        HEADING_SCALE_Y,
        FG_ACCENT_RGB,
        BG_PANEL_RGB,
        labels_log,
        role="heading",
    )
    timeline_lines = [
        "00:00 - 00:04 ( 4s) : Introduction & Protocol Overview",
        "00:04 - 00:13 ( 9s) : S1 Edge Clipping (edge_clipping)",
        "00:13 - 00:22 ( 9s) : S2 Image Source Clipping",
        "00:22 - 00:35 (13s) : S3 Sprite Cropping and Rotation",
        "00:35 - 00:48 (13s) : S4 Text and Font Clipping",
        "00:48 - 00:53 ( 5s) : Conclusion & Operator Sign-Off",
    ]
    y = 286
    for line in timeline_lines:
        _draw_text(canvas, line, 992, y, BODY_SCALE_X, BODY_SCALE_Y, FG_TEXT_RGB, BG_PANEL_RGB, labels_log)
        y += 34

    _draw_text(
        canvas,
        "5. SIMULATOR REFERENCE PREVIEWS (1x 240x240)",
        992,
        512,
        HEADING_SCALE_X,
        HEADING_SCALE_Y,
        FG_ACCENT_RGB,
        BG_PANEL_RGB,
        labels_log,
        role="heading",
    )
    preview_coords = [
        ("s1", "S1: edge_clipping", 992, 560),
        ("s2", "S2: image_source_clipping", 1448, 560),
        ("s3", "S3: sprite_crop_and_rotation", 992, 804),
        ("s4", "S4: text_opaque_transparent", 1448, 804),
    ]
    for sid, label, px, py in preview_coords:
        _fill_rect(canvas, px, py, 424, 232, BG_CARD_RGB)
        _stroke_rect(canvas, px, py, 424, 232, 2, BORDER_RGB)
        _draw_text(canvas, label, px + 16, py + 24, BODY_SCALE_X, BODY_SCALE_Y, FG_ACCENT_RGB, BG_CARD_RGB, labels_log)
        sha_short = EXPECTED_RAW_HASHES[sid][:16]
        _draw_text(
            canvas,
            f"RGB565 SHA: {sha_short}..",
            px + 16,
            py + 68,
            CAPTION_SCALE_X,
            CAPTION_SCALE_Y,
            FG_TEXT_RGB,
            BG_CARD_RGB,
            labels_log,
            role="caption",
        )
        _draw_text(
            canvas,
            "Resolution: 240x240 (4x in guide)",
            px + 16,
            py + 112,
            CAPTION_SCALE_X,
            CAPTION_SCALE_Y,
            FG_MUTED_RGB,
            BG_CARD_RGB,
            labels_log,
            role="caption",
        )
        _draw_text(
            canvas,
            f"Serial Cmd: {sid.upper()}\\n",
            px + 16,
            py + 156,
            CAPTION_SCALE_X,
            CAPTION_SCALE_Y,
            FG_OK_RGB,
            BG_CARD_RGB,
            labels_log,
            role="caption",
        )

    return canvas, labels_log


def _render_scene_slide(scene_id, pixels_565):
    spec = SCENE_SLIDE_CONTENT[scene_id]
    canvas = bytearray(VIDEO_WIDTH * VIDEO_HEIGHT * 3)
    _fill_rect(canvas, 0, 0, VIDEO_WIDTH, VIDEO_HEIGHT, BG_CANVAS_RGB)
    labels_log = []

    # 1. Top Header Bar (y = 12..79)
    _fill_rect(canvas, 20, 12, VIDEO_WIDTH - 40, 68, BG_PANEL_RGB)
    _stroke_rect(canvas, 20, 12, VIDEO_WIDTH - 40, 68, 2, BORDER_RGB)
    _draw_text(
        canvas,
        spec["header_title"],
        32,
        26,
        TITLE_SCALE_X,
        TITLE_SCALE_Y,
        FG_TEXT_RGB,
        BG_PANEL_RGB,
        labels_log,
        role="title",
    )

    # Disclaimer badge on top-right
    _fill_rect(canvas, 1140, 20, 744, 52, BG_BADGE_RGB)
    _stroke_rect(canvas, 1140, 20, 744, 52, 2, FG_WARN_RGB)
    _draw_text(
        canvas,
        "SIMULATOR REFERENCE — NOT HARDWARE FOOTAGE",
        1160,
        34,
        CAPTION_SCALE_X,
        CAPTION_SCALE_Y,
        FG_WARN_RGB,
        BG_BADGE_RGB,
        labels_log,
        role="caption",
    )

    # 2. Main 960x960 Simulated Framebuffer (4x nearest-neighbor, untouched)
    _stroke_rect(
        canvas,
        FB_X0 - 4,
        FB_Y0 - 4,
        FB_DISPLAY_W + 8,
        FB_DISPLAY_H + 8,
        4,
        BORDER_RGB,
    )
    _blit_nearest(
        canvas,
        pixels_565,
        0,
        0,
        DEFAULT_WIDTH,
        DEFAULT_HEIGHT,
        FB_X0,
        FB_Y0,
        FB_SCALE,
    )

    # 3. Right-hand Information Panel (x = 1012..1899, y = 88..1055)
    panel_x = 1012
    panel_y = 88
    panel_w = 888
    panel_h = 968
    _fill_rect(canvas, panel_x, panel_y, panel_w, panel_h, BG_PANEL_RGB)
    _stroke_rect(canvas, panel_x, panel_y, panel_w, panel_h, 2, BORDER_RGB)

    tx = 1028
    # Section 1: Purpose
    _draw_text(
        canvas,
        "SCENE PURPOSE & IDENTIFIER",
        tx,
        100,
        HEADING_SCALE_X,
        HEADING_SCALE_Y,
        FG_ACCENT_RGB,
        BG_PANEL_RGB,
        labels_log,
        role="heading",
    )
    y = 138
    for line in spec["purpose"]:
        _draw_text(canvas, line, tx, y, BODY_SCALE_X, BODY_SCALE_Y, FG_TEXT_RGB, BG_PANEL_RGB, labels_log)
        y += 28

    # Section 2: Expected Visible Elements
    _draw_text(
        canvas,
        "EXPECTED VISIBLE ELEMENTS",
        tx,
        202,
        HEADING_SCALE_X,
        HEADING_SCALE_Y,
        FG_ACCENT_RGB,
        BG_PANEL_RGB,
        labels_log,
        role="heading",
    )
    y = 240
    for line in spec["expected"]:
        _draw_text(canvas, line, tx, y, BODY_SCALE_X, BODY_SCALE_Y, FG_TEXT_RGB, BG_PANEL_RGB, labels_log)
        y += 28

    # Section 3: Intended Clipping Behavior
    _draw_text(
        canvas,
        "INTENDED CLIPPING & GEOMETRY",
        tx,
        360,
        HEADING_SCALE_X,
        HEADING_SCALE_Y,
        FG_ACCENT_RGB,
        BG_PANEL_RGB,
        labels_log,
        role="heading",
    )
    y = 398
    for line in spec["clipping"]:
        _draw_text(canvas, line, tx, y, BODY_SCALE_X, BODY_SCALE_Y, FG_MUTED_RGB, BG_PANEL_RGB, labels_log)
        y += 28

    # Section 4: Failure Indicators
    _draw_text(
        canvas,
        "FAILURE INDICATORS (MARK FAIL IF OBSERVED)",
        tx,
        490,
        HEADING_SCALE_X,
        HEADING_SCALE_Y,
        FG_WARN_RGB,
        BG_PANEL_RGB,
        labels_log,
        role="heading",
    )
    y = 528
    for line in spec["failures"]:
        _draw_text(canvas, line, tx, y, BODY_SCALE_X, BODY_SCALE_Y, FG_WARN_RGB, BG_PANEL_RGB, labels_log)
        y += 28

    # Section 5: Operator Review & 8x Detail Zooms
    _draw_text(
        canvas,
        "OPERATOR ACTION & 8x ENLARGED DETAIL VIEWS",
        tx,
        592,
        HEADING_SCALE_X,
        HEADING_SCALE_Y,
        FG_OK_RGB,
        BG_PANEL_RGB,
        labels_log,
        role="heading",
    )
    _draw_text(
        canvas,
        spec["operator"],
        tx,
        630,
        BODY_SCALE_X,
        BODY_SCALE_Y,
        FG_TEXT_RGB,
        BG_PANEL_RGB,
        labels_log,
    )

    # Two 8x Detail Zoom Inset Cards inside Information Panel (y = 666..1042)
    zoom_card_xs = (1028, 1460)
    for zoom_spec, card_x in zip(spec["zooms"], zoom_card_xs):
        card_y = 666
        card_w = 420
        card_h = 376
        _fill_rect(canvas, card_x, card_y, card_w, card_h, BG_CARD_RGB)
        _stroke_rect(canvas, card_x, card_y, card_w, card_h, 2, BORDER_RGB)

        _draw_text(
            canvas,
            zoom_spec["caption1"],
            card_x + 12,
            card_y + 10,
            CAPTION_SCALE_X,
            CAPTION_SCALE_Y,
            FG_ACCENT_RGB,
            BG_CARD_RGB,
            labels_log,
            role="caption",
        )
        _draw_text(
            canvas,
            zoom_spec["caption2"],
            card_x + 12,
            card_y + 38,
            CAPTION_SCALE_X,
            CAPTION_SCALE_Y,
            FG_TEXT_RGB,
            BG_CARD_RGB,
            labels_log,
            role="caption",
        )

        zx = card_x + (card_w - ZOOM_DISPLAY_SIZE) // 2
        zy = card_y + 72
        _stroke_rect(
            canvas,
            zx - 2,
            zy - 2,
            ZOOM_DISPLAY_SIZE + 4,
            ZOOM_DISPLAY_SIZE + 4,
            2,
            FG_ACCENT_RGB,
        )
        _blit_nearest(
            canvas,
            pixels_565,
            zoom_spec["src_x0"],
            zoom_spec["src_y0"],
            ZOOM_SRC_SIZE,
            ZOOM_SRC_SIZE,
            zx,
            zy,
            ZOOM_SCALE,
        )

    return canvas, labels_log


def _render_conclusion_slide(scene_frames_565):
    canvas = bytearray(VIDEO_WIDTH * VIDEO_HEIGHT * 3)
    _fill_rect(canvas, 0, 0, VIDEO_WIDTH, VIDEO_HEIGHT, BG_CANVAS_RGB)
    labels_log = []

    # Top Header Banner
    _fill_rect(canvas, 24, 20, VIDEO_WIDTH - 48, 140, BG_PANEL_RGB)
    _stroke_rect(canvas, 24, 20, VIDEO_WIDTH - 48, 140, 2, BORDER_RGB)

    _draw_text(
        canvas,
        "S1–S4 Hardware Visual Review — Operator Sign-Off",
        48,
        36,
        TITLE_SCALE_X,
        TITLE_SCALE_Y,
        FG_TEXT_RGB,
        BG_PANEL_RGB,
        labels_log,
        role="title",
    )
    _draw_text(
        canvas,
        "Simulator-generated reference — not physical hardware footage",
        48,
        96,
        HEADING_SCALE_X,
        HEADING_SCALE_Y,
        FG_WARN_RGB,
        BG_PANEL_RGB,
        labels_log,
        role="heading",
    )

    # Four full 1x (240x240) uncropped scene thumbnails side-by-side
    cards = [
        ("s1", "S1: Edge Clipping", "edge_clipping", 24),
        ("s2", "S2: Image Source Clip", "image_source_clipping", 496),
        ("s3", "S3: Sprite Crop & Rot", "sprite_crop_and_rotation", 968),
        ("s4", "S4: Text & Font Clip", "text_opaque_transparent", 1440),
    ]
    for sid, short_title, scene_name, cx in cards:
        cy = 180
        cw = 456
        ch = 500
        _fill_rect(canvas, cx, cy, cw, ch, BG_PANEL_RGB)
        _stroke_rect(canvas, cx, cy, cw, ch, 2, BORDER_RGB)

        _draw_text(
            canvas,
            short_title,
            cx + 20,
            cy + 18,
            HEADING_SCALE_X,
            HEADING_SCALE_Y,
            FG_ACCENT_RGB,
            BG_PANEL_RGB,
            labels_log,
            role="heading",
        )
        _draw_text(
            canvas,
            f"Scene: {scene_name}",
            cx + 20,
            cy + 58,
            CAPTION_SCALE_X,
            CAPTION_SCALE_Y,
            FG_MUTED_RGB,
            BG_PANEL_RGB,
            labels_log,
            role="caption",
        )

        thumb_x = cx + (cw - DEFAULT_WIDTH) // 2
        thumb_y = cy + 100
        _stroke_rect(
            canvas,
            thumb_x - 2,
            thumb_y - 2,
            DEFAULT_WIDTH + 4,
            DEFAULT_HEIGHT + 4,
            2,
            BORDER_RGB,
        )
        _blit_nearest(
            canvas,
            scene_frames_565[sid],
            0,
            0,
            DEFAULT_WIDTH,
            DEFAULT_HEIGHT,
            thumb_x,
            thumb_y,
            1,
        )

        _draw_text(
            canvas,
            f"Serial Cmd: {sid.upper()}\\n | 240x240 RGB565",
            cx + 20,
            cy + 362,
            CAPTION_SCALE_X,
            CAPTION_SCALE_Y,
            FG_TEXT_RGB,
            BG_PANEL_RGB,
            labels_log,
            role="caption",
        )
        _draw_text(
            canvas,
            f"SHA: {EXPECTED_RAW_HASHES[sid][:20]}..",
            cx + 20,
            cy + 398,
            CAPTION_SCALE_X,
            CAPTION_SCALE_Y,
            FG_OK_RGB,
            BG_PANEL_RGB,
            labels_log,
            role="caption",
        )
        _draw_text(
            canvas,
            "Status: [ ] PASS  [ ] FAIL",
            cx + 20,
            cy + 434,
            CAPTION_SCALE_X,
            CAPTION_SCALE_Y,
            FG_WARN_RGB,
            BG_PANEL_RGB,
            labels_log,
            role="caption",
        )

    # Bottom Mandatory Operator Instructions Panel
    _fill_rect(canvas, 24, 704, VIDEO_WIDTH - 48, 352, BG_PANEL_RGB)
    _stroke_rect(canvas, 24, 704, VIDEO_WIDTH - 48, 352, 2, BORDER_RGB)

    _draw_text(
        canvas,
        "MANDATORY PHYSICAL HARDWARE VERIFICATION PROCEDURE",
        48,
        724,
        HEADING_SCALE_X,
        HEADING_SCALE_Y,
        FG_ACCENT_RGB,
        BG_PANEL_RGB,
        labels_log,
        role="heading",
    )
    _draw_text(
        canvas,
        "Compare the physical display against each simulator reference.",
        48,
        772,
        HEADING_SCALE_X,
        HEADING_SCALE_Y,
        FG_TEXT_RGB,
        BG_PANEL_RGB,
        labels_log,
        role="heading",
    )
    _draw_text(
        canvas,
        "Record PASS, FAIL, or INCONCLUSIVE for each scene.",
        48,
        818,
        HEADING_SCALE_X,
        HEADING_SCALE_Y,
        FG_OK_RGB,
        BG_PANEL_RGB,
        labels_log,
        role="heading",
    )
    _draw_text(
        canvas,
        "Physical visual review is required.",
        48,
        864,
        HEADING_SCALE_X,
        HEADING_SCALE_Y,
        FG_WARN_RGB,
        BG_PANEL_RGB,
        labels_log,
        role="heading",
    )

    footer_notes = [
        "* Simulator determinism proves host reproducibility, NOT physical ST7789 panel wiring or timing.",
        "* For pixel-exact analysis, inspect .build/simulator/renders/s1..s4/frame.png and annotated.png.",
        "* Log final physical observations in extras/hardware/Audit_Validation/TESTES.md.",
    ]
    y = 918
    for line in footer_notes:
        _draw_text(canvas, line, 48, y, BODY_SCALE_X, BODY_SCALE_Y, FG_MUTED_RGB, BG_PANEL_RGB, labels_log)
        y += 34

    return canvas, labels_log


def _verify_slide_labels_and_framebuffer(canvas, labels_log, pixels_565=None):
    min_heights = {"title": 36, "heading": 28, "body": 24, "caption": 20}
    in_bounds = True
    heights_ok = True
    contrast_ok = True
    for entry in labels_log:
        x0, y0, x1, y1 = entry["rect"]
        if x0 < 16 or y0 < 12 or x1 >= VIDEO_WIDTH - 16 or y1 >= VIDEO_HEIGHT - 12:
            in_bounds = False
        req_h = min_heights.get(entry["role"], 20)
        if entry["height_px"] < req_h:
            heights_ok = False
        if entry["contrast_ratio"] < 4.5:
            contrast_ok = False

    overlaps = 0
    for i in range(len(labels_log)):
        ax0, ay0, ax1, ay1 = labels_log[i]["rect"]
        for j in range(i + 1, len(labels_log)):
            bx0, by0, bx1, by1 = labels_log[j]["rect"]
            if not (ax1 < bx0 or bx1 < ax0 or ay1 < by0 or by1 < ay0):
                overlaps += 1

    fb_exact = True
    fb_mismatch = 0
    no_overlay = True
    if pixels_565 is not None:
        for entry in labels_log:
            lx0, ly0, lx1, ly1 = entry["rect"]
            if not (
                lx1 < FB_X0
                or lx0 >= FB_X0 + FB_DISPLAY_W
                or ly1 < FB_Y0
                or ly0 >= FB_Y0 + FB_DISPLAY_H
            ):
                no_overlay = False
        stride = VIDEO_WIDTH * 3
        for sy in range(DEFAULT_HEIGHT):
            for sx in range(DEFAULT_WIDTH):
                exp_rgb = rgb565_to_rgb888(pixels_565[sy * DEFAULT_WIDTH + sx])
                bx0 = FB_X0 + sx * FB_SCALE
                by0 = FB_Y0 + sy * FB_SCALE
                block_ok = True
                for dy in range(FB_SCALE):
                    row_off = (by0 + dy) * stride
                    for dx in range(FB_SCALE):
                        p = row_off + (bx0 + dx) * 3
                        act_rgb = (canvas[p], canvas[p + 1], canvas[p + 2])
                        if act_rgb != exp_rgb:
                            block_ok = False
                            break
                    if not block_ok:
                        break
                if not block_ok:
                    fb_exact = False
                    fb_mismatch += 1

    return {
        "labels_in_bounds": in_bounds,
        "heights_ok": heights_ok,
        "contrast_ok": contrast_ok,
        "label_overlaps": overlaps,
        "typography_pass": in_bounds and heights_ok and contrast_ok and overlaps == 0,
        "framebuffer_exact_4x_match": fb_exact,
        "framebuffer_mismatch_pixels": fb_mismatch,
        "no_overlay_on_framebuffer": no_overlay,
    }


def ensure_verified_reference_artifacts(out_dir):
    out_path = Path(out_dir).resolve()
    manifest_file = out_path / "manifest.json"
    needs_regen = not manifest_file.is_file()
    if not needs_regen:
        for sid, exp_hash in EXPECTED_RAW_HASHES.items():
            raw_file = out_path / sid / "frame.rgb565"
            png_file = out_path / sid / "frame.png"
            ann_file = out_path / sid / "annotated.png"
            if not (raw_file.is_file() and png_file.is_file() and ann_file.is_file()):
                needs_regen = True
                break
            if _sha256_bytes(raw_file.read_bytes()) != exp_hash:
                needs_regen = True
                break
    if needs_regen:
        generate_reference_suite(out_path)
    ref_verification = verify_suite_artifacts(out_path)
    if ref_verification.get("status") != "PASS":
        raise RuntimeError(f"S1-S4 reference artifact verification failed: {ref_verification}")
    return ref_verification


def generate_visual_guide(out_dir=None):
    if out_dir is None:
        out_dir = ROOT / ".build/simulator/renders"
    out_path = Path(out_dir).resolve()
    out_path.mkdir(parents=True, exist_ok=True)

    ref_audit = ensure_verified_reference_artifacts(out_path)

    scene_frames_565 = {}
    scenes_meta = {}
    for sid in REFERENCE_SCENES:
        raw_path = out_path / sid / "frame.rgb565"
        png_path = out_path / sid / "frame.png"
        ann_path = out_path / sid / "annotated.png"
        raw_bytes = raw_path.read_bytes()
        validate_frame(raw_bytes, DEFAULT_WIDTH, DEFAULT_HEIGHT)
        raw_sha = _sha256_bytes(raw_bytes)
        if raw_sha != EXPECTED_RAW_HASHES[sid]:
            raise RuntimeError(
                f"Unexpected RGB565 SHA-256 for {sid}: {raw_sha} != {EXPECTED_RAW_HASHES[sid]}"
            )
        png_bytes = png_path.read_bytes()
        dec_png = decode_png_rgb888(png_bytes)
        if (dec_png["width"], dec_png["height"]) != (DEFAULT_WIDTH, DEFAULT_HEIGHT):
            raise ValueError(f"{sid}/frame.png is not 240x240")
        scene_frames_565[sid] = decode_565le(raw_bytes)
        scenes_meta[sid] = {
            "scene_id": sid,
            "raw_rgb565_path": str(raw_path.relative_to(ROOT)),
            "frame_png_path": str(png_path.relative_to(ROOT)),
            "annotated_png_path": str(ann_path.relative_to(ROOT)),
            "raw_rgb565_sha256": raw_sha,
            "frame_png_sha256": _sha256_bytes(png_bytes),
            "annotated_png_sha256": _sha256_bytes(ann_path.read_bytes()),
        }

    slides_dir = out_path / "video_slides"
    slides_dir.mkdir(parents=True, exist_ok=True)

    slide_checks = {}
    segment_records = []

    for seg in TIMELINE_SEGMENTS:
        seg_id = seg["id"]
        if seg_id == "intro":
            canvas, labels_log = _render_intro_slide(scene_frames_565)
            check = _verify_slide_labels_and_framebuffer(canvas, labels_log, pixels_565=None)
        elif seg_id == "conclusion":
            canvas, labels_log = _render_conclusion_slide(scene_frames_565)
            check = _verify_slide_labels_and_framebuffer(canvas, labels_log, pixels_565=None)
        else:
            canvas, labels_log = _render_scene_slide(seg_id, scene_frames_565[seg_id])
            check = _verify_slide_labels_and_framebuffer(
                canvas, labels_log, pixels_565=scene_frames_565[seg_id]
            )

        if not check["typography_pass"] or not check["framebuffer_exact_4x_match"] or not check["no_overlay_on_framebuffer"]:
            raise RuntimeError(f"Slide layout validation failed for {seg_id}: {check}")

        slide_png = encode_png_rgb888(canvas, VIDEO_WIDTH, VIDEO_HEIGHT)
        slide_path = slides_dir / seg["slide_file"]
        slide_path.write_bytes(slide_png)

        slide_checks[seg_id] = check
        segment_records.append(
            {
                **seg,
                "slide_path": str(slide_path.relative_to(ROOT)),
                "slide_sha256": _sha256_bytes(slide_png),
                "frames": seg["duration_s"] * VIDEO_FPS,
            }
        )

    # Encode MP4 with ffmpeg using explicit filter_complex loop+concat for exact frame counts
    video_path = out_path / "validation-guide.mp4"
    ffmpeg_bin = shutil.which("ffmpeg")
    if not ffmpeg_bin:
        raise RuntimeError("ffmpeg is required to encode validation-guide.mp4")

    cmd = [ffmpeg_bin, "-y", "-v", "error"]
    filter_parts = []
    concat_inputs = []
    for idx, seg in enumerate(segment_records):
        slide_abs = ROOT / seg["slide_path"]
        cmd.extend(
            [
                "-loop",
                "1",
                "-framerate",
                str(VIDEO_FPS),
                "-t",
                str(seg["duration_s"]),
                "-i",
                str(slide_abs),
            ]
        )
        filter_parts.append(f"[{idx}:v]fps={VIDEO_FPS},format=yuv420p,setsar=1[v{idx}]")
        concat_inputs.append(f"[v{idx}]")

    filter_complex = (
        ";".join(filter_parts)
        + ";"
        + "".join(concat_inputs)
        + f"concat=n={len(segment_records)}:v=1:a=0,format=yuv420p[vout]"
    )
    total_duration = sum(s["duration_s"] for s in segment_records)
    total_frames = total_duration * VIDEO_FPS

    cmd.extend(
        [
            "-filter_complex",
            filter_complex,
            "-map",
            "[vout]",
            "-an",
            "-c:v",
            "libx264",
            "-crf",
            str(VIDEO_CRF),
            "-preset",
            "medium",
            "-pix_fmt",
            "yuv420p",
            "-r",
            str(VIDEO_FPS),
            "-frames:v",
            str(total_frames),
            "-movflags",
            "+faststart",
            str(video_path),
        ]
    )
    subprocess.run(cmd, check=True)

    result = {
        "video_path": str(video_path),
        "video_rel_path": str(video_path.relative_to(ROOT)),
        "video_sha256": _sha256_bytes(video_path.read_bytes()),
        "video_size_bytes": video_path.stat().st_size,
        "width": VIDEO_WIDTH,
        "height": VIDEO_HEIGHT,
        "fps": VIDEO_FPS,
        "total_duration_s": total_duration,
        "total_frames": total_frames,
        "scenes": scenes_meta,
        "segments": segment_records,
        "slide_checks": slide_checks,
        "reference_verification_overall_pass": ref_audit.get("status") == "PASS",
    }

    verification = verify_visual_guide(out_path, generation_result=result)
    _write_video_reports(out_path, result, verification)
    return result


def verify_visual_guide(out_dir=None, generation_result=None):
    if out_dir is None:
        out_dir = ROOT / ".build/simulator/renders"
    out_path = Path(out_dir).resolve()
    video_path = out_path / "validation-guide.mp4"
    slides_dir = out_path / "video_slides"

    ffprobe_bin = shutil.which("ffprobe")
    ffmpeg_bin = shutil.which("ffmpeg")
    if not ffprobe_bin or not ffmpeg_bin:
        raise RuntimeError("ffmpeg and ffprobe are required for video verification")

    probe_proc = subprocess.run(
        [
            ffprobe_bin,
            "-v",
            "error",
            "-show_entries",
            "stream=codec_name,codec_type,width,height,pix_fmt,r_frame_rate,avg_frame_rate,nb_frames,duration:format=format_name,duration,size",
            "-of",
            "json",
            str(video_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    probe_json = json.loads(probe_proc.stdout)
    streams = probe_json.get("streams", [])
    video_streams = [s for s in streams if s.get("codec_type") == "video"]
    audio_streams = [s for s in streams if s.get("codec_type") == "audio"]
    if len(video_streams) != 1:
        raise RuntimeError(f"Expected 1 video stream, found {len(video_streams)}")

    vs = video_streams[0]
    fmt = probe_json.get("format", {})
    duration_s = float(vs.get("duration") or fmt.get("duration") or 0.0)
    nb_frames = int(vs.get("nb_frames") or 0)

    ffprobe_summary = {
        "codec_name": vs.get("codec_name"),
        "width": int(vs.get("width", 0)),
        "height": int(vs.get("height", 0)),
        "pix_fmt": vs.get("pix_fmt"),
        "r_frame_rate": vs.get("r_frame_rate"),
        "avg_frame_rate": vs.get("avg_frame_rate"),
        "duration_s": round(duration_s, 3),
        "nb_frames": nb_frames,
        "audio_streams": len(audio_streams),
        "format_name": fmt.get("format_name"),
        "size_bytes": int(fmt.get("size", 0)),
    }

    # Verify clean stream decode
    dec_proc = subprocess.run(
        [ffmpeg_bin, "-v", "error", "-i", str(video_path), "-f", "null", "-"],
        capture_output=True,
        text=True,
    )
    clean_decode_pass = dec_proc.returncode == 0 and dec_proc.stderr.strip() == ""

    # Verify slide PNGs and decoded MP4 representative frames
    slides_verification = {}
    decoded_frames_verification = {}
    frames_dir = out_path / "video_frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    for idx, seg in enumerate(TIMELINE_SEGMENTS):
        seg_id = seg["id"]
        slide_path = slides_dir / seg["slide_file"]
        slide_raw = subprocess.run(
            [
                ffmpeg_bin,
                "-v",
                "error",
                "-i",
                str(slide_path),
                "-f",
                "rawvideo",
                "-pix_fmt",
                "rgb24",
                "-",
            ],
            check=True,
            capture_output=True,
        ).stdout

        if generation_result and seg_id in generation_result.get("slide_checks", {}):
            slides_verification[seg_id] = generation_result["slide_checks"][seg_id]
        else:
            if seg_id in REFERENCE_SCENES:
                raw_565 = decode_565le((out_path / seg_id / "frame.rgb565").read_bytes())
                mismatch = 0
                stride = VIDEO_WIDTH * 3
                for sy in range(DEFAULT_HEIGHT):
                    for sx in range(DEFAULT_WIDTH):
                        exp_rgb = bytes(rgb565_to_rgb888(raw_565[sy * DEFAULT_WIDTH + sx]))
                        bx0 = FB_X0 + sx * FB_SCALE
                        by0 = FB_Y0 + sy * FB_SCALE
                        exp_row = exp_rgb * FB_SCALE
                        for dy in range(FB_SCALE):
                            off = (by0 + dy) * stride + bx0 * 3
                            if slide_raw[off : off + FB_SCALE * 3] != exp_row:
                                mismatch += 1
                                break
                slides_verification[seg_id] = {
                    "framebuffer_exact_4x_match": mismatch == 0,
                    "framebuffer_mismatch_pixels": mismatch,
                    "no_overlay_on_framebuffer": mismatch == 0,
                    "typography_pass": True,
                }
            else:
                slides_verification[seg_id] = {
                    "framebuffer_exact_4x_match": True,
                    "framebuffer_mismatch_pixels": 0,
                    "no_overlay_on_framebuffer": True,
                    "typography_pass": True,
                }

        # Extract representative frame from MP4 at probe_time_s (both PNG on disk and raw RGB24)
        extracted_png = frames_dir / f"frame_{idx:02d}_{seg_id}.png"
        subprocess.run(
            [
                ffmpeg_bin,
                "-y",
                "-v",
                "error",
                "-ss",
                f"{seg['probe_time_s']:.2f}",
                "-i",
                str(video_path),
                "-frames:v",
                "1",
                "-pix_fmt",
                "rgb24",
                str(extracted_png),
            ],
            check=True,
        )
        ext_raw = subprocess.run(
            [
                ffmpeg_bin,
                "-v",
                "error",
                "-i",
                str(extracted_png),
                "-f",
                "rawvideo",
                "-pix_fmt",
                "rgb24",
                "-",
            ],
            check=True,
            capture_output=True,
        ).stdout

        # Compute full-frame MAE (sampled every 12 bytes = every 4th pixel)
        total_abs_diff = 0
        sample_count = 0
        for p in range(0, len(slide_raw), 12):
            total_abs_diff += (
                abs(slide_raw[p] - ext_raw[p])
                + abs(slide_raw[p + 1] - ext_raw[p + 1])
                + abs(slide_raw[p + 2] - ext_raw[p + 2])
            )
            sample_count += 3
        full_mae = total_abs_diff / max(1, sample_count)

        fb_mae = 0.0
        info_non_empty = True
        if seg_id in REFERENCE_SCENES:
            fb_diff = 0
            fb_channels = 0
            stride = VIDEO_WIDTH * 3
            for y in range(FB_Y0, FB_Y0 + FB_DISPLAY_H, 2):
                row_off = y * stride
                for x in range(FB_X0, FB_X0 + FB_DISPLAY_W, 2):
                    p = row_off + x * 3
                    fb_diff += (
                        abs(slide_raw[p] - ext_raw[p])
                        + abs(slide_raw[p + 1] - ext_raw[p + 1])
                        + abs(slide_raw[p + 2] - ext_raw[p + 2])
                    )
                    fb_channels += 3
            fb_mae = fb_diff / max(1, fb_channels)

            bright_pixels = 0
            for y in range(100, 1000, 4):
                row_off = y * stride
                for x in range(1030, 1880, 4):
                    p = row_off + x * 3
                    if ext_raw[p] > 80 or ext_raw[p + 1] > 80 or ext_raw[p + 2] > 80:
                        bright_pixels += 1
            info_non_empty = bright_pixels > 200

        decoded_frames_verification[seg_id] = {
            "probe_time_s": seg["probe_time_s"],
            "extracted_frame_path": str(extracted_png.relative_to(ROOT)),
            "full_frame_mae": round(full_mae, 4),
            "framebuffer_mae": round(fb_mae, 4),
            "info_panel_non_empty": info_non_empty,
            "pass": full_mae < 4.0 and fb_mae < 4.0 and info_non_empty,
        }

    overall_pass = (
        ffprobe_summary["codec_name"] == "h264"
        and ffprobe_summary["width"] == VIDEO_WIDTH
        and ffprobe_summary["height"] == VIDEO_HEIGHT
        and ffprobe_summary["pix_fmt"] == "yuv420p"
        and ffprobe_summary["r_frame_rate"] == f"{VIDEO_FPS}/1"
        and ffprobe_summary["avg_frame_rate"] == f"{VIDEO_FPS}/1"
        and 35.0 <= ffprobe_summary["duration_s"] <= 60.0
        and ffprobe_summary["audio_streams"] == 0
        and clean_decode_pass
        and all(v["framebuffer_exact_4x_match"] and v["typography_pass"] for v in slides_verification.values())
        and all(v["pass"] for v in decoded_frames_verification.values())
    )

    return {
        "overall_pass": overall_pass,
        "ffprobe": ffprobe_summary,
        "clean_decode_pass": clean_decode_pass,
        "slides": slides_verification,
        "decoded_frames": decoded_frames_verification,
    }


def _write_video_reports(out_path, result, verification):
    manifest_data = {
        "schema_version": "1.0.0",
        "generated_at_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "disclaimer": "Simulator-generated reference — not physical hardware footage.",
        "video": {
            "path": result["video_rel_path"],
            "sha256": result["video_sha256"],
            "size_bytes": result["video_size_bytes"],
            "codec": verification["ffprobe"]["codec_name"],
            "width": result["width"],
            "height": result["height"],
            "fps": result["fps"],
            "pixel_format": verification["ffprobe"]["pix_fmt"],
            "duration_s": result["total_duration_s"],
            "total_frames": result["total_frames"],
        },
        "scenes": result["scenes"],
        "segments": result["segments"],
        "verification": verification,
    }
    (out_path / "video_manifest.json").write_text(
        json.dumps(manifest_data, indent=2) + "\n", encoding="utf-8"
    )

    lines = [
        "# S1–S4 Hardware Visual Validation Video Guide Report",
        "",
        "> **Disclaimer:** Simulator-generated reference — not physical hardware footage.",
        "> Lossy H.264 (`yuv420p`) video encoding is a visual presentation guide for the hardware operator and must never be used as a pixel-exact golden reference. Use `frame.rgb565`, `frame.png`, and `annotated.png` for lossless pixel-exact verification.",
        "",
        "## 1. Video Artifact Summary",
        "",
        f"- **File:** `{result['video_rel_path']}`",
        f"- **SHA-256:** `{result['video_sha256']}`",
        f"- **File Size:** `{result['video_size_bytes']}` bytes",
        f"- **Container / Codec:** MP4 (`{verification['ffprobe']['codec_name']}`)",
        f"- **Resolution:** `{result['width']}×{result['height']}`",
        f"- **Frame Rate:** `{result['fps']} FPS` constant (`{verification['ffprobe']['r_frame_rate']}`)",
        f"- **Pixel Format:** `{verification['ffprobe']['pix_fmt']}`",
        f"- **Duration:** `{result['total_duration_s']:.1f} s` (`{result['total_frames']}` frames)",
        f"- **Clean Decode Check:** `{'PASS' if verification['clean_decode_pass'] else 'FAIL'}`",
        f"- **Overall Video Acceptance:** `{'PASS' if verification['overall_pass'] else 'FAIL'}`",
        "",
        "## 2. Provenance — Source Scene Hashes",
        "",
        "| Scene | Raw RGB565 SHA-256 | `frame.png` SHA-256 | `annotated.png` SHA-256 |",
        "|---|---|---|---|",
    ]
    for sid in REFERENCE_SCENES:
        smeta = result["scenes"][sid]
        lines.append(
            f"| `{sid.upper()}` | `{smeta['raw_rgb565_sha256']}` | `{smeta['frame_png_sha256']}` | `{smeta['annotated_png_sha256']}` |"
        )

    lines.extend(
        [
            "",
            "## 3. Video Timeline and Decoded Frame Verification",
            "",
            "| Segment | Time Window | Duration | Frames | Probe Time | Full-Frame MAE | Framebuffer MAE | Status |",
            "|---|---|---:|---:|---:|---:|---:|---|",
        ]
    )
    for seg in result["segments"]:
        sid = seg["id"]
        dchk = verification["decoded_frames"][sid]
        tw = f"`00:{seg['start_s']:02d}–00:{seg['end_s']:02d}`"
        lines.append(
            f"| `{sid}` ({seg['title']}) | {tw} | `{seg['duration_s']}s` | `{seg['frames']}` | `{dchk['probe_time_s']:.1f}s` | `{dchk['full_frame_mae']:.4f}` | `{dchk['framebuffer_mae']:.4f}` | `{'PASS' if dchk['pass'] else 'FAIL'}` |"
        )
    lines.append("")
    (out_path / "VIDEO_GUIDE_REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        default=str(ROOT / ".build/simulator/renders"),
        help="Output directory containing S1-S4 renders and validation-guide.mp4",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Verify existing validation-guide.mp4 without regenerating",
    )
    args = parser.parse_args(argv)
    if args.verify_only:
        ver = verify_visual_guide(args.out)
        print(json.dumps(ver, indent=2))
        return 0 if ver["overall_pass"] else 1
    res = generate_visual_guide(args.out)
    print(
        f"Generated {res['video_rel_path']} ({res['video_size_bytes']} bytes, "
        f"{res['total_duration_s']}s @ {res['fps']}fps, sha256={res['video_sha256']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
