#include "ValidationBench.h"

#include <Arduino.h>
#include "ValidationBenchMath.h"
#include "ValidationTelemetry.h"

namespace {
constexpr uint8_t kRounds = 3;
constexpr uint8_t kSamplesPerRound = 10;
constexpr uint16_t kRepetitions = 10;
uint16_t rgb565[16 * 16];
uint8_t image1[32], image4[128], image8[256];
uint16_t palette[16];

void op_fill_large(TFT_eSPI& t, TFT_eSprite&, uint16_t i) {
  t.fillRect(0, 40, 160, 100, i & 1 ? TFT_RED : TFT_BLUE);
}
void op_fill_small(TFT_eSPI& t, TFT_eSprite&, uint16_t i) {
  t.fillRect(10, 10, 16, 16, i & 1 ? TFT_RED : TFT_BLUE);
}
void op_text(TFT_eSPI& t, TFT_eSprite&, uint16_t) {
  t.drawString("ABC 0123", 4, 12);
}
void op_image(TFT_eSPI& t, TFT_eSprite&, uint16_t) {
  t.pushImage(24, 80, 16, 16, rgb565);
}
void op_image_transparent(TFT_eSPI& t, TFT_eSprite&, uint16_t) {
  t.pushImage(24, 80, 16, 16, rgb565, TFT_MAGENTA);
}
void op_image1(TFT_eSPI& t, TFT_eSprite&, uint16_t) {
  t.pushImage(24, 80, 16, 16, image1, false);
}
void op_image4(TFT_eSPI& t, TFT_eSprite&, uint16_t) {
  t.pushImage(24, 80, 16, 16, image4, false, palette);
}
void op_image8(TFT_eSPI& t, TFT_eSprite&, uint16_t) {
  t.pushImage(24, 80, 16, 16, image8, true);
}
void op_push_pixels(TFT_eSPI& t, TFT_eSprite&, uint16_t) {
  t.startWrite();
  t.setAddrWindow(24, 80, 16, 16);
  t.pushPixels(rgb565, 16 * 16);
  t.endWrite();
}
void op_sprite(TFT_eSPI& t, TFT_eSprite& s, uint16_t i) {
  s.pushSprite(24, 80, i & 1 ? TFT_MAGENTA : TFT_BLACK);
}
void op_rotate(TFT_eSPI&, TFT_eSprite& s, uint16_t i) {
  s.pushRotated(static_cast<int16_t>((i * 45) % 360), TFT_MAGENTA);
}

struct Scenario {
  const char* id;
  uint8_t font;
  bool opaque;
  bool wide;
  void (*operation)(TFT_eSPI&, TFT_eSprite&, uint16_t);
};
const Scenario scenarios[] = {
    {"fillrect_160x100", 1, true, false, op_fill_large},
    {"fillrect_16x16", 1, true, false, op_fill_small},
    {"font1_opaque", 1, true, false, op_text},
    {"font1_transparent", 1, false, false, op_text},
    {"font2_opaque", 2, true, false, op_text},
    {"font2_transparent", 2, false, false, op_text},
    {"font4_opaque", 4, true, false, op_text},
    {"font4_transparent", 4, false, false, op_text},
    {"pushimage_rgb565", 1, true, false, op_image},
    {"pushimage_rgb565_transparent", 1, true, false, op_image_transparent},
    {"pushimage_1bpp", 1, true, false, op_image1},
    {"pushimage_4bpp", 1, true, false, op_image4},
    {"pushimage_8bpp", 1, true, false, op_image8},
    {"pushpixels", 1, true, false, op_push_pixels},
    {"pushsprite_16bpp_32x32", 1, true, false, op_sprite},
    {"pushrotated_16bpp_200x24", 1, true, true, op_rotate},
};

void prepare(TFT_eSPI& tft, const Scenario& scenario) {
  tft.setTextPadding(0);
  tft.setTextFont(scenario.font);
  tft.setTextColor(TFT_WHITE, scenario.opaque ? TFT_BLACK : TFT_WHITE);
  tft.fillScreen(TFT_BLACK);
}
}  // namespace

void run_bench_suite(TFT_eSPI& tft, TFT_eSprite& sprite, TFT_eSprite& wide_sprite, Print& log) {
  for (uint16_t i = 0; i < 16 * 16; ++i) rgb565[i] = i & 1 ? TFT_MAGENTA : TFT_CYAN;
  for (uint16_t i = 0; i < sizeof(image1); ++i) image1[i] = i & 1 ? 0xAA : 0x55;
  for (uint16_t i = 0; i < sizeof(image4); ++i) image4[i] = static_cast<uint8_t>(i);
  for (uint16_t i = 0; i < sizeof(image8); ++i) image8[i] = static_cast<uint8_t>(i);
  for (uint8_t i = 0; i < 16; ++i) palette[i] = static_cast<uint16_t>(i * 0x1111);

  for (const Scenario& scenario : scenarios) {
    TFT_eSprite& target = scenario.wide ? wide_sprite : sprite;
    if ((scenario.operation == op_sprite && !sprite.created()) ||
        (scenario.operation == op_rotate && !wide_sprite.created())) {
      validation_emit_case_start(log, scenario.id, 0);
      validation_emit_case_return(log, scenario.id, 0, "SKIP");
      continue;
    }
    prepare(tft, scenario);
    scenario.operation(tft, target, 0);
    for (uint8_t round = 1; round <= kRounds; ++round) {
      for (uint8_t sample = 0; sample < kSamplesPerRound; ++sample) {
        prepare(tft, scenario);
        const uint32_t heap_before = ESP.getFreeHeap();
        uint32_t started;
        // BENCH_BEGIN
        started = micros();
        for (uint16_t repetition = 0; repetition < kRepetitions; ++repetition)
          scenario.operation(tft, target, repetition);
        const uint32_t total_us = elapsed_us(started, micros());
        // BENCH_END
        const uint32_t heap_after = ESP.getFreeHeap();
        log.print("BENCH,");
        log.print(scenario.id);
        log.print(',');
        log.print(round);
        log.print(',');
        log.print(sample);
        log.print(',');
        log.print(kRepetitions);
        log.print(',');
        log.print(total_us);
        log.print(',');
        log.print(heap_before);
        log.print(',');
        log.print(heap_after);
        log.print(',');
        log.println(ESP.getMaxFreeBlockSize());
        yield();
      }
    }
  }
  tft.setTextPadding(0);
  tft.setTextFont(1);
  tft.setTextColor(TFT_WHITE, TFT_BLACK);
}
