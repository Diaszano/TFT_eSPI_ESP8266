// Cropped pushSprite window arithmetic. The real TFT_eSprite::setWindow and
// TFT_eSprite::pushSprite(tx, ty, sx, sy, sw, sh) bodies are spliced in by run.py. Extreme
// positions or sizes must not overflow signed int32_t (UBSan aborts on the raw sx + sw - 1), and
// in-bounds crops must match a reference copy.
#include <cassert>
#include <climits>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <vector>

template <typename T>
static void transpose(T& a, T& b) {
  T t = a;
  a = b;
  b = t;
}

namespace rec {
std::vector<uint16_t> canvas;
int N = 0;
void reset(int n) {
  N = n;
  canvas.assign(size_t(n) * n, 0);
}
void plot(int32_t x, int32_t y, uint16_t c) {
  if (x >= 0 && y >= 0 && x < N && y < N) canvas[size_t(y) * N + x] = c;
}
}  // namespace rec

struct TFT_eSPI {
  bool _swap = false;
  void setSwapBytes(bool s) { _swap = s; }
  bool getSwapBytes() const { return _swap; }
  void startWrite() {}
  void endWrite() {}
  void drawPixel(int32_t x, int32_t y, uint32_t c) { rec::plot(x, y, (uint16_t)c); }
  void pushImage(int32_t x, int32_t y, int32_t w, int32_t h, uint16_t* data) {
    pushImage(x, y, w, h, static_cast<const uint16_t*>(data));
  }
  void pushImage(int32_t x, int32_t y, int32_t w, int32_t h, const uint16_t* data) {
    for (int32_t j = 0; j < h; ++j)
      for (int32_t i = 0; i < w; ++i) rec::plot(x + i, y + j, data[size_t(j) * w + i]);
  }
  // 8 bpp / 4 bpp / 1 bpp overloads are compiled but not exercised by the 16 bpp crop below.
  void pushImage(int32_t, int32_t, int32_t, int32_t, uint8_t*, bool) {}
  void pushImage(int32_t, int32_t, int32_t, int32_t, uint8_t*, bool, const uint16_t*) {}
};

class TFT_eSprite {
 public:
  TFT_eSPI* _tft = nullptr;
  bool _created = true;
  uint8_t _bpp = 16;
  int32_t _iwidth = 0, _iheight = 0, _dwidth = 0, _dheight = 0, _bitwidth = 0;
  int32_t _xs = 0, _xe = 0, _ys = 0, _ye = 0, _xptr = 0, _yptr = 0;
  bool _vpDatum = false;
  int32_t _xWidth = 0, _yHeight = 0;
  uint8_t rotation = 0;
  uint16_t* _img = nullptr;
  uint8_t* _img8 = nullptr;
  uint8_t* _img4 = nullptr;
  const uint16_t* _colorMap = nullptr;

  int16_t width() { return _created ? (int16_t)_dwidth : 0; }
  int16_t height() { return _created ? (int16_t)_dheight : 0; }
  uint16_t readPixel(int32_t x, int32_t y) { return _img[size_t(y) * _iwidth + x]; }

  void setWindow(int32_t x0, int32_t y0, int32_t x1, int32_t y1);
  bool pushSprite(int32_t tx, int32_t ty, int32_t sx, int32_t sy, int32_t sw, int32_t sh);
};

// FUNCTIONS UNDER TEST

// Reference copy of an in-bounds crop: img[sy + j][sx + i] -> canvas[ty + j][tx + i].
static void refCrop(const std::vector<uint16_t>& img, int W, int tx, int ty, int sx, int sy, int sw,
                    int sh) {
  for (int j = 0; j < sh; ++j)
    for (int i = 0; i < sw; ++i) rec::plot(tx + i, ty + j, img[size_t(sy + j) * W + sx + i]);
}

int main() {
  const int32_t W = 16, H = 8;
  std::vector<uint16_t> img(W * H);
  for (int i = 0; i < W * H; ++i) img[i] = (uint16_t)(i + 1);

  TFT_eSPI tft;
  TFT_eSprite s;
  s._tft = &tft;
  s._iwidth = s._dwidth = s._bitwidth = W;
  s._iheight = s._dheight = H;
  s._img = img.data();

  // In-bounds crops: full sprite and a sub-window, both must match the reference.
  for (int pass = 0; pass < 2; ++pass) {
    rec::reset(40);
    const int32_t tx = pass == 0 ? 2 : 0, ty = pass == 0 ? 3 : 0;
    const int32_t sx = pass == 0 ? 0 : 2, sy = pass == 0 ? 0 : 1;
    const int32_t sw = pass == 0 ? W : 5, sh = pass == 0 ? H : 3;
    assert(s.pushSprite(tx, ty, sx, sy, sw, sh));
    std::vector<uint16_t> got = rec::canvas;  // pushed result
    rec::reset(rec::N);                       // clear, then draw the reference
    refCrop(img, W, tx, ty, sx, sy, sw, sh);
    for (int y = 0; y < rec::N; ++y)
      for (int x = 0; x < rec::N; ++x)
        if (got[size_t(y) * rec::N + x] != rec::canvas[size_t(y) * rec::N + x]) {
          std::printf("crop mismatch at %d,%d (sx=%d sy=%d sw=%d sh=%d)\n", x, y, sx, sy, sw, sh);
          std::abort();
        }
  }

  // Extreme positions and sizes: no signed overflow is allowed. The window arithmetic saturates
  // and rec::plot bounds-checks every write, so any overflow or out-of-bounds access aborts.
  rec::reset(40);
  const int32_t big[] = {INT32_MIN, INT32_MIN + 1, -100000,       -1,       0, 1,
                         16,        100000,        INT32_MAX - 1, INT32_MAX};
  for (int32_t sx : big)
    for (int32_t sw : big)
      for (int32_t sy : big)
        for (int32_t sh : big) s.pushSprite(0, 0, sx, sy, sw, sh);

  std::puts("PASS sprite-crop");
}
