#include "internal/color_conversion.h"

int main() {
  using namespace tft_espi_internal;
  return rgb888_to_rgb565(255, 0, 0) == rgb332_to_rgb565(rgb565_to_rgb332(0xF800)) ? 0 : 1;
}
