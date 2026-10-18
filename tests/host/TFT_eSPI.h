#ifndef VALIDATION_HOST_TFT_ESPI_H
#define VALIDATION_HOST_TFT_ESPI_H
#include <cstdint>
#include <vector>

constexpr uint16_t TFT_BLACK = 0;
constexpr uint16_t TFT_WHITE = 0xffff;
constexpr uint16_t TFT_RED = 0xf800;
constexpr uint16_t TFT_BLUE = 0x001f;
constexpr uint16_t TFT_GREEN = 0x07e0;

class TFT_eSPI {
 public:
  unsigned windows = 0;
  unsigned rows = 0;
  unsigned payload_pixels = 0;
  unsigned fills = 0;
  uint16_t first_pixel = 0;
  uint16_t last_pixel = 0;
  void startWrite() {}
  void endWrite() {}
  void setAddrWindow(int32_t x, int32_t y, int32_t width, int32_t height) {
    if (x < 0 || y < 0 || width < 0 || height < 0 ||
        x + width > 240 || y + height > 240) ++bad_windows;
    if (width && height) ++windows;
  }
  unsigned bad_windows = 0;
  unsigned images = 0;
  unsigned strings = 0;
  uint8_t font = 1;
  bool swap_bytes = false;
  void pushPixels(uint16_t* pixels, uint32_t count) {
    if (!rows) first_pixel = pixels[0];
    last_pixel = pixels[count - 1];
    ++rows;
    payload_pixels += count;
  }
  void fillScreen(uint16_t) { ++fills; }
  void fillRect(int32_t, int32_t, int32_t, int32_t, uint16_t) {}
  void drawRect(int32_t, int32_t, int32_t, int32_t, uint16_t) {}
  void drawFastHLine(int32_t, int32_t, int32_t, uint16_t) {}
  void drawString(const char*, int32_t, int32_t, int = 1) { ++strings; }
  void setTextFont(uint8_t value) { font = value; }
  void setTextColor(uint16_t, uint16_t) {}
  void pushImage(int32_t, int32_t, int32_t, int32_t, uint16_t*) { ++images; }
  void setSwapBytes(bool value) { swap_bytes = value; }
  int32_t width() const { return 240; }
  int32_t height() const { return 240; }
};

class TFT_eSprite {
 public:
  explicit TFT_eSprite(TFT_eSPI*) {}
  bool available = true;
  unsigned pushes = 0;
  int32_t min_x = 10000;
  int32_t max_x = -1;
  std::vector<int32_t> positions;
  bool created() const { return available; }
  void fillSprite(uint16_t) {}
  void pushSprite(int32_t x, int32_t) {
    ++pushes;
    if (x < min_x) min_x = x;
    if (x > max_x) max_x = x;
    positions.push_back(x);
  }
};
#endif
