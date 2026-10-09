#include <cassert>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <string>
#include <utility>
#include <vector>
#include "test_support.h"

class String {
 public:
  String(const char* text = "") : value(text) {}
  String(std::string text) : value(std::move(text)) {}
  bool operator==(const char* text) const { return value == text; }
  friend String operator+(const char* left, const String& right) {
    return String(std::string(left) + right.value);
  }
  friend String operator+(const String& left, const char* right) {
    return String(left.value + right);
  }
  std::string value;
};

namespace fs {
enum SeekMode { SeekSet };
class File {
 public:
  std::vector<uint8_t>* bytes = nullptr;
  size_t offset = 0;
  size_t* seek_count = nullptr;
  size_t* fail_seek_at = nullptr;
  bool* fail_read = nullptr;
  File() = default;
  File(std::vector<uint8_t>* contents, size_t position, size_t* calls, size_t* fail_at,
       bool* failed_read)
      : bytes(contents),
        offset(position),
        seek_count(calls),
        fail_seek_at(fail_at),
        fail_read(failed_read) {}
  explicit operator bool() const { return bytes != nullptr; }
  bool seek(uint32_t position, SeekMode) {
    if (seek_count && ++*seek_count == *fail_seek_at) return false;
    if (!bytes || position > bytes->size()) return false;
    offset = position;
    return true;
  }
  uint32_t size() const { return bytes ? bytes->size() : 0; }
  int read() {
    if (!bytes || (fail_read && *fail_read) || offset >= bytes->size()) return -1;
    return (*bytes)[offset++];
  }
  size_t read(uint8_t* output, size_t count) {
    if (fail_read && *fail_read) return 0;
    size_t available = bytes && offset < bytes->size() ? bytes->size() - offset : 0;
    size_t amount = count < available ? count : available;
    if (amount) std::memcpy(output, bytes->data() + offset, amount);
    offset += amount;
    return amount;
  }
  void close() { bytes = nullptr; offset = 0; }
};

class FS {
 public:
  std::vector<uint8_t> data;
  size_t seek_count = 0, fail_seek_at = 0;
  bool fail_read = false;
  bool exists(const String&) const { return true; }
  File open(const String&, const char*) {
    seek_count = 0;
    return File(&data, 0, &seek_count, &fail_seek_at, &fail_read);
  }
};
}  // namespace fs

fs::FS SPIFFS;
static int write_starts = 0, write_ends = 0, pixel_draws = 0;
struct SerialPort {
  template <typename T>
  void println(const T&) {}
};
SerialPort Serial;
uint8_t pgm_read_byte(const uint8_t* pointer) { return *pointer; }
void yield() {}

#define malloc host_test::tracked_malloc
#define free host_test::tracked_free

class TFT_eSPI {
 public:
  struct Metrics {
    const uint8_t* gArray = nullptr;
    uint16_t gCount = 0, yAdvance = 0, spaceWidth = 0;
    int16_t ascent = 0, descent = 0;
    uint16_t maxAscent = 0, maxDescent = 0;
  } gFont;
  uint16_t* gUnicode = nullptr;
  uint8_t* gHeight = nullptr;
  uint8_t* gWidth = nullptr;
  uint8_t* gxAdvance = nullptr;
  int16_t* gdY = nullptr;
  int8_t* gdX = nullptr;
  uint32_t* gBitmap = nullptr;
  bool fontLoaded = false, spiffs = true, fs_font = false;
  fs::File fontFile;
  fs::FS& fontFS = SPIFFS;
  uint8_t* fontPtr = nullptr;
  uint16_t textcolor = 1, textbgcolor = 0;
  int cursor_x = 0, cursor_y = 0, bg_cursor_x = 0, last_cursor_x = 0;
  bool textwrapX = false, textwrapY = false, _fillbg = false;
  uint16_t (*getColor)(int, int) = nullptr;

