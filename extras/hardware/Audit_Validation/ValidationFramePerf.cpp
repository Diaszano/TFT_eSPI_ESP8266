#include "ValidationFramePerf.h"

#include <Arduino.h>
#include <stdio.h>
#include "ValidationFrameSampler.h"
#include "ValidationInput.h"
#include "ValidationPerfTelemetry.h"

namespace {
enum class Scene { Scanline, Fill };

void draw(Scene scene, uint32_t frame, TFT_eSPI& tft, uint16_t* line) {
  if (scene == Scene::Fill) {
    tft.fillScreen((frame & 1) ? TFT_BLUE : TFT_RED);
    return;
  }
  tft.startWrite();
  tft.setAddrWindow(0, 0, 240, 240);
  for (uint16_t row = 0; row < 240; ++row) tft.pushPixels(line, 240);
  tft.endWrite();
}

bool run_profile(Scene scene, const char* profile, bool cold, TFT_eSPI& tft, Print& log) {
  static uint16_t counter = 0;
  char run_id[17];
  snprintf(run_id, sizeof(run_id), "F%08lx%04x",
           static_cast<unsigned long>(ESP.getCycleCount()), counter++);
  ValidationPerfEmitter perf(log, run_id);
  const uint32_t expected = cold ? 1 : 1000;
  if (!perf.begin("FP1", 0, expected, profile)) return false;
  uint16_t line[240];
  uint32_t observed = 0;
  uint64_t elapsed = 0;
  uint32_t batch_id = 0;
  while (observed < expected) {
    validation::FrameBatch batch;
    while (batch.count < 128 && observed < expected) {
      const uint32_t frame = observed + (cold ? 0 : 1);
      if (scene == Scene::Scanline)
        for (uint16_t x = 0; x < 240; ++x)
          line[x] = static_cast<uint16_t>(((frame + x) & 31) << 11 | ((x >> 2) & 63) << 5 |
                                          ((frame >> 1) & 31));
      const uint32_t before = micros();
      draw(scene, frame, tft, line);
      const uint32_t after = micros();
      uint32_t duration;
      if (!validation::validation_frame_sample(before, after, &duration) ||
          !batch.append(duration)) {
        perf.abort("FP1", observed, "INVALID_SAMPLE");
        return false;
      }
      elapsed += duration;
      ++observed;
      yield();
    }
    for (uint8_t chunk = 0; chunk < (batch.count + 15) / 16; ++chunk) {
      const uint8_t left = batch.count - chunk * 16;
      if (!perf.samples("FP1", batch_id, chunk, batch.durations_us + chunk * 16,
                        left < 16 ? left : 16)) return false;
    }
    ++batch_id;
    if (validation_poll_control(log, false) == validation::ControlAction::Quit) {
      perf.abort("FP1", observed, "Q");
      return false;
    }
  }
  return perf.end("FP1", observed, elapsed, "PASS");
}
}  // namespace

namespace validation {
void run_frame_perf(FrameSuite suite, TFT_eSPI& tft, TFT_eSprite&, Print& log) {
  if (suite != FrameSuite::Full) return;
  if (!run_profile(Scene::Scanline, "fp1_scanline_cold", true, tft, log)) return;
  if (!run_profile(Scene::Scanline, "fp1_scanline", false, tft, log)) return;
  if (!run_profile(Scene::Fill, "fp1_fill_cold", true, tft, log)) return;
  run_profile(Scene::Fill, "fp1_fill", false, tft, log);
}
}
