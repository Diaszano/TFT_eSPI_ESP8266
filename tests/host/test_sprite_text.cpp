// Sprite glyph rendering (GLCD, font 2, font 4) over an exactly sized heap image. Extreme
// positions and origins may draw nothing but must never overflow or touch memory outside it;
// normal draws must match the golden output of the previous implementation.
#include <cassert>
#include <climits>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <initializer_list>

#define PROGMEM
#define pgm_read_byte(p) (*(const uint8_t*)(p))
#define pgm_read_word(p) (*(const uint16_t*)(p))
template <typename T>
uintptr_t pgm_read_dword(const T* p) {
  return (uintptr_t)*p;
}
inline uintptr_t pgm_read_dword(const void* p) {
  return *(const uintptr_t*)p;
}
#define LOAD_GLCD
#define LOAD_FONT2
#define LOAD_FONT4
#define LOAD_RLE
#include <Fonts/Font16.h>
#include <Fonts/Font32rle.h>
#include <Fonts/glcdfont.inc>
#include "internal/clip.h"

const uint8_t widtbl_null[1] = {0};
const uint8_t chr_null[1] = {0};
const uint8_t* const chrtbl_null[1] = {chr_null};
struct fontinfo {
  const uint8_t* chartbl;
  const uint8_t* widthtbl;
  uint8_t height;
  uint8_t baseline;
};
const fontinfo fontdata[] = {
    {(const uint8_t*)font, widtbl_null, 0, 0},
    {(const uint8_t*)chrtbl_null, widtbl_null, 8, 7},
    {(const uint8_t*)chrtbl_f16, widtbl_f16, chr_hgt_f16, baseline_f16},
    {(const uint8_t*)chrtbl_null, widtbl_null, 0, 0},
    {(const uint8_t*)chrtbl_f32, widtbl_f32, chr_hgt_f32, baseline_f32},
};

class TFT_eSprite {
 public:
  static constexpr int32_t W = 48, H = 32;
  bool _created = true, _vpOoB = false, _cp437 = true;
  uint8_t _bpp = 16, textsize = 1;
  int32_t _xDatum = 0, _yDatum = 0, _vpX = 0, _vpY = 0, _vpW = W, _vpH = H;
  int32_t _xs = 0, _ys = 0, _xe = 0, _ye = 0, _xptr = 0, _yptr = 0;
  uint32_t textcolor = 0xF800, textbgcolor = 0x001F;
  uint16_t* img = static_cast<uint16_t*>(std::calloc(W * H + 1, 2));  // +1: off-screen pixel
  ~TFT_eSprite() { std::free(img); }

  void drawPixel(int32_t x, int32_t y, uint32_t c) {
    if (__builtin_add_overflow(x, _xDatum, &x) || __builtin_add_overflow(y, _yDatum, &y)) return;
    if (x >= _vpX && y >= _vpY && x < _vpW && y < _vpH) img[y * W + x] = uint16_t(c);
  }
  void fillRect(int32_t x, int32_t y, int32_t w, int32_t h, uint32_t c) {
    if (!tft_espi_internal::clipSpan(x, w, _xDatum, _vpX, _vpW) ||
        !tft_espi_internal::clipSpan(y, h, _yDatum, _vpY, _vpH))
      return;
    for (int32_t j = 0; j < h; ++j)
      for (int32_t i = 0; i < w; ++i) img[(y + j) * W + x + i] = uint16_t(c);
  }
  void drawFastHLine(int32_t x, int32_t y, int32_t w, uint32_t c) { fillRect(x, y, w, 1, c); }
  void setWindow(int32_t x0, int32_t y0, int32_t x1, int32_t y1) {
    if (x0 >= W || x1 < 0 || y0 >= H || y1 < 0) {
      _xs = _xe = 0, _ys = _ye = H;
    } else {
      _xs = x0 < 0 ? 0 : x0, _xe = x1 >= W ? W - 1 : x1, _ys = y0 < 0 ? 0 : y0,
      _ye = y1 >= H ? H - 1 : y1;
    }
    _xptr = _xs, _yptr = _ys;
  }
  void writeColor(uint16_t c) {
    img[_xptr + _yptr * W] = c;
    if (++_xptr > _xe) {
      _xptr = _xs;
      if (++_yptr > _ye) _yptr = _ys;
    }
  }
  void drawChar(int32_t x, int32_t y, uint16_t c, uint32_t color, uint32_t bg, uint8_t size);
  int16_t drawChar(uint16_t uniCode, int32_t x, int32_t y, uint8_t font);
  uint64_t checksum() const {
    uint64_t h = 1469598103934665603ULL;
    for (int i = 0; i < W * H; ++i) h = (h ^ img[i]) * 1099511628211ULL;
    return h;
  }
};

// FUNCTIONS UNDER TEST

int main(int argc, char** argv) {
  const bool print = argc > 1 && std::strcmp(argv[1], "--print") == 0;
  const uint64_t golden[] = {
      0xcedf4b09074a63b7ULL,
      0x9aa29112334475a7ULL,
      0xcaa0a33b8bfdab33ULL,
      0xe9769b6d2faeb037ULL,
  };
  size_t n = 0;
  TFT_eSprite s;
  for (int32_t datum : {0, -3})
    for (uint8_t size : {1, 2}) {
      std::memset(s.img, 0, TFT_eSprite::W * TFT_eSprite::H * 2);
      s._xDatum = s._yDatum = datum;
      s.textsize = size;
      s.drawChar(-2, 1, 'A', 0xFFFF, 0x0000, size);
      s.drawChar(40, 20, 'W', 0x07E0, 0x07E0, size);
      s.drawChar('7', 10, -4, 2);
      s.drawChar('3', 30, 12, 4);
      s.textbgcolor = s.textcolor;
      s.drawChar('5', 1, 18, 4);
      s.textbgcolor = 0x001F;
      if (print)
        std::printf("      0x%016llxULL,\n", (unsigned long long)s.checksum());
      else
        assert(s.checksum() == golden[n++]);
    }
  if (print) return 0;
  const int32_t big[] = {INT32_MIN, INT32_MIN + 1, -100000,       -1,       0, 1,
                         47,        100000,        INT32_MAX - 1, INT32_MAX};
  for (int32_t datum : {0, 7, INT32_MAX, INT32_MIN})
    for (int32_t a : big)
      for (int32_t b : big) {
        s._xDatum = s._yDatum = datum;
        for (uint8_t size : {1, 3}) {
          s.textsize = size;
          s.drawChar(a, b, 'W', 0xFFFF, 0x0000, size);
          s.drawChar(a, b, 'W', 0xFFFF, 0xFFFF, size);
          s.drawChar('8', a, b, 2);
          s.drawChar('8', a, b, 4);
        }
      }
  std::puts("PASS sprite-text");
}
