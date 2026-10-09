#include <cassert>
#include <cstdint>
#include <cstring>
#include <new>
#define LOAD_GFXFF
#define LOAD_GLCD
struct GFXglyph { uint8_t width, height, xAdvance; int8_t xOffset, yOffset; };
struct GFXfont { GFXglyph* glyph; uint16_t first, last; uint8_t yAdvance; };
struct FontData { const uint8_t* widthtbl; uint8_t height, baseline; };
static const uint8_t widths[96] = {};
static FontData fontdata[9] = {{widths, 8, 0}, {widths, 8, 0}};
template <class T> T pgm_read_byte(const T* pointer) { return *pointer; }
uint16_t pgm_read_word(const uint16_t* pointer) { return *pointer; }
template <class T> uintptr_t pgm_read_dword(T* const* pointer) {
  return reinterpret_cast<uintptr_t>(*pointer);
}
enum Datum { TL_DATUM, TC_DATUM, TR_DATUM, ML_DATUM, MC_DATUM, MR_DATUM,
             BL_DATUM, BC_DATUM, BR_DATUM, L_BASELINE, C_BASELINE, R_BASELINE };
class TFT_eSPI {
 public:
  // MEMBER UNDER TEST
  uint8_t textsize = 1, textfont = 1, textdatum = TL_DATUM, glyph_ab = 0, glyph_bb = 0;
  uint16_t padX = 0, textcolor = 1, textbgcolor = 0;
  bool isDigits = false;
  int draws = 0;
  int16_t fontHeight(uint8_t font);
  int16_t textWidth(const char* text, uint8_t font);
  int16_t drawString(const char* text, int32_t x, int32_t y, uint8_t font);
  uint16_t decodeUTF8(uint8_t character) { return character; }
  uint16_t decodeUTF8(uint8_t* text, uint16_t* offset, uint16_t) { return text[(*offset)++]; }
  int16_t drawChar(uint16_t, int32_t, int32_t, uint8_t) { ++draws; return 6; }
  void fillRect(int32_t, int32_t, int32_t, int32_t, uint16_t) { ++draws; }
};
// FUNCTIONS UNDER TEST
static void check(void* storage) {
  std::memset(storage, 0xA5, sizeof(TFT_eSPI));
  TFT_eSPI* display = new (storage) TFT_eSPI;
  GFXfont* expected = nullptr;
  unsigned char actual_bytes[sizeof(expected)], expected_bytes[sizeof(expected)];
  std::memcpy(actual_bytes, &display->gfxFont, sizeof(expected));
  std::memcpy(expected_bytes, &expected, sizeof(expected));
  assert(std::memcmp(actual_bytes, expected_bytes, sizeof(expected)) == 0);
  assert(display->fontHeight(1) == 8);
  assert(display->textWidth("A", 1) == 6);
  assert(display->drawString("A", 0, 0, 1) == 6);
  assert(display->draws == 1);
  display->~TFT_eSPI();
}
int main() {
  alignas(TFT_eSPI) unsigned char local[sizeof(TFT_eSPI)];
  check(local);
  void* dynamic = ::operator new(sizeof(TFT_eSPI));
  check(dynamic);
  ::operator delete(dynamic);
}
