#include <cassert>
#include <cstdint>

struct GFXglyph {
  uint8_t width, height;
  int8_t xOffset, yOffset;
  uint8_t xAdvance;
  uint16_t bitmapOffset;
};
struct GFXfont {
  uint8_t* bitmap;
  GFXglyph* glyph;
  uint16_t first, last;
};

uint16_t pgm_read_word(const uint16_t* value) { return *value; }
uintptr_t pgm_read_dword(GFXglyph* const* value) {
  return reinterpret_cast<uintptr_t>(*value);
}
int8_t pgm_read_byte(const int8_t* value) { return *value; }
uint8_t pgm_read_byte(const uint8_t* value) { return *value; }

class TFT_eSPI {
 public:
  GFXfont* gfxFont = nullptr;
  uint8_t textfont = 0;
  int16_t glyph_ab = 0, glyph_bb = 0;
  void setFreeFont(const GFXfont* font);
  void setTextFont(uint8_t) {}
};

// FUNCTION UNDER TEST

int main() {
  GFXglyph glyphs[] = {{0, 1, 0, 0, 1, 0}, {0, 8, 0, -7, 1, 0}};
  GFXfont font = {nullptr, glyphs, 65, 66};
  TFT_eSPI display;
  display.setFreeFont(&font);
  assert(display.glyph_ab == 7);
  assert(display.glyph_bb == 1);
}
