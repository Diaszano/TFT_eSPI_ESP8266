# ST7789 240x240 manual hardware test plan

Status: prepared, not executed. Running it requires separate authorization.

Target: ESP-12F (ESP8266EX, 4 MiB flash, 26 MHz crystal), ST7789 240x240 RGB565 on HSPI.
Wiring: MOSI GPIO13, SCLK GPIO14, DC GPIO0, RST GPIO2, CS tied to GND, backlight GPIO5 active LOW.

## Preconditions

1. Build both firmware images from the same sketch: one against `main`, one against the branch under
   test. Use `espressif8266@4.2.1` and `-DSPI_FREQUENCY=27000000`, because 27 MHz is the only verified
   clock. Record the ELF sizes.
2. Install manually. The operator enters the bootloader by holding GPIO0 low during reset, then
   confirms the post-install reboot by hand. Do not let any tool auto-reset the board, erase flash
   or touch LittleFS.
3. GPIO0 and GPIO2 are boot-strapping pins. Confirm that the board boots normally (GPIO0 high,
   GPIO2 high) with the display attached before running any test.
4. Serial at 115200 for timing and heap logs only. Open it manually.

## Cases

Run every case on `main` and on the branch, in rotations 0, 1, 2 and 3. Rotations 2 and 3 use the
80-pixel CGRAM offset, which exercises the coordinate fix.

| # | Case | Steps | Pass criteria |
|---|------|-------|---------------|
| 1 | Init and backlight | Power up, `init()`, `fillScreen(TFT_BLACK)` | Backlight on (GPIO5 LOW); no noise; boot completes |
| 2 | `fillScreen` | Fill red, green, blue, white, black | Uniform colours, correct RGB order, no stripes at edges |
| 3 | Edge clipping | `fillRect` and `drawFastHLine`/`VLine` crossing each edge, plus `fillRect(100,100,INT32_MAX,INT32_MAX)` | Only on-screen pixels drawn; no wrap to the opposite edge; no reset |
| 4 | Font 1 opaque/transparent | `drawString("ABCJ 0123", x, y, 1)` with bg != fg, then bg == fg over a striped background | Glyphs identical to `main`; transparent leaves the stripes intact |
| 5 | Font 2 opaque/transparent | Same as 4 with font 2, including Portuguese test strings used by Dzunix | Same as 4 |
| 6 | Font 4 opaque/transparent | `drawNumber` with padding, digits 0-9, values that shrink in width | No stale pixels, correct padding, transparent over stripes |
| 7 | Text at the right/bottom edge | Font 1/2/4 glyphs partially off-screen | Clipped cleanly; no wrapped pixels |
| 8 | PROGMEM icon | 16x16 and 33x17 RGB565 icons, opaque and with a transparent colour, also with `setSwapBytes(true)` | Colours and orientation match `main` |
| 9 | Clipped 1 bpp image | `pushImage(0, -5, w, h, bitmap1bpp, false)` | Top 5 rows hidden; the visible part starts at source row 5 (on `main` this shows rows 0..) |
| 10 | 8/4 bpp sprites | `pushSprite` at x = -3 (odd offset), with and without a transparent colour | Matches `main` |
| 11 | Rotated sprite | `pushRotated` at 0, 45, 90, 200 degrees; a 200-pixel-wide sprite | Matches `main`; no reset |
| 12 | Repeated partial updates | Loop 10 000 times: update a 4-digit counter (font 4), a 32x32 sprite and one line | No visual drift; no WDT reset; heap stable |
| 13 | Wi-Fi coexistence | Repeat 12 with Wi-Fi associated | No WDT or exception resets |

## Measurements

- Time each case with `micros()` around the call, over 100 repetitions, and report the median and
  maximum. Compare `main` against the branch on the same board at the same clock. These are the
  only valid source for speed claims; host transaction counts are not.
- Heap: log `ESP.getFreeHeap()`, `ESP.getMaxFreeBlockSize()` and `ESP.getHeapFragmentation()` every
  1 000 iterations in case 12. Pass when the values are stable after warm-up.
- Stack: log `ESP.getFreeContStack()` after case 12 and after the deepest text and sprite calls.
  Compare with the compile-time chain estimates (drawNumber 320 B, pushToSprite 416 B).

## Reporting

For every case, record pass or fail, a photo of any difference from `main`, the timings, and the
heap and stack logs. Stop at the first reset or visible corruption, and keep the serial log.
