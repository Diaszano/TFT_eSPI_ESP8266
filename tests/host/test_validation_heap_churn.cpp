#include <cassert>
#include "ValidationMemoryMath.h"

int main() {
  uint16_t fragmentation = 0;
  assert(!validation::fragmentation_permille(0, 0, &fragmentation));
  assert(!validation::fragmentation_permille(100, 101, &fragmentation));
  assert(validation::fragmentation_permille(20000, 15000, &fragmentation));
  assert(fragmentation == 250);
  assert(!validation::may_allocate(20000, 15000, 7712));
  assert(validation::may_allocate(20000, 15000, 7711));
  assert(!validation::may_allocate(20000, 1000, 1001));
  uint32_t bytes = 0;
  assert(validation::estimate_sprite_bytes(32, 32, 16, &bytes));
  assert(bytes >= 2048);
  assert(!validation::estimate_sprite_bytes(65535, 65535, 16, &bytes));
  assert(!validation::estimate_sprite_bytes(0, 32, 16, &bytes));
}
