[English](../en/configuration.md) | Português (Brasil)

# Configuração

A biblioteca lê `User_Setup.h` da pasta da biblioteca. Edite esse arquivo em uma instalação local do Arduino IDE. No PlatformIO, é possível manter a biblioteca intacta e fornecer definições equivalentes pelo `platformio.ini`.

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

`USER_SETUP_LOADED` informa à biblioteca que o sketch fornece a configuração e evita que o arquivo de configuração da biblioteca seja incluído novamente.

O pacote Arduino mantém os arquivos de implementação em `src/`. Edite o `User_Setup.h` da raiz do pacote como antes; o encaminhador em `src` preserva essa configuração, e o `User_Setup_Select.h` da raiz continua como encaminhador de compatibilidade para includes diretos. O `tft_setup.h` opcional do projeto ainda é carregado antes do seletor.

## Opções suportadas

| Opção | Padrão | Finalidade |
| --- | --- | --- |
| `ST7789_DRIVER` | Obrigatória | Seleciona o único controlador de display suportado. |
| `TFT_WIDTH`, `TFT_HEIGHT` | `240`, `240` | Dimensões do painel antes da rotação. |
| `TFT_MOSI`, `TFT_SCLK`, `TFT_DC`, `TFT_RST` | `13`, `14`, `0`, `2` | Pinos de dados/clock SPI, data-command e reset. |
| `TFT_CS` | Não definido | Pino opcional de seleção; no painel padrão, CS fica em nível baixo. |
| `TFT_MISO` | Não definido | Pino de leitura. Deixe indefinido em módulos somente para escrita. |
| `TFT_BL`, `TFT_BACKLIGHT_ON` | `5`, `LOW` | Pino opcional do backlight e nível ativo. |
| `SPI_FREQUENCY` | `40000000` | Clock de escrita SPI em Hz. |
| `SPI_READ_FREQUENCY` | `10000000` (padrão do header) | Clock de leitura SPI opcional, mais lento, quando MISO está conectado. |
| `TFT_SPI_MODE` | `SPI_MODE3` | Modo SPI do ST7789. |
| `TFT_SPI_OVERLAP` | Desativado | Usa a disposição de pinos SPI overlap do ESP8266. |
| `SUPPORT_TRANSACTIONS` | Depende do core | Ativa transações SPI quando disponíveis no core ESP8266. |
| `TFT_RGB_ORDER` | Padrão do controlador | Defina como `TFT_BGR` se vermelho e azul aparecerem trocados. |
| `TFT_INVERSION_ON` | Desativada | Ativa a inversão de cores do painel quando necessária. |
| `CGRAM_OFFSET` | Desativada | Aplica deslocamento na memória do display para painéis que precisam dele. |
| `LOAD_GLCD` | Ativada | Inclui a fonte GLCD embutida. |
| `LOAD_FONT2`, `LOAD_FONT4`, `LOAD_FONT6`, `LOAD_FONT7`, `LOAD_FONT8` | Ativadas na configuração fornecida na raiz | Incluem a fonte embutida correspondente. |
| `LOAD_GFXFF` | Ativada na configuração fornecida na raiz | Inclui as fontes GFX FreeFonts. |
| `SMOOTH_FONT` | Ativada na configuração fornecida na raiz | Ativa fontes suaves. |
| `FONT_FS_AVAILABLE` | Definida pela configuração de fonte suave | Ativa o suporte ao sistema de arquivos para fontes suaves. |
| `AA_GRAPHICS` | Sem efeito; obsoleta | Mantida por compatibilidade; não carrega uma extensão adicional. |
| `USER_SETUP_LOADED` | Desativada | Usa definições fornecidas pelo setup do projeto ou pelas opções de build. |
| `DISABLE_ALL_LIBRARY_WARNINGS` | Desativada | Suprime avisos da biblioteca quando suportado pelo compilador. |

Altere a ordem RGB ou a inversão uma opção por vez e execute `Colour_Test` para comparar o resultado. Use `TFT_SPI_OVERLAP` somente em placas conectadas para o modo overlap do ESP8266; essa opção não seleciona outro controlador.

O cabeçalho rejeita configurações incompatíveis durante a compilação:

| Erro | Causa |
| --- | --- |
| `TFT_eSPI_ESP8266 supports only ST7789_DRIVER` | `ST7789_DRIVER` não foi definido. |
| `TFT_eSPI_ESP8266 supports only SPI` | `TFT_PARALLEL_8_BIT` ou `TFT_PARALLEL_16_BIT` foi definido. |
| `TFT_eSPI_ESP8266 has no touch support` | `TOUCH_CS` foi definido. |
