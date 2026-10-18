#include "ValidationFramePerf.h"

#include <Arduino.h>
#include <stdio.h>
#include "ValidationFrameSampler.h"
#include "ValidationInput.h"
#include "ValidationPerfTelemetry.h"

namespace {
enum class Scene { Scanline, Fill, Region, Mixed };
uint16_t run_counter = 0;
uint16_t mixed_image[12 * 12];

void new_run_id(char* run_id, size_t size) {
  snprintf(run_id, size, "F%08lx%04x", static_cast<unsigned long>(ESP.getCycleCount()),
           run_counter++);
}

void draw(Scene scene, uint32_t frame, TFT_eSPI& tft, uint16_t* line, uint16_t size,
          uint8_t position, TFT_eSprite* sprite) {
  if (scene == Scene::Fill) {
    tft.fillScreen((frame & 1) ? TFT_BLUE : TFT_RED);
    return;
  }
  if (scene == Scene::Region) {
    const uint16_t visible = position == 2 ? size / 2 : size;
    const uint16_t origin = position == 0   ? (240 - size) / 2
                            : position == 1 ? 240 - size
                                            : 240 - visible;
    tft.startWrite();
    tft.setAddrWindow(origin, origin, visible, visible);
    for (uint16_t row = 0; row < visible; ++row) tft.pushPixels(line, visible);
    tft.endWrite();
    return;
  }
  if (scene == Scene::Mixed) {
    validation::draw_mixed_frame(frame, tft, *sprite);
    return;
  }
  tft.startWrite();
  tft.setAddrWindow(0, 0, 240, 240);
  for (uint16_t row = 0; row < 240; ++row) tft.pushPixels(line, 240);
  tft.endWrite();
}

bool run_profile(Scene scene, const char* profile, bool cold, TFT_eSPI& tft, Print& log,
                 uint16_t size = 0, uint8_t position = 0, TFT_eSprite* sprite = nullptr) {
  char run_id[17];
  new_run_id(run_id, sizeof(run_id));
  ValidationPerfEmitter perf(log, run_id);
  const char* suite = scene == Scene::Region ? "FP2" : scene == Scene::Mixed ? "FP3" : "FP1";
  const uint32_t expected = cold ? 1 : 1000;
  if (!perf.begin(suite, scene == Scene::Mixed ? 0x13579bdfUL : 0, expected, profile)) return false;
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
      draw(scene, frame, tft, line, size, position, sprite);
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
                        left < 16 ? left : 16))
        return false;
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
void prepare_mixed_image() {
  for (uint16_t i = 0; i < 12 * 12; ++i) mixed_image[i] = (i & 1) ? TFT_GREEN : TFT_BLUE;
}

void draw_mixed_frame(uint32_t frame, TFT_eSPI& tft, TFT_eSprite& sprite) {
  tft.setTextFont(1);
  tft.setTextColor(TFT_WHITE, TFT_BLACK);
  tft.drawString("Frame", 4, 4);
  tft.setTextFont(2);
  tft.drawString("Mixed", 4, 24);
  tft.drawRect(4, 54, 20, 20, TFT_RED);
  tft.drawFastHLine(40, 64, 90, TFT_GREEN);
  tft.fillRect(144, 54, 12, 12, TFT_BLUE);
  tft.pushImage(12, 96, 12, 12, mixed_image);
  tft.fillRect(0, 180, 240, 32, TFT_BLACK);
  sprite.fillSprite((frame & 1) ? TFT_RED : TFT_BLUE);
  sprite.pushSprite(40 + (frame * 3 + 0x13579bdfUL) % 160, 180);
}

void run_frame_perf(FrameSuite suite, TFT_eSPI& tft, TFT_eSprite& sprite, Print& log) {
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
        snprintf(cold_profile, sizeof(cold_profile), "fp2_%u_%s_cold", sizes[s],
                 positions[position]);
        if (!run_profile(Scene::Region, cold_profile, true, tft, log, sizes[s], position)) return;
        if (!run_profile(Scene::Region, profile, false, tft, log, sizes[s], position)) return;
      }
    }
  } else if (suite == FrameSuite::Mixed) {
    if (!sprite.created()) {
      char run_id[17];
      new_run_id(run_id, sizeof(run_id));
      ValidationPerfEmitter perf(log, run_id);
      if (perf.begin("FP3", 0x13579bdfUL, 1000, "fp3_mixed")) perf.end("FP3", 0, 0, "SKIP");
      return;
    }
    prepare_mixed_image();
    if (run_profile(Scene::Mixed, "fp3_mixed_cold", true, tft, log, 0, 0, &sprite))
      run_profile(Scene::Mixed, "fp3_mixed", false, tft, log, 0, 0, &sprite);
    tft.setTextFont(1);
    tft.setSwapBytes(false);
  }
}
}  // namespace validation
