#include "ValidationBenchMath.h"
#include <cassert>

int main() {
  assert(elapsed_us(0xFFFFFFFEu, 3u) == 5u);
  assert(!valid_sample(0u, 10u));
  assert(!valid_sample(10u, 0u));
  assert(valid_sample(10u, 2u));
}