  bool loadMetrics();
  void unloadFont();
  bool readInt32(uint32_t& value);
  void drawGlyph(uint16_t code);
  void loadFont(const uint8_t array[]);
  void loadFont(String fontName, bool flash);
  bool getUnicodeIndex(uint16_t, uint16_t* index) {
    *index = 0;
    return true;
  }
  int width() const { return 100; }
  int height() const { return 100; }
  void startWrite() { ++write_starts; }
  void endWrite() { ++write_ends; }
  void fillRect(int, int, int, int, uint16_t) { ++pixel_draws; }
  void drawFastHLine(int, int, int, uint16_t) { ++pixel_draws; }
  void drawPixel(int, int, uint16_t) { ++pixel_draws; }
  void drawRect(int, int, int, int, uint16_t) { ++pixel_draws; }
  uint16_t alphaBlend(uint8_t, uint16_t fg, uint16_t) { return fg; }
};

class TFT_eSprite : public TFT_eSPI {
 public:
  bool _created = false;
  void* createSprite(int16_t, int16_t) { _created = true; return this; }
  void deleteSprite() { _created = false; }
  void fillSprite(uint16_t) { ++pixel_draws; }
  void pushSprite(int16_t, int16_t) { ++pixel_draws; }
  uint16_t readPixel(int, int) { return 0; }
  void drawGlyph(uint16_t code);
};

// FUNCTIONS UNDER TEST

static void put32(std::vector<uint8_t>& bytes, uint32_t value) {
  bytes.push_back(static_cast<uint8_t>(value >> 24));
  bytes.push_back(static_cast<uint8_t>(value >> 16));
  bytes.push_back(static_cast<uint8_t>(value >> 8));
  bytes.push_back(static_cast<uint8_t>(value));
}

static std::vector<uint8_t> font_file(uint32_t version, uint32_t count = 1,
                                     uint32_t glyphWidth = 2,
                                     uint32_t glyphHeight = 2, uint32_t unicode = 65,
                                     uint32_t xAdvance = 3, uint32_t yOffset = 2,
                                     uint32_t xOffset = 0, uint32_t ascent = 2,
                                     uint32_t descent = 0) {
  std::vector<uint8_t> bytes;
  const uint32_t values[] = {count, version, 4, 0, ascent, descent, unicode, glyphHeight,
                             glyphWidth, xAdvance, yOffset, xOffset, 0};
  for (uint32_t value : values) put32(bytes, value);
  bytes.insert(bytes.end(), glyphWidth * glyphHeight, 0xFF);
  return bytes;
}

static void reject_file(std::vector<uint8_t> bytes) {
  SPIFFS.data = std::move(bytes);
  TFT_eSPI display;
  host_test::allocation_number = host_test::fail_at = host_test::outstanding = 0;
  display.loadFont(String("font"), true);
  assert(!display.fontLoaded);
  assert(!display.gUnicode && !display.gHeight && !display.gWidth);
  assert(!display.fontFile);
  assert(host_test::outstanding == 0);
}

