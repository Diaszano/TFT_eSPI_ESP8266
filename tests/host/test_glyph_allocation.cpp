#include <cassert>
#include <cstdint>
#include <cstdlib>

namespace fs {
enum SeekMode { SeekSet };
class File {
 public:
  explicit operator bool() const { return true; }
  void close() {}
  bool seek(uint32_t, SeekMode) { return true; }
  size_t read(uint8_t*, size_t) { return 0; }
};
}  // namespace fs

static int starts = 0, ends = 0, draws = 0;
void* failed_malloc(size_t) {
  return nullptr;
}
#define malloc failed_malloc

struct Metrics {
  const uint8_t* gArray = nullptr;
  uint16_t gCount = 1, yAdvance = 4, spaceWidth = 1;
  int16_t ascent = 2, descent = 0;
  uint16_t maxAscent = 2, maxDescent = 0;
};
uint8_t pgm_read_byte(const uint8_t* value) {
  return *value;
}

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
  bool fontLoaded = true, fs_font = true, spiffs = true;
  fs::File fontFile;
  uint16_t textcolor = 1, textbgcolor = 0;
  int cursor_x = 0, cursor_y = 0, bg_cursor_x = 0, last_cursor_x = 0;
  bool textwrapX = false, textwrapY = false, _fillbg = false;
  uint16_t (*getColor)(int, int) = nullptr;

  void drawGlyph(uint16_t code);
  void unloadFont();
  bool getUnicodeIndex(uint16_t, uint16_t* index) {
    *index = 0;
    return true;
  }
  int width() const { return 100; }
  int height() const { return 100; }
  void startWrite() { ++starts; }
  void endWrite() { ++ends; }
  void fillRect(int, int, int, int, uint16_t) { ++draws; }
  void drawFastHLine(int, int, int, uint16_t) { ++draws; }
  void drawPixel(int, int, uint16_t) { ++draws; }
  void drawRect(int, int, int, int, uint16_t) { ++draws; }
  uint16_t alphaBlend(uint8_t, uint16_t fg, uint16_t) { return fg; }
};

// FUNCTION UNDER TEST

int main() {
  uint8_t height[] = {2}, width[] = {2}, advance[] = {2};
  int16_t dy[] = {2};
  int8_t dx[] = {0};
  uint32_t bitmap[] = {24};
  TFT_eSPI display;
  display.gHeight = height;
  display.gWidth = width;
  display.gxAdvance = advance;
  display.gdY = dy;
  display.gdX = dx;
  display.gBitmap = bitmap;
  display.drawGlyph(65);
  assert(starts == 0 && ends == 0);
  assert(draws == 0);
}
