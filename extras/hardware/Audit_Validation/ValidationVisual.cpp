#include "ValidationVisual.h"

#include <Arduino.h>
#include "ValidationCommand.h"
#include "ValidationTelemetry.h"
#include "ValidationVisualScenes.h"

namespace {
bool advance(Print& log) {
  static validation::ValidationCommandReader reader;
  while (true) {
    while (Serial.available()) {
      validation::ValidationCommand command;
      if (reader.consume(static_cast<char>(Serial.read()), &command)) {
        if (command.kind == validation::ValidationCommandKind::Next) return true;
        if (command.kind == validation::ValidationCommandKind::Quit) return false;
        log.println("UNKNOWN; only N or Q is accepted during visual review");
      }
    }
    yield();
  }
}
}  // namespace

void run_visual_suite(uint8_t selected_case, TFT_eSPI& tft, Print& log) {
  const uint8_t first = selected_case ? selected_case - 1 : 0;
  const uint8_t end = selected_case ? selected_case : 4;
  for (uint8_t i = first; i < end; ++i) {
    validation_emit_case_start(log, validation_visual_case_name(i), 0);
    const uint32_t started = micros();
    const bool completed = draw_validation_visual_case(i, tft);
    validation_emit_case_return(log, validation_visual_case_name(i), micros() - started,
                                completed ? "VISUAL_REVIEW_REQUIRED" : "FAIL");
    if (i + 1 < end && !advance(log)) break;
  }
}
