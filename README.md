English | [Português (Brasil)](https://github.com/Diaszano/TFT_eSPI_ESP8266/blob/main/README.pt-BR.md)

# TFT_eSPI_ESP8266

[![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/Diaszano/TFT_eSPI_ESP8266/badge)](https://scorecard.dev/viewer/?uri=github.com/Diaszano/TFT_eSPI_ESP8266)

TFT_eSPI_ESP8266 is an Arduino graphics library for driving an ST7789 display over SPI from an ESP8266. It keeps the familiar `TFT_eSPI.h` header and `TFT_eSPI` class, with graphics, text, fonts and RAM sprites configured for this target.

| Part | Supported target |
| --- | --- |
| Board | ESP8266, such as NodeMCU or Wemos D1 mini |
| Display controller | ST7789, 240 × 240 default setup |
| Bus | SPI, write-only by default |
| Setup | `User_Setup.h` in this repository |

## Quick start

Add the library to a PlatformIO project:

```ini
lib_deps = https://github.com/Diaszano/TFT_eSPI_ESP8266.git
```

With the default wiring in `User_Setup.h`, try this sketch:

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

## Documentation

- [Getting started](docs/en/getting-started.md)
- [Configuration](docs/en/configuration.md)
- [Fonts](docs/en/fonts.md)
- [Sprites](docs/en/sprites.md)
- [Limitations and migration](docs/en/limitations.md)
- [Development](docs/en/development.md)
- [API reference](https://diaszano.github.io/TFT_eSPI_ESP8266/)

This fork is maintained by Lucas Dias (Diaszano) and is based on [Bodmer/TFT_eSPI](https://github.com/Bodmer/TFT_eSPI) 2.5.44. The package release version is maintained in the library manifests; `TFT_ESPI_VERSION` intentionally identifies the inherited 2.5.44 source baseline. Upstream and contributor notices remain in [license.txt](license.txt).
