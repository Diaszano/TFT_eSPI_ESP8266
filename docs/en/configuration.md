English | [Português (Brasil)](https://github.com/Diaszano/TFT_eSPI_ESP8266/blob/main/docs/pt-BR/configuration.md)

# Configuration

The library reads `User_Setup.h` from the library folder. Edit that file for a local Arduino IDE installation. In PlatformIO, you can keep the library untouched and provide equivalent definitions from `platformio.ini`.

```ini
[env:my_esp8266]
platform = espressif8266
board = nodemcuv2
framework = arduino
lib_deps = https://github.com/Diaszano/TFT_eSPI_ESP8266.git
build_flags =
  -DUSER_SETUP_LOADED
  -DST7789_DRIVER
  -DTFT_WIDTH=240
  -DTFT_HEIGHT=240
  -DTFT_MOSI=13
  -DTFT_SCLK=14
  -DTFT_DC=0
  -DTFT_RST=2
  -DTFT_BL=5
  -DTFT_BACKLIGHT_ON=LOW
  -DSPI_FREQUENCY=40000000
  -DLOAD_GLCD
```

`USER_SETUP_LOADED` tells the library that the sketch provides its setup and prevents the library setup from being included again.

## Supported options

| Option | Default | Purpose |
| --- | --- | --- |
| `ST7789_DRIVER` | Required | Selects the only supported display controller. |
| `TFT_WIDTH`, `TFT_HEIGHT` | `240`, `240` | Panel dimensions before rotation. |
| `TFT_MOSI`, `TFT_SCLK`, `TFT_DC`, `TFT_RST` | `13`, `14`, `0`, `2` | SPI data/clock, data-command and reset pins. |
| `TFT_CS` | Undefined | Optional chip-select pin; the default panel ties CS low. |
| `TFT_MISO` | Undefined | Read pin. Leave undefined for a write-only module. |
| `TFT_BL`, `TFT_BACKLIGHT_ON` | `5`, `LOW` | Optional backlight pin and active level. |
| `SPI_FREQUENCY` | `40000000` | SPI write clock in Hz. |
| `SPI_READ_FREQUENCY` | Controller default | Optional slower SPI read clock when MISO is wired. |
| `TFT_SPI_MODE` | `SPI_MODE3` | SPI mode for the ST7789. |
| `TFT_SPI_OVERLAP` | Off | Uses the ESP8266 overlap SPI pin arrangement. |
| `SUPPORT_TRANSACTIONS` | Core-dependent | Enables SPI transactions when supported by the ESP8266 core. |
| `TFT_RGB_ORDER` | Controller default | Set to `TFT_BGR` if the panel displays red and blue swapped. |
| `TFT_INVERSION_ON` | Off | Enables panel color inversion when required by the module. |
| `CGRAM_OFFSET` | Off | Applies a display-memory offset for panels that need it. |
| `LOAD_GLCD` | On | Includes the built-in 6×8 font. |
| `LOAD_FONT2`, `LOAD_FONT4`, `LOAD_FONT6`, `LOAD_FONT7`, `LOAD_FONT8` | Off | Includes the corresponding built-in font. |
| `LOAD_GFXFF` | Off | Includes the GFX FreeFonts. |
| `SMOOTH_FONT` | Off | Enables anti-aliased smooth fonts. |
| `FONT_FS_AVAILABLE` | Set by smooth-font setup | Enables smooth-font filesystem support. |
| `USER_SETUP_LOADED` | Off | Uses definitions supplied by the sketch or build flags. |
| `DISABLE_ALL_LIBRARY_WARNINGS` | Off | Suppresses library warnings where supported by the compiler. |

Change RGB order or inversion one option at a time and run `Colour_Test` to compare the result. `TFT_SPI_OVERLAP` is for boards wired for the ESP8266 overlap mode; it does not select a different controller.

The header rejects incompatible configurations at compile time:

| Error | Trigger |
| --- | --- |
| `TFT_eSPI_ESP8266 supports only ST7789_DRIVER` | `ST7789_DRIVER` is not defined. |
| `TFT_eSPI_ESP8266 supports only SPI` | Either `TFT_PARALLEL_8_BIT` or `TFT_PARALLEL_16_BIT` is defined. |
| `TFT_eSPI_ESP8266 has no touch support` | `TOUCH_CS` is defined. |
