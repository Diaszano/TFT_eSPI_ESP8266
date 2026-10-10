#include <cassert>
#include <cstdint>
#include <cstdlib>
#include <cstring>

class TFT_eSprite {
 public:
  int32_t _sx = 0, _sy = 0;
  uint32_t _sw = 0, _sh = 0;
  uint32_t _scolor = 0;
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

#ifndef FUZZ_TARGET
static void check_equal(const TFT_eSprite& sprite, const uint16_t* expected, uint32_t size) {
  assert(!sprite.failed);
  for (uint32_t i = 0; i < size; ++i) assert(sprite.pixels[i] == expected[i]);
}
#endif

#ifdef FUZZ_TARGET
extern "C" int LLVMFuzzerTestOneInput(const uint8_t* data, size_t size) {
  // Input contract layout (11 bytes min):
  // [0]: width (1..16) -> (data[0] % 16) + 1
  // [1]: height (1..8) -> (data[1] % 8) + 1
  // [2]: bpp (1 or 4) -> (data[2] & 1) ? 4 : 1
  // [3]: sub_x (0..width-1)
  // [4]: sub_y (0..height-1)
  // [5]: sub_w (1..width-sub_x)
  // [6]: sub_h (1..height-sub_y)
  // [7..8]: int16_t dx
  // [9..10]: int16_t dy
  // [11]: scolor (raw value masked to bpp)
  // [12..]: pixel values for initial matrix, clamped to bpp
  if (size < 12) return 0;

  uint32_t w = (data[0] % 16) + 1;
  uint32_t h = (data[1] % 8) + 1;
  int bpp = (data[2] & 1) ? 4 : 1;
  uint16_t max_pixel_val = (bpp == 1) ? 1 : 15;

  uint32_t sub_x = data[3] % w;
  uint32_t sub_y = data[4] % h;
  uint32_t sub_w = (data[5] % (w - sub_x)) + 1;
  uint32_t sub_h = (data[6] % (h - sub_y)) + 1;

  int16_t dx = static_cast<int16_t>(data[7] | (static_cast<uint16_t>(data[8]) << 8));
  int16_t dy = static_cast<int16_t>(data[9] | (static_cast<uint16_t>(data[10]) << 8));
  uint32_t scolor = data[11] & max_pixel_val;

  TFT_eSprite sprite;
  sprite.reset(w, h, bpp);
  sprite._sx = sub_x;
  sprite._sy = sub_y;
  sprite._sw = sub_w;
  sprite._sh = sub_h;
  sprite._scolor = scolor;

  uint16_t original[128] = {};
  uint32_t total_pixels = w * h;
  for (uint32_t i = 0; i < total_pixels; ++i) {
    uint8_t byte_val = (12 + i < size) ? data[12 + i] : static_cast<uint8_t>(i + 1);
    uint16_t px = byte_val & max_pixel_val;
    original[i] = px;
    sprite.pixels[i] = px;
  }

  sprite.scroll(dx, dy);

  assert(!sprite.failed);

  // Compute immutable reference oracle
  uint16_t reference[128] = {};
  for (uint32_t i = 0; i < total_pixels; ++i) {
    reference[i] = original[i];
  }

  if (std::abs(static_cast<int>(dx)) >= static_cast<int>(sub_w) ||
      std::abs(static_cast<int>(dy)) >= static_cast<int>(sub_h)) {
    // Entire subarea is replaced with scolor
    for (uint32_t y = sub_y; y < sub_y + sub_h; ++y) {
      for (uint32_t x = sub_x; x < sub_x + sub_w; ++x) {
        reference[y * w + x] = static_cast<uint16_t>(scolor);
      }
    }
  } else {
    // 1. Shift valid pixels inside the subarea to destination positions
    // Temporary subarea buffer to avoid in-place overwrite issues during oracle computation
    uint16_t sub_dest[128] = {};
    bool sub_covered[128] = {};
    for (uint32_t y = 0; y < sub_h; ++y) {
      for (uint32_t x = 0; x < sub_w; ++x) {
        int32_t dst_x = static_cast<int32_t>(x) + dx;
        int32_t dst_y = static_cast<int32_t>(y) + dy;
        if (dst_x >= 0 && dst_x < static_cast<int32_t>(sub_w) && dst_y >= 0 &&
            dst_y < static_cast<int32_t>(sub_h)) {
          uint32_t orig_idx = (sub_y + y) * w + (sub_x + x);
          uint32_t sub_idx = static_cast<uint32_t>(dst_y) * sub_w + static_cast<uint32_t>(dst_x);
          sub_dest[sub_idx] = original[orig_idx];
          sub_covered[sub_idx] = true;
        }
      }
    }

    // 2. Put shifted pixels back into reference, and uncovered subarea positions get scolor
    for (uint32_t y = 0; y < sub_h; ++y) {
      for (uint32_t x = 0; x < sub_w; ++x) {
        uint32_t sub_idx = y * sub_w + x;
        uint32_t ref_idx = (sub_y + y) * w + (sub_x + x);
        if (sub_covered[sub_idx]) {
          reference[ref_idx] = sub_dest[sub_idx];
        } else {
          reference[ref_idx] = static_cast<uint16_t>(scolor);
        }
      }
    }
  }

  for (uint32_t i = 0; i < total_pixels; ++i) {
    assert(sprite.pixels[i] == reference[i]);
  }

  return 0;
}
#else
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
  const uint16_t diagonal_expected[] = {0, 0, 0, 0, 0, 1, 2, 3, 0, 5, 6, 7};
  check_equal(sprite, diagonal_expected, 12);

  sprite.reset(6, 3, 4);
  for (uint32_t i = 0; i < 18; ++i) sprite.pixels[i] = static_cast<uint16_t>(90 + i);
  sprite._sx = 1;
  sprite._sy = 1;
  sprite._sw = 4;
  sprite._sh = 1;
  sprite.scroll(1, 0);
  const uint16_t margin_expected[] = {90, 91, 92,  93,  94,  95,  96,  0,   97,
                                      98, 99, 101, 102, 103, 104, 105, 106, 107};
  check_equal(sprite, margin_expected, 18);

  sprite.reset(4, 1, 1);
  sprite.scroll(4, 0);
  const uint16_t full_expected[] = {0, 0, 0, 0};
  check_equal(sprite, full_expected, 4);
}
#endif
