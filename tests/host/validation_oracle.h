#pragma once

#include <algorithm>
#include <cstdint>
#include <vector>

struct Rect64 {
  int64_t x, y, w, h;
};

inline Rect64 intersect_viewport(Rect64 r, int64_t width, int64_t height) {
  if (r.w <= 0 || r.h <= 0 || width <= 0 || height <= 0) return {0, 0, 0, 0};
  const int64_t left = std::min<int64_t>(width, std::max<int64_t>(0, r.x));
  const int64_t top = std::min<int64_t>(height, std::max<int64_t>(0, r.y));
  const int64_t right = std::min<int64_t>(width, r.x + r.w);
  const int64_t bottom = std::min<int64_t>(height, r.y + r.h);
  if (right <= left || bottom <= top) return {left, top, 0, 0};
  return {left, top, right - left, bottom - top};
}

inline void paint_rect_reference(std::vector<uint16_t>& fb, int width, int height, Rect64 r,
                                 uint16_t color) {
  if (width <= 0 || height <= 0 || fb.size() < static_cast<size_t>(width) * height) return;
  const Rect64 visible = intersect_viewport(r, width, height);
  for (int64_t y = visible.y; y < visible.y + visible.h; ++y)
    for (int64_t x = visible.x; x < visible.x + visible.w; ++x)
      fb[static_cast<size_t>(y) * width + x] = color;
}
