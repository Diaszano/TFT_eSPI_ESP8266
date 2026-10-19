// Sprite paths that used to size stack buffers from sprite geometry: pushToSprite and both
// pushRotated overloads. Destination writes are recorded into a canvas; the golden checksums were
// produced by the unbounded implementation, and every run handed to pushImage/pushPixels must now
// fit the fixed staging capacity.
#include <cassert>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <vector>

#define FP_SCALE 10

namespace rec {
constexpr int kCanvas = 1200;
std::vector<uint16_t> canvas(kCanvas* kCanvas);
uint32_t maxRun = 0, pushes = 0;
int32_t wx0, wy0, wx1, wy1, wx, wy;  // TFT window and write cursor

void reset() {
  std::fill(canvas.begin(), canvas.end(), 0);
  maxRun = pushes = 0;
}
void plot(int32_t x, int32_t y, uint16_t c) {
  if (x >= 0 && y >= 0 && x < kCanvas && y < kCanvas) canvas[y * kCanvas + x] = c;
}
uint64_t checksum() {
  uint64_t h = 1469598103934665603ULL;
  for (uint16_t p : canvas) h = (h ^ p) * 1099511628211ULL;
  return h;
}
}  // namespace rec

struct TFT_eSPI {
  bool _vpOoB = false;
  int16_t _xPivot = 120, _yPivot = 120;
  int32_t _vpX = 0, _vpY = 0, _vpW = 240, _vpH = 240;
  void startWrite() {}
  void endWrite() {}
  void setWindow(int32_t x0, int32_t y0, int32_t x1, int32_t y1) {
    rec::wx0 = rec::wx = x0, rec::wy0 = rec::wy = y0, rec::wx1 = x1, rec::wy1 = y1;
  }
  void pushPixels(const void* data, uint32_t len) {
    ++rec::pushes;
    if (len > rec::maxRun) rec::maxRun = len;
    const uint16_t* p = static_cast<const uint16_t*>(data);
    while (len--) {
      assert(rec::wy <= rec::wy1);  // never write past the window
      rec::plot(rec::wx, rec::wy, *p++);
      if (++rec::wx > rec::wx1) rec::wx = rec::wx0, ++rec::wy;
    }
  }
};

class TFT_eSprite {
 public:
  TFT_eSPI* _tft;
  bool _created = true, _swap = false;
  uint8_t _bpp = 16;
  int32_t _dwidth, _dheight, _iwidth;
  int16_t _xPivot = 0, _yPivot = 0;
  int32_t _sinra = 0, _cosra = 0;
  uint16_t* _img = nullptr;
  uint16_t* _colorMap = nullptr;
  std::vector<uint16_t> pixels;

  TFT_eSprite(TFT_eSPI* tft, int w, int h, uint8_t bpp)
      : _tft(tft), _bpp(bpp), _dwidth(w), _dheight(h), _iwidth(w) {
    pixels.resize(size_t(w) * h);
    for (size_t i = 0; i < pixels.size(); ++i) pixels[i] = uint16_t(i * 2654435761u >> 13) | 1;
    for (size_t i = 0; i < pixels.size(); i += 5) pixels[i] = 0;  // transparent pixels (0)
    _img = pixels.data();
  }
  int16_t width() { return _dwidth; }
  int16_t height() { return _dheight; }
  int8_t getColorDepth() { return _bpp; }
  bool getSwapBytes() { return _swap; }
  void setSwapBytes(bool s) { _swap = s; }
  // Non-16 bpp sources go through readPixel, which returns the unswapped colour.
  uint16_t readPixel(int32_t x, int32_t y) {
    uint16_t c = pixels[y * _iwidth + x];
    return c >> 8 | c << 8;
  }
  void pushImage(int32_t x, int32_t y, int32_t w, int32_t h, uint16_t* data, uint8_t = 0) {
    ++rec::pushes;
    if (uint32_t(w) > rec::maxRun) rec::maxRun = w;
    for (int32_t j = 0; j < h; ++j)
      for (int32_t i = 0; i < w; ++i)
        if (x + i >= 0 && x + i < _dwidth && y + j >= 0 && y + j < _dheight)
          rec::plot(x + i, y + j, data[j * w + i]);
  }
  bool pushRotated(int16_t angle, uint32_t transp = 0x00FFFFFF);
  bool pushRotated(TFT_eSprite* spr, int16_t angle, uint32_t transp = 0x00FFFFFF);
  bool getRotatedBounds(int16_t angle, int16_t* min_x, int16_t* min_y, int16_t* max_x,
                        int16_t* max_y);
  bool getRotatedBounds(TFT_eSprite* spr, int16_t angle, int16_t* min_x, int16_t* min_y,
                        int16_t* max_x, int16_t* max_y);
  void getRotatedBounds(int16_t angle, int16_t w, int16_t h, int16_t xp, int16_t yp, int16_t* min_x,
                        int16_t* min_y, int16_t* max_x, int16_t* max_y);
  bool pushToSprite(TFT_eSprite* dspr, int32_t x, int32_t y, uint16_t transp);
};

