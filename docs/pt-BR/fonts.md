[English](../en/fonts.md) | Português (Brasil)

# Fontes

## Fontes embutidas

Ative uma fonte com a macro `LOAD_*` correspondente em `User_Setup.h`. A fonte GLCD fica ativa por padrão; as outras são opcionais. As fontes embutidas 4, 6, 7 e 8 usam codificação run-length em flash. A configuração incluída habilita todas as fontes embutidas e as GFX FreeFonts.

| Fonte | Macro de configuração | Notas |
| --- | --- | --- |
| GLCD | `LOAD_GLCD` | 6×8; aproximadamente 1.820 bytes de flash. |
| Font 2 | `LOAD_FONT2` | 16 pixels de altura; aproximadamente 3.534 bytes. |
| Font 4 | `LOAD_FONT4` | 26 pixels de altura; aproximadamente 5.848 bytes, codificada em RLE. |
| Font 6 | `LOAD_FONT6` | 48 pixels de altura; aproximadamente 2.666 bytes, codificada em RLE. |
| Font 7 | `LOAD_FONT7` | Fonte de 7 segmentos, 48 pixels; aproximadamente 2.438 bytes, codificada em RLE. |
| Font 8 | `LOAD_FONT8` | 75 pixels de altura; aproximadamente 3.256 bytes, codificada em RLE. |

Os valores são aproximados e vêm dos comentários de fontes no `User_Setup.h` do upstream; o tamanho final depende do compilador e das opções selecionadas. Desative macros `LOAD_*` que não usa para reduzir o uso de flash.

## FreeFonts

Defina `LOAD_GFXFF` para incluir as FreeFonts do Adafruit GFX. Selecione uma fonte com `setFreeFont()`, por exemplo `tft.setFreeFont(FF18)`. Os nomes `FF*` são aliases fornecidos pelo exemplo `Free_Font_Demo` no arquivo `Free_Fonts.h`, que os mapeia para os objetos de fonte. Passe `nullptr` para voltar à fonte embutida.

## Fontes suaves

Fontes personalizadas que antes ficavam em `Fonts/Custom/` na raiz do pacote agora devem ficar em `src/Fonts/Custom/`. Mantenha os includes dos sketches, como `#include <Fonts/Custom/MinhaFonte.h>`, sem alterações.

Fontes suaves usam arquivos `.vlw` e exigem `SMOOTH_FONT`. O exemplo `Font_Demo_1` lê os arquivos do LittleFS. Envie a pasta de dados do exemplo e carregue ou libere a fonte:

```sh
make uploadfs EX=Font_Demo_1
```

```cpp
tft.loadFont("NotoSansBold15", LittleFS);
tft.drawString("Texto suave", 10, 20);
tft.unloadFont();
```

`Font_Demo_1_Array` demonstra como incorporar os dados da fonte em um array de flash em vez de usar um sistema de arquivos. O projeto opcional Processing em `extras/Create_Smooth_Font/Create_font` gera arquivos de fontes suaves `.vlw`.

Fontes no sistema de arquivos são verificadas quanto ao cabeçalho VLW completo, versão 11, métricas de glifo representáveis e bytes de bitmap dentro do arquivo. Se o arquivo for encurtado após o carregamento, o desenho do glifo é interrompido e a fonte é liberada. A sobrecarga que recebe um array em flash não recebe seu tamanho e, portanto, não detecta um array truncado; passe todos os dados da fonte gerada.

## Converter BMP para sprites de 4 bits

Use `Tools/bmp2array4bit` para converter um BMP indexado em arrays de paleta e pixels; a ferramenta não converte fontes. Remova a transparência, converta a imagem para cores indexadas com no máximo 16 cores e exporte sem codificação run-length. Depois execute `python bmp2array4bit.py imagem.bmp -o imagem.c`.
