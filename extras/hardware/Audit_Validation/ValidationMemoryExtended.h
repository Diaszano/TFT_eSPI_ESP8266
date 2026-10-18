#ifndef VALIDATION_MEMORY_EXTENDED_H
#define VALIDATION_MEMORY_EXTENDED_H

#include <TFT_eSPI.h>
#include <Print.h>

namespace validation {
bool heap_lifecycle_step(uint32_t index, TFT_eSPI& tft, uint32_t* allocation_us,
                         uint32_t* total_us);
void run_heap_churn(TFT_eSPI& tft, Print& log);
void run_heap_pressure(TFT_eSPI& tft, Print& log);
}  // namespace validation

#endif
