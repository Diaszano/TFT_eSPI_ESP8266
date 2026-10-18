#include "ValidationFramePerf.h"

#include <Arduino.h>
#include <stdio.h>
#include "ValidationFrameSampler.h"
#include "ValidationInput.h"
#include "ValidationPerfTelemetry.h"

namespace {
enum class Scene { Scanline, Fill, Region };

void draw(Scene scene, uint32_t frame, TFT_eSPI& tft, uint16_t* line,
          uint16_t size, uint8_t position) {
  if (scene == Scene::Fill) {
    tft.fillScreen((frame & 1) ? TFT_BLUE : TFT_RED);
    return;
  }
  if (scene == Scene::Region) {
    const uint16_t visible = position == 2 ? size / 2 : size;
    const uint16_t origin = position == 0 ? (240 - size) / 2 :
                            position == 1 ? 240 - size : 240 - visible;
    tft.startWrite();
    tft.setAddrWindow(origin, origin, visible, visible);
    for (uint16_t row = 0; row < visible; ++row) tft.pushPixels(line, visible);
    tft.endWrite();
    return;
  }
  tft.startWrite();
  tft.setAddrWindow(0, 0, 240, 240);
  for (uint16_t row = 0; row < 240; ++row) tft.pushPixels(line, 240);
  tft.endWrite();
}

bool run_profile(Scene scene, const char* profile, bool cold, TFT_eSPI& tft, Print& log,
                 uint16_t size = 0, uint8_t position = 0) {
  static uint16_t counter = 0;
  char run_id[17];
  snprintf(run_id, sizeof(run_id), "F%08lx%04x",
           static_cast<unsigned long>(ESP.getCycleCount()), counter++);
  ValidationPerfEmitter perf(log, run_id);
  const char* suite = scene == Scene::Region ? "FP2" : "FP1";
  const uint32_t expected = cold ? 1 : 1000;
  if (!perf.begin(suite, 0, expected, profile)) return false;
  uint16_t line[240];
  uint32_t observed = 0;
  uint64_t elapsed = 0;
  uint32_t batch_id = 0;
  while (observed < expected) {
    validation::FrameBatch batch;
    while (batch.count < 128 && observed < expected) {
      const uint32_t frame = observed + (cold ? 0 : 1);
      if (scene == Scene::Scanline || scene == Scene::Region)
        for (uint16_t x = 0; x < 240; ++x)
          line[x] = static_cast<uint16_t>(((frame + x) & 31) << 11 | ((x >> 2) & 63) << 5 |
                                          ((frame >> 1) & 31));
      const uint32_t before = micros();
      draw(scene, frame, tft, line, size, position);
      const uint32_t after = micros();
      uint32_t duration;
      if (!validation::validation_frame_sample(before, after, &duration) ||
          !batch.append(duration)) {
        perf.abort(suite, observed, "INVALID_SAMPLE");
        return false;
      }
      elapsed += duration;
      ++observed;
      yield();
    }
    for (uint8_t chunk = 0; chunk < (batch.count + 15) / 16; ++chunk) {
      const uint8_t left = batch.count - chunk * 16;
      if (!perf.samples(suite, batch_id, chunk, batch.durations_us + chunk * 16,
                        left < 16 ? left : 16)) return false;
    }
    ++batch_id;
    if (validation_poll_control(log, false) == validation::ControlAction::Quit) {
      perf.abort(suite, observed, "Q");
      return false;
    }
  }
  return perf.end(suite, observed, elapsed, "PASS");
}
}  // namespace

namespace validation {
void run_frame_perf(FrameSuite suite, TFT_eSPI& tft, TFT_eSprite&, Print& log) {
  if (suite == FrameSuite::Full) {
    if (!run_profile(Scene::Scanline, "fp1_scanline_cold", true, tft, log)) return;
    if (!run_profile(Scene::Scanline, "fp1_scanline", false, tft, log)) return;
    if (!run_profile(Scene::Fill, "fp1_fill_cold", true, tft, log)) return;
    run_profile(Scene::Fill, "fp1_fill", false, tft, log);
  } else if (suite == FrameSuite::Partial) {
    const uint16_t sizes[] = {8, 32, 64, 120};
    const char* positions[] = {"center", "edge", "clip"};
    for (uint8_t s = 0; s < 4; ++s) {
      for (uint8_t position = 0; position < 3; ++position) {
        char profile[32], cold_profile[32];
        snprintf(profile, sizeof(profile), "fp2_%u_%s", sizes[s], positions[position]);
        snprintf(cold_profile, sizeof(cold_profile), "fp2_%u_%s_cold",
                 sizes[s], positions[position]);
        if (!run_profile(Scene::Region, cold_profile, true, tft, log, sizes[s], position)) return;
        if (!run_profile(Scene::Region, profile, false, tft, log, sizes[s], position)) return;
      }
    }
  }
}
}
