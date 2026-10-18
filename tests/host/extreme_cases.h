#pragma once

#include <cstdint>
#include <vector>

struct ExtremeCase {
  const char* id;
  int32_t x, y, w, h;
  bool hardware_safe;
};

inline const std::vector<ExtremeCase>& extreme_cases() {
  static const std::vector<ExtremeCase> cases = {
      {"fully_offscreen_241", 241, 0, 1, 1, true},
      {"negative_one_pixel", -1, -1, 2, 2, true},
      {"viewport_zero", 0, 0, 0, 0, true},
      {"line_near_edge", -1, 239, 242, 1, true},
      {"image_16x16_crop", -3, -2, 16, 16, true},
      {"sprite_32x32_offscreen", 241, 0, 32, 32, false},
      {"int32_max_origin", INT32_MAX, 0, 1, 1, false},
      {"int32_min_origin", INT32_MIN, 0, INT32_MAX, 1, false},
      {"negative_dimensions", 0, 0, -1, -1, false},
  };
  return cases;
}
