[English](../en/getting-started.md) | Português (Brasil)

# Primeiros passos

## Ligações

O `User_Setup.h` padrão é destinado a um módulo ST7789 de 240 × 240. Conecte os sinais do display aos pinos do ESP8266:

| Sinal do display | GPIO ESP8266 | Configuração padrão |
| --- | ---: | --- |
| MOSI / SDA | 13 | `TFT_MOSI` |
| SCLK / SCL | 14 | `TFT_SCLK` |
| DC / A0 | 0 | `TFT_DC` |
| RESET | 2 | `TFT_RST` |
| Backlight | 5 | `TFT_BL` |
| CS | GND | `TFT_CS` não está definido |
| MISO / SDO | Sem conexão | O display funciona somente para escrita |
| VCC, GND | Alimentação da placa, terra | Confira os requisitos de tensão do módulo |

GPIO0 e GPIO2 são pinos de inicialização do ESP8266. Mantenha ambos em HIGH durante o reset e a inicialização; a ligação padrão do display faz isso na placa alvo.

## Instalação com PlatformIO

Adicione ao `platformio.ini`:

```ini
[env:my_esp8266]
platform = espressif8266
board = nodemcuv2
framework = arduino
lib_deps = https://github.com/Diaszano/TFT_eSPI_ESP8266.git
```

## Instalação com Arduino IDE

Baixe o repositório como ZIP e use **Sketch → Include Library → Add .ZIP Library**. Se a biblioteca original `TFT_eSPI` já estiver instalada, remova-a primeiro. As duas bibliotecas fornecem `TFT_eSPI.h`; com a original instalada, o Arduino IDE pode selecionar a cópia errada.

## Primeiro sketch

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

Compile e envie o sketch. Em seguida, execute o exemplo `Read_User_Setup` para confirmar os pinos e as opções selecionadas. `Colour_Test` verifica a ordem das cores e a inversão no painel.
