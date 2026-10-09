#pragma once

#include <stdint.h>

namespace tft_espi_internal {

inline uint16_t rgb888_to_rgb565(uint8_t r, uint8_t g, uint8_t b) {
  return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3);
}

inline uint8_t rgb565_to_rgb332(uint16_t c) {
  return ((c & 0xE000) >> 8) | ((c & 0x0700) >> 6) | ((c & 0x0018) >> 3);
}

inline uint16_t rgb332_to_rgb565(uint8_t color) {
  uint8_t blue[] = {0, 11, 21, 31};
  uint16_t color16 = 0;
  color16 = (color & 0x1C) << 6 | (color & 0xC0) << 5 | (color & 0xE0) << 8;
  color16 |= (color & 0x1C) << 3 | blue[color & 0x03];
  return color16;
}

}  // namespace tft_espi_internal
