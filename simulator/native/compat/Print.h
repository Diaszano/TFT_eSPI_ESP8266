#pragma once

#include <cstddef>
#include <cstdint>

class Print {
 public:
  virtual ~Print() = default;
  virtual std::size_t write(uint8_t value) = 0;
  std::size_t write(const uint8_t* buffer, std::size_t size) {
    std::size_t written = 0;
    while (written < size && write(buffer[written])) ++written;
    return written;
  }
  std::size_t write(const char* text) {
    std::size_t written = 0;
    while (text[written] && write(static_cast<uint8_t>(text[written]))) ++written;
    return written;
  }
};
