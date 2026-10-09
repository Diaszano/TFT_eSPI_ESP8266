English | [Português (Brasil)](https://github.com/Diaszano/TFT_eSPI_ESP8266/blob/main/docs/pt-BR/getting-started.md)

# Getting started

## Wiring

The default `User_Setup.h` targets a 240 × 240 ST7789 module. Match the display labels to these ESP8266 pins:

| Display signal | ESP8266 GPIO | Default setting |
| --- | ---: | --- |
| MOSI / SDA | 13 | `TFT_MOSI` |
| SCLK / SCL | 14 | `TFT_SCLK` |
| DC / A0 | 0 | `TFT_DC` |
| RESET | 2 | `TFT_RST` |
| Backlight | 5 | `TFT_BL` |
| CS | Ground | `TFT_CS` is not defined |
| MISO / SDO | Not connected | Display is write-only |
| VCC, GND | Board supply, ground | Check your module's voltage requirements |

GPIO0 and GPIO2 are ESP8266 boot-strap pins. Keep both HIGH during reset and boot; the configured display wiring does this on the target board.

## Install with PlatformIO

Add this to `platformio.ini`:

```ini
[env:my_esp8266]
platform = espressif8266
board = nodemcuv2
framework = arduino
lib_deps = https://github.com/Diaszano/TFT_eSPI_ESP8266.git
```

This repository provides the independently maintained `TFT_eSPI_ESP8266` package. Its release number is recorded in the manifests; `TFT_ESPI_VERSION` continues to identify the inherited 2.5.44 source baseline.

## Install with Arduino IDE

Download the repository as a ZIP and use **Sketch → Include Library → Add .ZIP Library**. If the original `TFT_eSPI` is already installed, remove it first. Both libraries provide `TFT_eSPI.h`; leaving the original installed can make Arduino IDE select the wrong copy.

## First sketch

```cpp
#include <TFT_eSPI.h>
TFT_eSPI tft;

void setup() {
  tft.init();
  tft.fillScreen(TFT_BLACK);
  tft.setTextColor(TFT_WHITE, TFT_BLACK);
  tft.drawString("Hello, ESP8266!", 20, 100, 2);
}

void loop() {}
```

Compile and upload, then run the `Read_User_Setup` example to confirm the selected pins and display settings. `Colour_Test` checks color order and inversion on the panel.
