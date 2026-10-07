[English](../en/limitations.md) | Português (Brasil)

# Limitações

A ligação padrão não tem conexão MISO. `readPixel()` retorna preto, e `readRect()` não consegue obter pixels do painel. O desenho com antialiasing diretamente no TFT precisa receber um `bg_color` explícito porque a biblioteca não pode ler o fundo existente. O antialiasing dentro de um Sprite não é afetado.

A biblioteca não tem API de touch nem DMA e suporta somente o ST7789 por SPI. O cabeçalho de configuração rejeita touch, interfaces paralelas e outros controladores.

## Vindo do TFT_eSPI

| Removido | Observação |
| --- | --- |
| Touch (`getTouch`, `calibrateTouch`...) e `TFT_eSPI_Button` | Definir `TOUCH_CS` causa erro durante a compilação. |
| DMA (`initDMA`, `pushImageDMA`, `dmaWait`...) | O ESP8266 não tem suporte a DMA aqui; use `pushImage`. |
| Outros controladores (`ILI9341`, `ST7735`...) e `ST7789_2_DRIVER` | Somente `ST7789_DRIVER` é aceito. |
| ESP32, RP2040, STM32 e ESP-IDF | Essas plataformas não fazem parte do alvo desta biblioteca. |
| Barramentos paralelos de 8/16 bits | Definir `TFT_PARALLEL_*` causa erro durante a compilação. |
| `User_Setups/` e seletor `User_Setup_Select.h` | Edite `User_Setup.h` ou forneça as definições em `build_flags`. |

O pacote se chama `TFT_eSPI_ESP8266`; os sketches continuam incluindo `TFT_eSPI.h` e usando `TFT_eSPI`.
