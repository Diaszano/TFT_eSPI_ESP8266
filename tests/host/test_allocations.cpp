#include <cassert>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include "test_support.h"

using host_test::allocation_number;
using host_test::fail_at;
using host_test::outstanding;
using host_test::tracked_free;
#define malloc    host_test::tracked_malloc
#define calloc    host_test::tracked_calloc
#define free      host_test::tracked_free
#define TFT_BLACK 0

uint16_t pgm_read_word(const uint16_t* value) {
  return *value;
}
const uint16_t default_4bit_palette[16] = {};
namespace tft_espi_internal {
uint32_t sprite_frame2_offset_16bpp(int16_t width, int16_t height) {
  return (static_cast<uint32_t>(width) * height + 1) * sizeof(uint16_t);
}
}  // namespace tft_espi_internal

class TFT_eSPI {
 public:
  struct Metrics {
    const uint8_t* gArray = nullptr;
    uint16_t gCount = 1, yAdvance = 4, spaceWidth = 1;
    int16_t ascent = 2, descent = 0;
    uint16_t maxAscent = 2, maxDescent = 0;
  } gFont;
  uint16_t* gUnicode = nullptr;
  uint8_t* gHeight = nullptr;
  uint8_t* gWidth = nullptr;
  uint8_t* gxAdvance = nullptr;
  int16_t* gdY = nullptr;
  int8_t* gdX = nullptr;
  uint32_t* gBitmap = nullptr;
  bool fs_font = false;
  bool fontLoaded = true;
  uint32_t values[7] = {65, 2, 2, 3, 2, 0, 0};
  uint32_t value_index = 0;

  bool readInt32(uint32_t& value) {
    if (value_index >= 7) return false;
    value = values[value_index++];
    return true;
  }
  void yield() {}
  bool loadMetrics();
  void unloadFont();
};

class TFT_eSprite {
 public:
  bool _created = false, _vpOoB = true;
  int8_t _bpp = 4;
  int16_t _iwidth = 0, _dwidth = 0, _bitwidth = 0, _iheight = 0, _dheight = 0;
  int16_t _sx = 0, _sy = 0, _sw = 0, _sh = 0;
  uint16_t _scolor = 0;
  uint8_t* _img8 = nullptr;
  uint8_t* _img8_1 = nullptr;
  uint8_t* _img8_2 = nullptr;
  uint16_t* _img = nullptr;
  uint8_t* _img4 = nullptr;
  uint16_t* _colorMap = nullptr;
  int rotation = 0;
  int cursor_x = 0, cursor_y = 0;

  void* createSprite(int16_t w, int16_t h, uint8_t frames = 1);
  void* callocSprite(int16_t w, int16_t h, uint8_t frames);
  void createPalette(uint16_t colorMap[], uint8_t colors = 16);
  void createPalette(const uint16_t colorMap[], uint8_t colors = 16);
  void deleteSprite();
  void setViewport(int, int, int, int) {}
  void setPivot(int, int) {}
  bool created() const { return _created; }
};

// FUNCTION UNDER TEST

int main() {
  for (int failed_allocation = 1; failed_allocation <= 7; ++failed_allocation) {
    TFT_eSPI display;
    allocation_number = 0;
    fail_at = failed_allocation;
    outstanding = 0;
    assert(!display.loadMetrics());
    assert(!display.gUnicode && !display.gHeight && !display.gWidth);
    assert(!display.gxAdvance && !display.gdY && !display.gdX && !display.gBitmap);
    assert(!display.fontLoaded);
    assert(outstanding == 0);
  }

  TFT_eSPI display;
  display.fontLoaded = false;
  allocation_number = fail_at = outstanding = 0;
  assert(display.loadMetrics());
  assert(!display.fontLoaded);
  assert(outstanding == 7);
  tracked_free(display.gUnicode);
  tracked_free(display.gHeight);
  tracked_free(display.gWidth);
  tracked_free(display.gxAdvance);
  tracked_free(display.gdY);
  tracked_free(display.gdX);
  tracked_free(display.gBitmap);
  assert(outstanding == 0);

  TFT_eSprite sprite;
  allocation_number = 0;
  fail_at = 1;
  outstanding = 0;
  assert(sprite.createSprite(4, 4) == nullptr);
  assert(!sprite.created());
  assert(outstanding == 0);

  allocation_number = 0;
  fail_at = 2;
  assert(sprite.createSprite(4, 4) == nullptr);
  assert(!sprite.created());
  assert(outstanding == 0);
  fail_at = 0;
  assert(sprite.createSprite(4, 4) != nullptr);
  assert(sprite.created());
  sprite.deleteSprite();
  assert(outstanding == 0);

  uint16_t palette[] = {1, 2};
  sprite._created = true;
  allocation_number = 0;
  fail_at = 1;
  sprite.createPalette(palette, 2);
  assert(sprite._colorMap == nullptr);
  assert(outstanding == 0);
}
