#include "ValidationStress.h"

#include <Arduino.h>
#include "ValidationInput.h"
#include "ValidationStressMath.h"
#include "ValidationTelemetry.h"

namespace {
uint16_t fragmentation_permille(uint32_t heap, uint32_t largest) {
  return heap ? static_cast<uint16_t>((heap - largest) * 1000UL / heap) : 0;
}

void emit_progress(Print& log, uint32_t cycles, uint32_t elapsed, uint32_t heap, uint32_t largest) {
  log.print("STRESS,PROGRESS,L,");
  log.print(cycles);
  log.print(',');
  log.print(elapsed);
  log.print(',');
  log.print(heap);
  log.print(',');
  log.print(largest);
  log.print(',');
  log.println(fragmentation_permille(heap, largest));
}

void emit_end(Print& log, const char* id, uint32_t cycles, uint32_t elapsed, uint32_t heap_before,
              uint32_t heap_after, uint32_t largest, const char* status) {
  log.print("STRESS,END,");
  log.print(id);
  log.print(',');
  log.print(cycles);
  log.print(',');
  log.print(elapsed);
  log.print(',');
  log.print(heap_after);
  log.print(',');
  log.print(largest);
  log.print(',');
  log.print(fragmentation_permille(heap_after, largest));
  log.print(',');
  log.println(status);
  if (heap_drop_over_threshold(heap_before, heap_after)) log.println("STRESS,WARNING,HEAP_DROP");
}

bool quit_requested(Print& log) {
  return validation_poll_control(log, false) == validation::ControlAction::Quit;
}
}  // namespace

void run_stress_10k(TFT_eSPI& tft, TFT_eSprite& sprite, Print& log) {
  if (!sprite.created()) {
    validation_emit_case_start(log, "stress", 0);
    validation_emit_case_return(log, "stress", 0, "SKIP");
    return;
  }
  const uint32_t start = millis();
  const uint32_t heap_before = ESP.getFreeHeap();
  uint32_t cycles = 0;
  tft.setTextFont(1);
  tft.setTextPadding(0);
  tft.setTextColor(TFT_WHITE, TFT_BLACK);
  validation_emit_case_start(log, "stress", 0);
  for (uint32_t i = 0; i < 10000; ++i) {
    tft.drawNumber(i, 0, 0);
    sprite.fillSprite((i & 1) ? TFT_RED : TFT_BLUE);
    sprite.drawRect(0, 0, 32, 32, TFT_WHITE);
    sprite.pushSprite((i * 3) % (tft.width() - 31), (i * 5) % (tft.height() - 31));
    tft.drawFastHLine(0, i % tft.height(), tft.width(), TFT_GREEN);
    cycles = i + 1;
    if ((cycles & 15) == 0) yield();
    if (should_report_progress(cycles)) {
      emit_progress(log, cycles, elapsed_ms(start, millis()), ESP.getFreeHeap(),
                    ESP.getMaxFreeBlockSize());
      yield();
    }
  }
  tft.setTextPadding(0);
  const uint32_t elapsed = elapsed_ms(start, millis());
  const uint32_t heap_after = ESP.getFreeHeap();
  const uint32_t largest = ESP.getMaxFreeBlockSize();
  const char* status = heap_drop_over_threshold(heap_before, heap_after) ? "INCONCLUSIVE" : "PASS";
  emit_end(log, "L", cycles, elapsed, heap_before, heap_after, largest, status);
  validation_emit_case_return(log, "stress", elapsed * 1000UL, status);
}

void run_memory_profiles(TFT_eSPI& tft, TFT_eSprite& sprite, Print& log) {
  (void)tft;
  (void)sprite;
  const uint32_t heap_before = ESP.getFreeHeap();
  validation_emit_case_start(log, "memory_profiles", 0);
  const uint8_t depths[] = {1, 4, 8, 16};
  bool failed = false;
  for (uint8_t depth : depths) {
    TFT_eSprite probe(&tft);
    probe.setColorDepth(depth);
    if (probe.createSprite(24, 17)) {
      probe.drawPixel(0, 0, TFT_WHITE);
      probe.deleteSprite();
    } else
      failed = true;
    yield();
  }
  TFT_eSprite oversized(&tft);
  oversized.setColorDepth(16);
  if (oversized.createSprite(240, 240)) oversized.deleteSprite();
  const uint32_t heap_after = ESP.getFreeHeap();
  const char* status =
      failed || heap_drop_over_threshold(heap_before, heap_after) ? "INCONCLUSIVE" : "PASS";
  validation_emit_case_return(log, "memory_profiles", 0, status);
  emit_end(log, "M", 4, 0, heap_before, heap_after, ESP.getMaxFreeBlockSize(), status);
}

void run_endurance_30m(TFT_eSPI& tft, TFT_eSprite& sprite, Print& log) {
  if (!sprite.created()) {
    validation_emit_case_start(log, "endurance_30m", 0);
    validation_emit_case_return(log, "endurance_30m", 0, "SKIP");
    return;
  }
  const uint32_t started = millis();
  const uint32_t heap_before = ESP.getFreeHeap();
  uint32_t cycles = 0;
  validation_emit_case_start(log, "endurance_30m", 0);
  while (!endurance_finished(elapsed_ms(started, millis()))) {
    if (quit_requested(log)) {
      emit_end(log, "E30", cycles, elapsed_ms(started, millis()), heap_before, ESP.getFreeHeap(),
               ESP.getMaxFreeBlockSize(), "INCONCLUSIVE");
      validation_emit_case_return(log, "endurance_30m", elapsed_ms(started, millis()) * 1000UL,
                                  "INCONCLUSIVE");
      return;
    }
    tft.fillRect(cycles % 200, 20 + cycles % 180, 16, 16, cycles & 1 ? TFT_RED : TFT_BLUE);
    sprite.drawPixel(cycles % 32, (cycles / 32) % 32, cycles & 1 ? TFT_WHITE : TFT_BLACK);
    ++cycles;
    log.print("STRESS,PROGRESS,E30,");
    log.print(cycles);
    log.print(',');
    log.print(elapsed_ms(started, millis()));
    log.print(',');
    log.print(ESP.getFreeHeap());
    log.print(',');
    log.print(ESP.getMaxFreeBlockSize());
    log.print(',');
    log.println(fragmentation_permille(ESP.getFreeHeap(), ESP.getMaxFreeBlockSize()));
    delay(1000);
    yield();
  }
  const uint32_t elapsed = elapsed_ms(started, millis());
  const uint32_t heap_after = ESP.getFreeHeap();
  const char* status = heap_drop_over_threshold(heap_before, heap_after) ? "INCONCLUSIVE" : "PASS";
  emit_end(log, "E30", cycles, elapsed, heap_before, heap_after, ESP.getMaxFreeBlockSize(), status);
  validation_emit_case_return(log, "endurance_30m", elapsed * 1000UL, status);
}
