#include "validation_oracle.h"
#include <cassert>
#include <cstdint>
#include <climits>
#include <vector>

class TFT_eSPI {
 public:
  int32_t _xDatum = 0, _yDatum = 0, _xWidth = 8, _yHeight = 8, _vpX = 0, _vpY = 0, _vpW = 8,
          _vpH = 8;
  bool _vpDatum = false, _vpOoB = false, inTransaction = false, lockTransaction = false;
  std::vector<uint16_t> fb = std::vector<uint16_t>(64, 0xA55A);
  int32_t width() { return 8; }
  int32_t height() { return 8; }
  void begin_tft_write() {}
  void end_tft_write() {}
  void setWindow(int32_t x0, int32_t y0, int32_t x1, int32_t y1) {
    wx = x0;
    wy = y0;
    ww = x1 - x0 + 1;
    wh = y1 - y0 + 1;
  }
  void pushBlock(uint32_t color, int32_t count) {
    for (int32_t i = 0; i < count; i++) fb[(wy + i / ww) * 8 + wx + i % ww] = color;
  }
  int32_t wx = 0, wy = 0, ww = 0, wh = 0;
  void setViewport(int32_t, int32_t, int32_t, int32_t, bool);
  void drawFastHLine(int32_t, int32_t, int32_t, uint32_t);
  void drawFastVLine(int32_t, int32_t, int32_t, uint32_t);
  void fillRect(int32_t, int32_t, int32_t, int32_t, uint32_t);
  void drawRect(int32_t, int32_t, int32_t, int32_t, uint32_t);
};
// FUNCTIONS UNDER TEST

int main() {
  const int origins[] = {-9, -8, -1, 0, 1, 6, 7, 8, 9};
  for (int x : origins) {
    TFT_eSPI actual;
    std::vector<uint16_t> expected(64, 0xA55A);
    actual.fillRect(x, 2, 2, 2, 0x1234);
    paint_rect_reference(expected, 8, 8, {x, 2, 2, 2}, 0x1234);
    assert(actual.fb == expected);
    assert(actual.fb.front() == 0xA55A);
    assert(actual.fb.back() == 0xA55A);
  }
  TFT_eSPI actual;
  std::vector<uint16_t> expected(64, 0xA55A);
  actual.drawFastHLine(-1, 3, 4, 0x2222);
  paint_rect_reference(expected, 8, 8, {-1, 3, 4, 1}, 0x2222);
  actual.drawFastVLine(5, -1, 4, 0x3333);
  paint_rect_reference(expected, 8, 8, {5, -1, 1, 4}, 0x3333);
  assert(actual.fb == expected);
  actual.fillRect(0, 0, 0, 4, 0x1111);
  assert(actual.fb == expected);
  actual.drawRect(1, 1, 3, 3, 0x4444);
  for (int x = 1; x < 4; ++x) expected[1 * 8 + x] = expected[3 * 8 + x] = 0x4444;
  for (int y = 2; y < 3; ++y) expected[y * 8 + 1] = expected[y * 8 + 3] = 0x4444;
  assert(actual.fb == expected);
  actual.setViewport(-2, 1, 6, 5, true);
  assert(actual._vpX == 0 && actual._vpY == 1 && actual._vpW == 4 && actual._vpH == 6);
  actual.drawFastHLine(8, 2, 1, 0x4321);
  assert(actual.fb[2 * 8 + 7] == 0xA55A);
  actual.setViewport(INT32_MAX, 0, INT32_MAX, 1, true);
  assert(actual._vpOoB);
}
