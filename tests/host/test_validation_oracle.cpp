#include "validation_oracle.h"

#include <cassert>
#include <climits>

int main() {
  auto visible = intersect_viewport({-1, -1, 2, 2}, 240, 240);
  assert(visible.x == 0 && visible.y == 0 && visible.w == 1 && visible.h == 1);
  assert(intersect_viewport({240, 0, 1, 1}, 240, 240).w == 0);
  assert(intersect_viewport({INT32_MAX, 0, 1, 1}, 240, 240).x == 240);
  assert(intersect_viewport({INT32_MIN, 0, INT32_MAX, 1}, 240, 240).w == 0);

  std::vector<uint16_t> fb(4, 0xA55A);
  paint_rect_reference(fb, 2, 2, {-1, -1, 2, 2}, 0x1234);
  assert(fb[0] == 0x1234 && fb[1] == 0xA55A && fb[2] == 0xA55A && fb[3] == 0xA55A);
}
