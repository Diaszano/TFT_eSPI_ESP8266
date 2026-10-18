#pragma once

#include <cstddef>
#include <cstdint>
#include <vector>

namespace simulator {

class Rgb565Frame {
 public:
  Rgb565Frame(uint16_t width, uint16_t height);
  uint16_t width() const noexcept { return width_; }
  uint16_t height() const noexcept { return height_; }
  uint16_t pixel(uint16_t x, uint16_t y) const;
  void set_pixel(uint16_t x, uint16_t y, uint16_t color);
  void clear(uint16_t color = 0) noexcept;
  const std::vector<uint16_t>& pixels() const noexcept { return pixels_; }

 private:
  uint16_t width_;
  uint16_t height_;
  std::vector<uint16_t> pixels_;
};

}  // namespace simulator
