#ifndef VALIDATION_SOAK_H
#define VALIDATION_SOAK_H

#include <TFT_eSPI.h>
#include <Print.h>
#include <stdint.h>

namespace validation {
void run_mixed_soak(uint32_t requested_minutes, TFT_eSPI& tft, Print& log);
void run_wifi_latency(TFT_eSPI& tft, Print& log);
}

#endif
