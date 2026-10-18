#ifndef VALIDATION_BENCH_H
#define VALIDATION_BENCH_H

#include <TFT_eSPI.h>
#include <Print.h>

void run_bench_suite(TFT_eSPI& tft, TFT_eSprite& sprite, TFT_eSprite& wide_sprite, Print& log);

#endif