// FUNCTIONS UNDER TEST

int main(int argc, char** argv) {
  const bool print = argc > 1 && std::strcmp(argv[1], "--print") == 0;
  // Golden checksums recorded from the variable-length-buffer implementation.
  const uint64_t golden[] = {
      0x93ae2d45761c599bULL,  // pushToSprite, widest run 7
      0x14d121ae3522a507ULL,  // pushToSprite, widest run 33
      0x608ea5392f264bcfULL,  // pushToSprite, widest run 200
      0x6f212a1c69597afdULL,  // pushToSprite, widest run 1000
      0xd4a8ac9ce7c21acdULL,  // pushRotated sprite, widest run 200
      0x5c5dc89dbbf20ef9ULL,  // pushRotated sprite, widest run 200
      0xfa7989581a1ce9e1ULL,  // pushRotated tft, widest run 50
      0x9cb6beac4d77ab59ULL,  // pushRotated tft, widest run 200
      0xcfe7d8bdafdbc122ULL,  // pushRotated sprite, widest run 103
      0xd03c196f3fae63e4ULL,  // pushRotated sprite, widest run 103
      0x0b676ccc761a89ceULL,  // pushRotated tft, widest run 50
      0x487b54a1e3fe643cULL,  // pushRotated tft, widest run 103
      0x32487be12202f371ULL,  // pushRotated sprite, widest run 42
      0x35b38943d9787a8eULL,  // pushRotated sprite, widest run 42
      0xe4267dd871905e29ULL,  // pushRotated tft, widest run 31
      0xb271de3ce648e506ULL,  // pushRotated tft, widest run 42
      0x9c76b7dc75f472ffULL,  // pushRotated sprite, widest run 30
      0x5a283f5f65b91271ULL,  // pushRotated sprite, widest run 30
      0x4917083b8ed5af83ULL,  // pushRotated tft, widest run 0
      0x7f18e597e75717b1ULL,  // pushRotated tft, widest run 30
      0xa6b74bbcdb780d20ULL,  // pushRotated sprite, widest run 42
      0xce45aeb19527f1ceULL,  // pushRotated sprite, widest run 42
      0x6ae5dd3c34cf1f16ULL,  // pushRotated tft, widest run 32
      0xb0cde7fe86a4e5c6ULL,  // pushRotated tft, widest run 42
      0x38699a6a6a87848aULL,  // pushRotated sprite, widest run 88
      0xdaf3fc8d74b05531ULL,  // pushRotated sprite, widest run 88
      0xed3d7b69b83993bdULL,  // pushRotated tft, widest run 50
      0x8a75d27a4aab3801ULL,  // pushRotated tft, widest run 88
      0xb63be191c214f46fULL,  // pushRotated sprite, widest run 42
      0x29767494f57602d2ULL,  // pushRotated sprite, widest run 42
      0x88cb2fb21f735825ULL,  // pushRotated tft, widest run 31
      0xf540bda38e081a0aULL,  // pushRotated tft, widest run 42
      0x93ae2d45761c599bULL,  // pushToSprite, widest run 4
      0x14d121ae3522a507ULL,  // pushToSprite, widest run 4
      0x608ea5392f264bcfULL,  // pushToSprite, widest run 4
      0x6f212a1c69597afdULL,  // pushToSprite, widest run 4
      0xd4a8ac9ce7c21acdULL,  // pushRotated sprite, widest run 4
      0x5c5dc89dbbf20ef9ULL,  // pushRotated sprite, widest run 4
      0xfa7989581a1ce9e1ULL,  // pushRotated tft, widest run 4
      0x9cb6beac4d77ab59ULL,  // pushRotated tft, widest run 4
      0xcfe7d8bdafdbc122ULL,  // pushRotated sprite, widest run 5
      0xd03c196f3fae63e4ULL,  // pushRotated sprite, widest run 5
      0x0b676ccc761a89ceULL,  // pushRotated tft, widest run 5
      0x487b54a1e3fe643cULL,  // pushRotated tft, widest run 5
      0x32487be12202f371ULL,  // pushRotated sprite, widest run 6
      0x35b38943d9787a8eULL,  // pushRotated sprite, widest run 6
      0xe4267dd871905e29ULL,  // pushRotated tft, widest run 6
      0xb271de3ce648e506ULL,  // pushRotated tft, widest run 6
      0x9c76b7dc75f472ffULL,  // pushRotated sprite, widest run 30
      0x5a283f5f65b91271ULL,  // pushRotated sprite, widest run 30
      0x4917083b8ed5af83ULL,  // pushRotated tft, widest run 0
      0x7f18e597e75717b1ULL,  // pushRotated tft, widest run 30
      0xa6b74bbcdb780d20ULL,  // pushRotated sprite, widest run 6
      0xce45aeb19527f1ceULL,  // pushRotated sprite, widest run 6
      0x6ae5dd3c34cf1f16ULL,  // pushRotated tft, widest run 6
      0xb0cde7fe86a4e5c6ULL,  // pushRotated tft, widest run 6
      0x38699a6a6a87848aULL,  // pushRotated sprite, widest run 5
      0xdaf3fc8d74b05531ULL,  // pushRotated sprite, widest run 5
      0xed3d7b69b83993bdULL,  // pushRotated tft, widest run 5
      0x8a75d27a4aab3801ULL,  // pushRotated tft, widest run 5
      0xb63be191c214f46fULL,  // pushRotated sprite, widest run 6
      0x29767494f57602d2ULL,  // pushRotated sprite, widest run 6
      0x88cb2fb21f735825ULL,  // pushRotated tft, widest run 6
      0xf540bda38e081a0aULL,  // pushRotated tft, widest run 6
      0x93ae2d45761c599bULL,  // pushToSprite, widest run 7
      0x14d121ae3522a507ULL,  // pushToSprite, widest run 33
      0x608ea5392f264bcfULL,  // pushToSprite, widest run 200
      0x6f212a1c69597afdULL,  // pushToSprite, widest run 1000
      0xd4a8ac9ce7c21acdULL,  // pushRotated sprite, widest run 200
      0x5c5dc89dbbf20ef9ULL,  // pushRotated sprite, widest run 200
      0xfa7989581a1ce9e1ULL,  // pushRotated tft, widest run 50
      0x9cb6beac4d77ab59ULL,  // pushRotated tft, widest run 200
      0xcfe7d8bdafdbc122ULL,  // pushRotated sprite, widest run 103
      0xd03c196f3fae63e4ULL,  // pushRotated sprite, widest run 103
      0x0b676ccc761a89ceULL,  // pushRotated tft, widest run 50
      0x487b54a1e3fe643cULL,  // pushRotated tft, widest run 103
      0x32487be12202f371ULL,  // pushRotated sprite, widest run 42
      0x35b38943d9787a8eULL,  // pushRotated sprite, widest run 42
      0xe4267dd871905e29ULL,  // pushRotated tft, widest run 31
      0xb271de3ce648e506ULL,  // pushRotated tft, widest run 42
      0x9c76b7dc75f472ffULL,  // pushRotated sprite, widest run 30
      0x5a283f5f65b91271ULL,  // pushRotated sprite, widest run 30
      0x4917083b8ed5af83ULL,  // pushRotated tft, widest run 0
      0x7f18e597e75717b1ULL,  // pushRotated tft, widest run 30
      0xa6b74bbcdb780d20ULL,  // pushRotated sprite, widest run 42
      0xce45aeb19527f1ceULL,  // pushRotated sprite, widest run 42
      0x6ae5dd3c34cf1f16ULL,  // pushRotated tft, widest run 32
      0xb0cde7fe86a4e5c6ULL,  // pushRotated tft, widest run 42
      0x38699a6a6a87848aULL,  // pushRotated sprite, widest run 88
      0xdaf3fc8d74b05531ULL,  // pushRotated sprite, widest run 88
      0xed3d7b69b83993bdULL,  // pushRotated tft, widest run 50
      0x8a75d27a4aab3801ULL,  // pushRotated tft, widest run 88
      0xb63be191c214f46fULL,  // pushRotated sprite, widest run 42
      0x29767494f57602d2ULL,  // pushRotated sprite, widest run 42
      0x88cb2fb21f735825ULL,  // pushRotated tft, widest run 31
      0xf540bda38e081a0aULL,  // pushRotated tft, widest run 42
      0x93ae2d45761c599bULL,  // pushToSprite, widest run 4
      0x14d121ae3522a507ULL,  // pushToSprite, widest run 4
      0x608ea5392f264bcfULL,  // pushToSprite, widest run 4
      0x6f212a1c69597afdULL,  // pushToSprite, widest run 4
      0xd4a8ac9ce7c21acdULL,  // pushRotated sprite, widest run 4
      0x5c5dc89dbbf20ef9ULL,  // pushRotated sprite, widest run 4
      0xfa7989581a1ce9e1ULL,  // pushRotated tft, widest run 4
      0x9cb6beac4d77ab59ULL,  // pushRotated tft, widest run 4
      0xcfe7d8bdafdbc122ULL,  // pushRotated sprite, widest run 5
      0xd03c196f3fae63e4ULL,  // pushRotated sprite, widest run 5
      0x0b676ccc761a89ceULL,  // pushRotated tft, widest run 5
      0x487b54a1e3fe643cULL,  // pushRotated tft, widest run 5
      0x32487be12202f371ULL,  // pushRotated sprite, widest run 6
      0x35b38943d9787a8eULL,  // pushRotated sprite, widest run 6
      0xe4267dd871905e29ULL,  // pushRotated tft, widest run 6
      0xb271de3ce648e506ULL,  // pushRotated tft, widest run 6
      0x9c76b7dc75f472ffULL,  // pushRotated sprite, widest run 30
      0x5a283f5f65b91271ULL,  // pushRotated sprite, widest run 30
      0x4917083b8ed5af83ULL,  // pushRotated tft, widest run 0
      0x7f18e597e75717b1ULL,  // pushRotated tft, widest run 30
      0xa6b74bbcdb780d20ULL,  // pushRotated sprite, widest run 6
      0xce45aeb19527f1ceULL,  // pushRotated sprite, widest run 6
      0x6ae5dd3c34cf1f16ULL,  // pushRotated tft, widest run 6
      0xb0cde7fe86a4e5c6ULL,  // pushRotated tft, widest run 6
      0x38699a6a6a87848aULL,  // pushRotated sprite, widest run 5
      0xdaf3fc8d74b05531ULL,  // pushRotated sprite, widest run 5
      0xed3d7b69b83993bdULL,  // pushRotated tft, widest run 5
      0x8a75d27a4aab3801ULL,  // pushRotated tft, widest run 5
      0xb63be191c214f46fULL,  // pushRotated sprite, widest run 6
      0x29767494f57602d2ULL,  // pushRotated sprite, widest run 6
      0x88cb2fb21f735825ULL,  // pushRotated tft, widest run 6
      0xf540bda38e081a0aULL,  // pushRotated tft, widest run 6
  };
  size_t n = 0;
  auto check = [&](const char* name) {
    const uint64_t sum = rec::checksum();
    if (print) {
      std::printf("      0x%016llxULL,  // %s, widest run %u\n", (unsigned long long)sum, name,
                  rec::maxRun);
      return;
    }
    assert(n < sizeof(golden) / sizeof(golden[0]));
    if (sum != golden[n]) {
      std::printf("pixel mismatch: %s\n", name);
      assert(false);
    }
    // A run is staged in a fixed buffer, never one sized by the sprite.
    if (rec::maxRun > 32) {
      std::printf("unbounded run: %s (%u pixels)\n", name, rec::maxRun);
      assert(false);
    }
    ++n;
  };

  TFT_eSPI tft;
  for (uint8_t bpp : {16, 8}) {
    for (uint32_t transp : {0x00FFFFFFu, 0u}) {
      for (int w : {7, 33, 200, 1000}) {
        TFT_eSprite src(&tft, w, 9, bpp), dst(&tft, 1100, 40, bpp);
        rec::reset();
        src.pushToSprite(&dst, -3, 2, uint16_t(transp == 0 ? 0 : 0x1234));
        check("pushToSprite");
      }
      for (int16_t angle : {0, 17, 45, 90, 135, 200, 315}) {
        TFT_eSprite src(&tft, 200, 30, bpp);
        src._xPivot = 100, src._yPivot = 15;
        TFT_eSprite dst(&tft, 1100, 300, 16);
        for (int16_t px : {0, 550}) {
          dst._xPivot = px, dst._yPivot = 150;
          rec::reset();
          src.pushRotated(&dst, angle, transp);
          check("pushRotated sprite");
        }
        for (int16_t px : {-50, 120}) {
          tft._xPivot = px;
          rec::reset();
          src.pushRotated(angle, transp);
          check("pushRotated tft");
        }
        tft._xPivot = 120;
      }
    }
  }
  if (!print) {
    assert(n == sizeof(golden) / sizeof(golden[0]));
    std::puts("PASS sprite-stack");
  }
}
