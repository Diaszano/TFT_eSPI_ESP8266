#ifndef VALIDATION_FRAME_PERF_H
#define VALIDATION_FRAME_PERF_H

#include <TFT_eSPI.h>
#include <Print.h>

namespace validation {
enum class FrameSuite { Full, Partial, Mixed };
void run_frame_perf(FrameSuite suite, TFT_eSPI& tft, TFT_eSprite& sprite, Print& log);
}

#endif
