#include "core/Rgb565Frame.h"

#include <stdexcept>
#include <algorithm>

namespace simulator {
namespace {
std::size_t checked_size(uint16_t width, uint16_t height) {
  const std::size_t count = static_cast<std::size_t>(width) * height;
  if (!width || !height || count > 240u * 320u)
    throw std::invalid_argument("frame dimensions exceed the supported GRAM budget");
  return count;
}
}  // namespace

Rgb565Frame::Rgb565Frame(uint16_t width, uint16_t height)
    : width_(width), height_(height), pixels_(checked_size(width, height)) {
}

uint16_t Rgb565Frame::pixel(uint16_t x, uint16_t y) const {
  if (x >= width_ || y >= height_) throw std::out_of_range("RGB565 frame coordinate out of range");
  return pixels_[static_cast<std::size_t>(y) * width_ + x];
}

void Rgb565Frame::set_pixel(uint16_t x, uint16_t y, uint16_t color) {
  if (x >= width_ || y >= height_) throw std::out_of_range("RGB565 frame coordinate out of range");
  pixels_[static_cast<std::size_t>(y) * width_ + x] = color;
}

void Rgb565Frame::clear(uint16_t color) noexcept {
  std::fill(pixels_.begin(), pixels_.end(), color);
}

}  // namespace simulator
