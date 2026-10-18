#include "ValidationSoak.h"

#include <Arduino.h>
#include <stdio.h>
#include "ValidationFramePerf.h"
#include "ValidationFrameSampler.h"
#include "ValidationInput.h"
#include "ValidationMemoryExtended.h"
#include "ValidationMemoryMath.h"
#include "ValidationPerfTelemetry.h"

namespace {
uint16_t run_counter = 0;

bool flush(ValidationPerfEmitter& perf, validation::FrameBatch& batch, uint32_t* batch_id) {
  if (!batch.count) return true;
  for (uint8_t chunk = 0; chunk < (batch.count + 15) / 16; ++chunk) {
    const uint8_t left = batch.count - chunk * 16;
    if (!perf.samples("FM", *batch_id, chunk, batch.durations_us + chunk * 16,
                      left < 16 ? left : 16)) return false;
  }
  ++*batch_id;
  batch.reset();
  return true;
}

bool checkpoint(ValidationPerfEmitter& perf, uint32_t minute, uint32_t minimum,
                uint32_t failures) {
  return perf.mem("FM", minute, ESP.getFreeHeap(), ESP.getMaxFreeBlockSize(),
                  minimum, failures);
}
}

namespace validation {
void run_mixed_soak(uint32_t requested_minutes, TFT_eSPI& tft, Print& log) {
  if (requested_minutes != 30 && requested_minutes != 480 && requested_minutes != 1440)
    return;
  char id[17];
  snprintf(id, sizeof(id), "M%08lx%04x",
           static_cast<unsigned long>(ESP.getCycleCount()), run_counter++);
  ValidationPerfEmitter perf(log, id);
  const char* profile = requested_minutes == 30 ? "fm30" :
                        requested_minutes == 480 ? "fm8h" : "fm24h";
  if (!perf.begin("FM", 0x13579bdfUL, 0, profile)) return;
  uint32_t estimated_sprite;
  if (!estimate_sprite_bytes(32, 32, 16, &estimated_sprite) ||
      !may_allocate(ESP.getFreeHeap(), ESP.getMaxFreeBlockSize(), estimated_sprite)) {
    perf.end("FM", 0, 0, "SKIP");
    return;
  }
  TFT_eSprite sprite(&tft);
  sprite.setColorDepth(16);
  if (!sprite.createSprite(32, 32)) {
    perf.abort("FM", 0, "ALLOC_FAIL");
    return;
  }
  prepare_mixed_image();
  FrameBatch batch;
  uint32_t batch_id = 0;
  uint32_t observed = 0;
  uint32_t checkpoint_minute = 0;
  uint32_t minimum = ESP.getFreeHeap();
  const uint32_t started = millis();
  checkpoint(perf, 0, minimum, 0);
  const uint32_t requested_ms = requested_minutes * 60000UL;
  while (static_cast<uint32_t>(millis() - started) < requested_ms) {
    if (!may_allocate(ESP.getFreeHeap(), ESP.getMaxFreeBlockSize(), estimated_sprite)) {
      flush(perf, batch, &batch_id);
      sprite.deleteSprite();
      perf.abort("FM", observed, "HEAP_FLOOR");
      return;
    }
    const uint32_t before = micros();
    draw_mixed_frame(observed, tft, sprite);
    const uint32_t after = micros();
    uint32_t duration;
    if (!validation_frame_sample(before, after, &duration) || !batch.append(duration)) {
      sprite.deleteSprite();
      perf.abort("FM", observed, "INVALID_SAMPLE");
      return;
    }
    uint32_t allocation_us, operation_us;
    if (!heap_lifecycle_step(observed, tft, &allocation_us, &operation_us)) {
      flush(perf, batch, &batch_id);
      sprite.deleteSprite();
      perf.abort("FM", observed + 1, "ALLOC_FAIL");
      return;
    }
    ++observed;
    if (batch.count == 128 && !flush(perf, batch, &batch_id)) {
      sprite.deleteSprite();
      return;
    }
    yield();
    const uint32_t elapsed_ms = millis() - started;
    while (checkpoint_minute < elapsed_ms / 60000UL) {
      ++checkpoint_minute;
      const uint32_t free = ESP.getFreeHeap();
      if (free < minimum) minimum = free;
      if (!checkpoint(perf, checkpoint_minute, minimum, 0)) {
        sprite.deleteSprite();
        return;
      }
    }
    if (validation_poll_control(log, false) == ControlAction::Quit) {
      flush(perf, batch, &batch_id);
      sprite.deleteSprite();
      perf.abort("FM", observed, "Q");
      return;
    }
  }
  if (!flush(perf, batch, &batch_id)) {
    sprite.deleteSprite();
    return;
  }
  sprite.deleteSprite();
  tft.setTextFont(1);
  tft.setSwapBytes(false);
  perf.end("FM", observed, static_cast<uint64_t>(millis() - started) * 1000ULL, "PASS");
}
}
