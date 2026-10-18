#pragma once

#include "core/Rgb565Frame.h"
#include "core/SpiTrace.h"

#include <cstddef>
#include <cstdint>
#include <stdexcept>
#include <vector>

namespace simulator {

struct Profile {
  uint16_t gram_width;
  uint16_t gram_height;
  uint16_t visible_width;
  uint16_t visible_height;
  uint16_t offset_x;
  uint16_t offset_y;
  bool panel_bgr = false;  // Native color-filter order assumed for visible RGB565.

  static Profile test(uint16_t width, uint16_t height);
  static Profile nodemcu_st7789_240x240();
};

struct AddressWindow {
  uint16_t first;
  uint16_t last;
};

enum class St7789ErrorCode {
  DataWithoutCommand,
  IncompleteParameters,
  UnsupportedCommand,
  InvalidParameters,
  UnsupportedPixelFormat,
  UnsupportedMadctl,
  InvalidWindow,
  WindowOverflow,
  IncompletePixel,
  InvalidTransaction
};

class St7789Error : public std::runtime_error {
 public:
  St7789Error(St7789ErrorCode code, uint8_t command, std::size_t offset, const char* message);
  St7789ErrorCode code() const noexcept { return code_; }
  uint8_t command() const noexcept { return command_; }
  std::size_t offset() const noexcept { return offset_; }

 private:
  St7789ErrorCode code_;
  uint8_t command_;
  std::size_t offset_;
};

class St7789VirtualController {
 public:
  explicit St7789VirtualController(Profile profile);
  void reset();
  void begin();
  void command(uint8_t value);
  void data(const uint8_t* bytes, std::size_t size);
  void end();
  void replay(const SpiTrace& trace);
  void apply(const SpiTrace& trace);

  AddressWindow column_window() const noexcept { return columns_; }
  AddressWindow row_window() const noexcept { return rows_; }
  uint16_t gram(uint16_t x, uint16_t y) const { return frame_.pixel(x, y); }
  uint16_t raw_gram_pixel(uint16_t x, uint16_t y) const { return gram(x, y); }
  uint16_t visible_pixel(uint16_t x, uint16_t y) const;
  const Rgb565Frame& frame() const noexcept { return frame_; }
  uint8_t madctl() const noexcept { return madctl_; }
  uint8_t colmod() const noexcept { return colmod_; }
  bool display_on() const noexcept { return display_on_; }
  bool inverted() const noexcept { return inverted_; }
  bool has_incomplete_pixel() const noexcept { return has_high_byte_; }
  uint16_t visible_width() const noexcept { return profile_.visible_width; }
  uint16_t visible_height() const noexcept { return profile_.visible_height; }

 private:
  void finish_command();
  void apply_parameters();
  void write_pixel_byte(uint8_t value);
  void finish_pixels();
  int parameter_count(uint8_t command) const;

  Profile profile_;
  Rgb565Frame frame_;
  AddressWindow columns_{};
  AddressWindow rows_{};
  std::vector<uint8_t> parameters_;
  int expected_parameters_ = -1;
  int current_command_ = -1;
  bool ramwr_active_ = false;
  bool has_high_byte_ = false;
  uint8_t high_byte_ = 0;
  uint16_t cursor_x_ = 0;
  uint16_t cursor_y_ = 0;
  bool transaction_active_ = false;
  uint8_t madctl_ = 0;
  uint8_t colmod_ = 0x55;
  bool display_on_ = false;
  bool sleeping_ = false;
  bool inverted_ = false;
};

}  // namespace simulator
