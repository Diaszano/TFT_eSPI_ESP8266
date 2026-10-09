#pragma once

#include <stdint.h>

namespace tft_espi_internal {

inline uint32_t sprite_frame2_offset_16bpp(uint16_t width, uint16_t height) {
  return (static_cast<uint32_t>(width) * height + 1U) * sizeof(uint16_t);
}

}  // namespace tft_espi_internal
