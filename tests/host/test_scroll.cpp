#include <cassert>
#include <cstdint>
#include <cstdlib>
#include <cstring>

class TFT_eSprite {
 public:
  int16_t _sw = 0, _sh = 0, _sx = 0, _sy = 0;
  uint16_t _scolor = 0;
  int32_t _iwidth = 0;
  int _bpp = 4;
  uint16_t words[128] = {};
  uint8_t bytes[256] = {};
  uint16_t* _img = words;
  uint8_t* _img8 = bytes;
  uint8_t* _img4 = bytes;
  uint16_t pixels[128] = {};
  uint32_t width = 0, height = 0;
  bool failed = false;

  void scroll(int16_t dx, int16_t dy);

  uint16_t readPixelValue(uint32_t x, uint32_t y) {
    if (x >= width || y >= height) {
      failed = true;
      return 0;
    }
    return pixels[y * width + x];
  }

  void drawPixel(uint32_t x, uint32_t y, uint16_t value) {
    if (x >= width || y >= height) {
      failed = true;
      return;
    }
    pixels[y * width + x] = value;
  }

  void fillRect(uint32_t x, uint32_t y, uint32_t w, uint32_t h, uint16_t color) {
    for (uint32_t row = y; row < y + h; ++row)
      for (uint32_t col = x; col < x + w; ++col) drawPixel(col, row, color);
  }

  void reset(uint32_t w, uint32_t h, int bpp) {
    width = _sw = w;
    height = _sh = h;
    _iwidth = w;
    _bpp = bpp;
    _sx = _sy = 0;
    _scolor = 0;
    failed = false;
    for (uint32_t i = 0; i < w * h; ++i) pixels[i] = static_cast<uint16_t>(i + 1);
  }
};

// FUNCTION UNDER TEST

static void check_equal(const TFT_eSprite& sprite, const uint16_t* expected, uint32_t size) {
  assert(!sprite.failed);
  for (uint32_t i = 0; i < size; ++i) assert(sprite.pixels[i] == expected[i]);
}

int main() {
  TFT_eSprite sprite;
  sprite.reset(4, 1, 4);
  const uint16_t four_bit[] = {1, 2, 3, 4};
  std::memcpy(sprite.pixels, four_bit, sizeof(four_bit));
  sprite.scroll(1, 0);
  const uint16_t four_bit_expected[] = {0, 1, 2, 3};
  check_equal(sprite, four_bit_expected, 4);

  sprite.reset(4, 1, 1);
  const uint16_t one_bit[] = {1, 0, 1, 1};
  std::memcpy(sprite.pixels, one_bit, sizeof(one_bit));
  sprite.scroll(1, 0);
  const uint16_t one_bit_expected[] = {0, 1, 0, 1};
  check_equal(sprite, one_bit_expected, 4);

  sprite.reset(4, 1, 4);
  sprite.scroll(-1, 0);
  const uint16_t left_expected[] = {2, 3, 4, 0};
  check_equal(sprite, left_expected, 4);

  sprite.reset(4, 3, 4);
  sprite.scroll(1, 1);
  const uint16_t diagonal_expected[] = {0, 0, 0, 0,
                                        0, 1, 2, 3,
                                        0, 5, 6, 7};
  check_equal(sprite, diagonal_expected, 12);

  sprite.reset(6, 3, 4);
  for (uint32_t i = 0; i < 18; ++i) sprite.pixels[i] = static_cast<uint16_t>(90 + i);
  sprite._sx = 1;
  sprite._sy = 1;
  sprite._sw = 4;
  sprite._sh = 1;
  sprite.scroll(1, 0);
  const uint16_t margin_expected[] = {90, 91, 92, 93, 94, 95,
                                      96,  0,  97, 98, 99, 101,
                                      102, 103, 104, 105, 106, 107};
  check_equal(sprite, margin_expected, 18);

  sprite.reset(4, 1, 1);
  sprite.scroll(4, 0);
  const uint16_t full_expected[] = {0, 0, 0, 0};
  check_equal(sprite, full_expected, 4);
}
