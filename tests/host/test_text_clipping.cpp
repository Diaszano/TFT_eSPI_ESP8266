#include "internal/clip.h"
#include <cassert>
#include <cstdint>
#include <vector>

using namespace tft_espi_internal;

class FifoPixels {
 public:
  void push(uint16_t) {}
  void run(uint16_t, uint32_t) {}
  void end() {}
};

#define LOAD_FONT2
#define LOAD_GLCD
static const uint8_t glyph[8] = {0x81, 0x81, 0x81, 0x81, 0x81, 0x81, 0x81, 0x81};
static const uint8_t* chrtbl_f16[256] = {};
static const uint8_t widtbl_f16[256] = {};
static const uint8_t chr_hgt_f16 = 8;
static uint8_t font[256 * 5] = {};
uint32_t pgm_read_dword(const uint8_t* const*) {
  return 0x1000;
}
uint8_t pgm_read_byte(const uint8_t* p) {
  uintptr_t address = reinterpret_cast<uintptr_t>(p);
  if (address >= 0x1000 && address < 0x1008) return glyph[address - 0x1000];
  if (p >= widtbl_f16 && p < widtbl_f16 + 256) return 8;
  return *p;
}

class TFT_eSPI {
 public:
  int32_t _xDatum = 0, _yDatum = 0, _vpX = 0, _vpY = 0, _vpW = 8, _vpH = 8, wx = 0, wy = 0, ww = 0,
          wh = 0, pos = 0;
  bool _vpOoB = false, inTransaction = false, lockTransaction = false;
  bool _cp437 = true;
  uint8_t textsize = 1;
  uint16_t textcolor = 0xFFFF, textbgcolor = 0x2222;
  std::vector<uint16_t> fb = std::vector<uint16_t>(64, 0x5555);
  void begin_tft_write() {}
  void end_tft_write() {}
  void tft_Write_16(uint16_t) {}
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
  void drawPixel(int32_t x, int32_t y, uint32_t color) {
    if (x >= 0 && y >= 0 && x < 8 && y < 8) fb[y * 8 + x] = color;
  }
  void fillRect(int32_t, int32_t, int32_t, int32_t, uint32_t);
  int16_t drawChar(uint16_t, int32_t, int32_t, uint8_t);
  void drawChar(int32_t, int32_t, uint16_t, uint32_t, uint32_t, uint8_t);
  int16_t fontHeight(uint8_t) { return 8; }
};
// FUNCTIONS UNDER TEST

int main() {
  font['A' * 5] = font['A' * 5 + 1] = font['A' * 5 + 2] = 0x01;
  TFT_eSPI classic;
  classic.drawChar('A', 5, 5, 1);
  assert(classic.fb[5 * 8 + 5] == 0xFFFF && classic.fb[5 * 8 + 6] == 0xFFFF &&
         classic.fb[5 * 8 + 7] == 0xFFFF);
  assert(classic.fb[6 * 8 + 5] == 0x2222 && classic.fb[7 * 8 + 7] == 0x2222);

  TFT_eSPI opaque;
  assert(opaque.drawChar('A', 5, 5, 2) == 8);
  for (int y = 0; y < 8; y++)
    for (int x = 0; x < 8; x++) {
      uint16_t expected = 0x5555;
      if (y >= 5 && x >= 5) expected = (x == 5) ? 0xFFFF : 0x2222;
      assert(opaque.fb[y * 8 + x] == expected);
    }

  TFT_eSPI transparent;
  transparent.textbgcolor = transparent.textcolor;
  assert(transparent.drawChar('A', 5, 5, 2) == 8);
  for (int y = 0; y < 8; y++)
    for (int x = 0; x < 8; x++) {
      uint16_t expected = (y >= 5 && x == 5) ? 0xFFFF : 0x5555;
      assert(transparent.fb[y * 8 + x] == expected);
    }
}
