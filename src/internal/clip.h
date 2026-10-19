#pragma once

#include <stdint.h>

namespace tft_espi_internal {

// Clip the span [pos + datum, pos + datum + len) to [lo, hi); false when nothing is left.
// 64-bit so that extreme caller coordinates or lengths cannot overflow. Forced inline: an outlined
// call makes the callers keep pos/len in memory and grows their stack frames.
__attribute__((always_inline)) inline bool clipSpan(int32_t& pos, int32_t& len, int32_t datum,
                                                    int32_t lo, int32_t hi) {
  int64_t start = (int64_t)pos + datum;
  int64_t end = start + len;
  if (start < lo) start = lo;
  if (end > hi) end = hi;
  if (end <= start) return false;
  pos = (int32_t)start;
  len = (int32_t)(end - start);
  return true;
}

// out = a + b when the result fits in int32_t. A coordinate that does not fit lies outside every
// viewport, so callers skip the edge or pixel instead of wrapping.
__attribute__((always_inline)) inline bool offsetCoord(int32_t a, int64_t b, int32_t& out) {
  int64_t v = (int64_t)a + b;
  if (v < INT32_MIN || v > INT32_MAX) return false;
  out = (int32_t)v;
  return true;
}

// Glyph renderers do int32_t arithmetic on x, y and their sums with the origin, offset by at most
// one scaled glyph (< 2^17 pixels). Within +-2^30 that cannot overflow; anything further out is
// off every real panel, so it is not drawn. Origins beyond +-2^30 are rejected too.
__attribute__((always_inline)) inline bool glyphInRange(int32_t x, int32_t y, int32_t xDatum,
                                                        int32_t yDatum) {
  // v + 2^30 < 2^31 as uint32_t is exactly -2^30 <= v < 2^30. Each sum of two such values fits
  // int32_t, so the datum check needs no wider type.
  auto in = [](int32_t v) { return (uint32_t)v + (1u << 30) < (1u << 31); };
  return in(x) && in(y) && in(xDatum) && in(yDatum) && in(x + xDatum) && in(y + yDatum);
}

}  // namespace tft_espi_internal
