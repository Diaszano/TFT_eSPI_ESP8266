[English](README.md) | Português (Brasil)

# TFT_eSPI_ESP8266

TFT_eSPI_ESP8266 é uma biblioteca gráfica Arduino para controlar um display ST7789 por SPI com um ESP8266. Ela mantém o cabeçalho conhecido `TFT_eSPI.h` e a classe `TFT_eSPI`, com gráficos, texto, fontes e sprites em RAM configurados para este alvo.

| Parte | Alvo suportado |
| --- | --- |
| Placa | ESP8266, como NodeMCU ou Wemos D1 mini |
| Controlador do display | ST7789, configuração padrão de 240 × 240 |
| Barramento | SPI, somente escrita por padrão |
| Configuração | `User_Setup.h` neste repositório |

## Início rápido

Adicione a biblioteca a um projeto PlatformIO:

```ini
lib_deps = https://github.com/Diaszano/TFT_eSPI_ESP8266.git
```

Com a ligação padrão definida em `User_Setup.h`, experimente este sketch:

```cpp
#include <TFT_eSPI.h>
TFT_eSPI tft;

void setup() {
  tft.init();
  tft.fillScreen(TFT_BLACK);
  tft.setTextColor(TFT_WHITE, TFT_BLACK);
  tft.drawString("Olá, ESP8266!", 20, 100, 2);
}

void loop() {}
```

## Documentação

- [Primeiros passos](docs/pt-BR/getting-started.md)
- [Configuração](docs/pt-BR/configuration.md)
- [Fontes](docs/pt-BR/fonts.md)
- [Sprites](docs/pt-BR/sprites.md)
- [Limitações e migração](docs/pt-BR/limitations.md)
- [Desenvolvimento](docs/pt-BR/development.md)
- [Referência da API](https://diaszano.github.io/TFT_eSPI_ESP8266/)

Esta biblioteca é baseada em [Bodmer/TFT_eSPI](https://github.com/Bodmer/TFT_eSPI) 2.5.44. Consulte a [licença](license.txt).
