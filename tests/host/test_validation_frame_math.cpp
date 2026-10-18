#include <cassert>
#include "ValidationFrameSampler.h"

int main() {
  validation::FrameBatch batch;
  assert(batch.count == 0);
  assert(!validation::validation_frame_sample(1, 1, nullptr));
  uint32_t duration = 0;
  assert(validation::validation_frame_sample(0xfffffff0, 0x10, &duration));
  assert(duration == 32);
  assert(batch.append(duration));
  for (unsigned i = 1; i < 128; ++i) assert(batch.append(i));
  assert(!batch.append(129));
  assert(batch.count == 128);
  batch.reset();
  assert(batch.count == 0);
}
