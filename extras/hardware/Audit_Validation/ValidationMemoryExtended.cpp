#include "ValidationMemoryExtended.h"

#include <Arduino.h>
#include <stdio.h>
#include "ValidationInput.h"
#include "ValidationMemoryMath.h"
#include "ValidationPerfTelemetry.h"

namespace {
uint16_t run_counter = 0;
void run_id(char* output, size_t size) {
  snprintf(output, size, "H%08lx%04x",
           static_cast<unsigned long>(ESP.getCycleCount()), run_counter++);
}

void checkpoint(ValidationPerfEmitter& perf, const char* suite, uint32_t index,
                uint32_t minimum, uint32_t failures) {
  perf.mem(suite, index, ESP.getFreeHeap(), ESP.getMaxFreeBlockSize(), minimum, failures);
}
}

namespace validation {
void run_heap_churn(TFT_eSPI& tft, Print& log) {
  char id[17];
  run_id(id, sizeof(id));
  ValidationPerfEmitter perf(log, id);
  const uint32_t seed = 0x13579bdfUL;
  const uint32_t requested = 100000;
  if (!perf.begin("HC", seed, requested, "hc_v1")) return;
  uint32_t minimum = ESP.getFreeHeap();
  uint32_t failures = 0;
  uint64_t elapsed = 0;
  uint32_t samples[16] = {};
  checkpoint(perf, "HC", 0, minimum, failures);
  const uint8_t sizes[] = {8, 16, 24, 32};
  const uint8_t depths[] = {1, 4, 8, 16};
  for (uint32_t i = 0; i < requested; ++i) {
    const uint8_t choice = static_cast<uint8_t>((i + seed) & 15);
    const uint8_t side = sizes[choice & 3];
    const uint8_t depth = depths[choice >> 2];
    uint32_t estimated;
    if (!estimate_sprite_bytes(side, side, depth, &estimated) ||
        !may_allocate(ESP.getFreeHeap(), ESP.getMaxFreeBlockSize(), estimated)) {
      checkpoint(perf, "HC", i / 1024 + 1, minimum, failures);
      perf.abort("HC", i, "HEAP_FLOOR");
      return;
    }
    TFT_eSprite sprite(&tft);
    sprite.setColorDepth(depth);
    const uint32_t before = micros();
    if (!sprite.createSprite(side, side)) {
      ++failures;
      checkpoint(perf, "HC", i / 1024 + 1, minimum, failures);
      perf.abort("HC", i, "ALLOC_FAIL");
      return;
    }
    const uint32_t allocation_us = micros() - before;
    if (i < 16) samples[i] = allocation_us;
    sprite.fillSprite((i & 1) ? TFT_RED : TFT_BLUE);
    sprite.deleteSprite();
    elapsed += micros() - before;
    const uint32_t free = ESP.getFreeHeap();
    if (free < minimum) minimum = free;
    if ((i + 1) % 1024 == 0) {
      checkpoint(perf, "HC", (i + 1) / 1024, minimum, failures);
      yield();
    }
    if ((i + 1) % 128 == 0 &&
        validation_poll_control(log, false) == ControlAction::Quit) {
      perf.abort("HC", i + 1, "Q");
      return;
    }
  }
  if (!perf.samples("HC", 0, 0, samples, 16)) return;
  checkpoint(perf, "HC", requested / 1024 + 1, minimum, failures);
  perf.end("HC", requested, elapsed, "PASS");
}
}
