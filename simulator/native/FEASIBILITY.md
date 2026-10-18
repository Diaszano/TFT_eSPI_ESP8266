# Simulator gates: D0, D1 and D2

> Historical report: its BGR-converted visible pixel values describe the old
> simulator model. The current 240×240 profile exposes logical RGB565 after
> accounting for the configured BGR panel order. See
> [the color pipeline](../COLOR_PIPELINE.md). Physical filter order remains
> unverified.

Validated in worktree `/home/diaszano/.codex/worktrees/6ad5/simulator-scenes`,
branch `codex/simulator-scenes`, based on `531b5310`; Plan 09 changes are recorded
in four local commits. All checks are host/build-only; no UART, USB, GPIO or ESP8266 hardware was used.

## Effective display profile

`User_Setup.h` and `simulator/CMakeLists.txt` both select ST7789, 240×240,
MOSI=13, SCLK=14, DC=0, RST=2 and 40 MHz. `CGRAM_OFFSET` is inferred by
`ST7789_Defines.h` for 240×240 and, because `TFT_RGB_ORDER` is unset, the
production rotation code selects BGR (`MADCTL` bit 3). The simulator host target
enables GLCD/font 1, font 2 and font 4; the firmware setup also enables fonts
6–8, GFX fonts and Smooth fonts, which are outside this host profile.

