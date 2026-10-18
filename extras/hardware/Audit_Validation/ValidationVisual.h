#ifndef VALIDATION_VISUAL_H
#define VALIDATION_VISUAL_H

#include <TFT_eSPI.h>
#include <Print.h>
#include <stdint.h>

void run_visual_suite(uint8_t selected_case, TFT_eSPI& tft, Print& log);

#endif
