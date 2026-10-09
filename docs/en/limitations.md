English | [Português (Brasil)](https://github.com/Diaszano/TFT_eSPI_ESP8266/blob/main/docs/pt-BR/limitations.md)

# Limitations

The default wiring has no MISO connection. `readPixel()` returns black, and `readRect()` cannot retrieve pixels from the panel. Anti-aliased drawing directly to the TFT needs an explicit `bg_color` because the library cannot read the existing background. Anti-aliasing inside a Sprite is unaffected.

The library has no touch or DMA API and supports only the ST7789 over SPI. The setup header rejects touch, parallel interfaces and other controllers.

## Coming from TFT_eSPI

| Removed | Note |
| --- | --- |
| Touch (`getTouch`, `calibrateTouch`...) and `TFT_eSPI_Button` | Defining `TOUCH_CS` produces a compile-time error. |
| DMA (`initDMA`, `pushImageDMA`, `dmaWait`...) | The ESP8266 has no DMA support here; use `pushImage`. |
| Other controllers (`ILI9341`, `ST7735`...) and `ST7789_2_DRIVER` | Only `ST7789_DRIVER` is accepted. |
| ESP32, RP2040, STM32 and ESP-IDF | These platforms are outside this library's target. |
| Parallel 8/16-bit buses | Defining `TFT_PARALLEL_*` produces a compile-time error. |
| `User_Setups/` and `User_Setup_Select.h` selector | Edit `User_Setup.h` or provide setup definitions with `build_flags`. |

The package is named `TFT_eSPI_ESP8266`; sketches continue to include `TFT_eSPI.h` and use `TFT_eSPI`.
`AA_GRAPHICS` is a deprecated no-op kept for source compatibility. It does not load an extra graphics implementation; smooth fonts remain controlled by `SMOOTH_FONT`.

The compiler-warning gate covers owned source compiled through the pinned ESP8266 PlatformIO profile. Framework and vendor warnings are reported separately; this gate does not claim clang-tidy coverage.

The clang-tidy 22.1.8 target pilot currently fails to parse ESP8266 Xtensa flags and SDK headers. Its compilation database is validated, but no target tidy findings are baselined and no target tidy CI gate is enabled. The native PlatformIO `run -t compiledb` database currently contains Unity itself but not the test translation unit, and `pio test` has no compiledb target; native-only analysis also lacks a complete database.

The optional cppcheck 2.11 pilot scans the staged library and reports existing findings; it is not a clean or required gate. Its resolved analyzer package must be reviewed and pinned before any future required use.
