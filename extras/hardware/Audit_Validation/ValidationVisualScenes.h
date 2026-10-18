#ifndef VALIDATION_VISUAL_SCENES_H
#define VALIDATION_VISUAL_SCENES_H

#include <TFT_eSPI.h>
#include <stdint.h>

constexpr uint8_t VALIDATION_VISUAL_CASE_COUNT = 4;
const char* validation_visual_case_name(uint8_t index);
bool draw_validation_visual_case(uint8_t index, TFT_eSPI& tft);

#endif
