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
