#include "extreme_cases.h"
#include "validation_oracle.h"
#include "internal/clip.h"
#include <cassert>
#include <climits>
#include <cstring>
#include <vector>

using tft_espi_internal::clipSpan;

class TFT_eSPI {
 public:
  int32_t _xDatum = 0, _yDatum = 0, _xWidth = 8, _yHeight = 8, _vpX = 0, _vpY = 0, _vpW = 8,
          _vpH = 8;
  bool _vpDatum = false, _vpOoB = false, inTransaction = false, lockTransaction = false,
       _swapBytes = true;
  std::vector<uint16_t> fb = std::vector<uint16_t>(64, 0xA55A);
  int32_t wx = 0, wy = 0, ww = 0, wh = 0, pos = 0;
  int32_t width() { return 8; }
  int32_t height() { return 8; }
  void begin_tft_write() {}
  void end_tft_write() {}
  void setWindow(int32_t x0, int32_t y0, int32_t x1, int32_t y1) {
    wx = x0;
    wy = y0;
    ww = x1 - x0 + 1;
    wh = y1 - y0 + 1;
    pos = 0;
  }
  void pushBlock(uint32_t color, int32_t n) {
    while (n--) {
      fb[(wy + pos / ww) * 8 + wx + pos % ww] = color;
      ++pos;
    }
  }
  void pushPixels(uint16_t* data, int32_t n) {
    while (n--) {
      fb[(wy + pos / ww) * 8 + wx + pos % ww] = *data++;
      ++pos;
    }
  }
  void setViewport(int32_t, int32_t, int32_t, int32_t, bool);
  void fillRect(int32_t, int32_t, int32_t, int32_t, uint32_t);
  void drawFastHLine(int32_t, int32_t, int32_t, uint32_t);
  void drawFastVLine(int32_t, int32_t, int32_t, uint32_t);
  void pushImage(int32_t, int32_t, int32_t, int32_t, uint16_t*);
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
// FUNCTIONS UNDER TEST
#undef PI_CLIP

#ifndef FUZZ_TARGET
int main(int argc, char** argv) {
  if (argc != 2) return 2;
  const ExtremeCase* selected = nullptr;
  for (const ExtremeCase& test : extreme_cases())
    if (!strcmp(test.id, argv[1])) selected = &test;
  if (!selected) return 2;
  TFT_eSPI actual;
  std::vector<uint16_t> expected(64, 0xA55A);
  if (!strcmp(selected->id, "fully_offscreen_241")) {
    actual.fillRect(selected->x, selected->y, selected->w, selected->h, 0x1234);
    assert(actual.fb == expected);
  } else if (!strcmp(selected->id, "negative_one_pixel")) {
    actual.fillRect(selected->x, selected->y, selected->w, selected->h, 0x1234);
    paint_rect_reference(expected, 8, 8, {selected->x, selected->y, selected->w, selected->h},
                         0x1234);
    assert(actual.fb == expected);
  } else if (!strcmp(selected->id, "viewport_zero")) {
    actual.setViewport(selected->x, selected->y, selected->w, selected->h, true);
    assert(actual._vpOoB);
  } else if (!strcmp(selected->id, "line_near_edge")) {
    actual.drawFastHLine(selected->x, selected->y, selected->w, 0x1234);
    paint_rect_reference(expected, 8, 8, {selected->x, selected->y, selected->w, 1}, 0x1234);
    assert(actual.fb == expected);
  } else if (!strcmp(selected->id, "image_16x16_crop")) {
    uint16_t source[256];
    for (int i = 0; i < 256; i++) source[i] = i + 1;
    actual.pushImage(selected->x, selected->y, selected->w, selected->h, source);
    for (int y = 0; y < 8; y++)
      for (int x = 0; x < 8; x++) expected[y * 8 + x] = source[(y + 2) * 16 + x + 3];
    assert(actual.fb == expected);
  } else if (!strcmp(selected->id, "int32_max_origin")) {
    actual.setViewport(selected->x, selected->y, INT32_MAX, selected->h, true);
    assert(actual._vpOoB);
  } else if (!strcmp(selected->id, "int32_min_origin")) {
    actual.setViewport(selected->x, selected->y, selected->w, selected->h, true);
    assert(actual._vpOoB);
  } else if (!strcmp(selected->id, "negative_dimensions")) {
    actual.fillRect(selected->x, selected->y, selected->w, selected->h, 0x1234);
    assert(actual.fb == expected);
  } else if (!strcmp(selected->id, "sprite_32x32_offscreen")) {
    return 77;  // Sprite push is not part of this source-extraction fixture.
  }
  return 0;
}
#else
extern "C" int LLVMFuzzerTestOneInput(const uint8_t* data, size_t size) {
  if (size < 11) return 0;
  const int32_t x = static_cast<int32_t>(
      static_cast<uint32_t>(data[0]) | static_cast<uint32_t>(data[1]) << 8 |
      static_cast<uint32_t>(data[2]) << 16 | static_cast<uint32_t>(data[3]) << 24);
  const int32_t y = static_cast<int32_t>(
      static_cast<uint32_t>(data[4]) | static_cast<uint32_t>(data[5]) << 8 |
      static_cast<uint32_t>(data[6]) << 16 | static_cast<uint32_t>(data[7]) << 24);
  const int32_t w = 1 + data[8] % 16, h = 1 + data[9] % 16;
  TFT_eSPI actual;
  std::vector<uint16_t> expected(64, 0xA55A);
  if (data[10] & 1) {
    actual.fillRect(x, y, w, h, 0x1234);
    paint_rect_reference(expected, 8, 8, {x, y, w, h}, 0x1234);
  } else {
    actual.drawFastHLine(x, y, w, 0x1234);
    paint_rect_reference(expected, 8, 8, {x, y, w, 1}, 0x1234);
  }
  assert(actual.fb == expected);
  return 0;
}
#endif
