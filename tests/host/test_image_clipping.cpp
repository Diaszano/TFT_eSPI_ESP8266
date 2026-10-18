#include "validation_oracle.h"
#include <cassert>
#include <cstdint>
#include <vector>
#define pgm_read_byte(p) (*(p))

class TFT_eSPI {
 public:
  int32_t _xDatum = 0, _yDatum = 0, _vpX = 0, _vpY = 0, _vpW = 8, _vpH = 8;
  bool _vpOoB = false, inTransaction = false, lockTransaction = false, _swapBytes = true;
  std::vector<uint16_t> fb = std::vector<uint16_t>(64, 0xA55A);
  int32_t wx = 0, wy = 0, ww = 0, wh = 0, pos = 0;
  void begin_tft_write() {}
  void end_tft_write() {}
  void setWindow(int32_t x0, int32_t y0, int32_t x1, int32_t y1) {
    wx = x0;
    wy = y0;
    ww = x1 - x0 + 1;
    wh = y1 - y0 + 1;
    pos = 0;
  }
  void pushPixels(uint16_t* data, int32_t n) {
    for (int32_t i = 0; i < n; i++) {
      fb[(wy + pos / ww) * 8 + wx + pos % ww] = data[i];
      pos++;
    }
  }
  void pushImage(int32_t, int32_t, int32_t, int32_t, uint16_t*);
  void drawPixel(int32_t x, int32_t y, uint32_t color) {
    if (x >= 0 && y >= 0 && x < 8 && y < 8) fb[y * 8 + x] = color;
  }
  void drawBitmap(int16_t, int16_t, const uint8_t*, int16_t, int16_t, uint16_t);
};
#define PI_CLIP                           \
  if (_vpOoB) return;                     \
  x += _xDatum;                           \
  y += _yDatum;                           \
  if ((x >= _vpW) || (y >= _vpH)) return; \
  int32_t dx = 0, dy = 0, dw = w, dh = h; \
  if (x < _vpX) {                         \
    dx = _vpX - x;                        \
    dw -= dx;                             \
    x = _vpX;                             \
  }                                       \
  if (y < _vpY) {                         \
    dy = _vpY - y;                        \
    dh -= dy;                             \
    y = _vpY;                             \
  }                                       \
  if ((x + dw) > _vpW) dw = _vpW - x;     \
  if ((y + dh) > _vpH) dh = _vpH - y;     \
  if (dw < 1 || dh < 1) return;
// FUNCTION UNDER TEST
// BITMAP FUNCTION UNDER TEST
#undef PI_CLIP

int main() {
  std::vector<uint16_t> source(16 * 16), expected(64, 0xA55A);
  for (int y = 0; y < 16; y++)
    for (int x = 0; x < 16; x++) source[y * 16 + x] = static_cast<uint16_t>(y * 16 + x + 1);
  TFT_eSPI display;
  display.pushImage(-3, -2, 16, 16, source.data());
  for (int y = 0; y < 8; y++)
    for (int x = 0; x < 8; x++) expected[y * 8 + x] = source[(y + 2) * 16 + x + 3];
  assert(display.fb == expected);
  display.pushImage(8, 0, 16, 16, source.data());
  assert(display.fb == expected);
  std::vector<uint8_t> bits(2 * 2, 0xA5);  // width 13, two padded bytes per row
  TFT_eSPI bitmap_display;
  bitmap_display.drawBitmap(-2, 1, bits.data(), 13, 2, 0xBEEF);
  for (int y = 0; y < 2; y++)
    for (int x = 0; x < 8; x++) {
      const bool set = (bits[y * 2 + (x + 2) / 8] & (0x80 >> ((x + 2) & 7))) != 0;
      assert(bitmap_display.fb[(y + 1) * 8 + x] == (set ? 0xBEEF : 0xA55A));
    }
}
