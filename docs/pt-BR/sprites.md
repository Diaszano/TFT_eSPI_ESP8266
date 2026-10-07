[English](../en/sprites.md) | Português (Brasil)

# Sprites

Um Sprite é um buffer de imagem na RAM. Desenhe nele com a API gráfica e depois envie-o ao display com `pushSprite()`. Sprites ajudam a reduzir cintilação e a preparar gráficos fora da tela, mas consomem a heap do ESP8266.

Para um buffer de 240 × 240:

| Profundidade de cor | Bytes por pixel | RAM |
| ---: | ---: | ---: |
| 1 bit | 1/8 | 7.200 bytes |
| 4 bits | 1/2 | 28.800 bytes |
| 8 bits | 1 | 57.600 bytes |
| 16 bits | 2 | 115.200 bytes |

Um ESP8266 costuma ter cerca de 40 KB de heap livre para o sketch. Por isso, Sprites de tela inteira em 8 ou 16 bits não cabem; `createSprite()` retorna `nullptr` quando a alocação falha. Verifique o resultado antes de desenhar:

```cpp
auto *sprite = tft.createSprite(120, 40);
if (sprite == nullptr) {
  Serial.println("Falha ao alocar o Sprite");
  return;
}
```

Use um Sprite de área parcial ou escolha profundidade de cor de 4/1 bit quando fizer sentido. Consulte a heap disponível com `ESP.getFreeHeap()` antes de alocar buffers.

`pushRotated()` desenha um Sprite rotacionado. `pushSprite(x, y, transp)` trata a cor informada como transparente. O desenho com antialiasing dentro de um Sprite funciona sem MISO porque a mesclagem acontece no buffer do Sprite; para desenhar diretamente no TFT somente para escrita, informe uma cor de fundo conhecida.
