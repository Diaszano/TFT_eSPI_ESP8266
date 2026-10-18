#ifndef VALIDATION_FRAME_SAMPLER_H
#define VALIDATION_FRAME_SAMPLER_H

#include <stdint.h>
#include "ValidationBenchMath.h"

namespace validation {

struct FrameBatch {
  uint32_t durations_us[128] = {};
  uint8_t count = 0;

  bool append(uint32_t duration) {
    if (!duration || count == 128) return false;
    durations_us[count++] = duration;
    return true;
  }

  void reset() { count = 0; }
};

inline bool validation_frame_sample(uint32_t before, uint32_t after, uint32_t* duration) {
  if (!duration) return false;
  *duration = elapsed_us(before, after);
  return *duration != 0;
}

}  // namespace validation

#endif
