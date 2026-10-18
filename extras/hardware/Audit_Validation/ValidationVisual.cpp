#include "ValidationVisual.h"

#include <Arduino.h>
#include "ValidationInput.h"
#include "ValidationTelemetry.h"
#include "ValidationVisualScenes.h"

namespace {
bool advance(Print& log) {
  while (true) {
    const validation::ControlAction action = validation_poll_control(log, true);
    if (action == validation::ControlAction::Next) return true;
    if (action == validation::ControlAction::Quit) return false;
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
