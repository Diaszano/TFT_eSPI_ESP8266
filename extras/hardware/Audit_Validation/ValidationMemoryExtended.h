#ifndef VALIDATION_MEMORY_EXTENDED_H
#define VALIDATION_MEMORY_EXTENDED_H

#include <TFT_eSPI.h>
#include <Print.h>

namespace validation {
void run_heap_churn(TFT_eSPI& tft, Print& log);
void run_heap_pressure(TFT_eSPI& tft, Print& log);
}

#endif
