#ifndef VALIDATION_STRESS_MATH_H
#define VALIDATION_STRESS_MATH_H

#include <stdint.h>

inline uint32_t elapsed_ms(uint32_t before, uint32_t after) {
  return after - before;
}
inline bool heap_drop_over_threshold(uint32_t before, uint32_t after,
                                     uint32_t threshold_bytes = 1024u) {
  return before > after && before - after > threshold_bytes;
}
inline bool should_report_progress(uint32_t completed_cycles) {
  return completed_cycles != 0 && completed_cycles <= 10000 && completed_cycles % 1000 == 0;
}
inline bool endurance_finished(uint32_t elapsed) {
  return elapsed >= 1800000u;
}

#endif
