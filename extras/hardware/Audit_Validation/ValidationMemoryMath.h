#ifndef VALIDATION_MEMORY_MATH_H
#define VALIDATION_MEMORY_MATH_H

#include <stdint.h>

namespace validation {

inline bool fragmentation_permille(uint32_t free_heap, uint32_t largest_block, uint16_t* out) {
  if (!out || !free_heap || largest_block > free_heap) return false;
  *out =
      static_cast<uint16_t>((static_cast<uint64_t>(free_heap - largest_block) * 1000) / free_heap);
  return true;
}

inline bool may_allocate(uint32_t free_heap, uint32_t largest_block, uint32_t estimated_bytes,
                         uint32_t floor_bytes = 12288) {
  return estimated_bytes && largest_block <= free_heap && estimated_bytes <= largest_block &&
         estimated_bytes < free_heap && free_heap - estimated_bytes > floor_bytes;
}

inline bool estimate_sprite_bytes(uint32_t width, uint32_t height, uint8_t depth, uint32_t* out) {
  if (!out || !width || !height || (depth != 1 && depth != 4 && depth != 8 && depth != 16))
    return false;
  const uint64_t bits = static_cast<uint64_t>(width) * height * depth;
  // 64 bytes covers allocator bookkeeping; actual runtime headroom is checked separately.
  const uint64_t bytes = (bits + 7) / 8 + 64;
  if (bytes > UINT32_MAX) return false;
  *out = static_cast<uint32_t>(bytes);
  return true;
}

}  // namespace validation

#endif
