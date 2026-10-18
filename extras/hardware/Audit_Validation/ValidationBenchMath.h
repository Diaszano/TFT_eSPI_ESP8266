#ifndef VALIDATION_BENCH_MATH_H
#define VALIDATION_BENCH_MATH_H

#include <stdint.h>

// Each measured batch must finish within one uint32_t micros() period.
inline uint32_t elapsed_us(uint32_t before, uint32_t after) {
  return after - before;
}
inline bool valid_sample(uint32_t repetitions, uint32_t total_us) {
  return repetitions != 0 && total_us != 0;
}

#endif
