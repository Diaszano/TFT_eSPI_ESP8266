#include "ValidationStressMath.h"
#include <cassert>

int main() {
  assert(elapsed_ms(0xFFFFFFFEu, 3u) == 5u);
  assert(!heap_drop_over_threshold(40000, 38976));
  assert(heap_drop_over_threshold(40000, 38975));
  assert(!heap_drop_over_threshold(40000, 40010));
  assert(should_report_progress(1000));
  assert(should_report_progress(10000));
  assert(!should_report_progress(999));
  assert(!should_report_progress(10001));
  assert(!endurance_finished(1799999));
  assert(endurance_finished(1800000));
}
