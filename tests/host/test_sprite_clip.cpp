// Sprite fill/line clipping. The pixel store is an exactly sized heap block so ASan reports any
// write outside it; normal cases must match the canvas produced before the clip rewrite.
#include <cassert>
#include <climits>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <initializer_list>

class TFT_eSprite {
 public:
  bool _created = true, _vpOoB = false;
  uint8_t _bpp;
  int32_t _iwidth, _ih, _xDatum = 0, _yDatum = 0, _vpX = 0, _vpY = 0, _vpW, _vpH;
  uint8_t* _img8;
  uint8_t* _img4;
  uint16_t* _img;
  size_t bytes;

  TFT_eSprite(uint8_t bpp, int32_t w, int32_t h) : _bpp(bpp), _iwidth(w), _ih(h), _vpW(w), _vpH(h) {
    bytes = bpp == 16  ? size_t(w) * h * 2
            : bpp == 8 ? size_t(w) * h
            : bpp == 4 ? size_t(w) * h / 2
                       : size_t(w) * h / 8;
    _img8 = _img4 = static_cast<uint8_t*>(std::calloc(bytes, 1));
    _img = reinterpret_cast<uint16_t*>(_img8);
  }
  ~TFT_eSprite() { std::free(_img8); }
  // 1 and 4 bpp lines fall back to per-pixel plots; keep them bounds-checked here.
  void drawPixel(int32_t x, int32_t y, uint32_t color) {
    x += _xDatum, y += _yDatum;
    if (x < _vpX || y < _vpY || x >= _vpW || y >= _vpH) return;
    uint32_t bit = uint32_t(y) * _iwidth + x;
    if (_bpp == 4) {
      uint8_t& b = _img4[bit >> 1];
      b = (bit & 1) ? (b & 0xF0) | (color & 0x0F) : (b & 0x0F) | (color & 0x0F) << 4;
    } else {
      if (color & 1)
        _img8[bit >> 3] |= 0x80 >> (bit & 7);
      else
        _img8[bit >> 3] &= ~(0x80 >> (bit & 7));
    }
  }
  void drawFastVLine(int32_t x, int32_t y, int32_t h, uint32_t color);
  void drawFastHLine(int32_t x, int32_t y, int32_t w, uint32_t color);
  void fillRect(int32_t x, int32_t y, int32_t w, int32_t h, uint32_t color);
  uint64_t checksum() const {
    uint64_t h = 1469598103934665603ULL;
    for (size_t i = 0; i < bytes; ++i) h = (h ^ _img8[i]) * 1099511628211ULL;
    return h;
  }
};

// FUNCTIONS UNDER TEST

int main(int argc, char** argv) {
  const bool print = argc > 1 && std::strcmp(argv[1], "--print") == 0;
  const uint64_t golden[] = {
      0x161916d0167906e5ULL, 0x1724afa5b5705e80ULL, 0xfb8b6c5bd047849dULL, 0xdca3a22940368119ULL,
      0xf3fa5a5cc385ac5dULL, 0x4e997a592a09df8dULL, 0xdd74f1fa9a381e33ULL, 0xf02ef8539838cfadULL,
  };
  size_t n = 0;
  const int32_t big[] = {INT32_MIN, INT32_MIN + 1, -100000,       -1,       0, 1, 7, 15,
                         16,        100000,        INT32_MAX - 1, INT32_MAX};
  for (uint8_t bpp : {16, 8, 4, 1}) {
    TFT_eSprite s(bpp, 16, 8);
    for (int datum : {0, 3}) {
      s._xDatum = s._yDatum = datum;
      std::memset(s._img8, 0, s.bytes);
      s.fillRect(-2, 1, 6, 3, 0xF81F);
      s.drawFastHLine(5, 7, 20, 0x07E0);
      s.drawFastVLine(15, -4, 6, 0x001F);
      s.fillRect(14, 6, 9, 9, 0xFFFF);
      s.drawFastHLine(-30, 0, 33, 0x1234);
      s.drawFastVLine(0, 2, 3, 0x0841);
      if (print) {
        std::printf("      0x%016llxULL,\n", (unsigned long long)s.checksum());
      } else {
        assert(s.checksum() == golden[n++]);
      }
      // Extreme inputs: anything is allowed except touching memory outside the sprite.
      if (!print)
        for (int32_t a : big)
          for (int32_t b : big) {
            s.fillRect(a, 2, b, 2, 1);
            s.fillRect(2, a, 2, b, 1);
            s.fillRect(a, a, b, b, 1);
            s.drawFastHLine(a, 3, b, 1);
            s.drawFastHLine(3, 3, b, 1);
            s.drawFastVLine(3, a, b, 1);
            s.drawFastVLine(3, 3, b, 1);
          }
    }
  }
  if (!print) std::puts("PASS sprite-clip");
}
