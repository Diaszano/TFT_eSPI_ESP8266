#pragma once
#include <cstdint>
#include <cstddef>
#include <vector>

namespace stateful {
enum class Kind { Viewport, Rect, HLine, Swap, Font };
struct Operation {
  Kind kind;
  int x, y, w, h;
  uint16_t value;
  bool operator==(const Operation& other) const {
    return kind == other.kind && x == other.x && y == other.y && w == other.w && h == other.h &&
           value == other.value;
  }
};

inline std::vector<Operation> generate(uint32_t seed, unsigned count) {
  std::vector<Operation> operations;
  if (!seed) seed = 1;
  if (count > 256) count = 256;
  for (unsigned i = 0; i < count; ++i) {
    seed ^= seed << 13;
    seed ^= seed >> 17;
    seed ^= seed << 5;
    operations.push_back({static_cast<Kind>(seed % 5), static_cast<int>((seed >> 3) % 13) - 3,
                          static_cast<int>((seed >> 7) % 13) - 3,
                          static_cast<int>((seed >> 11) % 6), static_cast<int>((seed >> 16) % 6),
                          static_cast<uint16_t>(1 + (seed >> 21) % 65534)});
  }
  return operations;
}

template <typename F>
std::vector<Operation> shrink(std::vector<Operation> operations, F fails) {
  for (std::size_t i = 0; i < operations.size();) {
    std::vector<Operation> candidate = operations;
    candidate.erase(candidate.begin() + i);
    if (fails(candidate))
      operations.swap(candidate);
    else
      ++i;
  }
  return operations;
}
}  // namespace stateful
