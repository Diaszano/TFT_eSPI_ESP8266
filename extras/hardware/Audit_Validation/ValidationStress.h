#ifndef VALIDATION_STRESS_H
#define VALIDATION_STRESS_H

#include <TFT_eSPI.h>
#include <Print.h>

void run_stress_10k(TFT_eSPI& tft, TFT_eSprite& sprite, Print& log);
void run_memory_profiles(TFT_eSPI& tft, TFT_eSprite& sprite, Print& log);
void run_endurance_30m(TFT_eSPI& tft, TFT_eSprite& sprite, Print& log);

#endif
