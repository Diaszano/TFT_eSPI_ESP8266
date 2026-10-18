#include "ValidationExtremes.h"

#include <Arduino.h>
#include "ValidationTelemetry.h"

namespace {
void case_start(Print& log, const char* id) {
  log.flush();
  validation_emit_case_start(log, id, 0);
}

void case_end(Print& log, const char* id, uint32_t started) {
  validation_emit_case_return(log, id, micros() - started, "PASS");
  yield();
}
}  // namespace

void run_extreme_suite(TFT_eSPI& tft, TFT_eSprite& sprite, Print& log) {
  (void)
      sprite;  // Sprite coordinates are omitted until the production push path has a host fixture.
  uint32_t started;
  case_start(log, "fully_offscreen_241");
  started = micros();
  tft.fillRect(241, 0, 1, 1, TFT_RED);
  case_end(log, "fully_offscreen_241", started);

  case_start(log, "negative_one_pixel");
  started = micros();
  tft.fillRect(-1, -1, 2, 2, TFT_GREEN);
  case_end(log, "negative_one_pixel", started);

  case_start(log, "viewport_zero");
  started = micros();
  tft.setViewport(0, 0, 0, 0, true);
  tft.fillScreen(TFT_BLACK);
  tft.resetViewport();
  case_end(log, "viewport_zero", started);

  case_start(log, "line_near_edge");
  started = micros();
  tft.drawFastHLine(-1, 239, 242, TFT_BLUE);
  case_end(log, "line_near_edge", started);

  uint16_t image[16 * 16];
  for (uint16_t i = 0; i < 16 * 16; ++i) image[i] = i & 1 ? TFT_CYAN : TFT_MAGENTA;
  case_start(log, "image_16x16_crop");
  started = micros();
  tft.pushImage(-3, -2, 16, 16, image);
  case_end(log, "image_16x16_crop", started);

  case_start(log, "sprite_32x32_offscreen");
  validation_emit_case_return(log, "sprite_32x32_offscreen", 0, "SKIP");
}
