English | [Português (Brasil)](https://github.com/Diaszano/TFT_eSPI_ESP8266/blob/main/docs/pt-BR/sprites.md)

# Sprites

A Sprite is an image buffer in RAM. Draw into it using the graphics API, then send it to the display with `pushSprite()`. Sprites are useful for reducing flicker and preparing graphics off-screen, but their memory comes from the ESP8266 heap.

`TFT_eSprite` owns its pixel buffers and cannot be copied or assigned. Construct it directly with its display, and pass it to helpers by reference or pointer:

```cpp
TFT_eSprite sprite(&tft);
```

For a 240 × 240 buffer:

| Color depth | Bytes per pixel | RAM |
| ---: | ---: | ---: |
| 1 bit | 1/8 | 7,200 bytes |
| 4 bit | 1/2 | 28,800 bytes |
| 8 bit | 1 | 57,600 bytes |
| 16 bit | 2 | 115,200 bytes |

An ESP8266 often has about 40 KB of free heap for the sketch. Full-screen 8-bit and 16-bit Sprites therefore do not fit; `createSprite()` returns `nullptr` when allocation fails. Check the result before drawing:

```cpp
auto *sprite = tft.createSprite(120, 40);
if (sprite == nullptr) {
  Serial.println("Sprite allocation failed");
  return;
}
```

Use a partial-screen Sprite or choose 4-bit/1-bit color depth when appropriate. Check available heap with `ESP.getFreeHeap()` before allocating buffers.

`pushRotated()` draws a rotated Sprite. `pushSprite(x, y, transp)` treats the given color as transparent. Anti-aliased drawing inside a Sprite works without MISO because the blending happens in the Sprite buffer; direct drawing to the write-only TFT needs a known background color instead.
