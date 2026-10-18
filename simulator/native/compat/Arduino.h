#pragma once

#include <cstddef>
#include <cstdint>
#include <cmath>
#include <cstring>
#include <string>
#include <cstdio>

class String : public std::string {
 public:
  using std::string::string;
  String() = default;
  String(const std::string& value) : std::string(value) {}
  void toCharArray(char* out, std::size_t size) const {
    if (!size) return;
    const std::size_t count = size - 1 < length() ? size - 1 : length();
    copy(out, count);
    out[count] = '\0';
  }
};
constexpr int LOW = 0;
constexpr int HIGH = 1;
constexpr int OUTPUT = 1;
constexpr int INPUT = 0;
constexpr int MSBFIRST = 1;
constexpr int LSBFIRST = 0;
constexpr int SPI_MODE3 = 3;

void pinMode(uint8_t pin, uint8_t mode);
void digitalWrite(uint8_t pin, uint8_t value);
void delay(uint32_t ms);
void delayMicroseconds(uint32_t us);
uint8_t digitalPinToBitMask(uint8_t pin);
inline long random(long max_value) {
  static uint32_t state = 1;
  state = state * 1103515245u + 12345u;
  return max_value > 0 ? static_cast<long>((state >> 1) % max_value) : 0;
}
inline char* ltoa(long value, char* out, int base) {
  if (base == 10)
    std::snprintf(out, 32, "%ld", value);
  else
    std::snprintf(out, 32, "%lx", static_cast<unsigned long>(value));
  return out;
}