int main() {
  reject_file(font_file(10));
  reject_file(std::vector<uint8_t>(23));
  reject_file(font_file(11, 0));
  reject_file(font_file(11, 65536));

  SPIFFS.data = font_file(11);
  SPIFFS.fail_read = true;
  TFT_eSPI short_header_read;
  short_header_read.loadFont(String("font"), true);
  assert(!short_header_read.fontLoaded && !short_header_read.fontFile);
  assert(host_test::outstanding == 0);
  SPIFFS.fail_read = false;

  SPIFFS.fail_seek_at = 1;
  TFT_eSPI failed_header_seek;
  failed_header_seek.loadFont(String("font"), true);
  assert(!failed_header_seek.fontLoaded && !failed_header_seek.fontFile);
  assert(host_test::outstanding == 0);
  SPIFFS.fail_seek_at = 0;

  auto partial_table = font_file(11);
  partial_table.resize(24);
  reject_file(partial_table);
  reject_file(font_file(11, 1, 256, 2));
  reject_file(font_file(11, 1, 2, 256));
  reject_file(font_file(11, 1, 2, 2, 65536));
  reject_file(font_file(11, 1, 2, 2, 65, 256));
  reject_file(font_file(11, 1, 2, 2, 65, 3, 32768));
  reject_file(font_file(11, 1, 2, 2, 65, 3, 2, 128));
  reject_file(font_file(11, 1, 2, 2, 65, 3, 2, 0, 32768));

  auto outside_bitmap = font_file(11);
  outside_bitmap.resize(54);
  reject_file(outside_bitmap);
  auto short_bitmap = font_file(11);
  short_bitmap.resize(55);
  reject_file(short_bitmap);

  SPIFFS.data = font_file(11);
  TFT_eSPI valid;
  valid.loadFont(String("font"), true);
  assert(valid.fontLoaded && valid.gWidth[0] == 2 && valid.gHeight[0] == 2);
  valid.unloadFont();
  assert(host_test::outstanding == 0);

  SPIFFS.data = font_file(11);
  SPIFFS.fail_seek_at = 2;
  TFT_eSPI failed_metrics_seek;
  failed_metrics_seek.loadFont(String("font"), true);
  assert(!failed_metrics_seek.fontLoaded && !failed_metrics_seek.fontFile);
  assert(host_test::outstanding == 0);
  SPIFFS.fail_seek_at = 0;

  auto zero_glyphs = font_file(11, 1, 0, 2);
  SPIFFS.data = zero_glyphs;
  TFT_eSPI zero_glyph;
  zero_glyph.loadFont(String("font"), true);
  assert(zero_glyph.fontLoaded && zero_glyph.gWidth[0] == 0);
  write_starts = write_ends = pixel_draws = 0;
  zero_glyph.drawGlyph(65);
  assert(zero_glyph.fontLoaded && write_starts == 1 && write_ends == 1 && pixel_draws == 0);
  zero_glyph.unloadFont();
  assert(host_test::outstanding == 0);

  SPIFFS.data = font_file(11, 1, 2, 2, 65, 3, 0xFFFF8000, 0xFFFFFF80);
  TFT_eSPI signed_edges;
  signed_edges.loadFont(String("font"), true);
  assert(signed_edges.fontLoaded && signed_edges.gdY[0] == INT16_MIN &&
         signed_edges.gdX[0] == INT8_MIN);
  signed_edges.unloadFont();
  assert(host_test::outstanding == 0);

  auto array_font = font_file(11, 1, 0, 2);
  TFT_eSPI array_display;
  array_display.loadFont(array_font.data());
  assert(array_display.fontLoaded && array_display.gWidth[0] == 0);
  array_display.unloadFont();
  assert(host_test::outstanding == 0);

  array_font = font_file(10);
  array_display.loadFont(array_font.data());
  assert(!array_display.fontLoaded && host_test::outstanding == 0);

  SPIFFS.data = font_file(11);
  TFT_eSPI shortened;
  shortened.loadFont(String("font"), true);
  assert(shortened.fontLoaded);
  SPIFFS.data.resize(52);
  write_starts = write_ends = pixel_draws = 0;
  shortened.drawGlyph(65);
  assert(!shortened.fontLoaded && !shortened.fontFile);
  assert(write_starts == 1 && write_ends == 1 && pixel_draws == 0);
  assert(host_test::outstanding == 0);

  SPIFFS.data = font_file(11);
  TFT_eSPI failed_draw_seek;
  failed_draw_seek.loadFont(String("font"), true);
  SPIFFS.fail_seek_at = 3;
  write_starts = write_ends = pixel_draws = 0;
  failed_draw_seek.drawGlyph(65);
  assert(!failed_draw_seek.fontLoaded && !failed_draw_seek.fontFile);
  assert(write_starts == 0 && write_ends == 0 && pixel_draws == 0);
  assert(host_test::outstanding == 0);
  SPIFFS.fail_seek_at = 0;

  SPIFFS.data = font_file(11);
  TFT_eSprite sprite;
  sprite.loadFont(String("font"), true);
  assert(sprite.fontLoaded);
  sprite.textcolor = sprite.textbgcolor = 1;
  SPIFFS.data.resize(52);
  pixel_draws = 0;
  sprite.drawGlyph(65);
  assert(!sprite.fontLoaded && !sprite.fontFile && !sprite._created);
  assert(pixel_draws == 0 && host_test::outstanding == 0);

  SPIFFS.data = font_file(11);
  TFT_eSprite failed_sprite_seek;
  failed_sprite_seek.loadFont(String("font"), true);
  failed_sprite_seek.textcolor = failed_sprite_seek.textbgcolor = 1;
  SPIFFS.fail_seek_at = 3;
  pixel_draws = 0;
  failed_sprite_seek.drawGlyph(65);
  assert(!failed_sprite_seek.fontLoaded && !failed_sprite_seek.fontFile);
  assert(!failed_sprite_seek._created && pixel_draws == 0 && host_test::outstanding == 0);
  SPIFFS.fail_seek_at = 0;
}