The controller model is the ST7789V 240×320 GRAM with a 240×240 active region.
The source describes the 240×320 memory bounds, the 0..239 / 0..319 address
ranges, and Y-first counter increments for `MV=1` ([Sitronix ST7789V
datasheet](https://dl.espressif.com/dl/schematics/ST7789V_SPEC_V1.0.pdf), §§8.11–8.12).
The 240×240 glass origin within that GRAM is rotation-dependent through the
production driver's `colstart`/`rowstart`; it is not a fixed profile offset.

## Root causes and corrections

| Finding | Classification | Correction/evidence |
| --- | --- | --- |
| Model validated CASET against 240 and RASET against 320 for every MADCTL value, and always advanced X first. | Simulator defect | With `MV=1`, swap effective CASET/RASET bounds, advance Y first, wrap Y to its start then advance X, and store the transposed address into 240×320 GRAM. New tests cover 80..319/0..239, endpoint pixel, transposed order and overflow. |
| `visible_pixel` mirrored Y using the 240-pixel viewport instead of the 320-address GRAM. | Simulator defect | Apply MY against the GRAM height. This maps rotation 2/3 windows using the driver's 80-address origin and leaves the visible 240×240 region exact. |
| `tft_Write_32C` shifted signed `int` values into bit 31. UBSan reproduced `left shift of 81665 by 16 places cannot be represented in type 'int'` at `TFT_eSPI.cpp:3110`. The first unsigned fix also let swapped coordinate bits spill into the other 16-bit field (C=300,D=100). | Production library defect | Cast to `uint32_t`, then mask each byte-swapped address to 16 bits before packing. RED reproduced the signed shift and the transport regression; GREEN preserves CASET/RASET bytes and passes sanitizers and ESP8266 compile-only matrix. |
| `image_crop16` and edge shapes initially used visible-only coordinates during diagnosis. | Test coverage gap | Restored negative/over-edge source rectangles. Production `PI_CLIP`/`fillRect` paths crop partial rectangles and images; fully off-screen fill emits no visible pixel. Exact reference comparisons pass. |
| No independent font RLE glyph reference exists for this host profile. | Incomplete evidence | Font 1/2/4 paths execute, but the scene reports `SKIP[NO_INDEPENDENT_FONT_GOLDEN]`. It does not claim visual correctness. |
| Physical S1–S4 cases require human visual approval. | Incomplete evidence | Firmware and simulator call the same extracted drawing function; host scene status is `SKIP[VISUAL_REVIEW_REQUIRED]`. |

## Addressing and rotation matrix

Raw GRAM bounds remain X=0..239 and Y=0..319. Table values below are the
production transmitted windows for the 4×4 directional marker at logical
(20,30); the actual marker color is BGR-converted blue `0x001F` because the
input's first pixel is red. Pixel coordinates are from the independently
calculated exact frame expectation.

| Rotation | MADCTL | colstart | rowstart | Visible | GRAM bounds | CASET | RASET | Expected marker | Actual | Result |
| ---: | ---: | ---: | ---: | --- | --- | --- | --- | --- | --- | --- |
| 0 | `0x08` | 0 | 0 | 240×240 | X 0..239, Y 0..319 | 0..239 | 0..239 | `(20,30)=001F` | `001F` | PASS |
| 1 | `0x68` | 0 | 0 | 240×240 | X 0..239, Y 0..319 | 0..239 | 0..239 | `(20,209)=001F` | `001F` | PASS |
| 2 | `0xC8` | 0 | 80 | 240×240 | X 0..239, Y 0..319 | 0..239 | 80..319 | `(219,209)=001F` | `001F` | PASS |
| 3 | `0xA8` | 80 | 0 | 240×240 | X 0..239, Y 0..319 | 80..319 | 0..239 | `(219,30)=001F` | `001F` | PASS |

The production edge scene is independently compared in all four orientations.
At rotation 0 it covers left/right/top/bottom partial rectangles, all four
partially visible corners, clipped horizontal and vertical lines, a zero-width
rectangle, and a fully off-screen rectangle. The `image_crop16` scene tests
partial source crops on all four edges. A separate controller test writes
address Y=250 (valid GRAM, outside the visible area) and confirms raw GRAM is
updated while every visible pixel stays black. Under `MV=1`, endpoint
CASET=319/RASET=239 is accepted and writes raw `(239,319)`; CASET=320 and
RASET=240 are rejected as `InvalidWindow`. Address-window validation rejects
unsupported addresses instead of clamping them.

## Gate D0 — production SPI seam

**PASS, scoped to the write-only ST7789 transport.** Production `TFT_eSPI.cpp`
and sprite code are compiled on the host; SPI init, `fillRect`, `drawLine`,
`pushImage`, RGB565 byte order, `pushBlock`/SPI1W15, `pushPixels`, and
`pushSwapBytePixels` are exercised. Display reads and touch SPI return
`UNSUPPORTED_OPERATION`. Physical bus timing and electrical behavior are not
inferred.

Original evidence at source base `78a58c91`: SPI inventory unittest, CMake build,
2/2 CTest, `make test-host`, and `make test-compile` passed. Updated host and
firmware build evidence is listed below.

## Gate D1 — ST7789 model and framebuffer

**PASS for the supported ST7789V command/profile subset.** The model now
interprets CASET, RASET, RAMWR, MADCTL `MX/MY/MV/RGB`, RGB565, reset/display
state and visible-window mapping. Address writes obey inclusive bounds and
rotation-dependent address increment order. Tests cover fragmented RGB565,
row/column wrapping, overflow, invalid windows, all four MADCTL orientations
using asymmetric colors, BGR presentation, inversion metadata, reset,
the 240×320 GRAM endpoint, and a valid invisible row. Unsupported controller
commands remain explicitly unsupported; inversion remains metadata rather than
an optical simulation.

The previous model passed tests that used only square 4×4 address windows; the
new 240×320/MV tests failed before the correction (`sim_st7789_rotation` at the
transposed pixel assertion, and `sim_production_render` on a rotated marker).
They now pass without relaxing bounds or assertions.

## Gate D2 — production rendering and scenes

**PASS for the four-or-more exact production scenes required by D2.** Real
`TFT_eSPI` graphics paths emit SPI traces; the ST7789 model replays those traces
and tests compare every visible RGB565 pixel against independent expectations:

| Scene | Verification |
| --- | --- |
| `solid_rgb565` | Exact 240×240 frame with independent RGB565 color bands and BGR order. |
| `edge_rect` | Exact frame from Plan 02's `validation_oracle.h`, including clipping, corners, axis lines, zero-width and fully off-screen input, in rotations 0–3. |
| `image_crop16` | Exact seeded RGB565 pattern with independent source indexing and four edge crops. |
| `rotation_0_3` | Exact asymmetric 4×4 marker table in each rotation; all four physical corners/directions are distinguishable. |
| `sprite_depths` | Exact checkerboard frame through real 1/4/8/16 bpp `TFT_eSprite` paths. |

`text_edges` executes production font 1/2/4 rendering but reports
`SKIP[NO_INDEPENDENT_FONT_GOLDEN]`. S1–S4 use the same extracted draw functions
as the physical sketch and are invoked by host tests, but report
`SKIP[VISUAL_REVIEW_REQUIRED]`. A render-only CLI result is labeled `RENDERED`,
never `PASS`; only the exact comparison tests pass.

## Regression and verification evidence

| Command | Result |
| --- | --- |
| `cmake --build .build/simulator/debug` | PASS |
| `ctest --test-dir .build/simulator/debug --output-on-failure` | PASS, 9/9, ASan+UBSan, including the C=300/D=100 CASET/RASET packing regression. |
| `make test-host` | PASS; text font 4 retains its pre-existing independent-fixture SKIP. |
| `make test-host-extremes` | PASS; extreme coordinate, clipping and image cases; sprite off-screen retains its expected SKIP. |
| `make test-compile` | PASS, exit 0; three ESP8266 `nodemcuv2` compile-only projects. PlatformIO warned that Core 6.1.18 is obsolete; no compile errors. |
| `make test-hw-build` | PASS, exit 0 after the final `tft_Write_32C` mask; reran the compile matrix and rebuilt the physical validation sketch. Build-only; no upload, serial, or reset. |
| `simulator_runner --scene solid_rgb565 --seed 7 --rotation 0` | `RENDERED`, exit 0. |
| `simulator_runner --scene text_edges` | `SKIP[NO_INDEPENDENT_FONT_GOLDEN]`, exit 3. |
| `simulator_runner --scene nonexistent` | `UNSUPPORTED`, exit 2. |
| `simulator_runner --scene solid_rgb565 --rotation 4` | usage error, exit 2. |
| Original `tft_Write_32C` + `sim_production_render` | RED: UBSan signed-left-shift at line 3110. |
| Unsigned `tft_Write_32C` + `sim_production_render` | GREEN: full pixel assertions run without UB. |
| Unsigned unmasked `tft_Write_32C` + `sim_real_transport` (C=300,D=100) | RED: CASET packed coordinate mismatch. |
| Masked `tft_Write_32C` + `sim_real_transport` | GREEN: CASET and RASET bytes match 0x012C/0x0064 and 0x0064/0x0064. |

## Limitations and hardware evidence

No physical ESP8266 or logic analyzer was used. The compile-only target proves
ESP8266 toolchain compatibility, not transmitted electrical timing or what a
specific 240×240 module wires as its visible crop. The controller model covers
the documented/observed command subset only. Text lacks an independent host
font golden; S1–S4 still need authorized manual visual review. There are no
commits, pushes, merges, firmware uploads, or worktree changes outside this
isolated branch.
